#!/usr/bin/env python3
from flask import Blueprint, jsonify, request, send_file

storage_bp = Blueprint("storage", __name__)


@storage_bp.route("/api/storage")
def api_storage():
    from utils.scan_store import disk_status, list_scans, removable_mounts
    st = disk_status()
    st["scans"] = list_scans(80)
    st["mounts"] = removable_mounts()
    return jsonify(st)


@storage_bp.route("/api/storage/delete", methods=["POST"])
def api_storage_delete():
    from utils.scan_store import delete_all_scans, delete_scan
    data = request.get_json(silent=True) or {}
    if data.get("all"):
        n = delete_all_scans()
        return jsonify({"ok": True, "deleted": n})
    path = data.get("path") or ""
    if not path:
        return jsonify({"ok": False, "error": "No path"}), 400
    try:
        ok, msg = delete_scan(path)
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": ok, "msg": msg})


@storage_bp.route("/api/storage/export")
def api_storage_export():
    from pathlib import Path
    from utils.scan_store import safe_data_path
    path = request.args.get("path") or ""
    if not path:
        return jsonify({"ok": False, "error": "No path"}), 400
    try:
        p = safe_data_path(Path(path))
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    if not p.is_file():
        return jsonify({"ok": False, "error": "not found"}), 404
    return send_file(p, as_attachment=True, download_name=p.name)


@storage_bp.route("/api/storage/copy", methods=["POST"])
def api_storage_copy():
    from utils.scan_store import copy_to
    data = request.get_json(silent=True) or {}
    dest = data.get("dest") or ""
    if not dest:
        return jsonify({"ok": False, "error": "No destination"}), 400
    try:
        ok, msg = copy_to(dest, data.get("path") or "")
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    return jsonify({"ok": ok, "msg": msg})
