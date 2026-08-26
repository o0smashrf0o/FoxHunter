#!/usr/bin/env python3
"""Device actions: Wi-Fi attacks (authz), BT pair/l2ping/Blue Sonar."""
from __future__ import annotations

import re
import subprocess
from flask import Blueprint, jsonify, request

from shared import resolve_bt_hci, resolve_wifi_iface, run_sync

device_actions_bp = Blueprint("device_actions", __name__)


def _parse_rssi(text: str):
    if not text:
        return None
    m = re.search(r"RSSI\s*(?:return\s*value)?\s*[:=]?\s*(-?\d+)", text, re.I)
    return int(m.group(1)) if m else None


def _bt_rssi_sample(mac: str, hci: str) -> dict:
    mac_u = mac.upper().replace("-", ":")
    sample = {"mac": mac_u, "hci": hci, "rssi": None, "method": None, "rtt_ms": None}
    run_sync(["sudo", "-n", "hciconfig", hci, "up"], timeout=5)
    run_sync(["sudo", "-n", "rfkill", "unblock", "bluetooth"], timeout=5)
    rc, out = run_sync(["sudo", "-n", "hcitool", "-i", hci, "rssi", mac_u], timeout=5)
    rssi = _parse_rssi(out)
    if rssi is not None:
        sample.update(rssi=rssi, method="hcitool_rssi")
        return sample
    run_sync(["sudo", "-n", "hcitool", "-i", hci, "cc", mac_u], timeout=8)
    rc, out = run_sync(["sudo", "-n", "hcitool", "-i", hci, "rssi", mac_u], timeout=5)
    rssi = _parse_rssi(out)
    if rssi is not None:
        sample.update(rssi=rssi, method="hcitool_cc+rssi")
        return sample
    rc, out = run_sync(["sudo", "-n", "l2ping", "-i", hci, "-c", "2", "-t", "2", mac_u], timeout=12)
    rtts = [float(x) for x in re.findall(r"rtt=([0-9.]+)\s*ms", out or "", re.I)]
    if rtts:
        sample.update(rtt_ms=round(sum(rtts) / len(rtts), 2), method="l2ping_rtt")
    else:
        sample["method"] = "failed"
        sample["raw"] = (out or "")[:200]
    return sample


@device_actions_bp.route("/api/device_action", methods=["POST"])
def api_device_action():
    data = request.get_json(silent=True) or {}
    mac = (data.get("mac") or "").strip()
    dev_type = (data.get("type") or "").lower()
    action = (data.get("action") or "").strip()
    source = data.get("source") or ""
    if not mac or not action:
        return jsonify({"error": "mac and action required"}), 400

    if dev_type == "wifi":
        iface = resolve_wifi_iface(source)
        if action == "info":
            return jsonify({"ok": True, "info": {"mac": mac, "iface": iface}, "source": "local"})
        if action == "deauth":
            rc, out = run_sync(
                ["sudo", "-n", "aireplay-ng", "--deauth", "5", "-a", mac, iface], timeout=15
            )
            return jsonify({"ok": rc == 0, "output": out[:2000], "rc": rc})
        if action == "probe":
            rc, out = run_sync(
                ["sudo", "-n", "timeout", "8", "airodump-ng", "--bssid", mac, iface], timeout=12
            )
            return jsonify({"ok": True, "output": out[:2000], "rc": rc})
        return jsonify({"error": f"unknown wifi action {action}"}), 400

    if dev_type == "bt":
        hci = resolve_bt_hci(source)
        is_ubertooth = "ubertooth" in (source or "").lower()
        hci_only = {"pair", "l2ping", "sdptool", "rssi_ping", "blue_sonar", "blue_sonar_stop", "blue_sonar_status"}
        if is_ubertooth and action in hci_only:
            return jsonify({"ok": False, "error": "Needs HCI adapter; Ubertooth is passive-only"}), 400

        if action == "info":
            out = subprocess.getoutput(f"sudo -n bluetoothctl info {mac} 2>/dev/null")
            return jsonify({"ok": bool(out.strip()), "info": out[:2000], "source": "bluetoothctl"})

        if action == "pair":
            rc, out = run_sync(["sudo", "-n", "bluetoothctl", "pair", mac], timeout=15)
            return jsonify({"ok": rc == 0, "output": out[:2000], "rc": rc})

        if action == "l2ping":
            rc, out = run_sync(["sudo", "-n", "l2ping", "-i", hci, "-c", "3", mac], timeout=15)
            return jsonify({"ok": rc == 0, "output": out[:2000], "rc": rc})

        if action == "sdptool":
            rc, out = run_sync(["sudo", "-n", "sdptool", "-i", hci, "browse", mac], timeout=15)
            return jsonify({"ok": rc == 0, "output": out[:3000], "rc": rc})

        if action == "rssi_ping":
            sample = _bt_rssi_sample(mac, hci)
            ok = sample.get("rssi") is not None or sample.get("rtt_ms") is not None
            return jsonify({
                "ok": ok, "sample": sample, "rssi": sample.get("rssi"),
                "rtt_ms": sample.get("rtt_ms"), "method": sample.get("method"), "hci": hci,
                "msg": "ok" if ok else "no signal",
            })

        if action == "blue_sonar":
            try:
                from utils import blue_sonar as bs
                st = bs.start(mac, hci=hci, sleep=data.get("sleep", 1.0))
            except Exception as e:
                return jsonify({"ok": False, "error": str(e)}), 500
            return jsonify({"ok": True, "msg": f"Blue Sonar tracking {mac}", "status": st, "hci": hci})

        if action == "blue_sonar_stop":
            from utils import blue_sonar as bs
            st = bs.stop()
            return jsonify({
                "ok": True, "msg": "stopped", "status": st,
                "min_rssi": st.get("min_rssi"), "max_rssi": st.get("max_rssi"),
                "samples": st.get("samples"),
            })

        if action == "blue_sonar_status":
            from utils import blue_sonar as bs
            st = bs.status()
            last = st.get("last") or {}
            rssi = last.get("rssi") if isinstance(last, dict) else st.get("rssi")
            return jsonify({
                "ok": bool(st.get("running")) or rssi is not None,
                "running": bool(st.get("running")),
                "rssi": rssi,
                "min_rssi": st.get("min_rssi"),
                "max_rssi": st.get("max_rssi"),
                "samples": st.get("samples"),
                "method": "blue_sonar",
                "hci": st.get("hci") or hci,
                "mac": st.get("mac") or mac,
                "msg": (last.get("msg") if isinstance(last, dict) else None) or ("tracking" if st.get("running") else "idle"),
                "status": st,
            })

        return jsonify({"error": f"unknown bt action {action}"}), 400

    return jsonify({"error": f"unknown type {dev_type}"}), 400
