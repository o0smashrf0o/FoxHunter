#!/usr/bin/env python3
from flask import Blueprint, jsonify, request

detect_bp = Blueprint("detect", __name__)


@detect_bp.route("/api/detect/capabilities")
def caps():
    from utils.capability_gate import list_tools, live_capabilities
    tools = [t for t in list_tools() if t.get("kind") == "detect" or (t.get("meta") or {}).get("kind") == "detect"]
    # include all gated tools for UI
    if not tools:
        tools = list_tools()
    return jsonify({"tools": tools, "capabilities": live_capabilities()})


@detect_bp.route("/api/detect/run", methods=["POST"])
def run():
    data = request.get_json(silent=True) or {}
    tool_id = data.get("tool_id") or data.get("tool") or ""
    if not tool_id:
        return jsonify({"ok": False, "error": "tool_id required"}), 400
    from utils.capability_gate import check_tool
    gate = check_tool(tool_id)
    if not gate.get("ok"):
        return jsonify({"ok": False, "gate": gate, "error": gate.get("message"), "hits": [], "count": 0}), 409
    from utils.detectors import run_detector
    result = run_detector(tool_id)
    try:
        from utils import findings
        if result.get("hits"):
            findings.create_finding(
                tool_id,
                {"summary": result.get("msg"), "hits": result.get("hits", [])[:20], "severity": "info"},
                target=tool_id,
            )
    except Exception:
        pass
    return jsonify(result)


@detect_bp.route("/api/oui/lookup")
def oui_lookup():
    mac = request.args.get("mac", "")
    from utils.oui_lookup import lookup_vendor
    hit = lookup_vendor(mac)
    return jsonify({"ok": True, "mac": mac, "found": bool(hit), "vendor": hit})
