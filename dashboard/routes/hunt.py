#!/usr/bin/env python3
from flask import Blueprint, jsonify, request

hunt_bp = Blueprint("hunt", __name__)


@hunt_bp.route("/api/soi", methods=["GET"])
def api_soi_list():
    from utils import soi
    return jsonify({"soi": soi.list_soi(active_only=request.args.get("active") == "1")})


@hunt_bp.route("/api/soi", methods=["POST"])
def api_soi_upsert():
    data = request.get_json(silent=True) or {}
    from utils import soi
    try:
        rec = soi.upsert_soi(
            mac=data.get("mac") or "",
            kind=data.get("kind") or "wifi",
            name=data.get("name") or "",
            note=data.get("note") or "",
            extra=data.get("extra") or {},
            active=int(data.get("active") if data.get("active") is not None else 1),
        )
        return jsonify({"ok": True, "soi": rec})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 400


@hunt_bp.route("/api/soi/clear", methods=["POST"])
def api_soi_clear():
    data = request.get_json(silent=True) or {}
    from utils import soi
    rec = soi.set_active(data.get("mac") or "", int(data.get("active") or 0))
    return jsonify({"ok": bool(rec), "soi": rec})


@hunt_bp.route("/api/hunt/start", methods=["POST"])
def api_hunt_start():
    data = request.get_json(silent=True) or {}
    from utils import hunt
    return jsonify(hunt.start(data.get("mac") or "", data.get("kind") or "wifi", data.get("source") or ""))


@hunt_bp.route("/api/hunt/stop", methods=["POST"])
def api_hunt_stop():
    from utils import hunt
    return jsonify(hunt.stop())


@hunt_bp.route("/api/hunt/status")
def api_hunt_status():
    from utils import hunt
    return jsonify(hunt.status())


@hunt_bp.route("/api/hunt/sample", methods=["POST"])
def api_hunt_sample():
    from utils import hunt
    return jsonify(hunt.sample())
