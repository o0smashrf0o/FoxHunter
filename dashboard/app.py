#!/usr/bin/env python3
"""Fox Hunter Flask dashboard — http://0.0.0.0:8080"""
from __future__ import annotations

import os
import sys

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(DASHBOARD_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, DASHBOARD_DIR)

from flask import Flask, jsonify, redirect, render_template, request, session

from routes.core import core_bp
from routes.devices import devices_bp
from routes.device_actions import device_actions_bp
from routes.detect import detect_bp
from routes.tools import tools_bp
from routes.kismet import kismet_bp
from routes.findings import findings_bp
from routes.hunt import hunt_bp
from routes.heatmap import heatmap_bp

app = Flask(__name__)
try:
    from utils.auth import flask_secret
    app.secret_key = flask_secret()
except Exception:
    app.secret_key = os.urandom(24)

_OPEN = ("/login", "/static/")


@app.before_request
def _hud_auth():
    try:
        from utils.auth import auth_enabled
    except Exception:
        return None
    if not auth_enabled():
        return None
    path = request.path or "/"
    if path == "/login" or path.startswith("/static/"):
        return None
    if session.get("hud_ok"):
        return None
    if request.method == "POST" and path == "/login":
        return None
    return redirect("/login")


@app.route("/login", methods=["GET", "POST"])
def login():
    from utils.auth import auth_enabled, verify_password
    if not auth_enabled():
        return redirect("/")
    err = ""
    if request.method == "POST":
        if verify_password(request.form.get("password") or ""):
            session["hud_ok"] = True
            return redirect("/")
        err = "Wrong password"
    return render_template("login.html", error=err)


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


@app.route("/api/bt_continuous_devices")
def api_bt_continuous_devices():
    from utils.bt_continuous import bt_continuous_manager
    try:
        st = bt_continuous_manager.status()
    except Exception:
        return jsonify({"ok": True, "running": False, "hci": "", "active_device_count": 0, "devices": []})
    running = bool(st.get("running"))
    rows = []
    if running:
        try:
            lock = getattr(bt_continuous_manager, "_lock", None)
            table = getattr(bt_continuous_manager, "_devices", None) or {}
            if lock is not None:
                with lock:
                    items = list(table.values())
            else:
                items = list(table.values())
            for d in items:
                rows.append({
                    "name": d.get("name") or "",
                    "mac": d.get("mac") or "",
                    "rssi_dbm": d.get("rssi_dbm"),
                    "type": d.get("type") or "",
                    "vendor": d.get("vendor") or "",
                })
            rows.sort(
                key=lambda x: x.get("rssi_dbm") if x.get("rssi_dbm") is not None else -999,
                reverse=True,
            )
        except Exception:
            rows = []
    return jsonify({
        "ok": True,
        "running": running,
        "hci": st.get("hci") or "",
        "active_device_count": len(rows) if running else 0,
        "devices": rows,
    })


app.register_blueprint(core_bp)
app.register_blueprint(devices_bp)
app.register_blueprint(device_actions_bp)
app.register_blueprint(detect_bp)
app.register_blueprint(tools_bp)
app.register_blueprint(kismet_bp)
app.register_blueprint(findings_bp)
app.register_blueprint(hunt_bp)
app.register_blueprint(heatmap_bp)
try:
    from routes.storage import storage_bp
    app.register_blueprint(storage_bp)
except Exception:
    pass


@app.errorhandler(Exception)
def _err(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    import traceback
    tb = traceback.format_exc()
    try:
        from utils.paths import LOGS_DASHBOARD, ensure_data_dirs
        ensure_data_dirs()
        (LOGS_DASHBOARD / "error.log").write_text(tb)
    except Exception:
        pass
    return "<pre style='color:#b8ff2a;background:#07060f;padding:1rem;white-space:pre-wrap'>" + tb + "</pre>", 500


if __name__ == "__main__":
    from utils.paths import ensure_data_dirs
    ensure_data_dirs()
    app.run(host="0.0.0.0", port=int(os.environ.get("FOXHUNTER_PORT", "8080")), debug=False)
