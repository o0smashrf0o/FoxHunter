#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.paths import BT_SCAN_DIR, DATA_DIR, WIFI_SCAN_DIR, ensure_data_dirs

_CSV_FIELDS = (
    "ts", "kind", "iface", "ssid", "name", "mac", "rssi_dbm",
    "channel", "encryption", "vendor", "type",
)
_last_snap: Dict[str, float] = {}
SNAP_EVERY = 300.0


def _kind_dir(kind: str) -> Path:
    ensure_data_dirs()
    return WIFI_SCAN_DIR if kind == "wifi" else BT_SCAN_DIR


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")


def _dir_size(path: Path) -> int:
    total = 0
    try:
        for p in path.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except Exception:
                    pass
    except Exception:
        pass
    return total


def disk_status() -> Dict[str, Any]:
    ensure_data_dirs()
    usage = shutil.disk_usage(str(DATA_DIR))
    data_bytes = _dir_size(DATA_DIR)
    total = int(usage.total) or 1
    free = int(usage.free)
    data_pct = round(100.0 * data_bytes / total, 2)
    free_pct = round(100.0 * free / total, 2)
    used_pct = round(100.0 * (total - free) / total, 1)
    level = "ok"
    if data_pct >= 50 or free_pct <= 20:
        level = "warn"
    if data_pct >= 70 or free_pct <= 10 or free < 400 * 1024 * 1024:
        level = "hot"
    return {
        "data_dir": str(DATA_DIR),
        "data_bytes": data_bytes,
        "data_human": _human(data_bytes),
        "disk_total": total,
        "disk_free": free,
        "disk_total_human": _human(total),
        "disk_free_human": _human(free),
        "data_pct": data_pct,
        "free_pct": free_pct,
        "used_pct": used_pct,
        "level": level,
    }


def _human(n: int) -> str:
    x = float(n)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if x < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(x)} {unit}"
            return f"{x:.1f} {unit}"
        x /= 1024.0
    return f"{n} B"


def save_snapshot(kind: str, devices: List[Dict[str, Any]], meta: Optional[dict] = None, force: bool = True) -> Optional[str]:
    kind = "wifi" if kind == "wifi" else "bt"
    devices = list(devices or [])
    now = time.time()
    if not force:
        latest = _kind_dir(kind) / "latest.json"
        _write_json(latest, kind, devices, meta, now)
        last = _last_snap.get(kind) or 0
        if now - last < SNAP_EVERY:
            return None
        if not devices:
            return None
    _last_snap[kind] = now
    stamp = _stamp()
    d = _kind_dir(kind)
    jpath = d / f"{stamp}.json"
    cpath = d / f"{stamp}.csv"
    _write_json(jpath, kind, devices, meta, now)
    _write_json(d / "latest.json", kind, devices, meta, now)
    _write_csv(cpath, kind, devices, meta, now)
    return str(jpath)


def _write_json(path: Path, kind: str, devices: List[Dict[str, Any]], meta: Optional[dict], now: float) -> None:
    payload = {
        "ts": datetime.fromtimestamp(now, timezone.utc).isoformat(),
        "kind": kind,
        "iface": (meta or {}).get("iface") or (meta or {}).get("hci") or "",
        "count": len(devices),
        "devices": devices,
        "meta": meta or {},
    }
    path.write_text(json.dumps(payload, indent=2, default=str))


def _write_csv(path: Path, kind: str, devices: List[Dict[str, Any]], meta: Optional[dict], now: float) -> None:
    iface = (meta or {}).get("iface") or (meta or {}).get("hci") or ""
    ts = datetime.fromtimestamp(now, timezone.utc).isoformat()
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=_CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for d in devices:
            w.writerow({
                "ts": ts,
                "kind": kind,
                "iface": iface,
                "ssid": d.get("ssid") or "",
                "name": d.get("name") or "",
                "mac": d.get("mac") or "",
                "rssi_dbm": d.get("rssi_dbm") if d.get("rssi_dbm") is not None else "",
                "channel": d.get("channel") if d.get("channel") is not None else "",
                "encryption": d.get("encryption") or "",
                "vendor": d.get("vendor") or "",
                "type": d.get("type") or kind,
            })


def list_scans(limit: int = 80) -> List[Dict[str, Any]]:
    ensure_data_dirs()
    items = []
    for kind, d in (("wifi", WIFI_SCAN_DIR), ("bt", BT_SCAN_DIR)):
        if not d.is_dir():
            continue
        for p in d.glob("*.json"):
            if p.name == "latest.json":
                continue
            try:
                st = p.stat()
            except Exception:
                continue
            items.append({
                "name": p.name,
                "kind": kind,
                "path": str(p),
                "csv": str(p.with_suffix(".csv")) if p.with_suffix(".csv").is_file() else "",
                "bytes": st.st_size,
                "human": _human(st.st_size),
                "mtime": st.st_mtime,
            })
    items.sort(key=lambda x: x["mtime"], reverse=True)
    return items[:limit]


def safe_data_path(path: Path) -> Path:
    ensure_data_dirs()
    p = path.resolve()
    root = DATA_DIR.resolve()
    if root not in p.parents and p != root:
        raise ValueError("path outside data dir")
    return p


def delete_scan(path: str) -> Tuple[bool, str]:
    p = safe_data_path(Path(path))
    if not p.is_file():
        return False, "not found"
    csvp = p.with_suffix(".csv")
    p.unlink()
    if csvp.is_file():
        csvp.unlink()
    return True, "deleted"


def delete_all_scans() -> int:
    n = 0
    for d in (WIFI_SCAN_DIR, BT_SCAN_DIR):
        if not d.is_dir():
            continue
        for p in list(d.glob("*")):
            if p.is_file():
                p.unlink()
                n += 1
    return n


def removable_mounts() -> List[str]:
    found = []
    for base in (Path("/media"), Path("/run/media"), Path("/mnt")):
        if not base.is_dir():
            continue
        for p in base.rglob("*"):
            if p.is_dir() and p != base:
                try:
                    if p.stat().st_dev != Path("/").stat().st_dev:
                        found.append(str(p))
                except Exception:
                    pass
            if len(found) >= 12:
                return found
    return found


def copy_to(dest_dir: str, src_path: str = "") -> Tuple[bool, str]:
    dest = Path(dest_dir).expanduser().resolve()
    allowed = False
    for root in (Path("/media"), Path("/run/media"), Path("/mnt"), Path.home()):
        try:
            if root.resolve() in dest.parents or dest == root.resolve():
                allowed = True
                break
        except Exception:
            pass
    if not allowed or not dest.is_dir():
        return False, "destination must be a mounted drive"
    if src_path:
        src = safe_data_path(Path(src_path))
        shutil.copy2(src, dest / src.name)
        csvp = src.with_suffix(".csv")
        if csvp.is_file():
            shutil.copy2(csvp, dest / csvp.name)
        return True, str(dest / src.name)
    out = dest / f"foxhunter-scans-{_stamp()}"
    out.mkdir(parents=True, exist_ok=True)
    for d in (WIFI_SCAN_DIR, BT_SCAN_DIR):
        if d.is_dir():
            shutil.copytree(d, out / d.name, dirs_exist_ok=True)
    return True, str(out)
