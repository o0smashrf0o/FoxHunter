#!/usr/bin/env bash
# Install Kismet for Fox Hunter. Safe to re-run.
#   sudo bash /opt/foxhunter/os/bin/install-kismet.sh
set -uo pipefail

if [[ ${EUID:-0} -ne 0 ]]; then
  echo "sudo $0" >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
USER_NAME="${FOXHUNTER_USER:-${SUDO_USER:-smash}}"
KEYRING=/usr/share/keyrings/kismet-archive-keyring.gpg
LIST=/etc/apt/sources.list.d/kismet.list
KEY_URL=https://www.kismetwireless.net/repos/kismet-release.gpg.key

log() { echo "[kismet-install] $*"; }

have_kismet() {
  command -v kismet >/dev/null 2>&1 || [[ -x /usr/bin/kismet ]]
}

preseed() {
  if command -v debconf-set-selections >/dev/null 2>&1; then
    debconf-set-selections <<'EOF' || true
kismet-capture-common kismet-capture-common/install-setuid boolean true
kismet-capture-common kismet-capture-common/install-users string kismet
kismet kismet/install-setuid boolean true
kismet kismet/install-users string kismet
EOF
  fi
}

apt_try_kismet() {
  apt-get install -y kismet
}

add_official_repo() {
  local kind="$1" codename="$2"
  log "Adding Kismet $kind repo ($codename)"
  apt-get install -y --no-install-recommends ca-certificates gnupg wget curl >/dev/null 2>&1 || true
  mkdir -p /usr/share/keyrings
  if command -v wget >/dev/null 2>&1; then
    wget -O - "$KEY_URL" --quiet | gpg --dearmor > "$KEYRING"
  else
    curl -fsSL "$KEY_URL" | gpg --dearmor > "$KEYRING"
  fi
  echo "deb [signed-by=${KEYRING}] https://www.kismetwireless.net/repos/apt/${kind}/${codename} ${codename} main" > "$LIST"
  apt-get update -y
}

finish() {
  groupadd -f kismet || true
  if id "$USER_NAME" >/dev/null 2>&1; then
    usermod -aG kismet,plugdev "$USER_NAME" || true
  fi
  log "Kismet: $(command -v kismet || echo /usr/bin/kismet)"
  kismet --version 2>/dev/null | head -n 1 || true
}

if have_kismet; then
  log "Already installed"
  finish
  exit 0
fi

log "Installing Kismet"
apt-get update -y || true
preseed
if apt_try_kismet && have_kismet; then
  finish
  exit 0
fi

debian_codename() {
  local v="" c=""
  [[ -f /etc/debian_version ]] && v=$(cat /etc/debian_version)
  case "$v" in
    13*|trixie*) c=trixie ;;
    12*|bookworm*) c=bookworm ;;
    11*|bullseye*) c=bullseye ;;
  esac
  if [[ -z "$c" ]]; then
    . /etc/os-release 2>/dev/null || true
    case "${VERSION_CODENAME:-}" in
      trixie|bookworm|bullseye|jammy|noble) c=$VERSION_CODENAME ;;
    esac
  fi
  echo "${c:-trixie}"
}
CODENAME="$(debian_codename)"
CODES=()
for c in "$CODENAME" trixie bookworm; do
  skip=0
  for e in "${CODES[@]+"${CODES[@]}"}"; do
    [[ "$e" == "$c" ]] && skip=1
  done
  [[ $skip -eq 1 ]] || CODES+=("$c")
done

for kind in release git; do
  for code in "${CODES[@]}"; do
    add_official_repo "$kind" "$code" || continue
    preseed
    if apt_try_kismet && have_kismet; then
      finish
      exit 0
    fi
  done
done

log "FAILED: kismet binary not found"
exit 1
