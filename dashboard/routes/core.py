#!/usr/bin/env python3
from flask import Blueprint, jsonify, render_template, request

from shared import system_stats

core_bp = Blueprint("core", __name__)


@core_bp.route("/")
def index():
    return render_template("dashboard.html")


@core_bp.route("/api/system_stats")
def api_stats():
    return jsonify(system_stats())


@core_bp.route("/api/checks")
def api_checks():
    try:
        from utils.hardware_checks import run_all_checks
        return jsonify(run_all_checks())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@core_bp.route("/status")
def status():
    return jsonify({"app": "SmashDeck", "ok": True})


@core_bp.route("/api/version")
def version():
    from utils.paths import PROJECT_ROOT
    try:
        v = (PROJECT_ROOT / "VERSION").read_text().strip()
    except Exception:
        v = "0.0.0"
    return jsonify({"version": v, "name": "SmashDeck"})
