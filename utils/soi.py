#!/usr/bin/env python3
"""Signals of Interest — mark scan/finding targets for Hunt / Heatmap."""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from utils.paths import SOI_DB, ensure_data_dirs

ensure_data_dirs()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(SOI_DB))
    c.row_factory = sqlite3.Row
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS soi (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            mac TEXT NOT NULL,
            kind TEXT,
            name TEXT,
            note TEXT,
            active INTEGER NOT NULL DEFAULT 1,
            extra_json TEXT
        )
        """
    )
    c.execute("CREATE UNIQUE INDEX IF NOT EXISTS soi_mac ON soi(mac)")
    c.commit()
    return c


def upsert_soi(mac: str, kind: str = "wifi", name: str = "", note: str = "", extra: Optional[dict] = None, active: int = 1) -> Dict[str, Any]:
    mac_u = (mac or "").upper().strip()
    if not mac_u:
        raise ValueError("mac required")
    now = time.time()
    extra_s = json.dumps(extra or {})
    with _conn() as c:
        c.execute(
            """
            INSERT INTO soi (ts, mac, kind, name, note, active, extra_json)
            VALUES (?,?,?,?,?,?,?)
            ON CONFLICT(mac) DO UPDATE SET
              ts=excluded.ts, kind=excluded.kind, name=excluded.name,
              note=excluded.note, active=excluded.active, extra_json=excluded.extra_json
            """,
            (now, mac_u, kind, name, note, int(active), extra_s),
        )
        c.commit()
        row = c.execute("SELECT * FROM soi WHERE mac=?", (mac_u,)).fetchone()
    return _row(row)


def set_active(mac: str, active: int) -> Optional[Dict[str, Any]]:
    mac_u = (mac or "").upper()
    with _conn() as c:
        c.execute("UPDATE soi SET active=? WHERE mac=?", (int(active), mac_u))
        c.commit()
        row = c.execute("SELECT * FROM soi WHERE mac=?", (mac_u,)).fetchone()
    return _row(row) if row else None


def list_soi(active_only: bool = False) -> List[Dict[str, Any]]:
    q = "SELECT * FROM soi"
    if active_only:
        q += " WHERE active=1"
    q += " ORDER BY ts DESC"
    with _conn() as c:
        rows = c.execute(q).fetchall()
    return [_row(r) for r in rows]


def get_soi(mac: str) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM soi WHERE mac=?", ((mac or "").upper(),)).fetchone()
    return _row(row) if row else None


def _row(r) -> Dict[str, Any]:
    d = dict(r)
    try:
        d["extra"] = json.loads(d.pop("extra_json") or "{}")
    except Exception:
        d["extra"] = {}
    return d
