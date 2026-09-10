# Fox Hunter

Portable Raspberry Pi 4 RF / wireless survey & analysis deck.

Touch-first dashboard for Wi‑Fi, Bluetooth, SDR spectrum, TSCM detect, and tool launch.
GUI install — double-click, enter admin password once, go.

## Hardware (typical)

- RPi 4 (4GB+) + 7" touchscreen, 64-bit Pi OS
- Wi‑Fi: Alfa AC600 / Panda PAU06 (monitor + inject)
- Bluetooth: UD100 (HCI) + optional Ubertooth (passive)
- SDR: RTL-SDR and/or LimeSDR Mini
- Powered USB 3 hub (required)

## Quick start (Pi)

1. Copy this folder (or a `dist/foxhunter-install-*` release) to the Pi.
2. Double-click **FoxHunter.desktop** (or run `./foxhunter-media-start`).
3. Follow the installer (admin password once). Kismet is installed here.
4. Optional: set a HUD password when asked, or skip.
5. Launch **Fox Hunter** from the app menu afterward.

Install path: `/opt/foxhunter`  
User data: `~/.local/share/foxhunter/`

## Build install media (dev machine)

```bash
./scripts/make_release.sh
./scripts/make_release.sh --zip
```

## Dev launch (on Pi, in-tree)

```bash
./foxhunter-launch --dev
# dashboard only:
cd dashboard && python3 app.py   # http://localhost:8080
```

[Development Workflow](docs/development-workflow.md) — full cycle from clone to release.

## Features

| Area | Capabilities |
|------|----------------|
| Wi‑Fi | Live scan, Kismet survey, monitor mode, deauth/handshake (authorized only) |
| Bluetooth | HCI scan, device actions, **Blue Sonar** RSSI track, Ubertooth via Kismet |
| Detect | Camera / Flock / rogue AP / trackers / drone RID / scout (capability-gated) |
| Spectrum | RTL power / live FFT baseline (SDR) |
| Tools | nmap, nuclei, and extensible tool registry |

## Legal

Use only on networks and systems you own or have written authorization to test.
RF transmit is regulated — stay legal.

## Credits

Blue Sonar: [ZeroChaos-/blue_sonar](https://github.com/ZeroChaos-/blue_sonar) (BSD-2-Clause).
Inspired by field cyberdeck designs; Fox Hunter is a clean-room rewrite.
