#!/usr/bin/env python3
from flask import Blueprint, jsonify, request, send_file

heatmap_bp = Blueprint("heatmap", __name__)


@heatmap_bp.route("/api/heatmap/maps")
def api_maps():
    from utils import heatmap
    return jsonify({"maps": heatmap.list_maps()})


@heatmap_bp.route("/api/heatmap/maps", methods=["POST"])
def api_map_upload():
    f = request.files.get("map") or request.files.get("file")
    if not f:
        return jsonify({"ok": False, "error": "no file"}), 400
    data = f.read()
    if len(data) > 8 * 1024 * 1024:
        return jsonify({"ok": False, "error": "file too large (8MB)"}), 400
    mime = f.mimetype or "image/png"
    from utils import heatmap
    rec = heatmap.save_map(request.form.get("name") or f.filename or "map", data, mime)
    return jsonify({"ok": True, "map": rec})


@heatmap_bp.route("/api/heatmap/maps/<map_id>/image")
def api_map_image(map_id):
    from utils import heatmap
    p = heatmap.map_file(map_id)
    if not p:
        return jsonify({"error": "not found"}), 404
    return send_file(p)


@heatmap_bp.route("/api/heatmap/marks")
def api_marks():
    from utils import heatmap
    return jsonify({
        "marks": heatmap.list_marks(request.args.get("map_id") or "", request.args.get("mac") or "")
    })


@heatmap_bp.route("/api/heatmap/mark", methods=["POST"])
def api_mark():
    data = request.get_json(silent=True) or {}
    from utils import heatmap, hunt
    rssi = data.get("rssi")
    if rssi is None:
        rssi = hunt.last_rssi()
    rec = heatmap.add_mark(
        map_id=data.get("map_id") or "",
        x=float(data.get("x") or 0),
        y=float(data.get("y") or 0),
        rssi=rssi,
        mac=data.get("mac") or "",
        note=data.get("note") or "",
    )
    return jsonify({"ok": True, "mark": rec})


@heatmap_bp.route("/api/heatmap/marks/clear", methods=["POST"])
def api_marks_clear():
    data = request.get_json(silent=True) or {}
    from utils import heatmap
    n = heatmap.clear_marks(data.get("map_id") or "", data.get("mac") or "")
    return jsonify({"ok": True, "deleted": n})
