#!/usr/bin/env python3
"""Central paths for Fox Hunter runtime data and project root."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _resolve_data_dir() -> Path:
    env = (os.environ.get("FOXHUNTER_DATA") or os.environ.get("SMASHDECK_DATA") or "").strip()
    if env:
        return Path(env).expanduser().resolve()
    try:
        root = PROJECT_ROOT.resolve()
        if root in (Path("/opt/foxhunter").resolve(), Path("/opt/smashdeck").resolve()):
            xdg = os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share"))
            fh = Path(xdg) / "foxhunter"
            old = Path(xdg) / "smashdeck"
            return fh if fh.exists() or not old.exists() else old
    except Exception:
        pass
    return PROJECT_ROOT / "data"


DATA_DIR = _resolve_data_dir()
KISMET_DIR = DATA_DIR / "kismet"
PCAP_DIR = DATA_DIR / "pcap"
WIFI_SCAN_DIR = DATA_DIR / "wifi_scan"
BT_SCAN_DIR = DATA_DIR / "bt_scan"
EXPORTS_DIR = DATA_DIR / "exports"
FINDINGS_DIR = DATA_DIR / "findings"
LOGS_DIR = DATA_DIR / "logs"
LOGS_TOOLS = LOGS_DIR / "tools"
BT_CONTINUOUS_DIR = LOGS_DIR / "bt_continuous"
LOGS_DASHBOARD = LOGS_DIR / "dashboard"
LOGS_BOOTSTRAP = LOGS_DIR / "bootstrap"
PIDS_DIR = DATA_DIR / "pids"
CREDS_DIR = DATA_DIR / "creds"
SPECTRUM_DIR = DATA_DIR / "spectrum"
MAPS_DIR = DATA_DIR / "maps"
HUNT_DIR = DATA_DIR / "hunt"
FINDINGS_DB = FINDINGS_DIR / "findings.db"
SOI_DB = FINDINGS_DIR / "soi.db"
HEATMAP_DB = DATA_DIR / "maps" / "heatmap.db"
DASHBOARD_LOG = LOGS_DASHBOARD / "dashboard.log"

ALL_DIRS = (
    KISMET_DIR, PCAP_DIR, WIFI_SCAN_DIR, BT_SCAN_DIR, EXPORTS_DIR,
    FINDINGS_DIR, LOGS_TOOLS, BT_CONTINUOUS_DIR, LOGS_DASHBOARD, LOGS_BOOTSTRAP,
    PIDS_DIR, CREDS_DIR, SPECTRUM_DIR, MAPS_DIR, HUNT_DIR,
)


def ensure_data_dirs() -> Path:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    for d in ALL_DIRS:
        d.mkdir(parents=True, exist_ok=True)
    return DATA_DIR


def tool_log_path(name: str, ts: Optional[int] = None) -> Path:
    import time
    stamp = int(ts if ts is not None else time.time())
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in name)
    ensure_data_dirs()
    return LOGS_TOOLS / f"{safe}_{stamp}.log"
