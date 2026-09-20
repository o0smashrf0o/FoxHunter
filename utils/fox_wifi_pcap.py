#!/usr/bin/env python3
"""Record short Wi-Fi pcaps from Kismet sqlite when assoc/auth/data is seen."""

from __future__ import annotations

import os
import sqlite3
import struct
import time
from collections import deque
from pathlib import Path
from typing import Deque, Dict, Optional, Tuple

LOG_DIR = Path(os.environ.get("KISMET_LOG_DIR", "/home/smash/logs/kismet"))
PCAP_DIR = Path(os.environ.get("FOX_WIFI_PCAP_DIR", "/home/smash/logs/kismet/pcap"))
ENV_PATH = Path(os.environ.get("FOX_HUNTER_ENV", "/opt/foxhunter/fox_hunter.env"))
PRE_ROLL = 20.0
POST_ROLL = 45.0
COOLDOWN = 120.0
MAX_DIR_BYTES = 200 * 1024 * 1024
POLL_SEC = 0.5

MGMT_SUB = {0: "assoc-req", 1: "assoc-resp", 2: "reassoc-req", 3: "reassoc-resp", 11: "auth"}
DATA_SUB = {0: "data", 8: "qos-data"}


def env_on() -> bool:
    val = os.environ.get("FOX_WIFI_PCAP_ON_DATA", "")
    if ENV_PATH.is_file():
        try:
            for line in ENV_PATH.read_text().splitlines():
                line = line.strip()
                if line.startswith("FOX_WIFI_PCAP_ON_DATA="):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
        except OSError:
            pass
    return val.strip().upper() in ("1", "TRUE", "YES")


def latest_kismet() -> Optional[Path]:
    files = [p for p in LOG_DIR.glob("Kismet-*.kismet") if p.is_file()]
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def radiotap_len(buf: bytes) -> Optional[int]:
    if len(buf) < 4:
        return None
    return struct.unpack_from("<H", buf, 2)[0]


def frame_name(blob: bytes, dlt: int) -> Optional[str]:
    off = 0
    if dlt == 127:
        rt = radiotap_len(blob)
        if rt is None or rt < 8 or rt >= len(blob):
            return None
        off = rt
    elif dlt == 239:
        if len(blob) < 8:
            return None
        off = struct.unpack_from("<H", blob, 2)[0]
    elif dlt == 105:
        off = 0
    else:
        return None
    if off + 2 > len(blob):
        return None
    fc = struct.unpack_from("<H", blob, off)[0]
    ftype = (fc >> 2) & 0x3
    subtype = (fc >> 4) & 0xF
    if ftype == 0:
        return MGMT_SUB.get(subtype)
    if ftype == 2:
        return DATA_SUB.get(subtype)
    return None


def prune_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    files = sorted(path.glob("*.pcap"), key=lambda p: p.stat().st_mtime)
    total = sum(f.stat().st_size for f in files)
    while total > MAX_DIR_BYTES and files:
        f = files.pop(0)
        total -= f.stat().st_size
        try:
            f.unlink()
        except OSError:
            break


def write_pcap(path: Path, dlt: int, frames: list) -> None:
    snap = 65535
    with path.open("wb") as f:
        f.write(struct.pack("<IHHiIII", 0xA1B2C3D4, 2, 4, 0, 0, snap, dlt or 127))
        for ts, usec, blob in frames:
            blob = bytes(blob or b"")
            incl = min(len(blob), snap)
            f.write(struct.pack("<IIII", int(ts), int(usec or 0), incl, len(blob)))
            f.write(blob[:incl])


def open_db(db: Path) -> sqlite3.Connection:
    uri = f"file:{db}?mode=ro"
    con = sqlite3.connect(uri, uri=True, timeout=5)
    con.execute("PRAGMA query_only=ON")
    return con


def main() -> int:
    PCAP_DIR.mkdir(parents=True, exist_ok=True)
    ring: Deque[Tuple[float, int, int, int, str, str, bytes]] = deque()
    cooldown: Dict[Tuple[str, str], float] = {}
    last_id = 0
    db_path: Optional[Path] = None
    con: Optional[sqlite3.Connection] = None
    capturing_until = 0.0
    capture_dlt = 127
    pending_key: Optional[Tuple[str, str]] = None

    while True:
        if not env_on():
            time.sleep(2)
            continue

        latest = latest_kismet()
        if latest is None:
            time.sleep(2)
            continue
        if latest != db_path:
            if con is not None:
                try:
                    con.close()
                except sqlite3.Error:
                    pass
            try:
                con = open_db(latest)
                db_path = latest
                last_id = 0
            except sqlite3.Error:
                time.sleep(2)
                continue

        now = time.time()
        try:
            rows = con.execute(
                "SELECT packetid, ts_sec, ts_usec, dlt, sourcemac, destmac, packet "
                "FROM packets WHERE packetid > ? ORDER BY packetid ASC LIMIT 500",
                (last_id,),
            ).fetchall()
        except sqlite3.Error:
            time.sleep(1)
            continue

        for packetid, ts_sec, ts_usec, dlt, smac, dmac, blob in rows:
            last_id = packetid
            ts = float(ts_sec or 0) + float(ts_usec or 0) / 1e6
            smac = (smac or "").upper()
            dmac = (dmac or "").upper()
            blob = bytes(blob or b"")
            ring.append((ts, int(ts_sec or 0), int(ts_usec or 0), int(dlt or 127), smac, dmac, blob))
            cutoff = ts - PRE_ROLL - 1
            while ring and ring[0][0] < cutoff:
                ring.popleft()

            name = frame_name(blob, int(dlt or 0))
            if not name:
                continue
            key = (smac, dmac)
            last = cooldown.get(key, 0.0)
            if now - last < COOLDOWN and capturing_until <= now:
                continue
            if capturing_until <= now:
                capturing_until = now + POST_ROLL
                capture_dlt = int(dlt or 127)
                pending_key = key

        if pending_key and now >= capturing_until and capturing_until > 0:
            frames = [(s, u, b) for t, s, u, d, _a, _b, b in ring if t >= now - PRE_ROLL - POST_ROLL]
            if frames:
                prune_dir(PCAP_DIR)
                src, dst = pending_key
                safe_src = src.replace(":", "")[:12] or "unk"
                safe_dst = dst.replace(":", "")[:12] or "unk"
                out = PCAP_DIR / f"{time.strftime('%Y%m%d-%H%M%S')}-{safe_src}-{safe_dst}.pcap"
                write_pcap(out, capture_dlt, frames)
                cooldown[pending_key] = time.time()
            pending_key = None
            capturing_until = 0.0

        time.sleep(POLL_SEC)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
