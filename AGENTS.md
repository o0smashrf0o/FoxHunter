# AGENTS.md — SmashDeck

Portable RPi4 RF/wireless deck. Clean architecture, touch dashboard, GUI install.

## Layout

| Path | Role |
|------|------|
| `./smashdeck-gui` | End-user entry: install / update / launch |
| `./smashdeck-launch` | Dev bootstrap → dashboard → kiosk |
| `./smashdeck-media-start` | USB/media double-click helper |
| `dashboard/app.py` | Flask on `:8080` |
| `dashboard/routes/` | Blueprints (core, devices, bt, wifi, detect, tools, kismet) |
| `dashboard/shared/` | State, sources, helpers |
| `dashboard/static/` | CSS + ordered JS (`01_…` …) |
| `utils/` | Scans, devices, blue_sonar, kismet, process_manager, paths |
| `utils/bootstrap/` | First-run apt/venv/udev/sudoers |
| `config/` | YAML sources, fingerprints, OUI data |
| `packaging/` | Privileged install, sudoers, desktop templates |
| `third_party/blue_sonar/` | Vendored upstream script |
| `scripts/make_release.sh` | Lean install-media builder |

## Commands

```bash
./smashdeck-launch --dev          # in-tree
python3 -m utils.bootstrap --force
python3 -m utils.hardware_checks
cd dashboard && python3 app.py
./scripts/make_release.sh --zip
```

## Conventions

- Data under `CYBERDECK_DATA` / XDG / `./data` via `utils/paths.py` (SmashDeck-named helpers).
- Prefer structured tool output; PID files in `data/pids/`.
- HCI BT actions only on HCI adapters; Ubertooth is passive.
- No comments unless needed; match existing style.
- aarch64 Pi OS target; passwordless sudo scoped via `packaging/sudoers.smashdeck`.
