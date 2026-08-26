#!/usr/bin/env python3
"""
Blue Sonar for SmashDeck — continuous BT RSSI via l2ping + hcitool.

Upstream: https://github.com/ZeroChaos-/blue_sonar (BSD-2-Clause)
Kiosk-safe non-interactive service (upstream bash prompts on rfkill).
"""
from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from utils.paths import LOGS_TOOLS, PIDS_DIR, PROJECT_ROOT, ensure_data_dirs

ensure_data_dirs()
UPSTREAM_SCRIPT = PROJECT_ROOT / "third_party" / "blue_sonar" / "blue_sonar"
JOB_KEY = "blue_sonar"
META_PATH = PIDS_DIR / f"{JOB_KEY}.meta.json"
SAMPLES_PATH = LOGS_TOOLS / "blue_sonar_live.jsonl"
LOG_PATH = LOGS_TOOLS / "blue_sonar.log"

_MAC_RE = re.compile(r"^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$")
_RSSI_RE = re.compile(r"RSSI\s*(?:return\s*value)?\s*[:=]?\s*(-?\d+)", re.I)

_lock = threading.Lock()
_thread: Optional[threading.Thread] = None
_stop = threading.Event()
_state: Dict[str, Any] = {
    "running": False,
    "mac": "",
    "hci": "hci0",
    "sleep": 1.0,
    "started_at": None,
    "pid_l2ping": None,
    "last": None,
    "min_rssi": None,
    "max_rssi": None,
    "samples": 0,
    "error": None,
}


def _run(cmd: List[str], timeout: float = 8.0) -> tuple[int, str]:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return p.returncode, ((p.stdout or "") + (p.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        return -1, "timeout"
    except FileNotFoundError:
        return -1, f"not found: {cmd[0]}"
    except Exception as e:
        return -1, str(e)


def _norm_mac(mac: str) -> str:
    m = (mac or "").strip().upper().replace("-", ":")
    if not _MAC_RE.match(m):
        raise ValueError(f"invalid MAC: {mac}")
    return m


def _parse_rssi(text: str) -> Optional[int]:
    if not text:
        return None
    m = _RSSI_RE.search(text)
    if m:
        return int(m.group(1))
    m = re.search(r"(-?\d+)\s*dBm", text, re.I)
    return int(m.group(1)) if m else None


def _ensure_hci_up(hci: str) -> None:
    _run(["sudo", "-n", "rfkill", "unblock", "bluetooth"], timeout=5)
    _run(["sudo", "-n", "hciconfig", hci, "up"], timeout=5)


def _start_l2ping(mac: str, hci: str, delay: float) -> Optional[subprocess.Popen]:
    cmd = ["sudo", "-n", "l2ping", "-i", hci, "-t", "1", "-d", str(delay), mac]
    try:
        logf = open(LOG_PATH, "a", buffering=1)
        logf.write(f"\n# blue_sonar l2ping {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        logf.write(f"# CMD: {' '.join(cmd)}\n")
        return subprocess.Popen(
            cmd, stdout=logf, stderr=subprocess.STDOUT, start_new_session=True
        )
    except Exception as e:
        with _lock:
            _state["error"] = f"l2ping start failed: {e}"
        return None


def _kill_proc(proc: Optional[subprocess.Popen]) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        os.killpg(proc.pid, signal.SIGTERM)
    except Exception:
        try:
            proc.terminate()
        except Exception:
            pass
    try:
        proc.wait(timeout=2)
    except Exception:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def _write_meta() -> None:
    try:
        with _lock:
            META_PATH.write_text(json.dumps(dict(_state), indent=2))
    except Exception:
        pass


def _append_sample(sample: Dict[str, Any]) -> None:
    try:
        with open(SAMPLES_PATH, "a") as f:
            f.write(json.dumps(sample) + "\n")
    except Exception:
        pass


def _rssi_once(mac: str, hci: str) -> Dict[str, Any]:
    rc, out = _run(["sudo", "-n", "hcitool", "-i", hci, "rssi", mac], timeout=4)
    rssi = _parse_rssi(out)
    if rssi is None:
        _run(["sudo", "-n", "hcitool", "-i", hci, "cc", mac], timeout=8)
        rc, out = _run(["sudo", "-n", "hcitool", "-i", hci, "rssi", mac], timeout=4)
        rssi = _parse_rssi(out)
    return {
        "ts": time.time(),
        "mac": mac,
        "hci": hci,
        "rssi": rssi,
        "ok": rssi is not None,
        "raw": (out or "")[:200],
        "method": "blue_sonar",
    }


def _loop(mac: str, hci: str, sleep_s: float) -> None:
    _ensure_hci_up(hci)
    l2 = _start_l2ping(mac, hci, sleep_s)
    with _lock:
        _state["pid_l2ping"] = l2.pid if l2 else None
        _state["running"] = True
        if not l2:
            _state["error"] = _state.get("error") or "l2ping failed to start"
    _write_meta()
    time.sleep(1.0)
    try:
        while not _stop.is_set():
            if l2 and l2.poll() is not None:
                l2 = _start_l2ping(mac, hci, sleep_s)
                with _lock:
                    _state["pid_l2ping"] = l2.pid if l2 else None
                time.sleep(1.0)
            sample = _rssi_once(mac, hci)
            with _lock:
                _state["last"] = sample
                _state["samples"] = int(_state.get("samples") or 0) + 1
                r = sample.get("rssi")
                if r is not None:
                    mn, mx = _state.get("min_rssi"), _state.get("max_rssi")
                    _state["min_rssi"] = r if mn is None else min(mn, r)
                    _state["max_rssi"] = r if mx is None else max(mx, r)
                else:
                    sample["msg"] = "Out of range or not connected"
            _append_sample(sample)
            _write_meta()
            _stop.wait(max(0.2, float(sleep_s)))
    finally:
        _kill_proc(l2)
        with _lock:
            _state["running"] = False
            _state["pid_l2ping"] = None
        _write_meta()


def status() -> Dict[str, Any]:
    with _lock:
        snap = dict(_state)
        last = snap.get("last")
        if isinstance(last, dict):
            snap["rssi"] = last.get("rssi")
            snap["msg"] = last.get("msg")
        snap["running"] = bool(snap.get("running") and _thread and _thread.is_alive())
        snap["upstream_script"] = str(UPSTREAM_SCRIPT) if UPSTREAM_SCRIPT.is_file() else None
        return snap


def start(mac: str, hci: str = "hci0", sleep: float = 1.0) -> Dict[str, Any]:
    global _thread
    mac_u = _norm_mac(mac)
    hci = (hci or "hci0").strip() or "hci0"
    try:
        sleep_s = max(0.3, min(10.0, float(sleep)))
    except Exception:
        sleep_s = 1.0
    stop()
    time.sleep(0.15)
    try:
        if SAMPLES_PATH.exists():
            SAMPLES_PATH.write_text("")
    except Exception:
        pass
    _stop.clear()
    with _lock:
        _state.update({
            "running": True, "mac": mac_u, "hci": hci, "sleep": sleep_s,
            "started_at": time.time(), "pid_l2ping": None, "last": None,
            "min_rssi": None, "max_rssi": None, "samples": 0, "error": None,
        })
    _write_meta()
    t = threading.Thread(target=_loop, args=(mac_u, hci, sleep_s), daemon=True, name="blue_sonar")
    _thread = t
    t.start()
    return status()


def stop() -> Dict[str, Any]:
    global _thread
    _stop.set()
    t = _thread
    if t and t.is_alive():
        t.join(timeout=4.0)
    _thread = None
    with _lock:
        _state["running"] = False
        _state["pid_l2ping"] = None
    _write_meta()
    return status()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="SmashDeck Blue Sonar")
    ap.add_argument("-t", "--target", required=True)
    ap.add_argument("-i", "--interface", default="hci0")
    ap.add_argument("-s", "--sleep", type=float, default=1.0)
    ap.add_argument("--duration", type=float, default=0)
    args = ap.parse_args()
    print(json.dumps(start(args.target, args.interface, args.sleep), indent=2))
    try:
        end = time.time() + args.duration if args.duration > 0 else None
        while end is None or time.time() < end:
            time.sleep(1)
            print(json.dumps(status().get("last"), indent=2))
    except KeyboardInterrupt:
        pass
    print(json.dumps(stop(), indent=2))
