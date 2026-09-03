#!/usr/bin/env python3
"""HUD window controls — leave fullscreen / relaunch kiosk. Dashboard stays up."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path


def _run(cmd: list, timeout: float = 8.0) -> None:
    try:
        subprocess.run(cmd, timeout=timeout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def stop_browser() -> None:
    for pat in (
        "chromium.*127.0.0.1:8080",
        "chromium-browser.*127.0.0.1:8080",
        "foxhunter-kiosk",
        "epiphany.*127.0.0.1:8080",
    ):
        _run(["pkill", "-f", pat])
    _run(["pkill", "-x", "chromium"])
    _run(["pkill", "-x", "chromium-browser"])


def start_kiosk() -> None:
    prefix = Path(os.environ.get("FOXHUNTER_PREFIX") or "/opt/foxhunter")
    script = prefix / "os" / "bin" / "start-kiosk"
    if not script.is_file():
        script = Path(__file__).resolve().parent.parent / "os" / "bin" / "start-kiosk"
    env = os.environ.copy()
    env.setdefault("DISPLAY", ":0")
    try:
        subprocess.Popen(
            ["/bin/bash", str(script)],
            env=env,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def ui_action(action: str) -> dict:
    a = (action or "").lower().strip()
    if a in ("close", "minimize", "desktop"):
        stop_browser()
        return {"ok": True, "action": a}
    if a in ("maximize", "fullscreen", "kiosk"):
        start_kiosk()
        return {"ok": True, "action": a}
    return {"ok": False, "error": "unknown action"}
