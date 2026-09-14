#!/usr/bin/env python3
"""Bluetooth continuous scan manager for Fox Hunter.

Manages a single continuous Bluetooth discovery session using one daemon thread.
Handles scan scheduling, active device tracking with first_seen/last_seen/seen_count,
JSONL historical logging with rate limiting, TTL age-out with roll-off events,
date-rotated log files, storage retention, and low-space pause behavior.
"""

from __future__ import annotations

import errno
import json
import os
import re
import shutil
import time
import threading
import gzip
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.paths import DATA_DIR, BT_CONTINUOUS_DIR, ensure_data_dirs
from utils.iface_scan import hcitool_scan_bt
from dashboard.shared import DEVICE_CACHE

_JUNK_NAME_RE = re.compile(
    r"ManufacturerData|ServiceData|TxPower|\bRSSI\b|Value:|Advertisement|0x[0-9a-fA-F]{4,}",
    re.I,
)
_NAME_KEY_RE = re.compile(
    r"(?:Complete Local Name|Short(?:ened)? Local Name|\bName)\s*:\s*(.+)$",
    re.I,
)


def _clean_bt_name(raw: str, mac: str = "") -> str:
    s = (raw or "").strip()
    if not s:
        return ""
    s = s.splitlines()[0].strip()
    m = _NAME_KEY_RE.search(s)
    if m:
        s = m.group(1).strip()
    if mac and s.upper() == str(mac).upper():
        return ""
    if _JUNK_NAME_RE.search(s):
        return ""
    return s[:80]

CONFIG_FILE = Path(__file__).resolve().parent.parent / "config" / "bt_continuous_config.yaml"

DEFAULTS = {
    "scan_idle_seconds": 5,
    "active_device_ttl_seconds": 300,
    "observation_log_interval_seconds": 30,
    "rssi_change_threshold_db": 8,
    "default_hci": "hci0",
    "log_relative_directory": "logs/bt_continuous",
    "rotate_daily": True,
    "compress_after_days": 7,
    "retention_days": 30,
    "max_total_log_size_mb": 250,
    "minimum_free_space_mb": 512,
}


def load_config() -> Dict[str, Any]:
    """Load configuration from file, falling back to defaults."""
    config = dict(DEFAULTS)
    try:
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE) as f:
                user_config = json.load(f)
            config.update(user_config)
    except (json.JSONDecodeError, OSError):
        pass  # Use defaults
    return config


class BTContinuousManager:
    """Manages a single continuous Bluetooth discovery session.

    Ensures only one session runs at a time, locked to one HCI adapter.
    Handles scan scheduling, active device tracking with first_seen/last_seen/seen_count,
    JSONL historical logging with rate limiting, TTL age-out with roll-off events,
    date-rotated log files, storage retention, and low-space pause behavior.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._running = threading.Event()  # set = running, clear = stopped
        self._config = load_config()
        self._session_hci: Optional[str] = None
        self._session_id: Optional[str] = None
        self._started_at: Optional[float] = None
        self._devices: Dict[str, Dict[str, Any]] = {}  # mac -> active device info
        self._last_log_ts: Dict[str, float] = {}  # mac -> last log timestamp (rate limit)
        self._log_file: Optional[Any] = None  # current JSONL file handle
        self._log_path: Optional[Path] = None  # current JSONL file path
        self._log_dir = Path(self._config.get("log_dir") or BT_CONTINUOUS_DIR)
        self._current_date: Optional[str] = None  # YYYY-MM-DD of current log file
        self._logging_paused: bool = False
        self._pause_reason: Optional[str] = None
        self._last_error: Optional[str] = None
        self._thread: Optional[threading.Thread] = None
        self._retention_counter: int = 0
        self._consecutive_write_fails: int = 0

        ensure_data_dirs()

    # ------------------------------------------------------------------
    # Session lifecycle API (called from Flask routes)
    # ------------------------------------------------------------------

    def start(self, hci: Optional[str] = None) -> Dict[str, Any]:
        """Start or resume a continuous Bluetooth scan session.

        Args:
            hci: The HCI adapter (e.g. "hci0").  If None the config default
                 ``default_hci`` is used.

        Returns:
            Dict with status information that the UI uses to update its state.
        """
        with self._lock:
            # Already running?
            if self._running.is_set():
                if self._session_hci == hci:
                    return {
                        "ok": True,
                        "running": True,
                        "already_running": True,
                        "session_id": self._session_id,
                        "hci": self._session_hci,
                        "source_locked": True,
                    }
                # Different HCI while another session is active
                return {
                    "ok": False,
                    "error": f"continuous scan already running on {self._session_hci}",
                    "running_hci": self._session_hci,
                    "requested_hci": hci or self._config.get("default_hci", "hci0"),
                    "action": "stop the current continuous scan before starting another adapter",
                }

            # Use default HCI if not supplied
            if hci is None:
                hci = self._config.get("default_hci", "hci0")

            self._session_hci = hci
            self._session_id = (
                f"btcont-{datetime.utcnow():%Y%m%dT%H%M%S}-"
                f"{os.urandom(3).hex()}"
            )
            self._started_at = time.time()
            self._devices = {}
            self._last_log_ts = {}
            self._logging_paused = False
            self._pause_reason = None
            self._retention_counter = 0
            self._consecutive_write_fails = 0
            self._running.set()

            self._thread = threading.Thread(
                target=self._scan_loop,
                daemon=True,
                name="bt_continuous",
            )
            self._thread.start()

            return {
                "ok": True,
                "running": True,
                "already_running": False,
                "session_id": self._session_id,
                "hci": self._session_hci,
                "source_locked": True,
            }

    def stop(self) -> Dict[str, Any]:
        """Stop the current continuous Bluetooth scan session.

        Idempotent -- calling multiple times has the same effect as calling once.
        Signals the scan thread to stop, waits boundedly, then performs cleanup.

        Returns:
            Dict with idempotent state.
        """
        with self._lock:
            if not self._running.is_set():
                return {"ok": True, "already_stopped": True}

            # Signal the thread to stop
            self._running.clear()
            need_cleanup = True  # will be handled after join below

        # Join outside the lock so the thread can release any internal locks
        if self._thread is not None:
            self._thread.join(timeout=5.0)

        # Deterministic cleanup (close log, retention)
        self._final_cleanup()

        return {"ok": True, "already_stopped": False}

    def status(self) -> Dict[str, Any]:
        """Return the current manager status payload for the API."""

        with self._lock:
            running = self._running.is_set()
            started_iso = ""
            if self._started_at is not None:
                started_iso = (
                    datetime.fromtimestamp(self._started_at, tz=timezone.utc)
                    .isoformat()
                )

            lpaused = self._logging_paused and self._pause_reason == "low_storage"
            rows = []
            for d in self._devices.values():
                mac = d.get("mac") or ""
                name = _clean_bt_name(d.get("name") or "", mac)
                rows.append({
                    "name": name,
                    "mac": mac,
                    "rssi_dbm": d.get("rssi_dbm"),
                    "type": d.get("type") or "",
                    "vendor": d.get("vendor") or "",
                })
            rows.sort(
                key=lambda x: x.get("rssi_dbm") if x.get("rssi_dbm") is not None else -999,
                reverse=True,
            )
            return {
                "ok": True,
                "running": running,
                "status": "running" if running else "stopped",
                "session_id": self._session_id or "",
                "hci": self._session_hci or "",
                "source_locked": running,
                "started_at": started_iso,
                "active_device_count": len(self._devices),
                "devices": rows,
                "last_cycle_at": (
                    datetime.fromtimestamp(time.time(), tz=timezone.utc).isoformat()
                    if running
                    else ""
                ),
                "last_error": self._last_error if running else None,
                "logging_paused_low_storage": lpaused,
            }

    def devices(self) -> Dict[str, Any]:
        snap = self.status()
        return {
            "ok": True,
            "running": bool(snap.get("running")),
            "hci": snap.get("hci") or "",
            "active_device_count": snap.get("active_device_count") or 0,
            "devices": snap.get("devices") or [],
            }

    # ------------------------------------------------------------------
    # Background scan loop
    # ------------------------------------------------------------------

    def _scan_loop(self) -> None:
        """Background thread: run repeated scan cycles until stopped.

        Each iteration runs one scan, processes devices, performs housekeeping,
        then waits interruptibly for ``scan_idle_seconds``.  The loop exits
        promptly when the ``_running`` event is cleared.
        """
        self._last_error: Optional[str] = None
        cycle_count = 0

        try:
            while self._running.is_set():
                self._run_cycle()
                cycle_count += 1

                # Periodically run retention cleanup
                if cycle_count % self._config.get("retention_interval", 5) == 0:
                    self._retention_cleanup()

                # Wait interruptibly -- will return early if _running cleared
                self._running.wait(timeout=self._config["scan_idle_seconds"])

        except Exception as e:
            self._last_error = f"scan loop error: {e}"
        finally:
            self._final_cleanup()

    def _run_cycle(self) -> None:
        """Execute one complete scan cycle.

        1. Run exactly one scan using only session_hci.
        2. Process returned devices (update active table, rate-limited logging).
        3. Perform due housekeeping (TTL check).
        4. Return -- the caller waits interruptibly.
        """
        # 1. Run exactly one scan using only session_hci
        devices = self._safe_scan()

        # 2. Process returned devices
        self._process_devices(devices)

        # 3. Perform due housekeeping (TTL roll-off)
        self._check_ttl()

        # 4. Cycle counter incremented in _scan_loop; retention runs periodically

    def _safe_scan(self) -> List[Dict[str, Any]]:
        """Run ``hcitool_scan_bt`` with graceful error handling.

        Returns an empty list (not ``None``) on any exception so the loop
        if self._session_hci is None:
            return []
        never breaks; errors are recorded in ``_last_error`` and exposed via
        the status endpoint.
        """
        try:
            devices = hcitool_scan_bt(self._session_hci, limit=80)
            return devices if devices is not None else []
        except Exception as e:
            self._last_error = f"scan error: {e}"
            return []

    # ------------------------------------------------------------------
    # Device processing (active table + logging)
    # ------------------------------------------------------------------

    def _process_devices(self, devices: List[Dict[str, Any]]) -> None:
        """Process a scan's device list: update active table and logging state.

        The active table updates every cycle unconditionally.  JSONL writing
        is rate-limited per-device (``observation_log_interval_seconds``) and
        also triggered by meaningful field changes or first-seen / roll-off.
        """
        now = time.time()

        for d in devices:
            mac = (d.get("mac") or "").upper()
            if not mac:
                continue

            name = _clean_bt_name(d.get("name") or "", mac)
            rssi_dbm = d.get("rssi_dbm")
            dev_type = d.get("type") or "classic"
            vendor = d.get("vendor") or ""

            if mac not in self._devices:
                # ---- First seen in this continuous session ----
                self._devices[mac] = {
                    "mac": mac,
                    "name": name,
                    "rssi_dbm": rssi_dbm,
                    "type": dev_type,
                    "vendor": vendor,
                    "source": self._session_hci,
                    "first_seen": now,
                    "last_seen": now,
                    "seen_count": 1,
                }

                # Update shared cache so GET /api/devices?type=bt reflects it
                self._update_cache_device(mac, first_time=True)

                # Always log a first-seen observation
                self._log_observation(mac, "first_seen", {
                    "name": name, "rssi_dbm": rssi_dbm,
                    "type": dev_type, "vendor": vendor,
                })

            else:
                # ---- Device already tracked ----
                dev = self._devices[mac]

                # Track meaningful field changes for change-based logging
                fields_changed = self._device_fields_changed(mac, {
                    "name": name, "rssi_dbm": rssi_dbm,
                    "type": dev_type, "vendor": vendor,
                })

                if name:
                    dev["name"] = name
                if rssi_dbm is not None:
                    dev["rssi_dbm"] = rssi_dbm
                dev["type"] = dev_type
                dev["vendor"] = vendor
                dev["last_seen"] = now
                dev["seen_count"] = int(dev.get("seen_count") or 0) + 1

                # Also update the shared cache
                self._update_cache_device(mac, first_time=False)

                # ---- JSONL logging decision ----
                # Log if enough time has elapsed since last log for this device
                log_due = False
                if mac not in self._last_log_ts:
                    log_due = True
                elif now - self._last_log_ts[mac] > self._config["observation_log_interval_seconds"]:
                    log_due = True

                # Or if fields changed meaningfully
                if not log_due and fields_changed:
                    log_due = True

                if log_due:
                    self._log_observation(mac, "interval" if not fields_changed else "field_change", {
                        "name": name, "rssi_dbm": rssi_dbm,
                        "type": dev_type, "vendor": vendor,
                    })
                    self._last_log_ts[mac] = now

    def _device_fields_changed(self, mac: str, new_fields: Dict[str, Any]) -> bool:
        """Return ``True`` if any tracked field differs beyond the RSSI threshold."""

        dev = self._devices.get(mac, {})

        # RSSI change threshold
        old_rssi = dev.get("rssi_dbm")
        new_rssi = new_fields.get("rssi_dbm")
        if old_rssi is not None and new_rssi is not None:
            try:
                if abs(float(new_rssi) - float(old_rssi)) > self._config["rssi_change_threshold_db"]:
                    return True
            except (ValueError, TypeError):
                pass

        # Name / type / vendor string changes
        for key in ("name", "type", "vendor"):
            old_val = dev.get(key)
            new_val = new_fields.get(key)
            if str(old_val) != str(new_val):
                return True

        return False

    # ------------------------------------------------------------------
    # Shared-cache integration (DEVICE_CACHE["bt"])
    # ------------------------------------------------------------------

    def _update_cache_device(self, mac: str, first_time: bool) -> None:
        """Synchronise this manager's device into the global ``DEVICE_CACHE["bt"]``."""

        now = time.time()
        entry: Dict[str, Any] = {"mac": mac}

        if first_time:
            dev = self._devices.get(mac, {})
            entry.update(
                {
                    "name": dev.get("name", ""),
                    "rssi_dbm": dev.get("rssi_dbm"),
                    "type": dev.get("type", "classic"),
                    "vendor": dev.get("vendor", ""),
                    "active": True,
                    "last_seen": now,
                    "seen_count": 1,
                    "source": self._session_hci,
                    "continuous": True,
                    "continuous_session_id": self._session_id,
                }
            )
            DEVICE_CACHE["bt"][mac] = entry
        else:
            existing = DEVICE_CACHE["bt"].get(mac, {})
            entry["seen_count"] = int(existing.get("seen_count") or 0) + 1
            entry["last_seen"] = now
            entry["source"] = self._session_hci
            entry["continuous"] = True
            entry["continuous_session_id"] = self._session_id
            dev = self._devices.get(mac, {})
            if dev.get("name"):
                entry["name"] = dev["name"]
            if dev.get("rssi_dbm") is not None:
                entry["rssi_dbm"] = dev["rssi_dbm"]
            if dev.get("type"):
                entry["type"] = dev["type"]
            if dev.get("vendor"):
                entry["vendor"] = dev["vendor"]
            DEVICE_CACHE["bt"][mac] = entry

    # ------------------------------------------------------------------
    # TTL age-out / roll-off
    # ------------------------------------------------------------------

    def _check_ttl(self) -> None:
        """Remove devices that have exceeded the inactivity TTL and log roll-off."""

        now = time.time()
        ttl = self._config["active_device_ttl_seconds"]

        for mac in list(self._devices.keys()):
            if now - self._devices[mac]["last_seen"] > ttl:
                dev = self._devices.pop(mac)
                self._log_rolloff(mac, dev, now)
                cached = DEVICE_CACHE["bt"].get(mac) or {}
                sid = cached.get("continuous_session_id")
                same_session = sid == self._session_id
                same_source = (
                    not sid
                    and cached.get("continuous")
                    and cached.get("source") == self._session_hci
                )
                if same_session or same_source:
                    DEVICE_CACHE["bt"].pop(mac, None)

    def _log_rolloff(self, mac: str, device: Dict[str, Any], now: float) -> None:
        """Write a ``bluetooth_device_rolled_off`` JSONL event."""

        observed_at = datetime.fromtimestamp(now, tz=timezone.utc)
        observed_at_iso = observed_at.isoformat()
        observed_at_epoch = now

        # Device details from the just-removed record
        dev = self._devices.get(mac, device)  # fallback to passed-in dict
        device_block = {
            "address": mac,
            "address_type": None,
            "name": dev.get("name", ""),
            "rssi_dbm": dev.get("rssi_dbm"),
            "tx_power_dbm": None,
            "kind": dev.get("type", "classic"),
            "vendor": dev.get("vendor", ""),
            "manufacturer_data": {},
            "service_uuids": [],
        }

        session_device = {
            "first_seen_at": (
                datetime.fromtimestamp(device.get("first_seen"), tz=timezone.utc).isoformat()
                if device.get("first_seen")
                else ""
            ),
            "last_seen_at": (
                datetime.fromtimestamp(device.get("last_seen"), tz=timezone.utc).isoformat()
                if device.get("last_seen")
                else ""
            ),
            "seen_count": device.get("seen_count", 0),
        }

        inactive_seconds = int(now - device.get("last_seen", now))

        record = {
            "schema_version": 1,
            "event_type": "bluetooth_device_rolled_off",
            "reason": "inactive_ttl_expired",
            "observed_at": observed_at_iso,
            "observed_at_epoch": observed_at_epoch,
            "session_id": self._session_id or "",
            "adapter": self._session_hci or "",
            "device": device_block,
            "session_device": session_device,
            "inactive_for_seconds": inactive_seconds,
        }

        self._safe_jsonl_write(json.dumps(record, default=str) + "\n")

    # ------------------------------------------------------------------
    # JSONL logging: rotation, rate-limit, low-space pause, safe write
    # ------------------------------------------------------------------

    def _rotate_log(self) -> bool:
        """Open the current-date JSONL file. Return True on success."""
        log_dir = Path(self._log_dir)
        current_date = datetime.now().strftime("%Y-%m-%d")

        if self._current_date == current_date and self._log_file is not None:
            return True

        if self._log_file is not None:
            try:
                self._log_file.flush()
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            self._current_date = current_date
            self._log_path = log_dir / f"observations-{current_date}.jsonl"
            self._log_file = open(self._log_path, "a", encoding="utf-8", buffering=1)
            return True
        except Exception as e:
            self._log_file = None
            self._log_path = None
            self._last_error = f"log open failed: {e}"
            return False

    def _log_observation(self, mac: str, reason: str, device_data: Dict[str, Any]) -> None:
        """Write one JSONL observation record to the current day's file."""

        now = time.time()
        observed_at = datetime.fromtimestamp(now, tz=timezone.utc)
        observed_at_iso = observed_at.isoformat()
        observed_at_epoch = now

        # Build device sub-record from the manager's active table
        if mac in self._devices:
            dev = self._devices[mac]
        else:
            dev = {}

        device_block = {
            "address": mac,
            "address_type": None,
            "name": dev.get("name", ""),
            "rssi_dbm": dev.get("rssi_dbm"),
            "tx_power_dbm": None,
            "kind": dev.get("type", "classic"),
            "vendor": dev.get("vendor", ""),
            "manufacturer_data": {},
            "service_uuids": [],
        }

        session_device = {
            "first_seen_at": (
                datetime.fromtimestamp(dev["first_seen"], tz=timezone.utc).isoformat()
                if dev.get("first_seen")
                else ""
            ),
            "last_seen_at": (
                datetime.fromtimestamp(dev["last_seen"], tz=timezone.utc).isoformat()
                if dev.get("last_seen")
                else ""
            ),
            "seen_count": dev.get("seen_count", 0),
        }

        record = {
            "schema_version": 1,
            "event_type": "bluetooth_observation",
            "observed_at": observed_at_iso,
            "observed_at_epoch": observed_at_epoch,
            "session_id": self._session_id or "",
            "adapter": self._session_hci or "",
            "device": device_block,
            "session_device": session_device,
            "reason": reason,
        }

        self._safe_jsonl_write(json.dumps(record, default=str) + "\n")

    def _safe_jsonl_write(self, line: str) -> None:
        """Write one JSONL line. Never dereference a None log handle."""
        reserve = float(self._config.get("minimum_free_space_mb") or 0)
        free_mb: Optional[float] = None
        probe = Path(self._log_dir)
        while not probe.exists() and probe != probe.parent:
            probe = probe.parent
        try:
            usage = shutil.disk_usage(str(probe))
            free_mb = float(usage.free) / (1024.0 * 1024.0)
        except (TypeError, ValueError, OSError, AttributeError):
            free_mb = None

        if free_mb is not None and free_mb <= reserve:
            self._logging_paused = True
            self._pause_reason = "low_storage"
            self._last_error = "logging paused: low storage"
            return

        if self._logging_paused and self._pause_reason == "low_storage":
            if free_mb is not None and free_mb > reserve:
                self._logging_paused = False
                self._pause_reason = None
                self._last_error = None
            else:
                return

        if self._logging_paused and self._pause_reason not in (None, "low_storage"):
            return

        if self._log_file is None:
            if not self._rotate_log():
                self._logging_paused = True
                self._pause_reason = "log_open_failed"
                return

        if self._log_file is None:
            return

        try:
            self._log_file.write(line)
            self._log_file.flush()
            os.fsync(self._log_file.fileno())
            self._consecutive_write_fails = 0
        except OSError as e:
            if getattr(e, "errno", None) == errno.ENOSPC:
                self._logging_paused = True
                self._pause_reason = "low_storage"
                self._last_error = "logging paused: low storage"
            else:
                self._logging_paused = True
                self._pause_reason = "log_write_failed"
                self._last_error = f"log write failed: {e}"

    # ------------------------------------------------------------------
    # Storage retention (delete / compress old log files)
    # ------------------------------------------------------------------

    def _retention_cleanup(self) -> None:
        """Delete / compress old JSONL files per configured policy.

        Current-day file is never touched.  Three controls are applied:
        1. Delete files older than ``retention_days``.
        2. Compress files older than ``compress_after_days`` (but not current).
        3. Enforce ``max_total_log_size_mb`` by deleting oldest closed files.
        """
        # Identify the current-day file (protect it from deletion/compression)
        current_date = datetime.now().strftime("%Y-%m-%d")
        current_file = BT_CONTINUOUS_DIR / f"observations-{current_date}.jsonl"

        # ---- Gather all log files (excluding current day) ----
        all_files: List[Tuple[Path, float, int]] = []  # (path, mtime, size)

        for f in BT_CONTINUOUS_DIR.glob("observations-*.jsonl"):
            try:
                if f.name == f"observations-{current_date}.jsonl":
                    continue  # skip current day
                sz = f.stat().st_size
                all_files.append((f, f.stat().st_mtime, sz))
            except Exception:
                pass

        for f in BT_CONTINUOUS_DIR.glob("observations-*.jsonl.gz"):
            try:
                if f.name == f"observations-{current_date}.jsonl.gz":
                    continue  # skip current day compressed
                sz = f.stat().st_size
                all_files.append((f, f.stat().st_mtime, sz))
            except Exception:
                pass

        # ---- 1. Delete files older than retention_days ----
        retention_cutoff = time.time() - (self._config["retention_days"] * 86400)
        for f, mtime, sz in all_files:
            if mtime < retention_cutoff:
                try:
                    f.unlink()
                    csvp = f.with_suffix(".csv")
                    if csvp.exists():
                        csvp.unlink()
                except Exception:
                    pass

        # ---- 2. Compress eligible closed files older than compress_after_days ----
        compress_cutoff = time.time() - (self._config["compress_after_days"] * 86400)
        for f, mtime, sz in all_files:
            if mtime < compress_cutoff and f != current_file:
                try:
                    gz_path = f.with_suffix(".jsonl.gz")
                    with open(f, "rb") as f_in:
                        with gzip.open(gz_path, "wb") as f_out:
                            f_out.writelines(f_in)
                    f.unlink()  # remove original
                except Exception:
                    pass

        # ---- 3. Enforce max_total_log_size_mb ----
        # Recalculate total size of all remaining log files (incl. current)
        total_size = 0
        for f in BT_CONTINUOUS_DIR.glob("observations-*.jsonl"):
            try:
                total_size += f.stat().st_size
            except Exception:
                pass
        for f in BT_CONTINUOUS_DIR.glob("observations-*.jsonl.gz"):
            try:
                total_size += f.stat().st_size
            except Exception:
                pass

        max_total = self._config["max_total_log_size_mb"] * 1024 * 1024

        # If still over limit, delete oldest closed files
        if total_size > max_total:
            # Sort all closed files by mtime ascending (oldest first)
            closed: List[Tuple[Path, float, int]] = []
            for f in BT_CONTINUOUS_DIR.glob("observations-*.jsonl"):
                try:
                    if f.name == f"observations-{current_date}.jsonl":
                        continue
                    closed.append((f, f.stat().st_mtime, f.stat().st_size))
                except Exception:
                    pass
            closed.sort(key=lambda x: x[1])  # oldest first
            for f, _, sz in closed:
                if total_size <= max_total:
                    break
                try:
                    f.unlink()
                    csvp = f.with_suffix(".csv")
                    if csvp.exists():
                        csvp.unlink()
                    total_size -= sz
                except Exception:
                    pass

        # Recheck free space after cleanup – if space has recovered,
        # logging can resume automatically on the next cycle.
        try:
            usage = shutil.disk_usage(str(DATA_DIR))
            free_mb = usage.free / (1024.0 * 1024.0)
            if self._logging_paused and free_mb >= self._config["minimum_free_space_mb"]:
                self._logging_paused = False
                self._pause_reason = None
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Final cleanup when the thread stops
    # ------------------------------------------------------------------

    def _final_cleanup(self) -> None:
        """Flush and close the log file and run one last retention sweep."""

        if self._log_file is not None:
            try:
                self._log_file.flush()
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None

        # Run retention once more so no items are left in an inconsistent state
        try:
            self._retention_cleanup()
        except Exception:
            pass


# ----------------------------------------------------------------------
# Module-level singleton – the Flask routes import this instance
# ----------------------------------------------------------------------

bt_continuous_manager = BTContinuousManager()