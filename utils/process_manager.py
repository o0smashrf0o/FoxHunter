#!/usr/bin/env python3
"""Lightweight PID-file process tracking for SmashDeck tools."""
from __future__ import annotations

import glob
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.paths import DATA_DIR, LOGS_TOOLS, PIDS_DIR, ensure_data_dirs

ensure_data_dirs()
PID_DIR = PIDS_DIR


def _pidfile(key: str) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in key)
    return PID_DIR / f"{safe}.pid"


def start(
    cmd: List[str] | str,
    key: str,
    log_path: Optional[str] = None,
    shell: bool = False,
    env: Optional[Dict] = None,
) -> Optional[int]:
    if log_path is None:
        log_path = str(LOGS_TOOLS / f"{key}_{int(time.time())}.log")
    try:
        logf = open(log_path, "a", buffering=1)
        proc = subprocess.Popen(
            cmd,
            shell=shell,
            stdout=logf,
            stderr=subprocess.STDOUT,
            env=env or os.environ,
            start_new_session=True,
        )
        pid = proc.pid
        _pidfile(key).write_text(str(pid))
        (PID_DIR / f"{key}.logpath").write_text(log_path)
        return pid
    except Exception as e:
        print(f"[process_manager] start failed for {key}: {e}")
        return None


def stop(key: str, timeout: float = 3.0) -> bool:
    pf = _pidfile(key)
    if not pf.exists():
        return False
    try:
        pid = int(pf.read_text().strip())
        try:
            os.killpg(pid, signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGTERM)
            except Exception:
                pass
        time.sleep(min(timeout, 1.5))
        try:
            os.killpg(pid, signal.SIGKILL)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass
        pf.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def is_running(key: str) -> bool:
    pf = _pidfile(key)
    if not pf.exists():
        return False
    try:
        pid = int(pf.read_text().strip())
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, FileNotFoundError, ValueError):
        try:
            pf.unlink(missing_ok=True)
        except Exception:
            pass
        return False
    except Exception:
        return False


def get_pid(key: str) -> Optional[int]:
    pf = _pidfile(key)
    if pf.exists():
        try:
            return int(pf.read_text().strip())
        except Exception:
            pass
    return None


def list_active() -> List[Dict[str, Any]]:
    out = []
    for pf in PID_DIR.glob("*.pid"):
        key = pf.stem
        pid = None
        alive = False
        try:
            pid = int(pf.read_text().strip())
            os.kill(pid, 0)
            alive = True
        except Exception:
            alive = False
        lp = PID_DIR / f"{key}.logpath"
        logp = lp.read_text().strip() if lp.exists() else None
        out.append({"key": key, "pid": pid, "alive": alive, "log": logp})
    return out


def tail_log(key_or_path: str, lines: int = 20) -> str:
    p = Path(key_or_path)
    if not p.exists():
        lp = PID_DIR / f"{key_or_path}.logpath"
        if lp.exists():
            p = Path(lp.read_text().strip())
    if not p or not p.exists():
        cands = sorted(
            glob.glob(str(LOGS_TOOLS / f"*{key_or_path}*.log")),
            key=os.path.getmtime,
            reverse=True,
        )
        if cands:
            p = Path(cands[0])
    if not p or not p.exists():
        return ""
    try:
        with open(p, "r", errors="replace") as f:
            return "".join(f.readlines()[-lines:])
    except Exception:
        return ""
