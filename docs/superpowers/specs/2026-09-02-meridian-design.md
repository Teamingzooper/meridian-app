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
        |        bookmarks, history, route editor, playback controls
        |  HTTP/JSON on 127.0.0.1
        v
    meridiand        Python sidecar, runs unprivileged as the user
        |        holds the DVT LocationSimulation session
        |        interpolates routes, pushes ~1 point/sec
        |  RSD over the tunnel
        v
    tunneld      pymobiledevice3's own daemon, root, installed once
        |        upstream code - not ours to write or maintain
        v  USB
     iPhone

### Components

**tunneld** — upstream pymobiledevice3, installed once as a root LaunchDaemon.
Publishes connected devices and their RSD address/port over a local REST endpoint.
The only component needing root, and not our code.

**meridiand** — our sidecar, unprivileged. Polls tunneld for the device, auto-mounts
the DDI, holds the DVT session. Five endpoints:

| Method | Path        | Body                              | Purpose                     |
|--------|-------------|-----------------------------------|-----------------------------|
| GET    | `/status`   | —                                 | device + session state      |
| POST   | `/location` | `{lat, lon, jitter?}`             | set a fixed point           |
| POST   | `/route`    | `{coords[], speed_mps, loop}`     | start playback              |
| POST   | `/stop`     | —                                 | halt playback, hold position|
| POST   | `/clear`    | —                                 | release to real GPS         |

**Meridian.app** — all visuals. MapKit supplies address search (`MKLocalSearch`) and
road-following routes (`MKDirections`) built into macOS with no API keys and no
cost — the two things a browser build would otherwise pay a maps provider for.

## Privilege model

The tunnel needs root. Setup installs `tunneld` once as a LaunchDaemon: one sudo
at install time, never again. `meridiand` and the app both run as the user.

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
2. The app on top.

Working software early rather than only at the end.
