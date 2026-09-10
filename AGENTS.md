# AGENTS.md — Fox Hunter

Portable RPi4 RF/wireless deck. Clean architecture, touch dashboard, GUI install.

## Layout

| Path | Role |
|------|------|
| `./foxhunter-gui` | End-user entry: install / update / launch |
| `./foxhunter-launch` | Dev bootstrap → dashboard → kiosk |
| `./foxhunter-media-start` | USB/media double-click helper |
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
./foxhunter-launch --dev          # in-tree
python3 -m utils.bootstrap --force
python3 -m utils.hardware_checks
cd dashboard && python3 app.py
./scripts/make_release.sh --zip
```

## Conventions

- Data under `CYBERDECK_DATA` / XDG / `./data` via `utils/paths.py` (Fox Hunter-named helpers).
- Prefer structured tool output; PID files in `data/pids/`.
- HCI BT actions only on HCI adapters; Ubertooth is passive.
- No comments unless needed; match existing style.
- aarch64 Pi OS target; passwordless sudo scoped via `packaging/sudoers.foxhunter`.

## Git

- Branch naming: `feature/*` for new capabilities, `bugfix/*` for repairs, `hotfix/*` for production-critical fixes.
- Commit messages: `type: concise description` where type is one of `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`.
- PR requirement: must pass `scripts/test.sh` and `scripts/lint.sh` locally; squash merge only.
- Conventional commits encouraged; `git commit -m "feat: add new detector"` format.

## OpenCode

- Agent configuration resides in `~/.config/opencode/`.
- Prohibited actions: no sudo command execution, no Raspberry Pi deployment from this agent, no writing to `/opt/foxhunter` or `/data/`.
- Respect `packaging/sudoers.foxhunter` scope — only the 30 listed commands are passwordless.
- Respect data-handling rules: `data/` is runtime-generated, never commit scan outputs, DB files, or pcap captures.
- Definition of Done (per AGENTS.md): unit tests pass, lint passes, hardware checks run, no new `/data/` files, docstrings updated, `make_release.sh --zip` produces clean zip.

## Local testing

- Run `scripts/test.sh` to invoke pytest (or no-op if no tests/ directory exists).
- Run `scripts/lint.sh` to invoke mypy or per-file syntax validation.
- Coverage target: minimum 80% on any newly added test modules.

## Raspberry Pi hardware validation

- Run `python3 -m utils.hardware_checks` to verify required tools (python3, iw, ip, rfkill, kismet, nmap).
- Capability gate checks against `config/tool_capabilities.yaml` (camera_detect, flock_detect, rogue_ap_detect, tracker_detect, ble_inspector, drone_rid_detect, device_scout, spectrum_baseline).
- Required dongles: Wi‑Fi Alfa/ Panda (monitor + inject), Bluetooth UD100 + optional Ubertooth, SDR RTL-SDR / LimeSDR Mini.
- Ubertooth is passive only — no transmit.

## Deployment

- In-tree dev: `./foxhunter-launch --dev` launches Flask on `:8080` + kiosk.
- Release media: `./scripts/make_release.sh --zip` produces clean zip from repo.
- Install path: `/opt/foxhunter`; user data: `~/.local/share/foxhunter/`.
- After media build, test installed: `./foxhunter-gui --install`.
- Verify zip excludes `.venv`, `/data`, `/dist`, and includes `config/`, `scripts/`, `docs/`, `packaging/`.

## Privileged-file handling

- Scoped passwordless sudo via `packaging/sudoers.foxhunter` — 30 commands only (ip, iw, rfkill, aircrack-ng, kismet, blue_sonar, nmcli, bluetoothctl, l2ping, hcitool, hciconfig, timeout, and others).
- `askpass-zenity.sh` protocol: admin password entered once via zenity GUI, cached in memory only.
- Never hardcode sudo credentials; all commands are explicitly whitelisted.
- If a required command is missing from the whitelist, add it to `packaging/sudoers.foxhunter` with justification.

## Data-handling

- `data/` directory is runtime-generated — findings.db, logs, pcap, spectrum, wifi_scan, bt_scan, creds, exports, kismet, maps, hunt.
- Never commit files under `data/` to version control.
- `findings.db` is an SQLite store — .gitignore excludes it via `/data/` catch-all.
- `CYBERDECK_DATA` environment variable respected for custom data paths.
- Export formats (JSON/CSV) are opt-in and reviewed before release.

## Definition of Done

For any feature or fix to be considered complete:

1. `scripts/test.sh` passes (or no tests directory exists with a noted message).
2. `scripts/lint.sh` passes (mypy or per-file syntax validation).
3. `python3 -m utils.hardware_checks` runs without fatal errors for the relevant domain.
4. No new files added under `data/`.
5. Docstrings updated for any new public functions/modules.
6. `make_release.sh --zip` produces a clean zip (verified by inspecting contents).
7. AGENTS.md conventions followed (Git commit message format, no unnecessary comments).
8. Documentation updated (docs/development-workflow.md and/or docs/test-log.md as appropriate).
