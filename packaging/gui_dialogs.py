"""Zenity-backed dialogs for Fox Hunter GUI install."""
from __future__ import annotations

import subprocess
from typing import List, Optional, Sequence, Tuple


def _has_zenity() -> bool:
    return subprocess.call(["which", "zenity"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0


def info(text: str, title: str = "Fox Hunter") -> None:
    if _has_zenity():
        subprocess.call(["zenity", "--info", f"--title={title}", f"--text={text}", "--width=420"])
    else:
        print(f"[{title}] {text}")


def error(text: str, title: str = "Fox Hunter") -> None:
    if _has_zenity():
        subprocess.call(["zenity", "--error", f"--title={title}", f"--text={text}", "--width=420"])
    else:
        print(f"ERROR [{title}] {text}")


def confirm(text: str, title: str = "Fox Hunter") -> bool:
    if _has_zenity():
        return subprocess.call(
            ["zenity", "--question", f"--title={title}", f"--text={text}", "--width=420"]
        ) == 0
    print(f"[{title}] {text} [y/N]")
    try:
        return input().strip().lower() in ("y", "yes")
    except Exception:
        return False


def choose(text: str, options: Sequence[Tuple[str, str]], title: str = "Fox Hunter") -> Optional[str]:
    """options: list of (id, label). Returns id or None."""
    if _has_zenity():
        args = ["zenity", "--list", "--radiolist", f"--title={title}", f"--text={text}",
                "--column=Pick", "--column=id", "--column=Action", "--hide-column=2", "--width=480", "--height=320"]
        for i, (oid, label) in enumerate(options):
            args += ["TRUE" if i == 0 else "FALSE", oid, label]
        try:
            out = subprocess.check_output(args, text=True).strip()
            return out or None
        except Exception:
            return None
    print(text)
    for i, (oid, label) in enumerate(options):
        print(f"  {i+1}) {label}")
    try:
        n = int(input("Choice: ").strip())
        if 1 <= n <= len(options):
            return options[n - 1][0]
    except Exception:
        pass
    return None


def password(text: str = "Password", title: str = "Fox Hunter") -> Optional[str]:
    if _has_zenity():
        try:
            out = subprocess.check_output(
                ["zenity", "--password", f"--title={title}", f"--text={text}", "--width=360"],
                text=True,
            )
            return (out or "").strip()
        except Exception:
            return None
    try:
        return input(f"{text}: ").strip()
    except Exception:
        return None


class Progress:
    def __init__(self, title: str, text: str = ""):
        self.title = title
        self._proc = None
        if _has_zenity():
            self._proc = subprocess.Popen(
                ["zenity", "--progress", f"--title={title}", f"--text={text}",
                 "--percentage=0", "--auto-close", "--no-cancel", "--width=400"],
                stdin=subprocess.PIPE, text=True,
            )

    def update(self, pct: int, text: str = "") -> None:
        if self._proc and self._proc.stdin:
            try:
                if text:
                    self._proc.stdin.write(f"#{text}\n")
                self._proc.stdin.write(f"{int(pct)}\n")
                self._proc.stdin.flush()
            except Exception:
                pass
        else:
            print(f"[{self.title}] {pct}% {text}")

    def close(self) -> None:
        if self._proc and self._proc.stdin:
            try:
                self._proc.stdin.write("100\n")
                self._proc.stdin.close()
            except Exception:
                pass
            try:
                self._proc.wait(timeout=2)
            except Exception:
                pass
        self._proc = None
