#!/usr/bin/env python3
"""SmashDeck Flask dashboard — http://0.0.0.0:8080"""
from __future__ import annotations

import os
import sys

DASHBOARD_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(DASHBOARD_DIR)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
if DASHBOARD_DIR not in sys.path:
    sys.path.insert(0, DASHBOARD_DIR)

from flask import Flask, redirect, render_template, request, session

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
    from utils.auth import auth_enabled
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


app.register_blueprint(core_bp)
app.register_blueprint(devices_bp)
app.register_blueprint(device_actions_bp)
app.register_blueprint(detect_bp)
app.register_blueprint(tools_bp)
app.register_blueprint(kismet_bp)
app.register_blueprint(findings_bp)
app.register_blueprint(hunt_bp)
app.register_blueprint(heatmap_bp)


if __name__ == "__main__":
    from utils.paths import ensure_data_dirs
    ensure_data_dirs()
    app.run(host="0.0.0.0", port=int(os.environ.get("SMASHDECK_PORT", "8080")), debug=False)
