"""Paths and constants for installed Fox Hunter."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

_DEFAULT_PREFIX = Path("/opt/foxhunter")
if not _DEFAULT_PREFIX.exists() and Path("/opt/smashdeck").exists():
    _DEFAULT_PREFIX = Path("/opt/smashdeck")


def canonical_install_prefix() -> Path:
    override = (os.environ.get("FOXHUNTER_INSTALL_PREFIX") or os.environ.get("SMASHDECK_INSTALL_PREFIX") or "").strip()
    if override:
        return Path(override).expanduser().resolve()
    return _DEFAULT_PREFIX


INSTALL_PREFIX = canonical_install_prefix()
STATE_DIR = Path("/var/lib/foxhunter")
INSTALL_STATE_PATH = STATE_DIR / "install.json"
PACKAGING_DIR = Path(__file__).resolve().parent
MEDIA_ROOT = PACKAGING_DIR.parent


def xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def user_data_dir() -> Path:
    return xdg_data_home() / "foxhunter"


def read_version(root: Optional[Path] = None) -> str:
    root = root or MEDIA_ROOT
    try:
        return (root / "VERSION").read_text(encoding="utf-8").strip().splitlines()[0].strip()
    except Exception:
        return "0.0.0"


def parse_version(v: str) -> tuple:
    parts = []
    for p in (v or "0").strip().split("."):
        try:
            parts.append(int("".join(c for c in p if c.isdigit()) or "0"))
        except Exception:
            parts.append(0)
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def version_cmp(a: str, b: str) -> int:
    pa, pb = parse_version(a), parse_version(b)
    return (pa > pb) - (pa < pb)


def is_installed() -> bool:
    return (INSTALL_PREFIX / "foxhunter-gui").is_file() and (INSTALL_PREFIX / "dashboard" / "app.py").is_file()


def validate_install_paths(source: Path, prefix: Optional[Path] = None) -> Tuple[Path, Path]:
    source = Path(source).resolve()
    prefix = Path(prefix or canonical_install_prefix()).resolve()
    if not (os.environ.get("FOXHUNTER_INSTALL_PREFIX") or "").strip():
        prefix = _DEFAULT_PREFIX.resolve()
    if not source.is_dir():
        raise ValueError(f"Install source is not a directory: {source}")
    if not (source / "dashboard" / "app.py").is_file() and not (source / "foxhunter-gui").is_file():
        raise ValueError(f"Not a Fox Hunter tree: {source}")
    if prefix == source and prefix != _DEFAULT_PREFIX.resolve():
        raise ValueError(f"Refusing in-place install into media {source}")
    return source, prefix


def load_install_state() -> Optional[Dict[str, Any]]:
    if INSTALL_STATE_PATH.is_file():
        try:
            return json.loads(INSTALL_STATE_PATH.read_text())
        except Exception:
            pass
    if is_installed():
        return {"version": read_version(INSTALL_PREFIX), "prefix": str(INSTALL_PREFIX)}
    return None
