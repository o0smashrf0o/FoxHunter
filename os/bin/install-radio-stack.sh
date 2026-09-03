#!/usr/bin/env bash
# Broad RF stack — not limited to one vendor. Safe to re-run.
# On the Pi:  sudo bash /opt/foxhunter/os/bin/install-radio-stack.sh
set -euo pipefail
if [[ ${EUID:-0} -ne 0 ]]; then
  echo "sudo $0" >&2
  exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -y

install_group() {
  echo "[radio] apt: $*"
  apt-get install -y --no-install-recommends "$@" || true
}

install_group \
  iw wireless-tools rfkill net-tools usbutils \
  bluez bluez-tools \
  aircrack-ng nmap \
  dkms build-essential raspberrypi-kernel-headers linux-headers-generic

install_group firmware-realtek firmware-mediatek firmware-atheros \
  firmware-misc-nonfree firmware-linux-nonfree bluez-firmware

install_group rtl-sdr librtlsdr-dev rtl-433
install_group hackrf libhackrf0 libhackrf-dev
install_group soapysdr-tools soapysdr-module-rtlsdr soapysdr-module-hackrf
install_group realtek-rtl88xxau-dkms || true

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$SCRIPT_DIR/install-kismet.sh" ]]; then
  bash "$SCRIPT_DIR/install-kismet.sh"
else
  apt-get install -y kismet || true
fi

if [[ -f /opt/foxhunter/config/99-foxhunter.rules ]]; then
  cp /opt/foxhunter/config/99-foxhunter.rules /etc/udev/rules.d/99-foxhunter.rules
  udevadm control --reload-rules || true
  udevadm trigger || true
fi

usermod -aG plugdev,dialout,netdev "${SUDO_USER:-smash}" 2>/dev/null || true

echo "[radio] lsusb:"
lsusb || true
echo "[radio] iw dev:"
iw dev || true
echo "[radio] hci:"
hciconfig -a 2>/dev/null || bluetoothctl list || true
echo "[radio] SDR bins:"
command -v rtl_test && echo "  rtl_test OK" || echo "  rtl_test missing"
command -v hackrf_info && echo "  hackrf_info OK" || echo "  hackrf_info missing"
command -v SoapySDRUtil && echo "  SoapySDRUtil OK" || echo "  SoapySDRUtil missing"
echo "[radio] done — replug dongles if they were already inserted"
