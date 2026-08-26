#!/usr/bin/env python3
from flask import Blueprint, jsonify, request

tools_bp = Blueprint("tools", __name__)


@tools_bp.route("/api/tools")
def list_tools_api():
    from utils.tool_wrappers import TOOL_REGISTRY
    return jsonify({"tools": list(TOOL_REGISTRY.keys())})


@tools_bp.route("/launch_tool", methods=["POST"])
def launch_tool():
    data = request.get_json(silent=True) or {}
    name = data.get("tool") or "nmap"
    opts = data.get("options") or {}
    target = data.get("target")
    if target and "target" not in opts:
        opts["target"] = target
    try:
        from utils.tool_wrappers import get_tool
        tool = get_tool(name, **opts)
        key = tool.launch(target=target)
        if key:
            return jsonify({"tool": name, "key": key, "status": "launched"})
        res = tool.run(timeout=60)
        try:
            from utils.findings import insert_from_tool_result
            fid = insert_from_tool_result(name, res, target=target or "")
            return jsonify({"tool": name, "status": "ran_sync", "finding_id": fid, "parsed": res.get("parsed")})
        except Exception:
            return jsonify({"tool": name, "status": "ran_sync", "result": res})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
