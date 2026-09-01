#!/usr/bin/env python3
"""Optional HUD password. No file = no password."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
from typing import Optional

from utils.paths import DATA_DIR, ensure_data_dirs

AUTH_FILE = DATA_DIR / "auth.json"
ITERS = 120000


def auth_enabled() -> bool:
    return AUTH_FILE.is_file()


def set_password(password: str) -> None:
    if not password:
        clear_password()
        return
    ensure_data_dirs()
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERS)
    AUTH_FILE.write_text(json.dumps({
        "salt": salt.hex(),
        "hash": digest.hex(),
        "iters": ITERS,
    }))
    try:
        os.chmod(AUTH_FILE, 0o600)
    except Exception:
        pass


def clear_password() -> None:
    try:
        AUTH_FILE.unlink()
    except Exception:
        pass


def verify_password(password: str) -> bool:
    if not auth_enabled():
        return True
    try:
        data = json.loads(AUTH_FILE.read_text())
        salt = bytes.fromhex(data["salt"])
        iters = int(data.get("iters") or ITERS)
        digest = hashlib.pbkdf2_hmac("sha256", (password or "").encode("utf-8"), salt, iters)
        return secrets.compare_digest(digest.hex(), data["hash"])
    except Exception:
        return False


def flask_secret() -> str:
    ensure_data_dirs()
    p = DATA_DIR / "flask_secret"
    if p.is_file():
        return p.read_text().strip()
    val = secrets.token_hex(32)
    p.write_text(val)
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
    return val
