#!/usr/bin/env python3
from flask import Blueprint, jsonify, request

kismet_bp = Blueprint("kismet", __name__)


@kismet_bp.route("/api/kismet_status")
def status():
    from utils.kismet.client import get_client
    c = get_client()
    return jsonify(c.system_status())


@kismet_bp.route("/api/kismet_start", methods=["POST"])
def start():
    data = request.get_json(silent=True) or {}
    src = data.get("source") or ""
    from utils.kismet.client import ensure_kismet
    ok, msg = ensure_kismet(src)
    return jsonify({"ok": ok, "msg": msg})


@kismet_bp.route("/api/kismet_devices_live")
def devices_live():
    from utils.kismet.client import get_client, source_def
    from shared import merge_devices
    c = get_client()
    src = source_def(request.args.get("source") or "")
    iface = src.split(":")[0] if src else ""
    if src and c.is_port_open():
        c.ensure_source(src)
    devs = c.list_devices(int(request.args.get("limit") or 150))
    wifi = [d for d in devs if d.get("type") == "wifi" or d.get("ssid")]
    bt = [d for d in devs if d.get("type") == "bt" or "bt" in str(d.get("type"))]
    if wifi:
        merge_devices("wifi", wifi)
        try:
            from utils.scan_store import save_snapshot
            save_snapshot("wifi", wifi, {"iface": iface, "mode": "kismet"}, force=False)
        except Exception:
            pass
    if bt:
        merge_devices("bt", bt)
        try:
            from utils.scan_store import save_snapshot
            save_snapshot("bt", bt, {"mode": "kismet"}, force=False)
        except Exception:
            pass
    return jsonify({"ok": True, "devices": devs, "count": len(devs), "sources": c.list_sources(), "iface": iface})


@kismet_bp.route("/api/kismet_stop", methods=["POST"])
def stop():
    from utils.kismet.client import stop_kismet
    ok, msg = stop_kismet()
    return jsonify({"ok": ok, "msg": msg})
