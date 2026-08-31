#!/usr/bin/env python3
"""Walk-trace heatmap on an imported floorplan / area map."""
from __future__ import annotations

import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.paths import HEATMAP_DB, MAPS_DIR, ensure_data_dirs

ensure_data_dirs()
MAPS_DIR.mkdir(parents=True, exist_ok=True)


def _conn() -> sqlite3.Connection:
    MAPS_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(HEATMAP_DB))
    c.row_factory = sqlite3.Row
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS maps (
            id TEXT PRIMARY KEY,
            ts REAL NOT NULL,
            name TEXT,
            filename TEXT,
            mime TEXT
        )
        """
    )
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            map_id TEXT NOT NULL,
            mac TEXT,
            x REAL NOT NULL,
            y REAL NOT NULL,
            rssi INTEGER,
            note TEXT
        )
        """
    )
    c.commit()
    return c


def save_map(name: str, data: bytes, mime: str = "image/png") -> Dict[str, Any]:
    mid = uuid.uuid4().hex[:12]
    ext = ".jpg" if "jpeg" in mime or "jpg" in mime else ".png"
    fname = f"{mid}{ext}"
    path = MAPS_DIR / fname
    path.write_bytes(data)
    with _conn() as c:
        c.execute(
            "INSERT INTO maps (id, ts, name, filename, mime) VALUES (?,?,?,?,?)",
            (mid, time.time(), name or fname, fname, mime),
        )
        c.commit()
    return get_map(mid) or {"id": mid, "filename": fname}


def list_maps() -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute("SELECT * FROM maps ORDER BY ts DESC").fetchall()
    return [dict(r) for r in rows]


def get_map(map_id: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM maps WHERE id=?", (map_id,)).fetchone()
    if not row:
        return None
    d = dict(row)
    d["path"] = str(MAPS_DIR / d["filename"])
    return d


def map_file(map_id: str) -> Optional[Path]:
    m = get_map(map_id)
    if not m:
        return None
    p = MAPS_DIR / m["filename"]
    return p if p.is_file() else None


def add_mark(map_id: str, x: float, y: float, rssi: Optional[int] = None, mac: str = "", note: str = "") -> Dict[str, Any]:
    x = max(0.0, min(1.0, float(x)))
    y = max(0.0, min(1.0, float(y)))
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO marks (ts, map_id, mac, x, y, rssi, note) VALUES (?,?,?,?,?,?,?)",
            (time.time(), map_id, (mac or "").upper(), x, y, rssi, note),
        )
        c.commit()
        rid = int(cur.lastrowid)
        row = c.execute("SELECT * FROM marks WHERE id=?", (rid,)).fetchone()
    return dict(row)


def list_marks(map_id: str, mac: str = "") -> List[Dict[str, Any]]:
    with _conn() as c:
        if mac:
            rows = c.execute(
                "SELECT * FROM marks WHERE map_id=? AND mac=? ORDER BY ts",
                (map_id, mac.upper()),
            ).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM marks WHERE map_id=? ORDER BY ts", (map_id,)
            ).fetchall()
    return [dict(r) for r in rows]


def clear_marks(map_id: str, mac: str = "") -> int:
    with _conn() as c:
        if mac:
            cur = c.execute("DELETE FROM marks WHERE map_id=? AND mac=?", (map_id, mac.upper()))
        else:
            cur = c.execute("DELETE FROM marks WHERE map_id=?", (map_id,))
        c.commit()
        return cur.rowcount
