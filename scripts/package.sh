#!/usr/bin/env bash
# Build a distributable Meridian.dmg.
#
# The .dmg carries its own sidecar, built with PyInstaller, so a user needs no
# Python and no virtualenv — download, drag to Applications, run.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/build/Meridian.app"
STAGE="$ROOT/build/dmg"
DMG="$ROOT/build/Meridian.dmg"
VERSION="${1:-$(git -C "$ROOT" describe --tags --always 2>/dev/null || echo dev)}"

say() { printf '\033[1m%s\033[0m\n' "$*"; }

say "1/4  Building the app"
"$ROOT/scripts/build.sh" release >/dev/null

# jedi and IPython back pymobiledevice3's interactive shell, PIL only the icon
# script, and neither runs here — together they were a third of the payload.
say "2/4  Bundling the sidecar"
PY="${PYTHON:-python3}"
BUILD_VENV="$ROOT/build/pyi-venv"
"$PY" -m venv "$BUILD_VENV"
"$BUILD_VENV/bin/pip" install -q --upgrade pip
"$BUILD_VENV/bin/pip" install -q -e "$ROOT/meridiand" pyinstaller

rm -rf "$ROOT/build/pyi"
"$BUILD_VENV/bin/pyinstaller" \
  --noconfirm --clean --onedir \
  --name meridiand \
  --distpath "$ROOT/build/pyi/dist" \
  --workpath "$ROOT/build/pyi/work" \
  --specpath "$ROOT/build/pyi" \
  --collect-all pymobiledevice3 \
  --collect-all construct \
  --paths "$ROOT/meridiand" \
  --hidden-import meridiand \
  --exclude-module jedi \
  --exclude-module parso \
  --exclude-module IPython \
  --exclude-module IPython.core \
  --exclude-module prompt_toolkit \
  --exclude-module PIL \
  --exclude-module tkinter \
  --exclude-module pytest \
  --exclude-module _pytest \
  --exclude-module matplotlib \
  --exclude-module setuptools \
  --exclude-module pip \
  "$ROOT/meridiand/entrypoint.py" >/dev/null

test -x "$ROOT/build/pyi/dist/meridiand/meridiand" \
  || { echo "sidecar bundle failed" >&2; exit 1; }

cp -R "$ROOT/build/pyi/dist/meridiand" "$APP/Contents/Resources/meridiand"

say "3/4  Signing"
# Ad-hoc, so it runs locally. Without an Apple Developer ID, Gatekeeper still
# warns on first open; the README explains the right-click → Open step.
codesign --force --deep --sign - "$APP" 2>/dev/null \
  || echo "     note: ad-hoc signing failed; the app still runs"

say "4/4  Building the disk image"
rm -rf "$STAGE" "$DMG"
mkdir -p "$STAGE"
cp -R "$APP" "$STAGE/"
ln -s /Applications "$STAGE/Applications"

hdiutil create -volname "Meridian $VERSION" -srcfolder "$STAGE" \
  -ov -format UDZO "$DMG" >/dev/null

rm -rf "$STAGE"
echo
say "Built $DMG"
du -h "$DMG" | awk '{print "     " $1}'
