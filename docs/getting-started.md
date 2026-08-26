# SmashDeck — Getting Started

## Requirements
- Raspberry Pi 4, **64-bit** Raspberry Pi OS
- Internet on first install
- Powered USB hub for dongles

## Install
1. Build media on a dev machine: `./scripts/make_release.sh --zip`
2. Copy `dist/smashdeck-install-*` to the Pi
3. Double-click **SmashDeck.desktop**
4. Enter admin password once

## Dev
```bash
./smashdeck-launch --dev
# or
cd dashboard && python3 app.py
```

## Blue Sonar
HCI Bluetooth adapter → BT tab → scan → device → **Blue Sonar**.
