# Fox Hunter OS

Raspberry Pi OS (Debian) + Fox Hunter + WebKit kiosk.
Not a kernel fork — a branded image / convert script.

Linux user is created on first boot (Pi wizard). Fox Hunter HUD password is optional at install.

## Convert the Pi you already have (fast)

On the Pi, from the Fox Hunter tree:

```bash
sudo ./os/apply-os.sh
sudo reboot
```

This sets hostname `foxhunter`, boot splash, dashboard systemd service,
and fullscreen kiosk on login.

## Flashable image (slow)

On a **Linux** machine with Docker (~20GB, 30–90 min):

```bash
./scripts/build-os-image.sh
```

Flash `dist/pi-gen/deploy/FoxHunterOS-*.img` (or `.zip`) with Raspberry Pi Imager.

macOS Docker Desktop usually cannot build pi-gen (loop devices / binfmt).
Use a Linux VM, another Pi, or the apply script.

## What boots

1. Plymouth splash — **FOXHUNTER OS**
2. Autologin `smash`
3. `foxhunter-dashboard` on `:8080`
4. WebKit kiosk (Epiphany/GTK), Chromium only if WebKit is missing

Esc leaves the kiosk. `sudo systemctl status foxhunter-dashboard`
