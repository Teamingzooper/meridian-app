#!/usr/bin/env bash
# Rebuild and relaunch Meridian cleanly.
#
# LaunchServices will not pick up a changed Info.plist while the old app is still
# running, and needs a moment to propagate afterwards. Skipping either step makes
# `open` launch a stale registration whose main window never appears.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/build/Meridian.app"
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister

"$ROOT/scripts/build.sh" "${1:-release}"

echo "Stopping any running instance…"
pkill -x Meridian 2>/dev/null || true
# Two shapes to match: "python -m meridiand" from a checkout, and the bundled
# binary at Contents/Resources/meridiand/meridiand. Matching only the first left
# stale sidecars holding the port, which the next app then attached to.
pkill -f "m meridiand" 2>/dev/null || true
pkill -f "Meridian.app/Contents/Resources/meridiand" 2>/dev/null || true
sleep 1

if [ -x "$LSREGISTER" ]; then
  "$LSREGISTER" -f "$APP" 2>/dev/null || true
  sleep 1
fi

open "$APP"
echo "Meridian relaunched."
