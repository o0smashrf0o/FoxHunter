#!/usr/bin/env python3
"""Hardware / binary presence checks."""
from __future__ import annotations

import shutil
from typing import Any, Dict, List

from utils.device_detector import get_device_summary

BINARIES = [
    "python3", "iw", "ip", "rfkill", "hciconfig", "hcitool", "bluetoothctl",
    "l2ping", "kismet", "nmap", "airmon-ng", "airodump-ng",
    "rtl_power", "rtl_test", "hackrf_info", "hackrf_sweep", "SoapySDRUtil",
]


def check_binaries() -> List[Dict[str, Any]]:
    out = []
    for b in BINARIES:
        path = shutil.which(b)
        out.append({"name": b, "ok": bool(path), "path": path or ""})
    return out


def run_all_checks() -> Dict[str, Any]:
    devices = get_device_summary()
    bins = check_binaries()
    return {
        "ok": True,
        "devices": devices,
        "binaries": bins,
        "binary_ok": sum(1 for b in bins if b["ok"]),
        "binary_total": len(bins),
        "caps": devices.get("caps") or {},
    }


if __name__ == "__main__":
    import json
    print(json.dumps(run_all_checks(), indent=2, default=str))
