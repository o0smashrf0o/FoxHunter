#!/bin/bash
# sudo bash /boot/firmware/foxhunter-boot.sh
set +e
if [ "$(id -u)" -ne 0 ]; then echo "Run: sudo bash $0" >&2; exit 1; fi
BOOT=/boot/firmware
[ -f "$BOOT/foxhunter-boot.sh" ] || BOOT=/boot
PREFIX=/opt/foxhunter
mkdir -p "$PREFIX/os/bin" "$PREFIX/os/desktop" "$PREFIX/os/plymouth" "$PREFIX/os/xdg"

copy() { [ -f "$1" ] && cp "$1" "$2" && chmod +x "$2" 2>/dev/null; true; }
copy "$BOOT/start-kiosk" "$PREFIX/os/bin/start-kiosk"
copy "$BOOT/apply-desktop.sh" "$PREFIX/os/bin/apply-desktop.sh"
copy "$BOOT/foxhunter-kiosk" "$PREFIX/foxhunter-kiosk"
copy "$BOOT/labwc-autostart" "$PREFIX/os/xdg/labwc-autostart"
[ -d "$BOOT/foxhunter-desktop" ] && cp -a "$BOOT/foxhunter-desktop/." "$PREFIX/os/desktop/"

# --- splash: kill text theme, use PNG ---
if [ -f "$BOOT/splash.png" ]; then
  mkdir -p /usr/share/plymouth/themes/pix
  cp "$BOOT/splash.png" /usr/share/plymouth/themes/pix/splash.png
  cp "$BOOT/splash.png" /usr/share/rpd-wallpaper/foxhunter-splash.png 2>/dev/null
  mkdir -p /usr/share/rpd-wallpaper
  cp "$BOOT/splash.png" /usr/share/rpd-wallpaper/foxhunter-splash.png
fi
# remove old TEXT plymouth theme so it cannot show "FOXHUNTER OS"
rm -rf /usr/share/plymouth/themes/foxhunter
mkdir -p /etc/plymouth
cat > /etc/plymouth/plymouthd.conf <<'EOF'
[Daemon]
Theme=pix
ShowDelay=0
EOF
plymouth-set-default-theme pix 2>/dev/null
plymouth-set-default-theme -R pix 2>/dev/null
update-initramfs -u

bash "$PREFIX/os/bin/apply-desktop.sh"
sync
echo "[foxhunter] rebooting"
reboot
