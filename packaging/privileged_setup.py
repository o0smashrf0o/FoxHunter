#!/usr/bin/env python3
"""
Root install helper for SmashDeck.
Copies media → /opt/smashdeck, apt packages, venv, sudoers, udev, desktop entries.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
INSTALL_PREFIX = Path("/opt/smashdeck")
STATE_DIR = Path("/var/lib/smashdeck")
SUDOERS_DST = Path("/etc/sudoers.d/smashdeck")

EXCLUDE_NAMES = {
    ".git", ".venv", "__pycache__", ".bootstrap_complete",
    "node_modules", ".mypy_cache", ".pytest_cache", ".DS_Store",
}
EXCLUDE_ROOT_PATHS = ("data", "dist")

APT_PKGS = [
    "python3-venv", "python3-pip", "python3-dev", "python3-yaml",
    "git", "curl", "wget", "rsync", "zip", "unzip",
    "iw", "wireless-tools", "rfkill", "net-tools",
    "bluez", "bluez-tools",
    "aircrack-ng", "nmap",
    "rtl-sdr", "librtlsdr-dev",
    "zenity", "policykit-1",
    "python3-gi", "gir1.2-gtk-3.0", "gir1.2-webkit2-4.1",
    "epiphany-browser",
]


def log(msg: str) -> None:
    print(msg, flush=True)


def run(cmd: List[str], timeout: int = 600) -> int:
    log("+ " + " ".join(cmd))
    try:
        return subprocess.call(cmd, timeout=timeout)
    except Exception as e:
        log(f"run failed: {e}")
        return 1


def ensure_root() -> None:
    if os.geteuid() != 0:
        log("Must run as root")
        sys.exit(1)


def sync_tree(source: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    if shutil.which("rsync"):
        excludes = [f"--exclude={n}" for n in sorted(EXCLUDE_NAMES)]
        excludes += [f"--exclude=/{p}" for p in EXCLUDE_ROOT_PATHS]
        excludes += [
            "--exclude=third_party/gr-oots",
            "--exclude=**/*.pyc",
        ]
        run(["rsync", "-a", "--delete"] + excludes + [str(source) + "/", str(dest) + "/"])
        return
    skip = set(EXCLUDE_NAMES) | set(EXCLUDE_ROOT_PATHS)
    for item in source.iterdir():
        if item.name in skip:
            continue
        target = dest / item.name
        if item.is_dir():
            if target.exists():
                shutil.rmtree(target, ignore_errors=True)
            shutil.copytree(item, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".git", ".venv"))
        else:
            shutil.copy2(item, target)


def setup_venv(prefix: Path) -> bool:
    py = shutil.which("python3") or "/usr/bin/python3"
    venv = prefix / ".venv"
    if not venv.exists():
        if run([py, "-m", "venv", str(venv)]) != 0:
            return False
    pip = venv / "bin" / "pip"
    req = prefix / "requirements.txt"
    if req.is_file():
        run([str(pip), "install", "--upgrade", "pip", "wheel"], timeout=180)
        return run([str(pip), "install", "-r", str(req)], timeout=600) == 0
    return True


def install_sudoers(source_root: Path) -> bool:
    src = source_root / "packaging" / "sudoers.smashdeck"
    if not src.is_file():
        src = HERE / "sudoers.smashdeck"
    if not src.is_file():
        log("sudoers missing")
        return False
    tmp = Path("/tmp/smashdeck-sudoers")
    tmp.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
    os.chmod(tmp, 0o440)
    if run(["visudo", "-cf", str(tmp)]) != 0:
        log("sudoers validation failed")
        return False
    shutil.copy2(tmp, SUDOERS_DST)
    os.chmod(SUDOERS_DST, 0o440)
    log(f"installed {SUDOERS_DST}")
    return True


def install_udev(source_root: Path) -> None:
    src = source_root / "config" / "99-smashdeck.rules"
    if not src.is_file():
        return
    dst = Path("/etc/udev/rules.d/99-smashdeck.rules")
    shutil.copy2(src, dst)
    run(["udevadm", "control", "--reload-rules"])
    run(["udevadm", "trigger"])


def ensure_group_and_user(username: str) -> None:
    run(["groupadd", "-f", "smashdeck_ops"])
    run(["groupadd", "-f", "plugdev"])
    run(["groupadd", "-f", "dialout"])
    if username and username != "root":
        for g in ("smashdeck_ops", "plugdev", "dialout", "netdev"):
            run(["usermod", "-aG", g, username])


def install_desktop_entries(prefix: Path, desktop_user: str) -> None:
    icon = "network-wireless"
    apps = Path("/usr/share/applications")
    apps.mkdir(parents=True, exist_ok=True)
    content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=SmashDeck
GenericName=RF & Wireless Analysis
Comment=WiFi, Bluetooth, SDR survey toolkit
Exec={prefix}/smashdeck-gui --mode kiosk
TryExec={prefix}/smashdeck-gui
Icon={icon}
Terminal=false
Categories=Network;HamRadio;Security;Utility;
StartupNotify=true
"""
    kiosk = content.replace("Name=SmashDeck", "Name=SmashDeck Kiosk").replace(
        "--mode app", "--mode kiosk"
    )
    (apps / "smashdeck.desktop").write_text(content)
    (apps / "smashdeck-kiosk.desktop").write_text(kiosk)
    if desktop_user and desktop_user != "root":
        home = Path("/home") / desktop_user / "Desktop"
        if home.is_dir():
            dst = home / "SmashDeck.desktop"
            dst.write_text(content)
            os.chmod(dst, 0o755)
            try:
                shutil.chown(dst, user=desktop_user)
            except Exception:
                pass


def chmod_scripts(prefix: Path) -> None:
    for name in ("smashdeck-gui", "smashdeck-launch", "smashdeck-media-start", "smashdeck-kiosk"):
        p = prefix / name
        if p.is_file():
            os.chmod(p, 0o755)
    bs = prefix / "third_party" / "blue_sonar" / "blue_sonar"
    if bs.is_file():
        os.chmod(bs, 0o755)


def apt_install(pkgs: List[str]) -> None:
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    subprocess.call(["apt-get", "update"], env=env, timeout=300)
    subprocess.call(
        ["apt-get", "install", "-y", "--no-install-recommends", *pkgs],
        env=env,
        timeout=1200,
    )


def write_state(version: str, user: str, prefix: Path) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    state = {"version": version, "user": user, "prefix": str(prefix)}
    (STATE_DIR / "install.json").write_text(json.dumps(state, indent=2))


def action_install(args: argparse.Namespace) -> int:
    ensure_root()
    source = Path(args.source).resolve()
    prefix = INSTALL_PREFIX
    if os.environ.get("SMASHDECK_INSTALL_PREFIX"):
        prefix = Path(os.environ["SMASHDECK_INSTALL_PREFIX"]).resolve()
    if not (source / "dashboard" / "app.py").is_file():
        log(f"bad source: {source}")
        return 1
    if args.replace and prefix.exists():
        log(f"replacing {prefix}")
    user = args.user or os.environ.get("SUDO_USER") or os.environ.get("PKEXEC_UID") or ""
    if user.isdigit():
        import pwd
        try:
            user = pwd.getpwuid(int(user)).pw_name
        except Exception:
            user = ""
    if not user:
        user = "pi"

    log(f"Install SmashDeck from {source} → {prefix}")
    apt_install(APT_PKGS)
    # optional kismet
    subprocess.call(["apt-get", "install", "-y", "--no-install-recommends", "kismet"], timeout=600)

    sync_tree(source, prefix)
    chmod_scripts(prefix)
    if not setup_venv(prefix):
        log("venv setup failed")
        return 1
    install_sudoers(source if (source / "packaging" / "sudoers.smashdeck").is_file() else prefix)
    install_udev(prefix)
    ensure_group_and_user(user)
    install_desktop_entries(prefix, user)
    ver = "0.1.0"
    try:
        ver = (prefix / "VERSION").read_text().strip().splitlines()[0]
    except Exception:
        pass
    write_state(ver, user, prefix)
    log("Install complete")
    return 0


def action_uninstall(args: argparse.Namespace) -> int:
    ensure_root()
    prefix = INSTALL_PREFIX
    if prefix.exists():
        shutil.rmtree(prefix, ignore_errors=True)
    for p in (
        Path("/usr/share/applications/smashdeck.desktop"),
        Path("/usr/share/applications/smashdeck-kiosk.desktop"),
        SUDOERS_DST,
        Path("/etc/udev/rules.d/99-smashdeck.rules"),
    ):
        try:
            p.unlink()
        except Exception:
            pass
    log("Uninstall complete (user data kept)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="action", required=True)
    inst = sub.add_parser("install")
    inst.add_argument("--source", required=True)
    inst.add_argument("--profile", default="full")
    inst.add_argument("--replace", action="store_true")
    inst.add_argument("--user", default="")
    sub.add_parser("uninstall")
    rep = sub.add_parser("repair")
    rep.add_argument("--source", required=True)
    args = ap.parse_args()
    if args.action == "install":
        return action_install(args)
    if args.action == "uninstall":
        return action_uninstall(args)
    if args.action == "repair":
        args.replace = True
        return action_install(args)
    return 1


if __name__ == "__main__":
    sys.exit(main())
