# Meridian — Design

**Date:** 2026-09-02
**Status:** Approved

A free, local macOS menu-bar app that sets a USB-connected iPhone's simulated GPS
location. Replaces GhostMe ($12.95/mo), which is a paid GUI over the same
Apple developer-mode feature.

## Scope

This is a developer/QA tool: it simulates location on your own device over USB,
the way Xcode does. It deliberately does not implement detection evasion aimed at
apps that treat location as a compliance control (betting, banking, geo-licensed
streaming).

## Why a Python sidecar

Talking to an iPhone means implementing Apple's CoreDevice RemoteXPC tunnel, DDI
mounting, and the DVT service — thousands of lines of protocol that shifts with
each iOS release. `pymobiledevice3` implements it and is maintained (confirmed
working on iOS 26). Swift owns the UI; Python owns the wire.

Shelling out to the CLI per action does not work:

- The DVT session must stay open. `simulate-location set` appears to hang because
  it is holding that session; when it exits, the session closes.
- Route playback needs roughly one coordinate push per second. Spawning a process
  per point is untenable.

So the Python side is one long-lived sidecar, not a series of one-shot commands.

## Architecture

    Meridian.app     SwiftUI MenuBarExtra - MapKit - MKLocalSearch - MKDirections
        |            bookmarks, history, route editor, playback controls
        |  HTTP/JSON on 127.0.0.1, bearer token
        v
    meridiand        Python sidecar, runs unprivileged as the user
        |            holds Apple's native tunnel + the DVT LocationSimulation channel
        |            interpolates routes, pushes ~1 fix/sec
        v  USB
     iPhone

### Components

**meridiand** — the whole device side, in one unprivileged process. It opens a
tunnel, mounts the DDI if needed, holds the DVT channel, and serves a small local
API:

| Method | Path        | Body                              | Purpose                     |
|--------|-------------|-----------------------------------|-----------------------------|
| GET    | `/health`   | —                                 | liveness, no auth           |
| GET    | `/status`   | —                                 | device + session state      |
| POST   | `/connect`  | —                                 | open the channel eagerly    |
| POST   | `/location` | `{lat, lon}`                      | set a fixed point           |
| POST   | `/route`    | `{coords[], speed, loop}`         | start playback              |
| POST   | `/pause`    | —                                 | suspend playback            |
| POST   | `/resume`   | —                                 | continue playback           |
| POST   | `/stop`     | —                                 | halt, hold current position |
| POST   | `/clear`    | —                                 | release to real GPS         |
| POST   | `/jitter`   | `{radiusM}`                       | wander a static fix         |

Bound to loopback, and every route but `/health` requires the bearer token
written to a 0600 file. Loopback alone would let any local process move the
phone's location.

**Meridian.app** — all visuals. MapKit supplies address search (`MKLocalSearch`)
and road-following routes (`MKDirections`) built into macOS with no API keys and
no cost — the two things a browser build would otherwise pay a maps provider for.

## Privilege model

No root, and no installer step.

pymobiledevice3 11 can piggyback Apple's own `remoted` tunnel through
`remotepairingd` on macOS (`NativeRemotedTunnel`). It needs no privileges and
coexists with Xcode, so the sidecar opens the tunnel in-process as the logged-in
user. The original plan — installing pymobiledevice3's `tunneld` as a root
LaunchDaemon — is kept only as an automatic fallback for the case where the
native path is unavailable, and is never reached on a healthy macOS 26 machine.

The only thing the user must do on the phone is turn on Developer Mode.

## Features

| GhostMe             | Meridian                                                        |
|---------------------|-------------------------------------------------------------|
| Address search      | `MKLocalSearch`, the Apple Maps index                        |
| Location history    | Auto-recorded, JSON on disk, click to re-apply               |
| Bookmarks           | Named, reorderable, editable label                           |
| Routes              | Waypoints -> `MKDirections` road snap -> play/pause/loop      |

Speed presets: walk 1.4 m/s, bike 4.2 m/s, drive 13.4 m/s, plus custom.

Beyond GhostMe: click-to-drop a pin, paste raw coordinates, and a jitter toggle
adding a few meters of GPS-like noise so a static point does not look frozen.

## Data

Plain JSON in `~/Library/Application Support/Meridian/`: `bookmarks.json`,
`history.json`, `settings.json`. Inspectable, no migration burden.

## Error handling

Every failure maps to one actionable sentence in the menu:

| Condition            | Message                                    |
|----------------------|--------------------------------------------|
| No device            | Connect iPhone via USB                     |
| Developer Mode off   | Settings > Privacy & Security > Developer Mode |
| Device locked        | Unlock your iPhone                         |
| DDI not mounted      | auto-mount attempted, then reported        |
| tunneld down         | shown with a Fix button                    |

A session drop mid-route pauses playback, reconnects, and resumes rather than
failing silently.

## Testing

The interpolation engine is pure math — speed to point spacing, bearing, loop
wraparound — and is unit tested against a fake device transport, as are the API
contracts. Swift tests cover the bookmark/history store and route model. MapKit
views and the device handshake are verified by hand against a real iPhone.

## Build order

1. Sidecar first, provably moving a real device's location from a terminal.
   `meridiand doctor` walks the whole chain and reports where it breaks.
2. The app on top.

Working software early rather than only at the end.
