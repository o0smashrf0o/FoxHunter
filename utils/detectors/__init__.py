#!/usr/bin/env python3
"""TSCM detectors — fingerprint-driven, capability-gated."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

from utils.paths import PROJECT_ROOT

FP_DIR = PROJECT_ROOT / "config" / "fingerprints"


def _load_fp(name: str) -> Dict[str, Any]:
    p = FP_DIR / name
    if not p.is_file():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _wifi_devices() -> List[Dict[str, Any]]:
    try:
        from utils.kismet.client import get_client
        c = get_client()
        if c.is_port_open():
            devs = [d for d in c.list_devices(200) if d.get("type") == "wifi" or d.get("ssid") is not None]
            if devs:
                return devs
    except Exception:
        pass
    try:
        from utils.iface_scan import iw_scan_wifi
        # try common ifaces
        for iface in ("wlan1", "wlan2", "wlan0"):
            devs = iw_scan_wifi(iface, 100)
            if devs:
                return devs
    except Exception:
        pass
    return []


def _bt_devices() -> List[Dict[str, Any]]:
    try:
        from utils.iface_scan import hcitool_scan_bt
        for hci in ("hci1", "hci0"):
            devs = hcitool_scan_bt(hci, 80)
            if devs:
                return devs
    except Exception:
        pass
    return []


def _match_wifi_fingerprints(devices: List[Dict], fp: Dict[str, Any], category: str) -> List[Dict]:
    hits = []
    ssids = [s.lower() for s in (fp.get("ssids") or fp.get("ssid_patterns") or [])]
    ouis = [o.upper().replace(":", "") for o in (fp.get("ouis") or fp.get("oui") or [])]
    vendors = [v.lower() for v in (fp.get("vendors") or [])]
    for d in devices:
        reasons = []
        ssid = (d.get("ssid") or "").lower()
        mac = (d.get("mac") or "").upper().replace(":", "")
        vendor = (d.get("vendor") or "").lower()
        for pat in ssids:
            if pat and pat in ssid:
                reasons.append(f"ssid~{pat}")
        for o in ouis:
            if o and mac.startswith(o[:6]):
                reasons.append(f"oui={o[:6]}")
        for v in vendors:
            if v and v in vendor:
                reasons.append(f"vendor~{v}")
        if reasons:
            hits.append({
                **d,
                "category": category,
                "label": fp.get("name") or category,
                "match_reasons": reasons,
                "confidence": min(95, 40 + 15 * len(reasons)),
                "kind": category,
            })
    return hits


def run_camera_detect(**_) -> Dict[str, Any]:
    fp = _load_fp("cameras.json")
    devs = _wifi_devices()
    # cameras.json may be list or dict-of-brands
    hits = []
    if isinstance(fp, list):
        for entry in fp:
            hits.extend(_match_wifi_fingerprints(devs, entry, "camera"))
    elif isinstance(fp, dict):
        brands = fp.get("brands") or fp.get("cameras") or fp
        if isinstance(brands, dict):
            for name, entry in brands.items():
                if isinstance(entry, dict):
                    e = dict(entry)
                    e.setdefault("name", name)
                    hits.extend(_match_wifi_fingerprints(devs, e, "camera"))
        else:
            hits.extend(_match_wifi_fingerprints(devs, fp, "camera"))
    return {"ok": True, "hits": hits, "count": len(hits), "msg": f"{len(hits)} camera-like device(s)"}


def run_flock_detect(**_) -> Dict[str, Any]:
    fp = _load_fp("flock.json")
    hits = _match_wifi_fingerprints(_wifi_devices(), fp if isinstance(fp, dict) else {}, "flock")
    return {"ok": True, "hits": hits, "count": len(hits), "msg": f"{len(hits)} flock-like hit(s)"}


def run_rogue_ap_detect(**_) -> Dict[str, Any]:
    fp = _load_fp("rogue_ap.json")
    hits = _match_wifi_fingerprints(_wifi_devices(), fp if isinstance(fp, dict) else {}, "rogue_ap")
    # open free wifi lure heuristic
    for d in _wifi_devices():
        ssid = (d.get("ssid") or "").lower()
        enc = (d.get("encryption") or "").lower()
        if enc == "open" and any(x in ssid for x in ("free", "airport", "guest", "wifi")):
            hits.append({**d, "category": "rogue_ap", "label": "Open lure SSID", "match_reasons": ["open+lure-ssid"], "confidence": 55})
    return {"ok": True, "hits": hits, "count": len(hits), "msg": f"{len(hits)} rogue-like hit(s)"}


def run_tracker_detect(**_) -> Dict[str, Any]:
    fp = _load_fp("trackers_ble.json")
    devs = _bt_devices()
    hits = []
    names = [n.lower() for n in (fp.get("names") or fp.get("name_patterns") or [])] if isinstance(fp, dict) else []
    ouis = [o.upper().replace(":", "") for o in (fp.get("ouis") or [])] if isinstance(fp, dict) else []
    if isinstance(fp, dict) and isinstance(fp.get("trackers"), list):
        for t in fp["trackers"]:
            names += [x.lower() for x in (t.get("names") or [])]
            ouis += [o.upper().replace(":", "") for o in (t.get("ouis") or [])]
    for d in devs:
        reasons = []
        nm = (d.get("name") or "").lower()
        mac = (d.get("mac") or "").upper().replace(":", "")
        for n in names:
            if n and n in nm:
                reasons.append(f"name~{n}")
        for o in ouis:
            if o and mac.startswith(o[:6]):
                reasons.append(f"oui={o[:6]}")
        if reasons:
            hits.append({**d, "category": "tracker", "label": "Tracker", "match_reasons": reasons, "confidence": min(90, 45 + 15 * len(reasons))})
    return {"ok": True, "hits": hits, "count": len(hits), "msg": f"{len(hits)} tracker-like device(s)"}


def run_ble_inspector(**_) -> Dict[str, Any]:
    devs = _bt_devices()
    hits = [{**d, "category": "ble", "label": d.get("name") or d.get("mac"), "confidence": 50, "match_reasons": ["scan"]} for d in devs]
    return {"ok": True, "hits": hits, "count": len(hits), "msg": f"{len(hits)} BLE/BT device(s)"}


def run_drone_rid_detect(**_) -> Dict[str, Any]:
    hits = []
    for d in _wifi_devices() + _bt_devices():
        blob = f"{d.get('ssid','')} {d.get('name','')} {d.get('vendor','')}".lower()
        if any(x in blob for x in ("dji", "drone", "odid", "parrot", "autel", "skydio")):
            hits.append({**d, "category": "drone_rid", "label": "Drone-related", "match_reasons": ["name/vendor"], "confidence": 60})
    return {"ok": True, "hits": hits, "count": len(hits), "msg": f"{len(hits)} drone-related hit(s)"}


def run_device_scout(**_) -> Dict[str, Any]:
    wifi = _wifi_devices()
    bt = _bt_devices()
    by_mac: Dict[str, Dict] = {}
    for d in wifi + bt:
        mac = (d.get("mac") or "").upper()
        if not mac:
            continue
        if mac not in by_mac:
            by_mac[mac] = {**d, "radios": set(), "names": []}
        entry = by_mac[mac]
        r = "wifi" if d.get("ssid") is not None or d.get("type") == "wifi" else "bt"
        entry["radios"].add(r)
        nm = d.get("ssid") or d.get("name")
        if nm:
            entry["names"].append(nm)
    hits = []
    for mac, e in by_mac.items():
        radios = list(e.get("radios") or [])
        conf = 40 + (25 if len(radios) > 1 else 0)
        hits.append({
            "mac": mac,
            "name": (e.get("names") or [mac])[0],
            "names": e.get("names") or [],
            "vendor": e.get("vendor"),
            "rssi_dbm": e.get("rssi_dbm"),
            "category": "scout",
            "label": "Multi-radio" if len(radios) > 1 else "Session sighting",
            "match_reasons": [f"radios={','.join(radios)}"],
            "confidence": conf,
            "radios": radios,
        })
    hits.sort(key=lambda h: h.get("confidence") or 0, reverse=True)
    return {"ok": True, "hits": hits[:80], "count": len(hits), "msg": f"{len(hits)} scouted device(s)"}


def run_spectrum_baseline(**_) -> Dict[str, Any]:
    import subprocess
    import tempfile
    from pathlib import Path
    out = Path(tempfile.gettempdir()) / f"foxhunter_rtl_{int(time.time())}.csv"
    try:
        p = subprocess.run(
            ["rtl_power", "-f", "2400M:2500M:1M", "-i", "1", "-e", "5s", str(out)],
            capture_output=True, text=True, timeout=30,
        )
        powers = []
        if out.is_file():
            for line in out.read_text(errors="replace").splitlines():
                parts = line.split(",")
                for x in parts[6:]:
                    try:
                        powers.append(float(x))
                    except Exception:
                        pass
        if not powers:
            return {"ok": p.returncode == 0, "hits": [], "count": 0, "msg": "rtl_power produced no samples", "error": (p.stderr or "")[:300]}
        avg = sum(powers) / len(powers)
        peak = max(powers)
        floor = sorted(powers)[max(0, len(powers)//20)]
        elevated = peak > floor + 15
        hit = {
            "category": "spectrum",
            "label": "2.4 GHz baseline",
            "avg_dbm": round(avg, 1),
            "peak_dbm": round(peak, 1),
            "floor_dbm": round(floor, 1),
            "elevated": elevated,
            "confidence": 70 if elevated else 40,
            "match_reasons": ["rtl_power"],
        }
        return {"ok": True, "hits": [hit], "count": 1, "msg": f"avg={avg:.1f} peak={peak:.1f} elevated={elevated}"}
    except FileNotFoundError:
        return {"ok": False, "hits": [], "count": 0, "error": "rtl_power not installed", "msg": "rtl_power missing"}
    except Exception as e:
        return {"ok": False, "hits": [], "count": 0, "error": str(e), "msg": str(e)}


RUNNERS: Dict[str, Callable[..., Dict[str, Any]]] = {
    "camera_detect": run_camera_detect,
    "flock_detect": run_flock_detect,
    "rogue_ap_detect": run_rogue_ap_detect,
    "tracker_detect": run_tracker_detect,
    "ble_inspector": run_ble_inspector,
    "drone_rid_detect": run_drone_rid_detect,
    "device_scout": run_device_scout,
    "spectrum_baseline": run_spectrum_baseline,
}


def run_detector(tool_id: str, **opts) -> Dict[str, Any]:
    fn = RUNNERS.get(tool_id)
    if not fn:
        return {"ok": False, "error": f"unknown detector: {tool_id}", "hits": [], "count": 0}
    try:
        return fn(**opts)
    except Exception as e:
        return {"ok": False, "error": str(e), "hits": [], "count": 0, "msg": str(e)}
