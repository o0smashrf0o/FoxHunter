#!/usr/bin/env python3
"""MAC → vendor lookup using local OUI data (config/data)."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, Optional

from utils.paths import PROJECT_ROOT

OUI_DB = PROJECT_ROOT / "config" / "data" / "oui.sqlite"
_MANUF = PROJECT_ROOT / "config" / "data" / "manuf"
_conn: Optional[sqlite3.Connection] = None
_mem: Dict[str, str] = {}


def load_db() -> bool:
    global _conn, _mem
    if OUI_DB.is_file():
        try:
            _conn = sqlite3.connect(f"file:{OUI_DB}?mode=ro", uri=True, check_same_thread=False)
            return True
        except Exception:
            _conn = None
    if _MANUF.is_file() and not _mem:
        try:
            for line in _MANUF.read_text(errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split(None, 1)
                if len(parts) >= 2:
                    prefix = parts[0].replace(":", "").replace("-", "").upper()[:6]
                    _mem[prefix] = parts[1].strip()
        except Exception:
            pass
    return bool(_mem)


def lookup_vendor(mac: str) -> Optional[Dict[str, Any]]:
    if not mac:
        return None
    clean = mac.upper().replace("-", ":").replace(".", ":")
    hex6 = clean.replace(":", "")[:6]
    if _conn is None and not _mem:
        load_db()
    if _conn is not None:
        try:
            cur = _conn.execute(
                "SELECT short, long FROM oui WHERE prefix = ? LIMIT 1", (hex6,)
            )
            row = cur.fetchone()
            if row:
                return {"short": row[0] or row[1], "long": row[1] or row[0], "prefix": hex6}
        except Exception:
            # try simpler schema
            try:
                cur = _conn.execute(
                    "SELECT vendor FROM oui WHERE prefix = ? LIMIT 1", (hex6,)
                )
                row = cur.fetchone()
                if row:
                    return {"short": row[0], "long": row[0], "prefix": hex6}
            except Exception:
                pass
    if hex6 in _mem:
        return {"short": _mem[hex6], "long": _mem[hex6], "prefix": hex6}
    return None


def vendor_name(mac: str) -> str:
    hit = lookup_vendor(mac)
    if not hit:
        return "Unknown"
    return hit.get("short") or hit.get("long") or "Unknown"
