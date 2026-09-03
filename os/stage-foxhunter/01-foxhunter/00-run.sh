#!/bin/bash -e
# Copy Fox Hunter tree into the image and run apply-os in chroot.
SMASH_SRC="${FOXHUNTER_SRC:-}"
if [[ -z "$SMASH_SRC" ]]; then
  SMASH_SRC="$(cd "$(dirname "$0")/../../.." && pwd)"
fi
mkdir -p "${ROOTFS_DIR}/opt/foxhunter"
rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude 'dist' --exclude 'data' \
  --exclude '__pycache__' --exclude '.DS_Store' \
  "${SMASH_SRC}/" "${ROOTFS_DIR}/opt/foxhunter/"
chmod +x "${ROOTFS_DIR}/opt/foxhunter/os/apply-os.sh" \
         "${ROOTFS_DIR}/opt/foxhunter/os/bin/start-kiosk" \
         "${ROOTFS_DIR}/opt/foxhunter/os/bin/install-kismet.sh" \
         "${ROOTFS_DIR}/opt/foxhunter/os/bin/install-radio-stack.sh" \
         "${ROOTFS_DIR}/opt/foxhunter/foxhunter-kiosk" \
         "${ROOTFS_DIR}/opt/foxhunter/foxhunter-gui" || true
