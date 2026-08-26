#!/usr/bin/env python3
from flask import Blueprint, jsonify, request

findings_bp = Blueprint("findings", __name__)


@findings_bp.route("/findings")
@findings_bp.route("/api/findings")
def list_f():
    from utils import findings
    return jsonify({"findings": findings.list_findings(int(request.args.get("limit") or 50))})


@findings_bp.route("/export_findings")
def export_f():
    from utils import findings
    fmt = request.args.get("fmt") or "md"
    return findings.export_findings(fmt, 100), 200, {
        "Content-Type": "text/markdown" if fmt == "md" else "application/json"
    }
