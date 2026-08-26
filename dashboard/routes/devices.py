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
            from utils.iface_scan import iw_scan_wifi
            fresh = iw_scan_wifi(iface, int(data.get("limit") or 100))
        except Exception as e:
            return jsonify({"ok": False, "error": str(e), "devices": []}), 500
        devices = merge_devices("wifi", fresh)
        return jsonify({"ok": True, "type": "wifi", "iface": iface, "devices": devices, "count": len(fresh)})

    if scan_type in ("bt", "bluetooth", "ble"):
        hci = resolve_bt_hci(source)
        try:
            from utils.iface_scan import hcitool_scan_bt
            fresh = hcitool_scan_bt(hci, int(data.get("limit") or 50))
        except Exception as e:
            return jsonify({"ok": False, "error": str(e), "devices": []}), 500
        devices = merge_devices("bt", fresh)
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


@devices_bp.route("/api/sources")
def api_sources():
    from shared import load_source_settings
    try:
        from utils.device_detector import get_device_summary
        summary = get_device_summary()
    except Exception as e:
        summary = {"error": str(e)}
    return jsonify({"settings": load_source_settings(), "detected": summary})
