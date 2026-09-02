"""Local HTTP API over the engine.

Bound to loopback only, and every route but `/health` requires the bearer token
written to a 0600 file at startup. Loopback alone would let any process on the
machine move the phone's location; reading the token requires being the user.

Deliberately stdlib-only — five endpoints do not justify a web framework.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Callable

from .engine import Engine
from .errors import DeviceError
from .gpx import GpxError, parse_gpx, write_gpx
from .geo import Coord
from .route import SPEED_PRESETS

logger = logging.getLogger(__name__)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8787

MAX_BODY_BYTES = 1 << 20  # a long route polyline, with room to spare
MAX_ROUTE_POINTS = 20_000


def state_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "Meridian"


def write_token(directory: Path | None = None) -> str:
    """Mint a session token and leave it where only this user can read it."""
    directory = directory or state_dir()
    directory.mkdir(parents=True, exist_ok=True)

    token = secrets.token_urlsafe(32)
    path = directory / "token"
    # Create with 0600 from the outset rather than widening then narrowing.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(token)
    return token


def parse_coords(raw: Any) -> list[Coord]:
    """Validate a `[[lat, lon], ...]` payload into coordinates."""
    if not isinstance(raw, list) or not raw:
        raise ValueError("coords must be a non-empty list of [lat, lon] pairs")
    if len(raw) > MAX_ROUTE_POINTS:
        raise ValueError(f"a route may not exceed {MAX_ROUTE_POINTS} points")

    coords = []
    for index, pair in enumerate(raw):
        if not isinstance(pair, (list, tuple)) or len(pair) != 2:
            raise ValueError(f"coords[{index}] must be a [lat, lon] pair")
        coords.append(Coord(validate_lat(pair[0]), validate_lon(pair[1])))
    return coords


def validate_lat(value: Any) -> float:
    return _validate_number(value, -90.0, 90.0, "latitude")


def validate_lon(value: Any) -> float:
    return _validate_number(value, -180.0, 180.0, "longitude")


def _validate_number(value: Any, low: float, high: float, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{label} must be a number")
    number = float(value)
    if not low <= number <= high:
        raise ValueError(f"{label} must be between {low} and {high}")
    return number


def resolve_speed(payload: dict) -> float:
    """Accept either a named preset or an explicit metres-per-second value."""
    if "speedMps" in payload:
        speed = _validate_number(payload["speedMps"], 0.01, 1000.0, "speedMps")
        return speed

    name = payload.get("speed", "walk")
    if name not in SPEED_PRESETS:
        known = ", ".join(sorted(SPEED_PRESETS))
        raise ValueError(f"unknown speed '{name}'; expected one of {known}, or speedMps")
    return SPEED_PRESETS[name]


class Handler(BaseHTTPRequestHandler):
    server_version = "meridiand"
    engine: Engine
    token: str

    # -------------------------------------------------------------- plumbing

    def log_message(self, fmt: str, *args: Any) -> None:
        logger.debug("%s - %s", self.address_string(), fmt % args)

    def _send(self, status: HTTPStatus, payload: dict) -> None:
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _authorised(self) -> bool:
        header = self.headers.get("Authorization", "")
        prefix = "Bearer "
        if not header.startswith(prefix):
            return False
        return secrets.compare_digest(header[len(prefix):], self.token)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        if length == 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length))
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON: {exc.msg}") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    # --------------------------------------------------------------- routing

    def do_GET(self) -> None:  # noqa: N802 - name fixed by BaseHTTPRequestHandler
        if self.path == "/health":
            self._send(HTTPStatus.OK, {"ok": True, "service": "meridiand"})
            return
        self._dispatch({
            "/status": lambda _: self.engine.status(),
            "/devices": lambda _: self.engine.list_devices(),
        })

    def do_POST(self) -> None:  # noqa: N802
        self._dispatch(
            {
                "/connect": lambda _: self.engine.connect(),
                "/select": self._select,
                "/location": self._location,
                "/route": self._route,
                "/pause": lambda _: self.engine.pause(),
                "/resume": lambda _: self.engine.resume(),
                "/stop": lambda _: self.engine.stop(),
                "/clear": lambda _: self.engine.clear(),
                "/jitter": self._jitter,
                "/gpx/parse": self._gpx_parse,
                "/gpx/write": self._gpx_write,
            }
        )

    def _dispatch(self, routes: dict[str, Callable[[dict], dict]]) -> None:
        if not self._authorised():
            self._send(HTTPStatus.UNAUTHORIZED, {"error": {"code": "unauthorized", "message": "Bad or missing token."}})
            return

        handler = routes.get(self.path.split("?", 1)[0])
        if handler is None:
            self._send(HTTPStatus.NOT_FOUND, {"error": {"code": "not_found", "message": "No such endpoint."}})
            return

        try:
            payload = self._read_json() if self.command == "POST" else {}
            self._send(HTTPStatus.OK, handler(payload))
        except DeviceError as exc:
            # The device is reachable but not in a usable state; the message says why.
            self._send(HTTPStatus.CONFLICT, {"error": exc.as_dict()})
        except ValueError as exc:
            self._send(HTTPStatus.BAD_REQUEST, {"error": {"code": "bad_request", "message": str(exc)}})
        except TimeoutError:
            self._send(
                HTTPStatus.GATEWAY_TIMEOUT,
                {"error": {"code": "timeout", "message": "Your iPhone stopped responding. Try again."}},
            )
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("unhandled error serving %s", self.path)
            self._send(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {"error": {"code": "internal", "message": str(exc)}},
            )

    # -------------------------------------------------------------- endpoints

    def _location(self, payload: dict) -> dict:
        return self.engine.set_fixed(
            validate_lat(payload.get("lat")), validate_lon(payload.get("lon"))
        )

    def _route(self, payload: dict) -> dict:
        return self.engine.play_route(
            parse_coords(payload.get("coords")),
            speed_mps=resolve_speed(payload),
            loop=bool(payload.get("loop", False)),
            # Lifelike by default; callers wanting a metronome can opt out.
            realistic=bool(payload.get("realistic", True)),
        )

    def _select(self, payload: dict) -> dict:
        udid = payload.get("udid")
        if udid is not None and not isinstance(udid, str):
            raise ValueError("udid must be a string")
        kind = payload.get("kind", "device")
        if not isinstance(kind, str):
            raise ValueError("kind must be a string")
        return self.engine.select_device(udid or None, kind)

    def _jitter(self, payload: dict) -> dict:
        return self.engine.set_jitter(_validate_number(payload.get("radiusM"), 0.0, 100.0, "radiusM"))

    # GPX is parsed here rather than in the app so there is one implementation,
    # and it is the one with tests behind it.
    def _gpx_parse(self, payload: dict) -> dict:
        document = payload.get("gpx")
        if not isinstance(document, str) or not document.strip():
            raise ValueError("gpx must be a non-empty string")
        try:
            route = parse_gpx(document)
        except GpxError as exc:
            raise ValueError(str(exc)) from exc
        return {
            "name": route.name,
            "coords": [[p.lat, p.lon] for p in route.points],
            "count": len(route.points),
        }

    def _gpx_write(self, payload: dict) -> dict:
        coords = parse_coords(payload.get("coords"))
        name = payload.get("name") or "Meridian route"
        if not isinstance(name, str):
            raise ValueError("name must be a string")
        try:
            return {"gpx": write_gpx(coords, name[:200])}
        except GpxError as exc:
            raise ValueError(str(exc)) from exc


def build_server(engine: Engine, token: str, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"engine": engine, "token": token})
    return ThreadingHTTPServer((host, port), handler)
