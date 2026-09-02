"""Tests for request validation and the HTTP surface.

The endpoint tests run a real server against a fake engine, so routing, auth and
error mapping are exercised without a device.
"""
import json
import threading
import urllib.error
import urllib.request

import pytest

from meridiand.errors import DeviceError
from meridiand.geo import Coord
from meridiand.route import SPEED_PRESETS
from meridiand.server import (
    build_server,
    parse_coords,
    resolve_speed,
    validate_lat,
    validate_lon,
    write_token,
)


class TestCoordinateValidation:
    def test_accepts_valid_values(self):
        assert validate_lat(37.77) == 37.77
        assert validate_lon(-122.42) == -122.42

    def test_accepts_the_extremes(self):
        assert validate_lat(90.0) == 90.0
        assert validate_lat(-90.0) == -90.0
        assert validate_lon(180.0) == 180.0

    def test_accepts_integers(self):
        assert validate_lat(37) == 37.0

    @pytest.mark.parametrize("bad", [91.0, -91.0, 1e9])
    def test_rejects_out_of_range_latitude(self, bad):
        with pytest.raises(ValueError, match="latitude"):
            validate_lat(bad)

    @pytest.mark.parametrize("bad", [181.0, -181.0])
    def test_rejects_out_of_range_longitude(self, bad):
        with pytest.raises(ValueError, match="longitude"):
            validate_lon(bad)

    @pytest.mark.parametrize("bad", ["37.7", None, [], {}])
    def test_rejects_non_numbers(self, bad):
        with pytest.raises(ValueError):
            validate_lat(bad)

    def test_rejects_booleans_despite_python_treating_them_as_ints(self):
        with pytest.raises(ValueError):
            validate_lat(True)


class TestParseCoords:
    def test_parses_pairs(self):
        assert parse_coords([[1.0, 2.0], [3.0, 4.0]]) == [Coord(1.0, 2.0), Coord(3.0, 4.0)]

    def test_rejects_an_empty_route(self):
        with pytest.raises(ValueError):
            parse_coords([])

    def test_rejects_a_non_list(self):
        with pytest.raises(ValueError):
            parse_coords("here")

    def test_rejects_a_malformed_pair(self):
        with pytest.raises(ValueError, match=r"coords\[1\]"):
            parse_coords([[1.0, 2.0], [3.0]])

    def test_reports_which_point_is_out_of_range(self):
        with pytest.raises(ValueError, match="latitude"):
            parse_coords([[1.0, 2.0], [999.0, 4.0]])

    def test_rejects_an_absurdly_long_route(self):
        with pytest.raises(ValueError, match="exceed"):
            parse_coords([[0.0, 0.0]] * 20_001)


class TestResolveSpeed:
    def test_named_presets(self):
        assert resolve_speed({"speed": "bike"}) == SPEED_PRESETS["bike"]

    def test_defaults_to_walking(self):
        assert resolve_speed({}) == SPEED_PRESETS["walk"]

    def test_explicit_value_wins(self):
        assert resolve_speed({"speed": "walk", "speedMps": 30.0}) == 30.0

    def test_rejects_an_unknown_preset(self):
        with pytest.raises(ValueError, match="unknown speed"):
            resolve_speed({"speed": "teleport"})

    def test_rejects_a_nonsense_speed(self):
        with pytest.raises(ValueError):
            resolve_speed({"speedMps": 0})


class TestTokenFile:
    def test_written_with_owner_only_permissions(self, tmp_path):
        token = write_token(tmp_path)
        path = tmp_path / "token"
        assert path.read_text() == token
        assert (path.stat().st_mode & 0o777) == 0o600

    def test_each_call_mints_a_fresh_token(self, tmp_path):
        assert write_token(tmp_path) != write_token(tmp_path)

    def test_tokens_are_long_enough_to_matter(self, tmp_path):
        assert len(write_token(tmp_path)) >= 32


class FakeEngine:
    """Stands in for the real engine, recording what the handler asked of it."""

    def __init__(self):
        self.calls = []
        self.raises = None

    def _record(self, name, **kwargs):
        self.calls.append((name, kwargs))
        if self.raises is not None:
            raise self.raises
        return {"engine": "running", "mode": name}

    def status(self):
        return self._record("status")

    def connect(self):
        return self._record("connect")

    def set_fixed(self, lat, lon):
        return self._record("fixed", lat=lat, lon=lon)

    def play_route(self, coords, speed_mps, loop):
        return self._record("route", coords=list(coords), speed_mps=speed_mps, loop=loop)

    def pause(self):
        return self._record("pause")

    def resume(self):
        return self._record("resume")

    def stop(self):
        return self._record("stop")

    def clear(self):
        return self._record("clear")

    def set_jitter(self, radius_m):
        return self._record("jitter", radius_m=radius_m)


@pytest.fixture
def api():
    """A live loopback server on an ephemeral port, wired to a fake engine."""
    engine = FakeEngine()
    token = "test-token-value"
    server = build_server(engine, token, host="127.0.0.1", port=0)
    # Poll tightly so each test's teardown is not paced by the default 0.5s interval.
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()

    host, port = server.server_address[0], server.server_address[1]
    base = f"http://{host}:{port}"

    def call(path, payload=None, method=None, auth=token):
        data = None if payload is None else json.dumps(payload).encode()
        request = urllib.request.Request(
            base + path, data=data, method=method or ("POST" if data is not None else "GET")
        )
        request.add_header("Content-Type", "application/json")
        if auth is not None:
            request.add_header("Authorization", f"Bearer {auth}")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    call.base = base
    yield call, engine
    server.shutdown()
    server.server_close()


@pytest.fixture
def raw_post(api):
    """POST arbitrary bytes, bypassing JSON encoding, to exercise the decoder."""
    call, _ = api
    base = call.base

    def post(path, body):
        request = urllib.request.Request(base + path, data=body, method="POST")
        request.add_header("Content-Type", "application/json")
        request.add_header("Authorization", "Bearer test-token-value")
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as exc:
            return exc.code, json.loads(exc.read())

    return post


class TestAuth:
    def test_rejects_a_missing_token(self, api):
        call, _ = api
        status, body = call("/status", auth=None)
        assert status == 401
        assert body["error"]["code"] == "unauthorized"

    def test_rejects_a_wrong_token(self, api):
        call, _ = api
        assert call("/status", auth="nope")[0] == 401

    def test_accepts_the_right_token(self, api):
        call, _ = api
        assert call("/status")[0] == 200

    def test_health_needs_no_token(self, api):
        call, _ = api
        status, body = call("/health", auth=None)
        assert status == 200
        assert body["ok"] is True

    def test_an_unauthorised_call_never_reaches_the_engine(self, api):
        call, engine = api
        call("/location", {"lat": 1.0, "lon": 2.0}, auth=None)
        assert engine.calls == []


class TestEndpoints:
    def test_status(self, api):
        call, engine = api
        assert call("/status")[0] == 200
        assert engine.calls[0][0] == "status"

    def test_set_location(self, api):
        call, engine = api
        status, _ = call("/location", {"lat": 37.77, "lon": -122.42})
        assert status == 200
        assert engine.calls[0] == ("fixed", {"lat": 37.77, "lon": -122.42})

    def test_set_location_validates(self, api):
        call, engine = api
        status, body = call("/location", {"lat": 999, "lon": 0})
        assert status == 400
        assert "latitude" in body["error"]["message"]
        assert engine.calls == []

    def test_play_route(self, api):
        call, engine = api
        status, _ = call("/route", {"coords": [[0.0, 0.0], [0.0, 1.0]], "speed": "bike", "loop": True})
        assert status == 200
        name, kwargs = engine.calls[0]
        assert name == "route"
        assert kwargs["speed_mps"] == SPEED_PRESETS["bike"]
        assert kwargs["loop"] is True
        assert kwargs["coords"] == [Coord(0.0, 0.0), Coord(0.0, 1.0)]

    def test_route_rejects_a_bad_polyline(self, api):
        call, _ = api
        assert call("/route", {"coords": []})[0] == 400

    @pytest.mark.parametrize("path", ["/pause", "/resume", "/stop", "/clear", "/connect"])
    def test_simple_commands(self, api, path):
        call, engine = api
        assert call(path, {})[0] == 200
        assert engine.calls[0][0] == path.lstrip("/")

    def test_jitter(self, api):
        call, engine = api
        assert call("/jitter", {"radiusM": 5.0})[0] == 200
        assert engine.calls[0] == ("jitter", {"radius_m": 5.0})

    def test_jitter_rejects_absurd_radius(self, api):
        call, _ = api
        assert call("/jitter", {"radiusM": 5000.0})[0] == 400

    def test_body_that_is_not_json_at_all(self, raw_post):
        status, body = raw_post("/location", b"{not json")
        assert status == 400
        assert "invalid JSON" in body["error"]["message"]

    def test_body_that_is_a_json_array(self, raw_post):
        status, body = raw_post("/location", b"[1, 2, 3]")
        assert status == 400
        assert "JSON object" in body["error"]["message"]

    def test_unknown_endpoint(self, api):
        call, _ = api
        status, body = call("/teleport", {})
        assert status == 404
        assert body["error"]["code"] == "not_found"

    def test_missing_fields_are_rejected(self, api):
        call, _ = api
        status, _ = call("/location", {"lat": None, "lon": 1.0})
        assert status == 400


class TestDeviceErrorMapping:
    def test_device_errors_become_409_with_guidance(self, api):
        call, engine = api
        engine.raises = DeviceError("dev_mode_off", "Turn on Developer Mode.", False)
        status, body = call("/location", {"lat": 1.0, "lon": 2.0})
        assert status == 409
        assert body["error"] == {
            "code": "dev_mode_off",
            "message": "Turn on Developer Mode.",
            "recoverable": False,
        }

    def test_unexpected_errors_become_500(self, api):
        call, engine = api
        engine.raises = RuntimeError("boom")
        assert call("/status")[0] == 500
