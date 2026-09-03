#!/usr/bin/env python3
"""Ensure portable Fox Hunter.desktop + foxhunter-media-start are valid."""
from __future__ import annotations

import os
import stat
from pathlib import Path

PORTABLE_DESKTOP = """[Desktop Entry]
Version=1.0
Type=Application
Name={name}
GenericName=RF & Wireless Analysis
Comment={comment}
Exec=./foxhunter-media-start
TryExec=./foxhunter-media-start
Terminal=false
Categories=Network;
Keywords=SDR;Pentest;Kismet;WiFi;Bluetooth;RF;Fox Hunter;
StartupNotify=true
Icon=network-wireless
"""

MEDIA_START = r"""#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$(readlink -f "$0" 2>/dev/null || realpath "$0" 2>/dev/null || echo "$0")")" && pwd)"
cd "$ROOT" || exit 1
export FOXHUNTER_MEDIA_ROOT="$ROOT"
PY="${FOXHUNTER_PYTHON:-}"
if [[ -z "$PY" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then PY="$ROOT/.venv/bin/python"
  else PY="$(command -v python3 || true)"; fi
fi
if [[ -z "$PY" || ! -x "$PY" ]]; then
  echo "Fox Hunter: python3 not found." >&2; exit 1
fi
exec "$PY" "$ROOT/foxhunter-gui" "$@"
"""


def _chmod_exec(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def heal_media_launchers(media_root: Path | None = None) -> dict:
    root = Path(media_root or Path(__file__).resolve().parent.parent).resolve()
    fixed: list[str] = []
    start = root / "foxhunter-media-start"
    try:
        need = (not start.is_file()) or ("foxhunter-gui" not in start.read_text(encoding="utf-8", errors="replace"))
        if need:
            start.write_text(MEDIA_START, encoding="utf-8")
            fixed.append(str(start))
        _chmod_exec(start)
    except Exception as e:
        return {"ok": False, "error": str(e)}

    for fname, name, comment in (
        ("FoxHunter.desktop", "Fox Hunter", "Double-click to install or open Fox Hunter"),
        ("foxhunter.desktop", "Fox Hunter", "Install or open Fox Hunter"),
    ):
        path = root / fname
        content = PORTABLE_DESKTOP.format(name=name, comment=comment)
        try:
            old = path.read_text(encoding="utf-8", errors="replace") if path.is_file() else ""
            broken = (
                not path.is_file()
                or "./foxhunter-media-start" not in old
                or not old.lstrip().startswith("[")
            )
            if broken:
                path.write_text(content, encoding="utf-8")
                fixed.append(str(path))
            _chmod_exec(path)
        except Exception as e:
            return {"ok": False, "error": str(e), "fixed": fixed}

    gui = root / "foxhunter-gui"
    if gui.is_file():
        try:
            _chmod_exec(gui)
        except Exception:
            pass
    return {"ok": True, "root": str(root), "fixed": fixed}
