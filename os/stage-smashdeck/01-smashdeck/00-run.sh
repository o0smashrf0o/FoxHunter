#!/bin/bash -e
# Copy SmashDeck tree into the image and run apply-os in chroot.
SMASH_SRC="${SMASHDECK_SRC:-}"
if [[ -z "$SMASH_SRC" ]]; then
  SMASH_SRC="$(cd "$(dirname "$0")/../../.." && pwd)"
fi
mkdir -p "${ROOTFS_DIR}/opt/smashdeck"
rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude 'dist' --exclude 'data' \
  --exclude '__pycache__' --exclude '.DS_Store' \
  "${SMASH_SRC}/" "${ROOTFS_DIR}/opt/smashdeck/"
chmod +x "${ROOTFS_DIR}/opt/smashdeck/os/apply-os.sh" \
         "${ROOTFS_DIR}/opt/smashdeck/os/bin/start-kiosk" \
         "${ROOTFS_DIR}/opt/smashdeck/smashdeck-kiosk" \
         "${ROOTFS_DIR}/opt/smashdeck/smashdeck-gui" || true
