#!/usr/bin/env python3
"""Minimal Kismet REST client for SmashDeck."""
from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests

from utils.paths import KISMET_DIR, ensure_data_dirs
from utils.oui_lookup import vendor_name

ensure_data_dirs()
DEFAULT_URL = "http://127.0.0.1:2501"


class KismetClient:
    def __init__(self, base: str = DEFAULT_URL, user: str = "", password: str = ""):
        self.base = base.rstrip("/")
        self.session = requests.Session()
        if user:
            self.session.auth = (user, password)
        self.session.headers.update({"Content-Type": "application/json"})

    def is_port_open(self, host: str = "127.0.0.1", port: int = 2501, timeout: float = 0.4) -> bool:
        try:
            with socket.create_connection((host, port), timeout=timeout):
                return True
        except OSError:
            return False

    def _get(self, path: str, timeout: float = 8.0) -> Any:
        r = self.session.get(f"{self.base}{path}", timeout=timeout)
        r.raise_for_status()
        if "json" in (r.headers.get("content-type") or ""):
            return r.json()
        try:
            return r.json()
        except Exception:
            return r.text

    def _post(self, path: str, data: Optional[dict] = None, timeout: float = 10.0) -> Any:
        r = self.session.post(f"{self.base}{path}", data=json.dumps(data or {}), timeout=timeout)
        try:
            return r.json()
        except Exception:
            return {"status": r.status_code, "text": r.text[:500]}

    def system_status(self) -> Dict[str, Any]:
        if not self.is_port_open():
            return {"running": False, "console": _log_tail(), "web": self.base}
        try:
            st = self._get("/system/status.json")
            if not isinstance(st, dict):
                st = {}
            sources = []
            try:
                sources = self.list_sources() or []
            except Exception:
                pass
            return {
                "running": True,
                "status": st,
                "sources": sources,
                "summary": _status_summary(st, sources),
                "console": _log_tail(),
                "web": self.base,
            }
        except Exception as e:
            return {"running": self.is_port_open(), "error": str(e), "console": _log_tail(), "web": self.base}

    def list_devices(self, limit: int = 100) -> List[Dict[str, Any]]:
        if not self.is_port_open():
            return []
        try:
            raw = self._get(f"/devices/summary/devices.json")
        except Exception:
            return []
        if not isinstance(raw, list):
            return []
        out = []
        for d in raw[:limit]:
            if not isinstance(d, dict):
                continue
            mac = (d.get("kismet.device.base.macaddr") or d.get("kismet.device.base.key") or "").upper()
            name = d.get("kismet.device.base.name") or d.get("kismet.device.base.commonname") or ""
            ssid = ""
            try:
                ssid = (
                    (d.get("dot11.device.last_beaconed_ssid_record") or {}).get("dot11.advertisedssid.ssid")
                    or ""
                )
            except Exception:
                pass
            rssi = d.get("kismet.device.base.signal", {})
            if isinstance(rssi, dict):
                rssi = rssi.get("kismet.common.signal.last_signal")
            phy = (d.get("kismet.device.base.phyname") or "").lower()
            dtype = "wifi" if "802.11" in phy or "ieee80211" in phy else ("bt" if "bt" in phy or "bluetooth" in phy else phy or "unknown")
            out.append({
                "mac": mac,
                "name": name or ssid or mac,
                "ssid": ssid,
                "rssi_dbm": rssi,
                "type": dtype,
                "vendor": d.get("kismet.device.base.manuf") or vendor_name(mac),
                "last_seen": d.get("kismet.device.base.last_time") or time.time(),
                "active": True,
                "source": "kismet",
                "channel": d.get("kismet.device.base.channel"),
            })
        return out

    def list_sources(self) -> List[Any]:
        if not self.is_port_open():
            return []
        try:
            return self._get("/datasource/all_sources.json") or []
        except Exception:
            return []

    def add_source(self, definition: str) -> Any:
        return self._post("/datasource/add_source.cmd", {"definition": definition})


def _log_tail(n: int = 40) -> str:
    log = KISMET_DIR / "kismet_launch.log"
    try:
        lines = log.read_text(errors="replace").splitlines()
        return "\n".join(lines[-n:])
    except Exception:
        return ""


def _status_summary(st: Dict[str, Any], sources: List[Any]) -> Dict[str, Any]:
    def g(*keys):
        for k in keys:
            if k in st and st[k] is not None:
                return st[k]
        return None

    src_lines = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        name = s.get("kismet.datasource.name") or s.get("kismet.datasource.interface") or "?"
        iface = s.get("kismet.datasource.interface") or ""
        ch = s.get("kismet.datasource.channel") or s.get("kismet.datasource.hop_cur_channel") or ""
        run = s.get("kismet.datasource.running")
        pkts = s.get("kismet.datasource.num_packets")
        src_lines.append({
            "name": name,
            "interface": iface,
            "channel": ch,
            "running": run,
            "packets": pkts,
        })
    return {
        "version": g("kismet.system.version", "kismet.system.server_version"),
        "devices": g("kismet.system.devices.count", "kismet.system.num_devices"),
        "packet_rate": g("kismet.system.packets.rate", "kismet.system.packet_rate"),
        "memory": g("kismet.system.memory.rss", "kismet.system.memory.rss_bytes"),
        "started": g("kismet.system.timestamp.start_sec"),
        "sources": src_lines,
    }


_client: Optional[KismetClient] = None


def get_client() -> KismetClient:
    global _client
    if _client is None:
        _client = KismetClient()
    return _client


def _wifi_source_def() -> str:
    try:
        from utils.device_detector import get_device_summary
        for d in get_device_summary().get("wifi") or []:
            iface = d.get("iface") or d.get("id") or ""
            if iface and iface != "wlan0":
                return f"{iface}:name=SmashDeck"
    except Exception:
        pass
    return ""


def ensure_kismet(extra_source: str = "") -> Tuple[bool, str]:
    """Start kismet as a daemon and keep it running."""
    c = get_client()
    src = extra_source or _wifi_source_def()
    if c.is_port_open():
        if src:
            try:
                c.add_source(src)
            except Exception:
                pass
        return True, "Kismet already running"
    ensure_data_dirs()
    log = KISMET_DIR / "kismet_launch.log"
    homedir = str(KISMET_DIR)
    base = ["--no-ncurses", "--daemonize"]
    if src:
        base += ["-c", src]
    attempts = [
        ["sudo", "-n", "kismet"] + base,
        ["kismet"] + base,
        ["sudo", "-n", "kismet", "--no-ncurses"],
        ["kismet", "--no-ncurses"],
    ]
    last_err = "kismet not installed"
    logf = open(log, "a")
    logf.write(f"\n--- launch {time.strftime('%Y-%m-%d %H:%M:%S')} src={src}\n")
    logf.flush()
    for cmd in attempts:
        try:
            subprocess.Popen(
                cmd,
                cwd=homedir,
                stdout=logf,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                env={**os.environ, "HOME": homedir},
            )
        except FileNotFoundError:
            last_err = "kismet not installed"
            continue
        except Exception as e:
            last_err = str(e)
            continue
        for _ in range(30):
            time.sleep(0.4)
            if c.is_port_open():
                if src:
                    try:
                        c.add_source(src)
                    except Exception:
                        pass
                return True, "Kismet started"
        last_err = "Kismet start timeout — see data/kismet/kismet_launch.log"
    return False, last_err
