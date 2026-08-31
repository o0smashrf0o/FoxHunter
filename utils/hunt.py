#!/usr/bin/env python3
"""Hunt session — live RSSI samples + histogram for one SOI."""
from __future__ import annotations

import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional

from utils.iface_scan import bt_rssi_for, wifi_rssi_for

_HIST: Deque[Dict[str, Any]] = deque(maxlen=120)
_STATE: Dict[str, Any] = {
    "running": False,
    "mac": "",
    "kind": "wifi",
    "source": "",
    "last_rssi": None,
    "min_rssi": None,
    "max_rssi": None,
    "samples": 0,
    "started_at": None,
    "error": None,
}


def status() -> Dict[str, Any]:
    hist = list(_HIST)
    return {**_STATE, "histogram": hist, "ok": True}


def start(mac: str, kind: str = "wifi", source: str = "") -> Dict[str, Any]:
    _HIST.clear()
    _STATE.update({
        "running": True,
        "mac": (mac or "").upper(),
        "kind": kind if kind in ("wifi", "bt") else "wifi",
        "source": source or ("wlan1" if kind != "bt" else "hci0"),
        "last_rssi": None,
        "min_rssi": None,
        "max_rssi": None,
        "samples": 0,
        "started_at": time.time(),
        "error": None,
    })
    return status()


def stop() -> Dict[str, Any]:
    _STATE["running"] = False
    return status()


def sample() -> Dict[str, Any]:
    if not _STATE.get("running") or not _STATE.get("mac"):
        return status()
    kind = _STATE["kind"]
    src = _STATE["source"]
    mac = _STATE["mac"]
    rssi: Optional[int] = None
    try:
        if kind == "bt":
            rssi = bt_rssi_for(mac, src or "hci0")
        else:
            rssi = wifi_rssi_for(mac, src or "wlan1")
        _STATE["error"] = None if rssi is not None else "no signal"
    except Exception as e:
        _STATE["error"] = str(e)
        rssi = None
    rec = {"t": time.time(), "rssi": rssi}
    _HIST.append(rec)
    if rssi is not None:
        _STATE["last_rssi"] = rssi
        _STATE["samples"] = int(_STATE["samples"] or 0) + 1
        mn, mx = _STATE.get("min_rssi"), _STATE.get("max_rssi")
        _STATE["min_rssi"] = rssi if mn is None else min(mn, rssi)
        _STATE["max_rssi"] = rssi if mx is None else max(mx, rssi)
    return status()


def last_rssi() -> Optional[int]:
    return _STATE.get("last_rssi")
