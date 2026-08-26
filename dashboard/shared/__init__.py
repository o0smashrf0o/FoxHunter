"""Shared dashboard state and helpers."""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from utils.paths import PROJECT_ROOT

DEVICE_CACHE: Dict[str, Dict[str, Any]] = {"wifi": {}, "bt": {}}
SOURCE_SETTINGS: Optional[dict] = None


def load_source_settings() -> dict:
    global SOURCE_SETTINGS
    if SOURCE_SETTINGS is not None:
        return SOURCE_SETTINGS
    p = PROJECT_ROOT / "config" / "source_settings.yaml"
    try:
        SOURCE_SETTINGS = yaml.safe_load(p.read_text()) or {}
    except Exception:
        SOURCE_SETTINGS = {}
    return SOURCE_SETTINGS


def resolve_wifi_iface(source_key: str = "", default: str = "wlan1") -> str:
    settings = load_source_settings()
    src = (settings.get("wifi_sources") or {}).get(source_key) or {}
    if src.get("iface"):
        return src["iface"]
    # first non-builtin
    try:
        from utils.device_detector import get_device_summary
        for d in get_device_summary().get("wifi") or []:
            iface = d.get("iface") or d.get("id")
            if iface and iface != "wlan0":
                return iface
    except Exception:
        pass
    return default


def resolve_bt_hci(source_key: str = "", default: str = "hci0") -> str:
    settings = load_source_settings()
    src = (settings.get("bt_sources") or {}).get(source_key) or {}
    if src.get("hci"):
        return src["hci"]
    if source_key and "hci" in source_key:
        for part in source_key.replace("-", "_").split("_"):
            if part.startswith("hci"):
                return part
    try:
        from utils.device_detector import get_device_summary
        bts = get_device_summary().get("bt") or []
        if bts:
            return bts[0].get("hci") or bts[0].get("id") or default
    except Exception:
        pass
    return default


def merge_devices(kind: str, devices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cache = DEVICE_CACHE.setdefault(kind, {})
    now = time.time()
    for d in devices:
        mac = (d.get("mac") or "").upper()
        if not mac:
            continue
        prev = cache.get(mac) or {}
        merged = {**prev, **d, "mac": mac}
        merged["seen_count"] = int(prev.get("seen_count") or 0) + 1
        merged["last_seen"] = d.get("last_seen") or now
        if d.get("rssi_dbm") is None and prev.get("rssi_dbm") is not None:
            merged["rssi_dbm"] = prev["rssi_dbm"]
        cache[mac] = merged
    # expire stale (>10 min)
    for mac in list(cache.keys()):
        if now - float(cache[mac].get("last_seen") or 0) > 600:
            cache[mac]["active"] = False
    return sorted(
        cache.values(),
        key=lambda x: x.get("rssi_dbm") if x.get("rssi_dbm") is not None else -999,
        reverse=True,
    )


def run_sync(cmd: List[str], timeout: float = 15.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except FileNotFoundError:
        return -1, f"not found: {cmd[0]}"
    except Exception as e:
        return -1, str(e)


def system_stats() -> Dict[str, Any]:
    stats: Dict[str, Any] = {"ts": time.time()}
    try:
        load = os.getloadavg()
        stats["load"] = list(load)
    except Exception:
        stats["load"] = []
    try:
        with open("/proc/meminfo") as f:
            info = f.read()
        def _kb(key):
            import re
            m = re.search(rf"{key}:\s+(\d+)", info)
            return int(m.group(1)) if m else 0
        total, avail = _kb("MemTotal"), _kb("MemAvailable")
        stats["mem_total_mb"] = total // 1024
        stats["mem_avail_mb"] = avail // 1024
        stats["mem_used_pct"] = round(100 * (1 - avail / total), 1) if total else 0
    except Exception:
        pass
    try:
        t = Path("/sys/class/thermal/thermal_zone0/temp")
        if t.is_file():
            stats["temp_c"] = round(int(t.read_text().strip()) / 1000.0, 1)
    except Exception:
        pass
    return stats
