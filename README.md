# Meridian

[![CI](https://github.com/Teamingzooper/meridian-app/actions/workflows/ci.yml/badge.svg)](https://github.com/Teamingzooper/meridian-app/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/Teamingzooper/meridian-app?include_prereleases&sort=semver)](https://github.com/Teamingzooper/meridian-app/releases)
[![Licence](https://img.shields.io/badge/licence-MIT-blue.svg)](LICENSE)
[![Platform](https://img.shields.io/badge/macOS-14%2B-lightgrey.svg)](#requirements)

**Set your iPhone's GPS location from your Mac. Free, open source, no subscription.**

Meridian does what [GhostMe](https://www.getghostme.com/) charges $12.95/month for,
using the same underlying mechanism: Apple's own developer-mode location
simulation, the one Xcode uses. No jailbreak, no account, and no root.

<!-- SCREENSHOT:MAIN -->

## What it does

- **Search** any address or place — MapKit's index, the same one Apple Maps uses
- **Paste coordinates** or an Apple/Google Maps link straight into the search box
- **Right-click the map** to drop a pin, then confirm
- **Bookmarks and history**, filterable, one click to re-apply
- **Routes** — click waypoints, pick walk / bike / drive, then play, pause and loop.
  Waypoints snap to real streets, and routes can be **saved and reloaded**
- **GPX import and export**, so routes move between Meridian and anything else
- **Lifelike movement** — eases away from stops, slows into corners, varies pace
  slightly, instead of gliding at a constant speed
- **Multiple devices** — several iPhones and iPads, plus **booted iOS Simulators**
- **Hide** — one click to a decoy location, with drift
- **Command line** — `meridian set`, `meridian route`, scriptable from CI

### Against GhostMe

| | GhostMe | Meridian |
|---|---|---|
| Price | $12.95/mo or $42.95/yr | Free |
| Source | Closed | MIT |
| Address search | Yes | Yes |
| Bookmarks, history | Yes | Yes, filterable |
| Routes | Yes | Yes, **saved and named** |
| GPX import/export | No | Yes |
| iOS Simulator | No | Yes |
| Multiple devices | No | Yes |
| Command line / CI | No | Yes |
| Lifelike movement | No | Yes |

## Install

### Download

Grab the latest `.dmg` from [Releases](https://github.com/Teamingzooper/meridian-app/releases)
and drag **Meridian** to Applications. Python is bundled — nothing else to install.

> **First launch:** right-click the app and choose **Open**, then confirm.
> Meridian is signed ad-hoc rather than notarised (that needs a paid Apple
> Developer account), so Gatekeeper warns on a plain double-click. One-time step.

### Build from source

```bash
git clone https://github.com/Teamingzooper/meridian-app.git
cd meridian-app
./scripts/setup.sh
open build/Meridian.app
```

### Then, on your iPhone — once

1. Connect over USB and unlock it. Tap **Trust** if asked.
2. Turn on **Settings › Privacy & Security › Developer Mode**, then restart.
   (Developer Mode only appears after a Mac has connected at least once.)

## Requirements

| | |
|---|---|
| Mac | macOS 14 or later (built and tested on macOS 26) |
| iPhone / iPad | iOS 17 or later, Developer Mode on |
| Connection | USB cable |
| To build | Swift toolchain (Xcode or Command Line Tools), Python 3.10+ |

## Command line

```bash
meridian status                          # what is the phone reporting?
meridian set 48.8584 2.2945              # hold it at a coordinate
meridian route commute.gpx --speed bike  # play a GPX route
meridian route loop.gpx --loop           # repeat forever
meridian clear                           # back to real GPS
meridian doctor                          # check the whole chain
```

`meridian` starts the helper itself when none is running, so it works unattended
in a script or CI job. Add `--json` to any command for machine-readable output.

## If something isn't working

```bash
meridian doctor
```

It walks USB → tunnel → developer disk image → an actual write-and-clear against
the device, and stops at the first broken thing with the action that fixes it.

| Symptom | Cause |
|---|---|
| "No iPhone found" | Cable not connected, or the phone is locked |
| "Turn on Developer Mode" | The iOS setting above; needs a restart after enabling |
| "Tap Trust on your iPhone" | The pairing prompt was dismissed — unplug and replug |
| "No booted simulator" | Start a simulator in Xcode first |
| App opens with no window | Run `./scripts/run.sh`, which refreshes the LaunchServices registration |
| Location snaps back when you quit | Expected — the channel closes with the app |

## How it works

```
  Meridian.app     SwiftUI — MapKit search, directions, map
      │            bookmarks, routes, playback
      │  HTTP/JSON on 127.0.0.1, bearer token
      ▼
  meridiand        Python sidecar, unprivileged
      │            holds Apple's native tunnel + the DVT location channel
      │            interpolates routes, pushes ~1 fix/sec
      ▼  USB / simctl
   iPhone or Simulator
```

The simulated location holds only while the DVT channel stays open — which is why
`pymobiledevice3 developer dvt simulate-location set` appears to hang, and why
shelling out per update cannot work. The sidecar holds that channel open and
pushes coordinates down it.

Reaching the device needs a tunnel. pymobiledevice3 11 can piggyback Apple's own
`remoted` tunnel through `remotepairingd` on macOS, which needs **no root** and
coexists with Xcode, so that is the normal path. Its `tunneld` daemon remains an
automatic fallback. Simulators skip all of this and use `simctl` instead.

The API binds to loopback and every route but `/health` requires a bearer token
stored `0600` in Application Support — loopback alone would let any local process
move your phone's location.

## Development

```bash
cd meridiand && .venv/bin/python -m pytest tests/ -q   # 265 sidecar tests
swift test --package-path Meridian                     # 22 app tests
./scripts/run.sh                                       # rebuild and relaunch
./scripts/package.sh                                   # build the .dmg
python3 scripts/make_icon.py                           # regenerate the icon
```

State lives in `~/Library/Application Support/Meridian/` as plain JSON. Helper
logs go to `~/Library/Logs/Meridian-helper.log`.

Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Scope

Meridian is a developer and QA tool: it simulates location on your own device
over USB, the way Xcode does. It deliberately implements no detection evasion for
apps that treat location as a compliance control — betting, banking, geo-licensed
streaming. Those generally treat spoofing as fraud, and that is on you, not the
tool.

Two honest limits:

- **Hide substitutes a location, it does not remove one.** The DVT channel can
  only override the reported fix. Genuinely switching location off is
  Settings › Privacy & Security › Location Services on the phone, and no USB tool
  can reach it.
- **The green "you are here" dot is the Mac's position**, not the phone's. The
  channel writes location but cannot read it back. Since the two are joined by a
  cable, they are the same place to within a room.

## Licence

MIT — see [LICENSE](LICENSE).

Built on [pymobiledevice3](https://github.com/doronz88/pymobiledevice3).
Not affiliated with Apple Inc. or with GhostMe.
