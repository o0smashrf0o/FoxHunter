#!/usr/bin/env bash
# Run ON the Pi: sudo /opt/smashdeck/os/bin/fix-boot.sh
# Replaces Raspberry splash, sets wallpaper, fixes kiosk autostart.
set -euo pipefail
if [[ ${EUID:-0} -ne 0 ]]; then
  echo "sudo $0" >&2
  exit 1
fi

PREFIX="${SMASHDECK_PREFIX:-/opt/smashdeck}"
USER_NAME="${SUDO_USER:-smash}"
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6 || echo /home/smash)"
ART="$PREFIX/dashboard/static/img/fox-hunter.jpg"
SPLASH_SRC="$PREFIX/os/plymouth/splash.png"
PIX=/usr/share/plymouth/themes/pix
DEST=/usr/share/plymouth/themes/smashdeck

echo "[fix-boot] user=$USER_NAME prefix=$PREFIX"

# --- splash PNG ---
mkdir -p "$DEST"
if [[ -f "$SPLASH_SRC" ]]; then
  cp "$SPLASH_SRC" "$DEST/splash.png"
elif [[ -f "$ART" ]]; then
  python3 - <<PY
import sys
src, dst = "$ART", "$DEST/splash.png"
try:
    import gi
    gi.require_version("GdkPixbuf", "2.0")
    from gi.repository import GdkPixbuf
    GdkPixbuf.Pixbuf.new_from_file(src).savev(dst, "png", [], [])
except Exception:
    try:
        from PIL import Image
        Image.open(src).save(dst)
    except Exception as e:
        sys.exit("cannot convert splash: %s" % e)
PY
else
  echo "No splash art found" >&2
  exit 1
fi
cp "$DEST/splash.png" "$DEST/splash.png"
if [[ -d "$PIX" ]]; then
  cp -a "$PIX/splash.png" "$PIX/splash.png.bak" 2>/dev/null || true
  cp "$DEST/splash.png" "$PIX/splash.png"
  echo "[fix-boot] replaced Raspberry pix splash"
fi
if [[ -f "$PREFIX/os/plymouth/smashdeck.plymouth" ]]; then
  cp "$PREFIX/os/plymouth/smashdeck.plymouth" "$DEST/"
  cp "$PREFIX/os/plymouth/smashdeck.script" "$DEST/"
fi
mkdir -p /etc/plymouth
cat > /etc/plymouth/plymouthd.conf <<'EOF'
[Daemon]
Theme=pix
ShowDelay=0
EOF
# pix is already in initramfs — replacing splash.png is enough once initrd rebuilds
if command -v plymouth-set-default-theme >/dev/null 2>&1; then
  plymouth-set-default-theme pix || true
fi
if command -v update-initramfs >/dev/null 2>&1; then
  echo "[fix-boot] rebuilding initramfs (splash)…"
  update-initramfs -u || true
fi

# firmware rainbow off + plymouth on
for cfg in /boot/firmware/config.txt /boot/config.txt; do
  [[ -f "$cfg" ]] || continue
  grep -q '^disable_splash=' "$cfg" || echo 'disable_splash=1' >> "$cfg"
  sed -i 's/^disable_splash=.*/disable_splash=1/' "$cfg"
done
for cmd in /boot/firmware/cmdline.txt /boot/cmdline.txt; do
  [[ -f "$cmd" ]] || continue
  grep -q 'splash' "$cmd" || sed -i 's/$/ quiet splash logo.nologo vt.global_cursor_default=0/' "$cmd"
  grep -q 'logo.nologo' "$cmd" || sed -i 's/$/ logo.nologo/' "$cmd"
done

# --- wallpaper ---
if [[ -f "$ART" ]]; then
  mkdir -p "$HOME_DIR/.config/pcmanfm/LXDE-pi"
  cat > "$HOME_DIR/.config/pcmanfm/LXDE-pi/desktop-items-0.conf" <<EOF
[*]
wallpaper_mode=crop
wallpaper=$ART
desktop_bg=#07060f
desktop_fg=#b8ff2a
show_documents=0
show_trash=0
show_mounts=0
EOF
  chown -R "$USER_NAME:$USER_NAME" "$HOME_DIR/.config/pcmanfm"
  echo "[fix-boot] wallpaper set"
fi

# --- kiosk: epiphany URL not --application-mode ---
KIOSK="$PREFIX/os/bin/start-kiosk"
if [[ -f "$KIOSK" ]]; then
  sed -i 's/--application-mode/--new-window/g' "$KIOSK"
  chmod +x "$KIOSK"
fi
mkdir -p /etc/xdg/autostart "$HOME_DIR/.config/autostart" "$HOME_DIR/.config/labwc"
cat > /etc/xdg/autostart/smashdeck-kiosk.desktop <<EOF
[Desktop Entry]
Type=Application
Name=SmashDeck Kiosk
Exec=/usr/bin/env GTK_A11Y=none $PREFIX/os/bin/start-kiosk
X-GNOME-Autostart-enabled=true
EOF
cp /etc/xdg/autostart/smashdeck-kiosk.desktop "$HOME_DIR/.config/autostart/"
# Pi OS labwc does not always honor xdg autostart — hook it
touch "$HOME_DIR/.config/labwc/autostart"
if ! grep -q start-kiosk "$HOME_DIR/.config/labwc/autostart" 2>/dev/null; then
  echo "GTK_A11Y=none $PREFIX/os/bin/start-kiosk &" >> "$HOME_DIR/.config/labwc/autostart"
fi
chown -R "$USER_NAME:$USER_NAME" "$HOME_DIR/.config/autostart" "$HOME_DIR/.config/labwc"

echo "[fix-boot] done. Reboot:"
echo "  sudo reboot"
