# Meridian

A free macOS menu-bar app that sets your iPhone's GPS location over USB.

Does what [GhostMe](https://www.getghostme.com/) charges $12.95/month for, using
the same underlying mechanism: Apple's own developer-mode location simulation,
the one Xcode uses. No jailbreak, no subscription, no account, and no root.

## What it does

- **Search** any address or place — MapKit's index, the same one Apple Maps uses
- **Drop a pin** anywhere on the map, or paste coordinates
- **Bookmarks** for places you use often, reorderable and renameable
- **History** of everywhere you've been, one click to go back
- **Routes** — click waypoints, pick walk / bike / drive, then play, pause, loop.
  Waypoints snap to real streets via MapKit directions.
- **Drift** — a few metres of GPS-like wander, so a static fix doesn't look frozen

## Requirements

- macOS 14 or later (built and tested on macOS 26)
- Xcode or the Swift toolchain, to build the app
- Python 3.10+
- An iPhone running iOS 17 or later, with Developer Mode on

## Setup

```bash
./scripts/setup.sh
```

That creates a Python virtualenv, builds `Meridian.app`, and tells you what to do
on the phone. Then:

```bash
open build/Meridian.app
```

Meridian lives in the menu bar. The icon shows the state at a glance: outline for
idle, filled while simulating, an arrow while following a route.

### On your iPhone, once

1. Connect over USB and unlock it. Tap **Trust** if asked.
2. Turn on **Settings › Privacy & Security › Developer Mode**, then restart.
   (Developer Mode only appears after a Mac has connected at least once.)

## If something isn't working

```bash
meridiand/.venv/bin/python -m meridiand doctor
```

It walks the whole chain — USB, tunnel, developer disk image, then an actual
write-and-clear against the device — and stops at the first thing that's broken
with the one action that fixes it.

## How it works

    Meridian.app     SwiftUI menu bar - MapKit search, directions, map
        |            bookmarks, history, route editor, playback
        |  HTTP/JSON on 127.0.0.1, bearer token
        v
    meridiand        Python sidecar, unprivileged
        |            holds Apple's native tunnel + the DVT location channel
        |            interpolates routes, pushes ~1 fix/sec
        v  USB
     iPhone

The simulated location holds only while the DVT channel stays open — which is why
`pymobiledevice3 developer dvt simulate-location set` appears to hang, and why
shelling out per update cannot work. The sidecar holds that channel open and
pushes coordinates down it.

Getting to the device needs a tunnel. pymobiledevice3 11 can piggyback Apple's
own `remoted` tunnel through `remotepairingd` on macOS, which needs no root and
coexists with Xcode, so that is the normal path. Its `tunneld` daemon remains an
automatic fallback and is not reached on a healthy macOS 26 machine.

The API is bound to loopback and every route but `/health` requires a bearer
token stored 0600 in Application Support. Loopback alone would let any local
process move your phone's location.

## Development

```bash
cd meridiand && .venv/bin/python -m pytest tests/ -q   # 148 tests
./scripts/build.sh                                     # rebuild Meridian.app
```

State lives in `~/Library/Application Support/Meridian/` as plain JSON. Helper
logs go to `~/Library/Logs/Meridian-helper.log`.

## Scope

This is a developer and QA tool: it simulates location on your own device over
USB, the way Xcode does. It deliberately implements no detection evasion for apps
that treat location as a compliance control — betting, banking, geo-licensed
streaming. Those generally consider spoofing them fraud.

Built on [pymobiledevice3](https://github.com/doronz88/pymobiledevice3).
Not affiliated with Apple Inc. or with GhostMe.
