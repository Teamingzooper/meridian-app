#!/usr/bin/env bash
# One-time setup for Meridian. No sudo, no root daemon.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SUPPORT="$HOME/Library/Application Support/Meridian"
VENV="$ROOT/meridiand/.venv"

say()  { printf '\033[1m%s\033[0m\n' "$*"; }
fail() { printf '\033[31m%s\033[0m\n' "$*" >&2; exit 1; }

say "Meridian setup"
echo

[ "$(uname -s)" = "Darwin" ] || fail "Meridian's no-root tunnel is macOS only."

command -v python3 >/dev/null || fail "python3 not found. Install it, then re-run."
say "1/4  Python helper"
if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi
"$VENV/bin/pip" install -q --upgrade pip
"$VENV/bin/pip" install -q -e "$ROOT/meridiand"
echo "     installed into $VENV"

say "2/4  Recording how the app should launch the helper"
mkdir -p "$SUPPORT"
printf '%s\n-m\nmeridiand\n' "$VENV/bin/python" > "$SUPPORT/helper-command"
echo "     $SUPPORT/helper-command"

say "3/4  Building Meridian.app"
command -v swift >/dev/null || fail "Swift not found. Install Xcode or the Command Line Tools."
"$ROOT/scripts/build.sh" release >/dev/null
echo "     $ROOT/build/Meridian.app"

say "4/4  On your iPhone"
cat <<'STEPS'
     - Connect it over USB and unlock it. Tap Trust if asked.
     - Turn on Settings > Privacy & Security > Developer Mode, then restart the phone.
       (Developer Mode only appears once a Mac has connected to it at least once.)
STEPS

echo
say "Check everything works:"
echo "     $VENV/bin/python -m meridiand doctor"
echo
say "Then open the app:"
echo "     open $ROOT/build/Meridian.app"
