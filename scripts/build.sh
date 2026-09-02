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
    <!-- Menu bar only: no Dock icon, no main window. -->
    <key>LSUIElement</key>               <true/>
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

echo "Built $APP"
