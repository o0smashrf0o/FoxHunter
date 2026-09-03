#!/usr/bin/env bash
# Build clean Fox Hunter install media.
# Usage: ./scripts/make_release.sh [--zip]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
VERSION="$(tr -d '[:space:]' < VERSION 2>/dev/null || echo 0.0.0)"
DO_ZIP=0
OUT_BASE="$ROOT/dist"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --zip) DO_ZIP=1; shift ;;
    --out) OUT_BASE="${2:?}"; shift 2 ;;
    -h|--help) echo "Usage: $0 [--zip]"; exit 0 ;;
    *) echo "Unknown: $1" >&2; exit 2 ;;
  esac
done
NAME="foxhunter-install-${VERSION}"
DEST="${OUT_BASE}/${NAME}"
mkdir -p "$OUT_BASE"
rm -rf "$DEST"
mkdir -p "$DEST"
echo "[make_release] → $DEST"

python3 -c "import sys; from pathlib import Path; sys.path.insert(0,'.'); from packaging.heal_media_desktop import heal_media_launchers; print(heal_media_launchers(Path('.')))" || true

EXCLUDES=(
  --exclude='.git' --exclude='.venv' --exclude='__pycache__' --exclude='*.pyc'
  --exclude='/data' --exclude='/dist'
  --exclude='.bootstrap_complete' --exclude='.DS_Store' --exclude='**/.DS_Store'
)
if command -v rsync >/dev/null 2>&1; then
  rsync -a "${EXCLUDES[@]}" "$ROOT/" "$DEST/"
else
  tar -C "$ROOT" --exclude='.git' --exclude='.venv' --exclude='__pycache__' \
    --exclude='./data' --exclude='./dist' --exclude='.DS_Store' -cf - . | tar -C "$DEST" -xf -
fi
rm -rf "$DEST/data" "$DEST/dist" "$DEST/.venv" 2>/dev/null || true

# ensure OUI
if [[ ! -f "$DEST/config/data/oui.sqlite" && -f "$ROOT/config/data/oui.sqlite" ]]; then
  mkdir -p "$DEST/config/data"
  rsync -a "$ROOT/config/data/" "$DEST/config/data/" 2>/dev/null || cp -a "$ROOT/config/data/." "$DEST/config/data/"
fi

python3 - <<PY
import sys
from pathlib import Path
dest = Path("$DEST")
sys.path.insert(0, str(dest))
from packaging.heal_media_desktop import heal_media_launchers
print(heal_media_launchers(dest))
for name in ("foxhunter-gui", "foxhunter-launch", "foxhunter-media-start", "FoxHunter.desktop"):
    p = dest / name
    if p.is_file():
        p.chmod(p.stat().st_mode | 0o755)
bs = dest / "third_party" / "blue_sonar" / "blue_sonar"
if bs.is_file():
    bs.chmod(bs.stat().st_mode | 0o755)
PY

cat > "$DEST/INSTALL.txt" <<TXT
Fox Hunter ${VERSION} — install media
====================================
1. Copy this folder to a Raspberry Pi 4 (64-bit Pi OS).
2. Double-click Fox Hunter.desktop (Allow Launching if asked).
   Or: ./foxhunter-media-start
3. Enter admin password once; wait for install.
4. Later: use Fox Hunter from the application menu.

Install: /opt/foxhunter
Data:    ~/.local/share/foxhunter/
TXT
cp "$DEST/INSTALL.txt" "$DEST/README-USB.txt"
echo "$VERSION" > "$DEST/VERSION"
touch "$DEST/.foxhunter-install-media"

echo "[make_release] size:"
du -sh "$DEST" "$DEST/config" 2>/dev/null || true
test -f "$DEST/third_party/blue_sonar/blue_sonar" && echo "blue_sonar OK"
test -f "$DEST/config/data/oui.sqlite" && echo "oui.sqlite OK"
echo "[make_release] OK → $DEST"
if [[ "$DO_ZIP" -eq 1 ]]; then
  ZIP="${OUT_BASE}/${NAME}.zip"
  rm -f "$ZIP"
  (cd "$OUT_BASE" && zip -r -q "$(basename "$ZIP")" "$(basename "$DEST")")
  echo "[make_release] zip → $ZIP"
fi
