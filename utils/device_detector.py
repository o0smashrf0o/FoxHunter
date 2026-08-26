#!/usr/bin/env python3
"""USB / interface device detection for SmashDeck."""
from __future__ import annotations

import re
import subprocess
from typing import Any, Dict, List


def _run(cmd: List[str], timeout: float = 8.0) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return (p.stdout or "") + (p.stderr or "")
    except Exception:
        return ""


USB_DB = {
    "0bda:2838": {"type": "sdr", "model": "RTL-SDR", "caps": ["rx", "rtl"]},
    "0bda:2832": {"type": "sdr", "model": "RTL-SDR", "caps": ["rx", "rtl"]},
    "1d50:6089": {"type": "sdr", "model": "HackRF", "caps": ["rx", "tx", "hackrf"]},
    "1d50:6108": {"type": "sdr", "model": "LimeSDR Mini", "caps": ["rx", "tx", "lime"]},
    "1d50:6002": {"type": "bt", "model": "Ubertooth One", "caps": ["ubertooth", "passive"]},
    "0a5c:21e8": {"type": "bt", "model": "BCM20702 (UD100-class)", "caps": ["hci"]},
    "0bda:8176": {"type": "wifi", "model": "Realtek RTL8188", "caps": ["monitor"]},
    "148f:5370": {"type": "wifi", "model": "Ralink RT5370 (Panda)", "caps": ["monitor", "inject"]},
    "148f:5572": {"type": "wifi", "model": "Ralink RT5572 (Panda)", "caps": ["monitor", "inject"]},
    "0bda:8812": {"type": "wifi", "model": "RTL8812AU (Alfa)", "caps": ["monitor", "inject", "dual_band"]},
    "0bda:8813": {"type": "wifi", "model": "RTL8814AU", "caps": ["monitor", "inject"]},
}


def _lsusb_devices() -> List[Dict[str, Any]]:
    out = _run(["lsusb"])
    found = []
    for line in out.splitlines():
        m = re.search(r"ID\s+([0-9a-f]{4}):([0-9a-f]{4})\s*(.*)$", line, re.I)
        if not m:
            continue
        vid_pid = f"{m.group(1).lower()}:{m.group(2).lower()}"
        name = (m.group(3) or "").strip()
        meta = USB_DB.get(vid_pid, {})
        found.append({
            "vid_pid": vid_pid,
            "usb_name": name,
            "type": meta.get("type") or "usb",
            "model": meta.get("model") or name or vid_pid,
            "caps": meta.get("caps") or [],
            "id": vid_pid,
        })
    return found


def _wifi_ifaces() -> List[Dict[str, Any]]:
    out = _run(["iw", "dev"])
    ifaces = []
    cur = None
    for line in out.splitlines():
        m = re.match(r"^\s*Interface\s+(\S+)", line)
        if m:
            cur = {"type": "wifi", "id": m.group(1), "device_path": m.group(1),
                   "model": m.group(1), "caps": [], "iface": m.group(1)}
            ifaces.append(cur)
            continue
        if cur and "type" in line.lower():
            t = line.split()[-1].lower()
            cur["mode"] = t
            if t == "monitor":
                cur["caps"] = list(set(cur.get("caps", []) + ["monitor"]))
    # phy capabilities
    for d in ifaces:
        info = _run(["iw", "phy"])
        if "monitor" in info.lower():
            d["caps"] = list(set(d.get("caps", []) + ["monitor"]))
    return ifaces


def _bt_ifaces() -> List[Dict[str, Any]]:
    out = _run(["hciconfig", "-a"]) or _run(["bluetoothctl", "list"])
    found = []
    for m in re.finditer(r"(hci\d+)", out):
        hci = m.group(1)
        found.append({
            "type": "bt", "id": hci, "hci": hci, "model": hci,
            "caps": ["hci", "scan"], "device_path": hci,
        })
    # dedupe
    seen = set()
    uniq = []
    for d in found:
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        uniq.append(d)
    return uniq


def get_device_summary() -> Dict[str, Any]:
    usb = _lsusb_devices()
    wifi = _wifi_ifaces()
    bt = _bt_ifaces()
    sdrs = [d for d in usb if d.get("type") == "sdr"]
    all_devs = usb + wifi + bt
    # merge usb wifi/bt labels onto ifaces when possible
    return {
        "sdrs": sdrs,
        "wifi": wifi,
        "bt": bt,
        "usb": usb,
        "all": all_devs,
        "count": len(all_devs),
        "caps": {
            "wifi_monitor": any("monitor" in (d.get("caps") or []) for d in wifi)
                or any(d.get("type") == "wifi" and "monitor" in (d.get("caps") or []) for d in usb),
            "bt_hci_scan": bool(bt),
            "sdr_rx": bool(sdrs) or any("rtl" in str(d.get("caps")) for d in usb),
            "ubertooth": any("ubertooth" in (d.get("caps") or []) for d in usb),
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_device_summary(), indent=2))
