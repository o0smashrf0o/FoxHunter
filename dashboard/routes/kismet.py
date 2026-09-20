#!/usr/bin/env python3
import os
from flask import Blueprint, jsonify, request

kismet_bp = Blueprint("kismet", __name__)


@kismet_bp.route("/api/kismet_status")
def status():
    from utils.kismet.client import get_client
    c = get_client()
    return jsonify(c.system_status())


@kismet_bp.route("/api/kismet_start", methods=["POST"])
def start():
    data = request.get_json(silent=True) or {}
    src = data.get("source") or ""
    from utils.kismet.client import ensure_kismet
    ok, msg = ensure_kismet(src)
    return jsonify({"ok": ok, "msg": msg})


@kismet_bp.route("/api/kismet_devices_live")
def devices_live():
    from utils.kismet.client import get_client, source_def
    from shared import merge_devices
    c = get_client()
    src = source_def(request.args.get("source") or "")
    iface = src.split(":")[0] if src else ""
    if src and c.is_port_open():
        c.ensure_source(src)
    devs = c.list_devices(int(request.args.get("limit") or 150))
    wifi = [d for d in devs if d.get("type") == "wifi" or d.get("ssid")]
    bt = [d for d in devs if d.get("type") == "bt" or "bt" in str(d.get("type"))]
    if wifi:
        merge_devices("wifi", wifi)
        try:
            from utils.scan_store import save_snapshot
            save_snapshot("wifi", wifi, {"iface": iface, "mode": "kismet"}, force=False)
        except Exception:
            pass
    if bt:
        merge_devices("bt", bt)
        try:
            from utils.scan_store import save_snapshot
            save_snapshot("bt", bt, {"mode": "kismet"}, force=False)
        except Exception:
            pass
    return jsonify({"ok": True, "devices": devs, "count": len(devs), "sources": c.list_sources(), "iface": iface})


@kismet_bp.route("/api/kismet_stop", methods=["POST"])
def stop():
    from utils.kismet.client import stop_kismet
    ok, msg = stop_kismet()
    return jsonify({"ok": ok, "msg": msg})


@kismet_bp.route("/api/wifi_pcap_toggle", methods=["POST"])
def wifi_pcap_toggle():
    data = request.get_json(silent=True) or {}
    enable = data.get("enable", False)
    env_path = "/opt/foxhunter/fox_hunter.env"
    if enable:
        line = "FOX_WIFI_PCAP_ON_DATA=1"
    else:
        line = "FOX_WIFI_PCAP_ON_DATA=0"
    try:
        with open(env_path, "r") as f:
            content = f.read()
        lines = content.split("\n")
        new_lines = []
        found = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("FOX_WIFI_PCAP_ON_DATA="):
                new_lines.append(line.replace(line.split("=")[1], line.split("=")[-1] if "=" in line else "0"))
                # Actually just replace the value
                key, _, val = stripped.partition("=")
                new_lines.append(f"{key}={str(int(enables) if enables else 0)}")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(line if enable else "FOX_WIFI_PCAP_ON_DATA=0")
        with open(env_path, "w") as f:
            f.write("\n".join(new_lines))
        return jsonify({"ok": True, "msg": "FOX_WIFI_PCAP_ON_DATA=" + ("enabled" if enable else "disabled")})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@kismet_bp.route("/api/wifi_pcap_status")
def wifi_pcap_status():
    try:
        from utils.paths import ensure_data_dirs
        ensure_data_dirs()
        pcap_dir = Path("/home/smash/logs/kismet/pcap")
        last_file = None
        if pcap_dir.exists():
            files = list(pcap_dir.glob("*.pcapng"))
            if files:
                files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
                last_file = str(files[0])
        # Read env var
        env_val = "0"
        env_path = "/opt/foxhunter/fox_hunter.env"
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.strip().startswith("FOX_WIFI_PCAP_ON_DATA="):
                        env_val = line.strip().split("=")[-1]
                        break
        import os
        running = os.environ.get("FOX_WIFI_PCAP_ON_DATA", "0") in ("1", "true", "True", "yes", "YES")
        return jsonify({
            "ok": True,
            "running": running,
            "last_file": last_file,
            "env": env_val,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
