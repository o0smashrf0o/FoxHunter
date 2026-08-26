# SmashDeck

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

1. Copy this folder (or a `dist/smashdeck-install-*` release) to the Pi.
2. Double-click **SmashDeck.desktop** (or run `./smashdeck-media-start`).
3. Follow the installer (admin password once).
4. Launch **SmashDeck** from the app menu afterward.

Install path: `/opt/smashdeck`  
User data: `~/.local/share/smashdeck/`

## Build install media (dev machine)

```bash
./scripts/make_release.sh
./scripts/make_release.sh --zip
```

## Dev launch (on Pi, in-tree)

```bash
./smashdeck-launch --dev
# dashboard only:
cd dashboard && python3 app.py   # http://localhost:8080
```

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
Inspired by field cyberdeck designs; SmashDeck is a clean-room rewrite.
