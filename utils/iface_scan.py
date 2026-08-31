#!/usr/bin/env python3
"""Live Wi-Fi / Bluetooth scans without Kismet."""
from __future__ import annotations

import re
import subprocess
import time
from typing import Any, Dict, List, Optional

from utils.oui_lookup import vendor_name


def _run(cmd: List[str], timeout: float = 20.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except FileNotFoundError:
        return -1, f"not found: {cmd[0]}"
    except Exception as e:
        return -1, str(e)


def _sudo(cmd: List[str], timeout: float = 20.0) -> tuple[int, str]:
    return _run(["sudo", "-n"] + cmd, timeout=timeout)


def iw_scan_wifi(iface: str = "wlan1", limit: int = 100) -> List[Dict[str, Any]]:
    """Active iw scan. Prefers sudo; falls back to plain iw."""
    rc, out = _sudo(["iw", "dev", iface, "scan"], timeout=25)
    if rc != 0 or not out:
        rc, out = _run(["iw", "dev", iface, "scan"], timeout=25)
    if not out or rc != 0:
        return []
    devices: List[Dict[str, Any]] = []
    cur: Dict[str, Any] = {}
    for line in out.splitlines():
        line = line.rstrip()
        m = re.match(r"^BSS\s+([0-9a-f:]{17})", line, re.I)
        if m:
            if cur.get("mac"):
                devices.append(cur)
            mac = m.group(1).upper()
            cur = {
                "mac": mac,
                "ssid": "",
                "rssi_dbm": None,
                "channel": None,
                "frequency": None,
                "encryption": "open",
                "vendor": vendor_name(mac),
                "type": "wifi",
                "active": True,
                "last_seen": time.time(),
                "seen_count": 1,
                "source": f"iw:{iface}",
            }
            continue
        if not cur:
            continue
        if "signal:" in line:
            sm = re.search(r"signal:\s*(-?\d+(?:\.\d+)?)", line)
            if sm:
                cur["rssi_dbm"] = int(float(sm.group(1)))
        elif "freq:" in line:
            fm = re.search(r"freq:\s*(\d+)", line)
            if fm:
                freq = int(fm.group(1))
                cur["frequency"] = freq
                if 2400 <= freq <= 2500:
                    cur["channel"] = max(1, min(14, (freq - 2407) // 5))
                    cur["band"] = "2.4"
                elif 5000 <= freq <= 5900:
                    cur["channel"] = (freq - 5000) // 5
                    cur["band"] = "5"
        elif "SSID:" in line:
            ssid = line.split("SSID:", 1)[-1].strip()
            cur["ssid"] = ssid
        elif "RSN:" in line or "WPA:" in line:
            cur["encryption"] = "WPA2" if "RSN" in line else "WPA"
        elif "capability:" in line and "Privacy" in line and cur.get("encryption") == "open":
            cur["encryption"] = "WEP"
    if cur.get("mac"):
        devices.append(cur)
    devices.sort(key=lambda d: d.get("rssi_dbm") if d.get("rssi_dbm") is not None else -999, reverse=True)
    return devices[:limit]


def hcitool_scan_bt(hci: str = "hci0", limit: int = 50) -> List[Dict[str, Any]]:
    """Classic inquiry + best-effort BLE via bluetoothctl."""
    _sudo(["rfkill", "unblock", "bluetooth"], timeout=5)
    _sudo(["hciconfig", hci, "up"], timeout=5)
    devices: Dict[str, Dict[str, Any]] = {}

    rc, out = _sudo(["hcitool", "-i", hci, "scan", "--flush"], timeout=18)
    for line in out.splitlines():
        m = re.search(r"([0-9A-Fa-f:]{17})\s+(.+)$", line.strip())
        if not m:
            continue
        mac = m.group(1).upper()
        name = m.group(2).strip()
        devices[mac] = {
            "mac": mac,
            "name": name,
            "rssi_dbm": None,
            "type": "classic",
            "vendor": vendor_name(mac),
            "active": True,
            "last_seen": time.time(),
            "seen_count": 1,
            "source": f"hcitool:{hci}",
        }

    # BLE scan via bluetoothctl (short)
    rc, out = _sudo(["timeout", "8", "bluetoothctl", "--timeout", "6", "scan", "on"], timeout=12)
    # also try lescan
    rc2, out2 = _sudo(["timeout", "6", "hcitool", "-i", hci, "lescan", "--duplicates"], timeout=10)
    blob = out + "\n" + out2
    for line in blob.splitlines():
        m = re.search(r"([0-9A-Fa-f:]{17})\s*(.*)$", line.strip())
        if not m:
            continue
        mac = m.group(1).upper()
        rest = (m.group(2) or "").strip()
        if mac not in devices:
            devices[mac] = {
                "mac": mac,
                "name": rest or mac,
                "rssi_dbm": None,
                "type": "ble",
                "vendor": vendor_name(mac),
                "active": True,
                "last_seen": time.time(),
                "seen_count": 1,
                "source": f"ble:{hci}",
            }
        else:
            if rest and rest != mac:
                devices[mac]["name"] = rest
        rm = re.search(r"RSSI[:\s]+(-?\d+)", line, re.I)
        if rm:
            devices[mac]["rssi_dbm"] = int(rm.group(1))

    lst = list(devices.values())
    lst.sort(key=lambda d: d.get("rssi_dbm") if d.get("rssi_dbm") is not None else -999, reverse=True)
    return lst[:limit]


def wifi_rssi_for(mac: str, iface: str = "wlan1") -> Optional[int]:
    mac_u = (mac or "").upper()
    rc, out = _sudo(["iw", "dev", iface, "scan"], timeout=20)
    if rc != 0 or not out:
        rc, out = _run(["iw", "dev", iface, "scan"], timeout=20)
    hit = False
    rssi = None
    for line in out.splitlines():
        m = re.match(r"^BSS\s+([0-9a-f:]{17})", line, re.I)
        if m:
            hit = m.group(1).upper() == mac_u
            continue
        if hit and "signal:" in line:
            sm = re.search(r"signal:\s*(-?\d+(?:\.\d+)?)", line)
            if sm:
                rssi = int(float(sm.group(1)))
                break
    return rssi


def bt_rssi_for(mac: str, hci: str = "hci0") -> Optional[int]:
    mac_u = (mac or "").upper()
    rc, out = _sudo(["hcitool", "-i", hci, "rssi", mac_u], timeout=6)
    m = re.search(r"(-?\d+)", out)
    if rc == 0 and m:
        return int(m.group(1))
    rc, out = _sudo(["l2ping", "-i", hci, "-c", "1", "-t", "2", mac_u], timeout=8)
    rm = re.search(r"(-?\d+)\s*dB", out, re.I)
    if rm:
        return int(rm.group(1))
    return None
