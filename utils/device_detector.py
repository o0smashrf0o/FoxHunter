#!/usr/bin/env python3
"""USB / interface device detection for SmashDeck.

Known VID:PIDs are labeled; unknown wireless/BT/SDR sticks still show up
as live wlan*/hci* interfaces so any dongle can be used.
"""
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


# Labels only — detection never requires a match here.
USB_DB = {
    "0bda:2838": {"type": "sdr", "model": "RTL-SDR", "caps": ["rx", "rtl"]},
    "0bda:2832": {"type": "sdr", "model": "RTL-SDR", "caps": ["rx", "rtl"]},
    "0b05:17ab": {"type": "sdr", "model": "RTL-SDR (ASUS)", "caps": ["rx", "rtl"]},
    "1d50:6089": {"type": "sdr", "model": "HackRF One", "caps": ["rx", "tx", "hackrf"]},
    "1d50:cc15": {"type": "sdr", "model": "HackRF Jawbreaker", "caps": ["rx", "tx", "hackrf"]},
    "1d50:6108": {"type": "sdr", "model": "LimeSDR Mini", "caps": ["rx", "tx", "lime"]},
    "1d50:6002": {"type": "bt", "model": "Ubertooth One", "caps": ["ubertooth", "passive"]},
    "0a5c:21e8": {"type": "bt", "model": "SENA UD100 / BCM20702", "caps": ["hci"]},
    "0a5c:21e6": {"type": "bt", "model": "BCM20702", "caps": ["hci"]},
    "0a12:0001": {"type": "bt", "model": "CSR Bluetooth", "caps": ["hci"]},
    "0bda:8176": {"type": "wifi", "model": "Realtek RTL8188", "caps": ["monitor"]},
    "0bda:8179": {"type": "wifi", "model": "Realtek RTL8188EU", "caps": ["monitor"]},
    "0bda:8812": {"type": "wifi", "model": "RTL8812AU", "caps": ["monitor", "inject", "dual_band"]},
    "0bda:8813": {"type": "wifi", "model": "RTL8814AU", "caps": ["monitor", "inject"]},
    "0bda:0811": {"type": "wifi", "model": "RTL8811AU", "caps": ["monitor", "inject", "dual_band"]},
    "0bda:0821": {"type": "wifi", "model": "RTL8821AU", "caps": ["monitor", "inject", "dual_band"]},
    "0bda:b812": {"type": "wifi", "model": "RTL8812BU (Panda PAU0F-class)", "caps": ["monitor", "inject", "dual_band"]},
    "0bda:b82c": {"type": "wifi", "model": "RTL8822BU", "caps": ["monitor", "inject", "dual_band"]},
    "2357:010c": {"type": "wifi", "model": "RTL8812AU (TP-Link/Alfa)", "caps": ["monitor", "inject", "dual_band"]},
    "2357:012d": {"type": "wifi", "model": "RTL8812AU", "caps": ["monitor", "inject", "dual_band"]},
    "148f:5370": {"type": "wifi", "model": "Ralink RT5370 (Panda)", "caps": ["monitor", "inject"]},
    "148f:5372": {"type": "wifi", "model": "Ralink RT5372 (Panda PAU06)", "caps": ["monitor", "inject"]},
    "148f:5572": {"type": "wifi", "model": "Ralink RT5572 (Panda)", "caps": ["monitor", "inject"]},
    "0e8d:7961": {"type": "wifi", "model": "MediaTek MT7921AU (Alfa AWUS036AXM)", "caps": ["monitor", "inject", "dual_band", "wifi6"]},
    "0e8d:7612": {"type": "wifi", "model": "MediaTek MT7612U", "caps": ["monitor", "inject", "dual_band"]},
    "0cf3:9271": {"type": "wifi", "model": "Atheros AR9271", "caps": ["monitor", "inject"]},
    "0b05:17d2": {"type": "wifi", "model": "ASUS USB-AC68", "caps": ["monitor", "inject"]},
}


def _guess_from_name(name: str) -> Dict[str, Any]:
    n = (name or "").lower()
    if any(x in n for x in ("rtl283", "sdr", "hackrf", "lime", "bladerf", "usrp")):
        caps = ["rx"]
        if "hackrf" in n or "lime" in n:
            caps.append("tx")
        if "hackrf" in n:
            caps.append("hackrf")
        if "rtl" in n:
            caps.append("rtl")
        return {"type": "sdr", "caps": caps}
    if "bluetooth" in n or "csr8510" in n or "bcm207" in n:
        return {"type": "bt", "caps": ["hci"]}
    if any(x in n for x in ("802.11", "wlan", "wireless", "wi-fi", "wifi", "802.11ac", "802.11ax")):
        return {"type": "wifi", "caps": ["monitor"]}
    return {}


def _lsusb_devices() -> List[Dict[str, Any]]:
    out = _run(["lsusb"])
    found = []
    for line in out.splitlines():
        m = re.search(r"ID\s+([0-9a-f]{4}):([0-9a-f]{4})\s*(.*)$", line, re.I)
        if not m:
            continue
        vid_pid = f"{m.group(1).lower()}:{m.group(2).lower()}"
        name = (m.group(3) or "").strip()
        meta = dict(USB_DB.get(vid_pid) or {})
        if not meta:
            meta = _guess_from_name(name)
        found.append({
            "vid_pid": vid_pid,
            "usb_name": name,
            "type": meta.get("type") or "usb",
            "model": meta.get("model") or name or vid_pid,
            "caps": list(meta.get("caps") or []),
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
            cur = {
                "type": "wifi",
                "id": m.group(1),
                "device_path": m.group(1),
                "model": m.group(1),
                "caps": [],
                "iface": m.group(1),
            }
            ifaces.append(cur)
            continue
        if cur and "type" in line.lower():
            t = line.split()[-1].lower()
            cur["mode"] = t
            if t == "monitor":
                cur["caps"] = list(set(cur.get("caps", []) + ["monitor"]))
    phy = _run(["iw", "phy"])
    phy_monitor = "monitor" in phy.lower()
    phy_inject = "inject" in phy.lower() or "{managed, AP, monitor" in phy
    for d in ifaces:
        if phy_monitor:
            d["caps"] = list(set(d.get("caps", []) + ["monitor"]))
        if phy_inject:
            d["caps"] = list(set(d.get("caps", []) + ["inject"]))
        if d.get("iface") == "wlan0":
            d["model"] = "Onboard Wi-Fi"
            d["caps"] = [c for c in d.get("caps", []) if c != "inject"]
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
    seen = set()
    uniq = []
    for d in found:
        if d["id"] in seen:
            continue
        seen.add(d["id"])
        uniq.append(d)
    return uniq


def _sdr_bins() -> Dict[str, bool]:
    import shutil
    return {
        "rtl_test": bool(shutil.which("rtl_test") or shutil.which("rtl_power")),
        "hackrf_info": bool(shutil.which("hackrf_info")),
        "SoapySDRUtil": bool(shutil.which("SoapySDRUtil")),
    }


def get_device_summary() -> Dict[str, Any]:
    usb = _lsusb_devices()
    wifi = _wifi_ifaces()
    bt = _bt_ifaces()
    sdrs = [d for d in usb if d.get("type") == "sdr"]
    bins = _sdr_bins()
    sdr_rx = bool(sdrs) or bins["rtl_test"] or bins["hackrf_info"] or bins["SoapySDRUtil"]
    sdr_tx = any("tx" in (d.get("caps") or []) for d in sdrs) or bins["hackrf_info"]
    all_devs = usb + wifi + bt
    return {
        "sdrs": sdrs,
        "wifi": wifi,
        "bt": bt,
        "usb": usb,
        "all": all_devs,
        "count": len(all_devs),
        "sdr_tools": bins,
        "caps": {
            "wifi_monitor": any("monitor" in (d.get("caps") or []) for d in wifi)
                or any(d.get("type") == "wifi" and "monitor" in (d.get("caps") or []) for d in usb)
                or any((d.get("iface") or "") not in ("", "wlan0") for d in wifi),
            "bt_hci_scan": bool(bt),
            "sdr_rx": sdr_rx,
            "sdr_tx": sdr_tx,
            "ubertooth": any("ubertooth" in (d.get("caps") or []) for d in usb),
        },
    }


if __name__ == "__main__":
    import json
    print(json.dumps(get_device_summary(), indent=2))
