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

from flask import Flask

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
