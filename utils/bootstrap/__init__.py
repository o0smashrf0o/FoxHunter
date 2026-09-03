#!/usr/bin/env python3
"""Fox Hunter bootstrap — first-run apt/venv/udev (dev path)."""
from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

from utils.paths import PROJECT_ROOT, ensure_data_dirs, LOGS_BOOTSTRAP

VENV_DIR = PROJECT_ROOT / ".venv"
MARKER = PROJECT_ROOT / ".bootstrap_complete"

REQUIRED_APT = [
    "python3-venv", "python3-pip", "python3-dev",
    "git", "curl", "wget", "rsync", "zip", "unzip",
    "iw", "wireless-tools", "rfkill", "net-tools",
    "bluez", "bluez-tools", "bluez-hcidump",
    "aircrack-ng", "nmap",
    "rtl-sdr", "librtlsdr-dev",
    "zenity", "policykit-1",
    "chromium-browser", "chromium",
]


def _log(msg: str) -> None:
    ensure_data_dirs()
    print(msg, flush=True)
    try:
        p = LOGS_BOOTSTRAP / "bootstrap.log"
        with open(p, "a") as f:
            f.write(msg + "\n")
    except Exception:
        pass


def get_venv_python() -> Path:
    return VENV_DIR / "bin" / "python"


def reexec_into_venv() -> None:
    py = get_venv_python()
    if py.is_file() and Path(sys.executable).resolve() != py.resolve():
        os.execv(str(py), [str(py), *sys.argv])


def setup_venv() -> bool:
    if not VENV_DIR.exists():
        _log("Creating venv…")
        venv.create(str(VENV_DIR), with_pip=True)
    pip = VENV_DIR / "bin" / "pip"
    req = PROJECT_ROOT / "requirements.txt"
    if req.is_file():
        _log("pip install -r requirements.txt")
        rc = subprocess.call([str(pip), "install", "-r", str(req)])
        return rc == 0
    return True


def install_system_packages() -> None:
    missing = []
    for pkg in REQUIRED_APT:
        rc = subprocess.call(
            ["dpkg", "-s", pkg],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if rc != 0:
            missing.append(pkg)
    if not missing:
        _log("apt packages present")
        return
    _log(f"Installing apt packages: {missing[:12]}…")
    subprocess.call(["sudo", "-n", "apt-get", "update"], stdout=subprocess.DEVNULL)
    subprocess.call(["sudo", "-n", "apt-get", "install", "-y", "--no-install-recommends", *missing])


def check_arch() -> None:
    import platform
    mach = platform.machine().lower()
    if mach not in ("aarch64", "arm64", "x86_64", "amd64"):
        _log(f"WARNING: unusual arch {mach}")


def bootstrap_if_needed(force: bool = False) -> None:
    ensure_data_dirs()
    check_arch()
    if MARKER.exists() and not force:
        _log("Bootstrap marker present — quick ensure")
        try:
            install_system_packages()
        except Exception as e:
            _log(f"apt ensure warn: {e}")
        setup_venv()
        reexec_into_venv()
        return
    _log("=== Fox Hunter full bootstrap ===")
    try:
        install_system_packages()
    except Exception as e:
        _log(f"apt warn: {e}")
    ok = setup_venv()
    if ok:
        MARKER.write_text("ok\n")
        _log("Bootstrap complete")
    reexec_into_venv()


if __name__ == "__main__":
    force = "--force" in sys.argv
    bootstrap_if_needed(force=force)
