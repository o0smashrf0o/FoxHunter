"""Run privileged_setup.py via pkexec or sudo -A."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import List


def run_privileged(source_root: Path, args: List[str]) -> int:
    setup = source_root / "packaging" / "privileged_setup.py"
    if not setup.is_file():
        setup = Path("/opt/foxhunter/packaging/privileged_setup.py")
    if not setup.is_file():
        print("privileged_setup.py missing", file=sys.stderr)
        return 1
    py = sys.executable
    cmd_base = [py, str(setup), *args]
    # Prefer pkexec
    if subprocess.call(["which", "pkexec"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return subprocess.call(["pkexec", *cmd_base])
    # sudo with askpass if available
    askpass = source_root / "packaging" / "askpass-zenity.sh"
    env = os.environ.copy()
    if askpass.is_file():
        try:
            os.chmod(askpass, 0o755)
        except Exception:
            pass
        env["SUDO_ASKPASS"] = str(askpass)
        return subprocess.call(["sudo", "-A", *cmd_base], env=env)
    return subprocess.call(["sudo", *cmd_base])
