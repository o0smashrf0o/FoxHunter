#!/usr/bin/env python3
"""SQLite findings store for SmashDeck."""
from __future__ import annotations

import json
import sqlite3
import time
from typing import Any, Dict, List, Optional

from utils.paths import FINDINGS_DB, ensure_data_dirs

ensure_data_dirs()


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(str(FINDINGS_DB))
    c.row_factory = sqlite3.Row
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS findings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL NOT NULL,
            tool TEXT,
            target TEXT,
            severity TEXT,
            summary TEXT,
            data_json TEXT
        )
        """
    )
    c.commit()
    return c


def create_finding(
    tool: str,
    payload: Dict[str, Any],
    target: str = "",
    severity: Optional[str] = None,
) -> int:
    sev = severity or payload.get("severity") or "info"
    summary = payload.get("summary") or payload.get("msg") or str(payload)[:200]
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO findings (ts, tool, target, severity, summary, data_json) VALUES (?,?,?,?,?,?)",
            (time.time(), tool, target, sev, summary, json.dumps(payload)),
        )
        c.commit()
        return int(cur.lastrowid)


def insert_from_tool_result(tool: str, result: Dict[str, Any], target: str = "") -> int:
    parsed = result.get("parsed") or {}
    payload = {
        "summary": parsed.get("summary") or f"{tool} finished rc={result.get('rc')}",
        "severity": "info",
        "parsed": parsed,
        "success": result.get("success"),
        "log_path": result.get("log_path"),
    }
    return create_finding(tool, payload, target=target or "")


def list_findings(limit: int = 50) -> List[Dict[str, Any]]:
    with _conn() as c:
        rows = c.execute(
            "SELECT * FROM findings ORDER BY id DESC LIMIT ?", (int(limit),)
        ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["data"] = json.loads(d.pop("data_json") or "{}")
        except Exception:
            d["data"] = {}
        out.append(d)
    return out


def get_finding(fid: int) -> Optional[Dict[str, Any]]:
    with _conn() as c:
        row = c.execute("SELECT * FROM findings WHERE id=?", (fid,)).fetchone()
    if not row:
        return None
    d = dict(row)
    try:
        d["data"] = json.loads(d.pop("data_json") or "{}")
    except Exception:
        d["data"] = {}
    return d


def export_findings(fmt: str = "md", limit: int = 50) -> str:
    items = list_findings(limit)
    if fmt == "json":
        return json.dumps(items, indent=2, default=str)
    lines = ["# SmashDeck Findings", ""]
    for f in items:
        lines.append(f"## #{f['id']} {f.get('tool')} — {f.get('severity')}")
        lines.append(f"- target: {f.get('target')}")
        lines.append(f"- summary: {f.get('summary')}")
        lines.append("")
    return "\n".join(lines)
