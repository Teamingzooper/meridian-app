"""Tests for the `meridian` command line. No daemon, no device."""
import json

import pytest

from meridiand.cli import (
    CommandFailed,
    DaemonUnavailable,
    build_parser,
    describe,
    read_token,
    resolve_speed,
    run,
)
from meridiand.route import SPEED_PRESETS

GPX = """<?xml version="1.0"?>
<gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
  <trk><name>Loop</name><trkseg>
    <trkpt lat="1.0" lon="2.0"/><trkpt lat="3.0" lon="4.0"/>
  </trkseg></trk>
</gpx>"""


class Recorder:
    """Stands in for the HTTP layer, capturing what the CLI asked for."""

    def __init__(self, reply=None):
        self.calls = []
        self.reply = reply or {"mode": "idle", "device": {"name": "iPhone"}}

    def __call__(self, path, payload=None):
        self.calls.append((path, payload))
        return self.reply


def parse(argv):
    return build_parser().parse_args(argv)


class TestArgumentParsing:
    def test_status(self):
        assert parse(["status"]).command == "status"

    def test_set_takes_coordinates(self):
        args = parse(["set", "51.5", "-0.12"])
        assert (args.latitude, args.longitude) == (51.5, -0.12)

    def test_route_defaults_to_walking(self):
        assert parse(["route", "a.gpx"]).speed == "walk"

    def test_route_flags(self):
        args = parse(["route", "a.gpx", "--speed", "drive", "--loop"])
        assert args.speed == "drive" and args.loop is True

    def test_json_flag(self):
        assert parse(["--json", "status"]).json is True

    def test_a_command_is_required(self):
        with pytest.raises(SystemExit):
            parse([])

    def test_rejects_an_unknown_command(self):
        with pytest.raises(SystemExit):
            parse(["teleport"])


class TestResolveSpeed:
    @pytest.mark.parametrize("name", sorted(SPEED_PRESETS))
    def test_accepts_each_preset(self, name):
        assert resolve_speed(name) == {"speed": name}

    def test_accepts_a_raw_number(self):
        assert resolve_speed("7.5") == {"speedMps": 7.5}

    def test_rejects_nonsense(self):
        with pytest.raises(CommandFailed, match="unknown speed"):
            resolve_speed("teleport")


class TestDispatch:
    def test_status_calls_status(self):
        call = Recorder()
        run(parse(["status"]), call)
        assert call.calls == [("status", None)]

    def test_set_sends_coordinates(self):
        call = Recorder()
        run(parse(["set", "51.5", "-0.12"]), call)
        assert call.calls == [("location", {"lat": 51.5, "lon": -0.12})]

    def test_clear_and_stop(self):
        for command in ("clear", "stop"):
            call = Recorder()
            run(parse([command]), call)
            assert call.calls[0][0] == command

    def test_route_loads_the_gpx_and_sends_its_points(self, tmp_path):
        path = tmp_path / "loop.gpx"
        path.write_text(GPX)

        call = Recorder()
        run(parse(["route", str(path), "--speed", "bike", "--loop"]), call)

        endpoint, payload = call.calls[0]
        assert endpoint == "route"
        assert payload["coords"] == [[1.0, 2.0], [3.0, 4.0]]
        assert payload["speed"] == "bike"
        assert payload["loop"] is True

    def test_route_reports_a_missing_file(self, tmp_path):
        with pytest.raises(CommandFailed, match="couldn't read"):
            run(parse(["route", str(tmp_path / "nope.gpx")]), Recorder())

    def test_route_reports_a_broken_file(self, tmp_path):
        path = tmp_path / "bad.gpx"
        path.write_text("<gpx><trk>")
        with pytest.raises(CommandFailed, match="not valid GPX"):
            run(parse(["route", str(path)]), Recorder())

    def test_route_reports_an_empty_file(self, tmp_path):
        path = tmp_path / "empty.gpx"
        path.write_text('<gpx xmlns="http://www.topografix.com/GPX/1/1"></gpx>')
        with pytest.raises(CommandFailed, match="no usable points"):
            run(parse(["route", str(path)]), Recorder())


class TestDescribe:
    def test_idle(self):
        assert describe({"mode": "idle", "device": {"name": "Phone"}}) == "Phone: real GPS"

    def test_fixed_shows_coordinates(self):
        line = describe({
            "mode": "fixed", "device": {"name": "Phone"},
            "location": {"lat": 48.8584, "lon": 2.2945},
        })
        assert "48.85840" in line and "2.29450" in line

    def test_route_shows_progress(self):
        line = describe({
            "mode": "route", "device": {"name": "Phone"},
            "location": {"lat": 1.0, "lon": 2.0},
            "route": {"progress": 0.42, "paused": False},
        })
        assert "42%" in line and "moving" in line

    def test_route_shows_paused(self):
        line = describe({
            "mode": "route", "device": {"name": "Phone"},
            "location": {"lat": 1.0, "lon": 2.0},
            "route": {"progress": 0.1, "paused": True},
        })
        assert "paused" in line

    def test_copes_with_no_device(self):
        assert "no device" in describe({"mode": "idle"})


class TestToken:
    def test_reads_and_strips(self, tmp_path):
        (tmp_path / "token").write_text("  secret-value\n")
        assert read_token(tmp_path) == "secret-value"

    def test_missing_token_is_a_clear_failure(self, tmp_path):
        with pytest.raises(DaemonUnavailable, match="helper running"):
            read_token(tmp_path)
