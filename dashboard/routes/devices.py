#!/usr/bin/env python3
from flask import Blueprint, jsonify, request

from shared import DEVICE_CACHE, merge_devices, resolve_bt_hci, resolve_wifi_iface

devices_bp = Blueprint("devices", __name__)


@devices_bp.route("/api/devices")
def api_devices():
    kind = request.args.get("type", "all")
    out = {}
    if kind in ("all", "wifi"):
        out["wifi"] = list(DEVICE_CACHE.get("wifi", {}).values())
    if kind in ("all", "bt"):
        out["bt"] = list(DEVICE_CACHE.get("bt", {}).values())
    return jsonify(out)


@devices_bp.route("/api/scan", methods=["POST"])
def api_scan():
    data = request.get_json(silent=True) or {}
    scan_type = (data.get("type") or data.get("scan_type") or "wifi").lower()
    source = data.get("source") or ""

    if scan_type in ("wifi", "wlan"):
        iface = resolve_wifi_iface(source)
        try:
            from utils.wifi_link import iface_status
            from utils.iface_scan import iw_scan_wifi_result
            st = iface_status(iface)
            if data.get("release"):
                from utils.wifi_link import release_iface
                ok, msg = release_iface(iface)
                if not ok:
                    return jsonify({"ok": False, "error": msg, "needs_release": True, "iface": iface, "link": st, "devices": []})
                st = iface_status(iface)
            elif st.get("connected") and not data.get("force"):
                return jsonify({
                    "ok": False,
                    "needs_release": True,
                    "error": f"{iface} is connected" + (f' to "{st.get("ssid")}"' if st.get("ssid") else "") + " — disconnecting will drop this deck off that AP.",
                    "iface": iface,
                    "link": st,
                    "devices": [],
                })
            fresh, err = iw_scan_wifi_result(iface, int(data.get("limit") or 100))
        except Exception as e:
            return jsonify({"ok": False, "error": str(e), "devices": []}), 500
        if err and not fresh:
            return jsonify({"ok": False, "error": err, "iface": iface, "devices": []})
        devices = merge_devices("wifi", fresh)
        try:
            from utils.scan_store import save_snapshot
            save_snapshot("wifi", fresh, {"iface": iface, "mode": "scan"}, force=True)
        except Exception:
            pass
        return jsonify({"ok": True, "type": "wifi", "iface": iface, "devices": devices, "count": len(fresh)})

    if scan_type in ("bt", "bluetooth", "ble"):
        hci = resolve_bt_hci(source)
        try:
            from utils.iface_scan import hcitool_scan_bt
            fresh = hcitool_scan_bt(hci, int(data.get("limit") or 50))
        except Exception as e:
            return jsonify({"ok": False, "error": str(e), "devices": []}), 500
        devices = merge_devices("bt", fresh)
        try:
            from utils.scan_store import save_snapshot
            save_snapshot("bt", fresh, {"hci": hci, "mode": "scan"}, force=True)
        except Exception:
            pass
        return jsonify({"ok": True, "type": "bt", "hci": hci, "devices": devices, "count": len(fresh)})

    return jsonify({"error": f"unknown scan type {scan_type}"}), 400


@devices_bp.route("/api/clear_devices", methods=["POST"])
def api_clear():
    data = request.get_json(silent=True) or {}
    kind = data.get("type") or "all"
    if kind in ("all", "wifi"):
        DEVICE_CACHE["wifi"] = {}
    if kind in ("all", "bt"):
        DEVICE_CACHE["bt"] = {}
    return jsonify({"ok": True})


@devices_bp.route("/api/wifi_release", methods=["POST"])
def api_wifi_release():
    data = request.get_json(silent=True) or {}
    iface = (data.get("iface") or data.get("source") or "").strip()
    if not iface:
        return jsonify({"ok": False, "error": "No interface"}), 400
    from utils.wifi_link import release_iface, iface_status
    ok, msg = release_iface(iface)
    return jsonify({"ok": ok, "msg": msg, "link": iface_status(iface)})


@devices_bp.route("/api/sources")
def api_sources():
    from shared import load_source_settings
    try:
        from utils.device_detector import get_device_summary
        summary = get_device_summary()
    except Exception as e:
        summary = {"error": str(e)}
    return jsonify({"settings": load_source_settings(), "detected": summary})
