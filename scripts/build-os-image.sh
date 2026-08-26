#!/usr/bin/env bash
# Build SmashDeck OS (.img) with pi-gen in Docker.
# Needs: Docker, ~20GB disk, 30–90 minutes. Linux host recommended.
# macOS Docker Desktop often fails (binfmt/loop). Build on a Linux box or the Pi.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OS="$ROOT/os"
WORK="${SMASHDECK_PIGEN:-$ROOT/dist/pi-gen}"
BRANCH="${PIGEN_BRANCH:-arm64}"

echo "[build-os] SmashDeck OS image"
echo "    source  $ROOT"
echo "    pi-gen  $WORK  (branch $BRANCH)"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker is required to build the image on this machine." >&2
  echo "On the Pi you already have, skip this and run:" >&2
  echo "  sudo $OS/apply-os.sh" >&2
  exit 1
fi

if [[ ! -d "$WORK/.git" ]]; then
  mkdir -p "$(dirname "$WORK")"
  git clone --depth 1 --branch "$BRANCH" https://github.com/RPi-Distro/pi-gen.git "$WORK"
fi

# Lite-only: skip desktop stages
touch "$WORK/stage3/SKIP" "$WORK/stage4/SKIP" "$WORK/stage5/SKIP" 2>/dev/null || true
touch "$WORK/stage4/SKIP_IMAGES" "$WORK/stage5/SKIP_IMAGES" 2>/dev/null || true
rm -f "$WORK/stage2/EXPORT_IMAGE" 2>/dev/null || true

# Custom stage (copy so pi-gen paths stay simple)
rm -rf "$WORK/stage-smashdeck"
cp -a "$OS/stage-smashdeck" "$WORK/stage-smashdeck"
chmod +x "$WORK/stage-smashdeck/prerun.sh" \
         "$WORK/stage-smashdeck/01-smashdeck/"*.sh 2>/dev/null || true

# Config: STAGE_LIST inside pi-gen tree
{
  cat "$OS/config"
  echo "STAGE_LIST=\"stage0 stage1 stage2 stage-smashdeck\""
} > "$WORK/config"

export SMASHDECK_SRC="$ROOT"
# 00-run.sh resolves SMASHDECK_SRC; also inject a pointer file
echo "$ROOT" > "$WORK/stage-smashdeck/01-smashdeck/SMASHDECK_SRC.txt"

# Rewrite 00-run.sh to read the copied tree from the host bind.
# pi-gen docker mounts the pi-gen dir, NOT SmashDeck. Stage 00-run copies from
# a files/ snapshot we drop in now.
STAGE_FILES="$WORK/stage-smashdeck/01-smashdeck/files"
rm -rf "$STAGE_FILES"
mkdir -p "$STAGE_FILES"
rsync -a --delete \
  --exclude '.git' --exclude '.venv' --exclude 'dist' --exclude 'data' \
  --exclude '__pycache__' --exclude '.DS_Store' \
  "$ROOT/" "$STAGE_FILES/"

cat > "$WORK/stage-smashdeck/01-smashdeck/00-run.sh" <<'RUN'
#!/bin/bash -e
SRC="$(dirname "$0")/files"
mkdir -p "${ROOTFS_DIR}/opt/smashdeck"
rsync -a --delete "${SRC}/" "${ROOTFS_DIR}/opt/smashdeck/"
chmod +x "${ROOTFS_DIR}/opt/smashdeck/os/apply-os.sh" \
         "${ROOTFS_DIR}/opt/smashdeck/os/bin/start-kiosk" \
         "${ROOTFS_DIR}/opt/smashdeck/smashdeck-kiosk" \
         "${ROOTFS_DIR}/opt/smashdeck/smashdeck-gui" || true
RUN
chmod +x "$WORK/stage-smashdeck/01-smashdeck/00-run.sh"

cd "$WORK"
echo "[build-os] starting pi-gen docker build…"
./build-docker.sh
echo "[build-os] images in $WORK/deploy"
ls -lh "$WORK/deploy" || true
