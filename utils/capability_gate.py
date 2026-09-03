#!/usr/bin/env python3
"""Hardware capability checks for Fox Hunter tools."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from utils.device_detector import get_device_summary
from utils.paths import PROJECT_ROOT

CAPS_FILE = PROJECT_ROOT / "config" / "tool_capabilities.yaml"

CAP_LABELS = {
    "wifi_monitor": "USB Wi-Fi (monitor mode)",
    "bt_hci_scan": "Bluetooth HCI adapter",
    "sdr_rx": "SDR receiver (RTL-SDR / Lime / HackRF)",
    "sdr_tx": "SDR with TX",
    "wifi_inject": "Wi-Fi packet injection",
    "ubertooth": "Ubertooth One",
}


def _load_tools() -> Dict[str, Any]:
    if not CAPS_FILE.is_file():
        return {}
    try:
        data = yaml.safe_load(CAPS_FILE.read_text()) or {}
        return data.get("tools") or {}
    except Exception:
        return {}


def live_capabilities() -> Dict[str, bool]:
    summary = get_device_summary()
    caps = dict(summary.get("caps") or {})
    # inject heuristic: USB wifi known for inject
    usb = summary.get("usb") or []
    caps["wifi_inject"] = any(
        "inject" in (d.get("caps") or []) for d in usb
    ) or caps.get("wifi_monitor", False)
    caps["sdr_tx"] = any(
        "tx" in (d.get("caps") or []) for d in (summary.get("sdrs") or [])
    )
    caps.setdefault("wifi_monitor", False)
    caps.setdefault("bt_hci_scan", False)
    caps.setdefault("sdr_rx", False)
    caps.setdefault("ubertooth", False)
    return caps


def check_tool(tool_id: str, caps: Optional[Dict[str, bool]] = None) -> Dict[str, Any]:
    tools = _load_tools()
    meta = tools.get(tool_id) or {}
    caps = caps if caps is not None else live_capabilities()
    if meta.get("enabled") is False:
        return {
            "ok": False,
            "tool_id": tool_id,
            "name": meta.get("name") or tool_id,
            "message": meta.get("missing_hint") or "Tool disabled.",
            "missing": [],
            "enabled": False,
        }
    required: List[str] = list(meta.get("required") or [])
    any_of = meta.get("any_of") or []
    missing = [c for c in required if not caps.get(c)]
    any_ok = True
    if any_of:
        any_ok = False
        for group in any_of:
            if all(caps.get(c) for c in group):
                any_ok = True
                break
        if not any_ok:
            flat = sorted({c for g in any_of for c in g})
            missing = list(dict.fromkeys(missing + [c for c in flat if not caps.get(c)]))
    ok = not missing and any_ok
    return {
        "ok": ok,
        "tool_id": tool_id,
        "name": meta.get("name") or tool_id,
        "kind": meta.get("kind") or "utility",
        "message": "" if ok else (meta.get("missing_hint") or f"Missing: {', '.join(missing)}"),
        "missing": missing,
        "missing_labels": [CAP_LABELS.get(c, c) for c in missing],
        "enabled": meta.get("enabled", True),
    }


def list_tools() -> List[Dict[str, Any]]:
    caps = live_capabilities()
    tools = _load_tools()
    out = []
    for tid, meta in tools.items():
        gate = check_tool(tid, caps)
        gate["meta"] = meta
        out.append(gate)
    return out
