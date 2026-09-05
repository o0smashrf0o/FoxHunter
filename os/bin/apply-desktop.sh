#!/usr/bin/env bash
# Theme Pi OS + hook labwc so Fox Hunter is fullscreen on login.
set +e
if [[ ${EUID:-0} -ne 0 ]]; then echo "sudo $0" >&2; exit 1; fi

PREFIX="${FOXHUNTER_PREFIX:-/opt/foxhunter}"
BOOT=/boot/firmware
[[ -d "$BOOT" ]] || BOOT=/boot
USER_NAME="${SUDO_USER:-smash}"
id "$USER_NAME" >/dev/null 2>&1 || USER_NAME=smash
id "$USER_NAME" >/dev/null 2>&1 || USER_NAME=pi
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
SRC="$PREFIX/os/desktop"
[[ -d "$SRC" ]] || SRC="$BOOT/foxhunter-desktop"
echo "[desktop] theme  user=$USER_NAME"

# GTK
mkdir -p "$HOME_DIR/.config/gtk-3.0" "$HOME_DIR/.config/gtk-4.0"
if [[ -f "$SRC/gtk-3.0/gtk.css" ]]; then
  cp "$SRC/gtk-3.0/gtk.css" "$HOME_DIR/.config/gtk-3.0/gtk.css"
  cp "$SRC/gtk-3.0/gtk.css" "$HOME_DIR/.config/gtk-4.0/gtk.css"
fi
if [[ -f "$SRC/gtk-3.0/settings.ini" ]]; then
  cp "$SRC/gtk-3.0/settings.ini" "$HOME_DIR/.config/gtk-3.0/settings.ini"
  cp "$SRC/gtk-3.0/settings.ini" "$HOME_DIR/.config/gtk-4.0/settings.ini"
fi

# labwc user
mkdir -p "$HOME_DIR/.config/labwc"
for f in rc.xml themerc-override environment; do
  [[ -f "$SRC/labwc/$f" ]] && cp "$SRC/labwc/$f" "$HOME_DIR/.config/labwc/$f"
done

if [[ -f /etc/xdg/labwc/autostart.raspberry.bak ]]; then
  cp -a /etc/xdg/labwc/autostart.raspberry.bak /etc/xdg/labwc/autostart
fi
if [[ -f /etc/xdg/labwc/autostart ]]; then
  sed -i '/start-kiosk/d' /etc/xdg/labwc/autostart
fi
if [[ -f "$HOME_DIR/.config/labwc/autostart" ]]; then
  sed -i '/start-kiosk/d' "$HOME_DIR/.config/labwc/autostart"
fi
rm -f /etc/xdg/autostart/foxhunter-kiosk.desktop /etc/xdg/autostart/smashdeck-kiosk.desktop \
      "$HOME_DIR/.config/autostart/foxhunter-kiosk.desktop" "$HOME_DIR/.config/autostart/smashdeck-kiosk.desktop"

# panel theme if they exit kiosk
[[ -f "$SRC/wf-panel-pi.ini" ]] && cp "$SRC/wf-panel-pi.ini" "$HOME_DIR/.config/wf-panel-pi.ini"

chown -R "$USER_NAME:$USER_NAME" "$HOME_DIR/.config"
echo "[desktop] done"
