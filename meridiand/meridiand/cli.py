"""`meridian` — drive the simulated location from a shell or a CI job.

A one-shot command cannot hold a location by itself: the DVT channel closes with
the process and the phone reverts. So the CLI talks to the long-running sidecar
over its local API, starting one detached if none is listening. That makes
`meridian set ...` work unattended in a pipeline, not only while the app is open.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable, Optional

from .gpx import GpxError, parse_gpx
from .route import SPEED_PRESETS
from .server import DEFAULT_PORT, state_dir


class DaemonUnavailable(RuntimeError):
    """The sidecar is not listening and could not be started."""


class CommandFailed(RuntimeError):
    """The sidecar refused the request, with a reason worth printing."""


def read_token(directory: Optional[Path] = None) -> str:
    path = (directory or state_dir()) / "token"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise DaemonUnavailable(
            "Couldn't read Meridian's token. Is the helper running?"
        ) from exc


def request(path: str, payload: Optional[dict] = None, *, port: int, token: str) -> dict:
    """Call the sidecar, raising CommandFailed with its guidance on refusal."""
    url = f"http://127.0.0.1:{port}/{path}"
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, method="POST" if data is not None else "GET")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=200) as response:
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        body = exc.read()
        try:
            message = json.loads(body)["error"]["message"]
        except Exception:
            message = f"the helper returned HTTP {exc.code}"
        raise CommandFailed(message) from exc
    except urllib.error.URLError as exc:
        raise DaemonUnavailable("Meridian's helper isn't responding.") from exc


def is_alive(port: int) -> bool:
    try:
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/health", timeout=2
        ) as response:
            return response.status == 200
    except Exception:
        return False


def ensure_daemon(port: int, timeout: float = 25.0) -> None:
    """Start a detached sidecar if none is listening, and wait for it."""
    if is_alive(port):
        return

    subprocess.Popen(
        [sys.executable, "-m", "meridiand", "serve", "--port", str(port)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        # Detach so the helper outlives this command and keeps the channel open.
        start_new_session=True,
    )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if is_alive(port):
            return
        time.sleep(0.4)

    raise DaemonUnavailable("Timed out waiting for Meridian's helper to start.")


# --------------------------------------------------------------------- output


def describe(status: dict) -> str:
    """One human-readable line summarising a status response."""
    device = status.get("device") or {}
    name = device.get("name") or "no device"
    mode = status.get("mode", "idle")

    if mode == "idle":
        return f"{name}: real GPS"

    location = status.get("location") or {}
    where = f"{location.get('lat'):.5f}, {location.get('lon'):.5f}" if location else "unknown"

    if mode == "route":
        route = status.get("route") or {}
        percent = int(round(route.get("progress", 0) * 100))
        state = "paused" if route.get("paused") else "moving"
        return f"{name}: {state} along a route, {percent}% — at {where}"

    return f"{name}: simulating {where}"


# ------------------------------------------------------------------- commands


def _load_route(path: Path) -> tuple[list[list[float]], str]:
    try:
        route = parse_gpx(path.read_text(encoding="utf-8", errors="replace"))
    except OSError as exc:
        raise CommandFailed(f"couldn't read {path}: {exc.strerror or exc}") from exc
    except GpxError as exc:
        raise CommandFailed(str(exc)) from exc
    return [[p.lat, p.lon] for p in route.points], route.name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="meridian",
        description="Set your iPhone's simulated location from the command line.",
    )
    parser.add_argument("--port", type=int, default=DEFAULT_PORT, help=argparse.SUPPRESS)
    parser.add_argument("--json", action="store_true", help="print the raw status JSON")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("status", help="show what the phone is currently reporting")

    set_cmd = sub.add_parser("set", help="hold the phone at a coordinate")
    set_cmd.add_argument("latitude", type=float)
    set_cmd.add_argument("longitude", type=float)

    route_cmd = sub.add_parser("route", help="play a GPX file as a route")
    route_cmd.add_argument("file", type=Path)
    route_cmd.add_argument(
        "--speed", default="walk",
        help=f"one of {', '.join(sorted(SPEED_PRESETS))}, or a number in m/s",
    )
    route_cmd.add_argument("--loop", action="store_true", help="repeat when it ends")

    sub.add_parser("stop", help="stop route playback, holding position")
    sub.add_parser("clear", help="hand the phone back its real GPS")
    sub.add_parser("doctor", help="check the whole chain end to end")

    return parser


def resolve_speed(value: str) -> dict:
    """Accept a preset name or a raw metres-per-second figure."""
    if value in SPEED_PRESETS:
        return {"speed": value}
    try:
        return {"speedMps": float(value)}
    except ValueError:
        known = ", ".join(sorted(SPEED_PRESETS))
        raise CommandFailed(f"unknown speed '{value}'; expected {known}, or a number") from None


def run(args: argparse.Namespace, call: Callable[..., dict]) -> dict:
    """Dispatch one command. `call(path, payload)` performs the request."""
    if args.command == "status":
        return call("status")
    if args.command == "set":
        return call("location", {"lat": args.latitude, "lon": args.longitude})
    if args.command == "stop":
        return call("stop", {})
    if args.command == "clear":
        return call("clear", {})
    if args.command == "route":
        coords, _ = _load_route(args.file)
        return call("route", {"coords": coords, "loop": args.loop, **resolve_speed(args.speed)})
    raise CommandFailed(f"unknown command {args.command}")


def main(argv: Optional[list[str]] = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "doctor":
        from .doctor import main as doctor_main

        return doctor_main()

    try:
        ensure_daemon(args.port)
        token = read_token()
        status = run(args, lambda path, payload=None: request(
            path, payload, port=args.port, token=token
        ))
    except (DaemonUnavailable, CommandFailed) as exc:
        print(f"meridian: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(status, indent=2) if args.json else describe(status))
    return 0


if __name__ == "__main__":
    sys.exit(main())
