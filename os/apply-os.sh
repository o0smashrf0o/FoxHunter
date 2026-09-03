#!/usr/bin/env bash
# Convert a running Raspberry Pi OS install into Fox Hunter OS.
# Run on the Pi:  sudo /opt/foxhunter/os/apply-os.sh
#             or: sudo ./os/apply-os.sh   (from a Fox Hunter tree)
set -euo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "Run as root: sudo $0" >&2
  exit 1
fi

HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
PREFIX="${FOXHUNTER_PREFIX:-${SMASHDECK_PREFIX:-}}"
if [[ -z "$PREFIX" ]]; then
  if [[ -d /opt/foxhunter ]]; then PREFIX=/opt/foxhunter
  elif [[ -d /opt/smashdeck ]]; then PREFIX=/opt/smashdeck
  else PREFIX=/opt/foxhunter
  fi
fi
USER_NAME="${SUDO_USER:-${FOXHUNTER_USER:-smash}}"
if ! id "$USER_NAME" >/dev/null 2>&1; then
  if id smash >/dev/null 2>&1; then USER_NAME=smash
  elif id pi >/dev/null 2>&1; then USER_NAME=pi
  else
    echo "No smash/pi user found. Set FOXHUNTER_USER=..." >&2
    exit 1
  fi
fi
HOME_DIR="$(getent passwd "$USER_NAME" | cut -d: -f6)"
VERSION="$(tr -d '[:space:]' < "$ROOT/VERSION" 2>/dev/null || echo 0.1.0)"

log() { echo "[foxhunter-os] $*"; }

apt_install() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update -y
  apt-get install -y --no-install-recommends "$@"
}

install_runtime_pkgs() {
  log "Installing OS / kiosk packages"
  local pkgs=(
    python3-venv python3-pip python3-dev python3-yaml python3-gi
    gir1.2-gtk-3.0
    xserver-xorg xinit openbox unclutter
    plymouth plymouth-themes
    curl wget rsync unzip
    iw wireless-tools rfkill net-tools
    bluez bluez-tools aircrack-ng nmap
    rtl-sdr librtlsdr-dev
    zenity policykit-1
    usbutils hackrf rtl-sdr
  )
  apt_install "${pkgs[@]}" || true
  apt-get install -y --no-install-recommends gir1.2-webkit2-4.1 || \
    apt-get install -y --no-install-recommends gir1.2-webkit2-4.0 || true
  apt-get install -y --no-install-recommends epiphany-browser || true
  bash "$HERE/bin/install-kismet.sh" || {
    log "ERROR: Kismet install failed — Wi-Fi Continuous will not work"
    return 1
  }
}

ensure_foxhunter_tree() {
  if [[ ! -f "$PREFIX/dashboard/app.py" ]]; then
    log "Installing Fox Hunter into $PREFIX"
    python3 "$ROOT/packaging/privileged_setup.py" install --source "$ROOT" --user "$USER_NAME" --replace
  fi
  mkdir -p "$PREFIX/os"
  rsync -a --delete "$HERE/" "$PREFIX/os/"
  chmod +x "$PREFIX/os/bin/start-kiosk" "$PREFIX/os/apply-os.sh" "$PREFIX/foxhunter-kiosk" 2>/dev/null || true
}

brand_os() {
  log "Branding as Fox Hunter OS $VERSION"
  hostnamectl set-hostname foxhunter || echo foxhunter > /etc/hostname
  if ! grep -q foxhunter /etc/hosts; then
    sed -i 's/127.0.1.1.*/127.0.1.1\tfoxhunter/' /etc/hosts || \
      echo -e "127.0.1.1\tfoxhunter" >> /etc/hosts
  fi
  cp "$HERE/overlay/issue" /etc/issue
  cp "$HERE/overlay/motd" /etc/motd
  local debian_code=trixie
  if [[ -f /etc/debian_version ]]; then
    case "$(cat /etc/debian_version)" in
      12*|bookworm*) debian_code=bookworm ;;
      13*|trixie*) debian_code=trixie ;;
      11*|bullseye*) debian_code=bullseye ;;
    esac
  fi
  cat > /etc/os-release <<EOF
PRETTY_NAME="Fox Hunter OS ${VERSION}"
NAME="Fox Hunter OS"
VERSION_ID="${VERSION}"
VERSION="${VERSION} (Fox Hunter)"
VERSION_CODENAME=${debian_code}
ID=debian
ID_LIKE=debian
HOME_URL="https://github.com/o0smashrf0o/SmashDeck"
SUPPORT_URL="https://github.com/o0smashrf0o/SmashDeck/issues"
BUG_REPORT_URL="https://github.com/o0smashrf0o/SmashDeck/issues"
VARIANT="Fox Hunter"
VARIANT_ID=foxhunter
EOF
  echo "Fox Hunter OS ${VERSION}" > /etc/foxhunter-os-version
}

install_plymouth() {
  log "Boot splash"
  bash "$HERE/bin/fix-boot.sh" || true
}

install_services() {
  log "Dashboard + kiosk autostart (user=$USER_NAME)"
  local unit=/etc/systemd/system/foxhunter-dashboard.service
  sed "s/User=smash/User=${USER_NAME}/; s/Group=smash/Group=${USER_NAME}/; s|/home/smash|${HOME_DIR}|g" \
    "$HERE/systemd/foxhunter-dashboard.service" > "$unit"
  # venv python may not exist yet — fall back
  if [[ ! -x "$PREFIX/.venv/bin/python" ]]; then
    sed -i "s|$PREFIX/.venv/bin/python|/usr/bin/python3|" "$unit"
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl daemon-reload || true
    systemctl enable foxhunter-dashboard.service || true
    if [[ -d /run/systemd/system ]]; then
      systemctl restart foxhunter-dashboard.service || systemctl start foxhunter-dashboard.service || true
    fi
  fi

  mkdir -p /etc/xdg/autostart "$HOME_DIR/.config/autostart"
  sed "s|/opt/foxhunter|$PREFIX|g" "$HERE/autostart/foxhunter-kiosk.desktop" \
    > /etc/xdg/autostart/foxhunter-kiosk.desktop
  cp /etc/xdg/autostart/foxhunter-kiosk.desktop "$HOME_DIR/.config/autostart/"
  chown -R "$USER_NAME:$USER_NAME" "$HOME_DIR/.config/autostart"

  mkdir -p /etc/systemd/system/getty@tty1.service.d
  cat > /etc/systemd/system/getty@tty1.service.d/autologin.conf <<EOF
[Service]
ExecStart=
ExecStart=-/sbin/agetty --autologin ${USER_NAME} --noclear %I \$TERM
EOF

  # Lite (no display manager): start X on tty1
  if [[ ! -d /usr/share/xsessions ]] && ! systemctl is-enabled lightdm >/dev/null 2>&1 \
     && ! systemctl is-enabled gdm3 >/dev/null 2>&1; then
    local profile="$HOME_DIR/.bash_profile"
    if [[ ! -f "$profile" ]] || ! grep -q startx "$profile" 2>/dev/null; then
      cat >> "$profile" <<'EOF'

if [ -z "$DISPLAY" ] && [ "$(tty)" = "/dev/tty1" ]; then
  exec startx /opt/foxhunter/os/x11/xinitrc -- -keeptty >/tmp/foxhunter-x.log 2>&1
fi
EOF
      chown "$USER_NAME:$USER_NAME" "$profile"
    fi
    cp "$HERE/x11/xinitrc" "$PREFIX/os/x11/xinitrc"
    chmod +x "$PREFIX/os/x11/xinitrc"
  fi

  # Desktop: autologin graphical session if lightdm exists
  if [[ -d /etc/lightdm ]]; then
    mkdir -p /etc/lightdm/lightdm.conf.d
    cat > /etc/lightdm/lightdm.conf.d/90-foxhunter.conf <<EOF
[Seat:*]
autologin-user=${USER_NAME}
autologin-user-timeout=0
EOF
  fi

  mkdir -p "$HOME_DIR/.config/labwc"
  if [[ -f "$HOME_DIR/.config/labwc/autostart" ]] && grep -q start-kiosk "$HOME_DIR/.config/labwc/autostart"; then
    :
  else
    echo "GTK_A11Y=none $PREFIX/os/bin/start-kiosk &" >> "$HOME_DIR/.config/labwc/autostart"
  fi
  chown -R "$USER_NAME:$USER_NAME" "$HOME_DIR/.config/labwc"
}

groups_and_perms() {
  groupadd -f foxhunter_ops
  groupadd -f plugdev
  groupadd -f dialout
  groupadd -f kismet || true
  usermod -aG foxhunter_ops,plugdev,dialout,netdev,video,input,kismet "$USER_NAME" || true
}

log "Fox Hunter OS apply  version=$VERSION  user=$USER_NAME  prefix=$PREFIX"
install_runtime_pkgs
ensure_foxhunter_tree
brand_os
install_plymouth
groups_and_perms
install_services
bash "$HERE/bin/apply-desktop.sh" || true

log "Done. Reboot to boot into Fox Hunter OS."
log "  sudo reboot"
echo
echo "After reboot you should get:"
echo "  - hostname: foxhunter"
echo "  - splash:   FOXHUNTER OS"
echo "  - kiosk:    fullscreen HUD at :8080"
echo "Esc leaves the kiosk. Dashboard stays up as a service."
