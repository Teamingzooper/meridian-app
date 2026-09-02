#!/usr/bin/env bash
# Build Meridian.app from the Swift package.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$ROOT/build/Meridian.app"
CONFIG="${1:-release}"

echo "Building Meridian ($CONFIG)…"
swift build --package-path "$ROOT/Meridian" -c "$CONFIG"

BIN="$(swift build --package-path "$ROOT/Meridian" -c "$CONFIG" --show-bin-path)/Meridian"
[ -x "$BIN" ] || { echo "Build produced no binary at $BIN" >&2; exit 1; }

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BIN" "$APP/Contents/MacOS/Meridian"

# Regenerate the icon if it is missing, so a fresh clone builds a complete app.
ICON="$ROOT/assets/AppIcon.icns"
if [ ! -f "$ICON" ] && command -v python3 >/dev/null; then
  python3 "$ROOT/scripts/make_icon.py" >/dev/null 2>&1 || true
fi
[ -f "$ICON" ] && cp "$ICON" "$APP/Contents/Resources/AppIcon.icns"

cat > "$APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>              <string>Meridian</string>
    <key>CFBundleDisplayName</key>       <string>Meridian</string>
    <key>CFBundleIdentifier</key>        <string>dev.meridian.app</string>
    <key>CFBundleExecutable</key>        <string>Meridian</string>
    <key>CFBundlePackageType</key>       <string>APPL</string>
    <key>CFBundleShortVersionString</key><string>1.0</string>
    <key>CFBundleVersion</key>           <string>1</string>
    <key>LSMinimumSystemVersion</key>    <string>14.0</string>
    <key>CFBundleIconFile</key>          <string>AppIcon</string>
    <key>NSHumanReadableCopyright</key>  <string>Meridian. Not affiliated with Apple Inc.</string>
    <!-- Shows your real position in green next to the phone's simulated one in blue. -->
    <key>NSLocationWhenInUseUsageDescription</key>
    <string>Meridian shows your real location on the map so you can see it next to the location your iPhone is reporting.</string>
    <key>NSLocationUsageDescription</key>
    <string>Meridian shows your real location on the map so you can see it next to the location your iPhone is reporting.</string>
</dict>
</plist>
PLIST

# Ad-hoc sign so macOS will run it locally without a developer account.
codesign --force --deep --sign - "$APP" 2>/dev/null \
  || echo "note: ad-hoc signing failed; the app still runs but Gatekeeper may prompt"

# LaunchServices caches bundle metadata, including whether the app is a menu-bar
# accessory. Without this, `open` can launch an older registration and the main
# window silently never appears.
LSREGISTER=/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister
# Note: this does not take effect while an old instance is still running.
# Use scripts/run.sh to rebuild and relaunch in the right order.
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP" 2>/dev/null || true

echo "Built $APP"
