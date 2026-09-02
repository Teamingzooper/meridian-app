# Contributing to Meridian

Bug reports, fixes and features are all welcome.

## Getting set up

```bash
git clone https://github.com/Teamingzooper/meridian-app.git
cd meridian-app
./scripts/setup.sh
```

That builds the app and creates the sidecar's virtualenv at `meridiand/.venv`.

## The two halves

Meridian is a Swift app and a Python sidecar, split along a real boundary: the
app owns everything visual, the sidecar owns everything that touches a device.

- **`meridiand/`** — the sidecar. Talking to an iPhone means Apple's CoreDevice
  tunnel, developer disk image mounting and the DVT service, all of which
  `pymobiledevice3` already implements and maintains against new iOS releases.
- **`Meridian/`** — the SwiftUI app. MapKit supplies search and road-following
  directions with no API keys.

Anything that can live in the sidecar should, because it is far cheaper to test
there. GPX parsing is the clearest example: the app posts documents to
`/gpx/parse` rather than carrying a second, untested implementation in Swift.

## Running the tests

```bash
cd meridiand && .venv/bin/python -m pytest tests/ -q
swift test --package-path Meridian
```

Both run in CI on every push. Please keep them green.

The sidecar's core is written to be testable without hardware: geodesics, route
interpolation, motion profiles and pause/resume timing are pure functions that
take `now` as an argument rather than reading a clock, and the simulator backend
takes an injected subprocess runner. New logic should follow that pattern — if a
change can only be verified by plugging in a phone, it is usually possible to
move the decision-making part somewhere it can be tested.

## Testing against a real device

```bash
meridian doctor
```

Walks USB → tunnel → developer disk image → a real write-and-clear, and reports
the first thing that is broken.

## Rebuilding

Use `./scripts/run.sh` rather than `open`. LaunchServices caches bundle metadata
and ignores a changed `Info.plist` while the old instance is running, which makes
the app launch with no window and looks exactly like a code bug.

## Style

Match the surrounding code. Comments should explain *why* something is the way it
is — a constraint, a trade-off, a surprise — rather than restating what the code
plainly does.

## Scope

Meridian is a developer and QA tool. Pull requests adding detection evasion aimed
at apps that use location as a compliance control — betting, banking,
geo-licensed streaming — will be declined. Everything else is fair game.
