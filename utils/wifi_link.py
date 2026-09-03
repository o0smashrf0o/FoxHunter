#!/usr/bin/env python3
from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple


def _run(cmd: List[str], timeout: float = 8.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except Exception as e:
        return -1, str(e)


def _sudo(cmd: List[str], timeout: float = 8.0) -> tuple[int, str]:
    return _run(["sudo", "-n"] + cmd, timeout=timeout)


def iface_status(iface: str) -> Dict[str, Any]:
    iface = (iface or "").strip()
    info: Dict[str, Any] = {
        "iface": iface,
        "connected": False,
        "internet": False,
        "ssid": "",
        "managed": True,
    }
    if not iface:
        return info
    rc, out = _run(["iw", "dev", iface, "link"])
    if "Connected to" in out or "connected to" in out.lower():
        info["connected"] = True
        m = re.search(r"SSID:\s*(.+)", out)
        if m:
            info["ssid"] = m.group(1).strip()
    rc, route = _run(["ip", "route", "show", "default"])
    if iface and iface in route:
        info["internet"] = True
        info["connected"] = True
    rc, nm = _run(["nmcli", "-t", "-f", "DEVICE,STATE,CONNECTION", "device"])
    for line in (nm or "").splitlines():
        parts = line.split(":")
        if not parts or parts[0] != iface:
            continue
        state = (parts[1] if len(parts) > 1 else "").lower()
        if state in ("connected", "connecting"):
            info["connected"] = True
        if len(parts) > 2 and parts[2] and parts[2] not in ("", "--"):
            info["ssid"] = info["ssid"] or parts[2]
        if state == "unmanaged":
            info["managed"] = False
    return info


def release_iface(iface: str) -> Tuple[bool, str]:
    iface = (iface or "").strip()
    if not re.match(r"^[A-Za-z0-9_.-]+$", iface):
        return False, "bad interface"
    ctl = Path("/opt/foxhunter/os/bin/wifi-release")
    if not ctl.is_file():
        ctl = Path(__file__).resolve().parents[1] / "os" / "bin" / "wifi-release"
    notes = []
    if ctl.is_file():
        rc, out = _sudo([str(ctl), iface], timeout=15)
        notes.append(out or f"wifi-release rc={rc}")
    else:
        for cmd in (
            ["nmcli", "device", "disconnect", iface],
            ["nmcli", "device", "set", iface, "managed", "no"],
            ["iw", "dev", iface, "disconnect"],
            ["ip", "link", "set", iface, "up"],
        ):
            rc, out = _sudo(cmd, timeout=10)
            if out:
                notes.append(out)
    st = iface_status(iface)
    if st.get("connected") and st.get("managed"):
        return False, "Still associated: " + ("; ".join(notes) or "disconnect failed")
    return True, "Released " + iface + (" (" + st.get("ssid") + ")" if st.get("ssid") else "")
