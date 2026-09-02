"""Tests for the simctl backend. The subprocess is injected, so no simulator runs."""
import json

import pytest

from meridiand.device import KIND_SIMULATOR, TRANSPORT_SIMCTL
from meridiand.errors import DeviceError
from meridiand.geo import Coord
from meridiand.simulator import SimulatorSession, list_simulators, parse_booted

BOOTED = json.dumps({
    "devices": {
        "com.apple.CoreSimulator.SimRuntime.iOS-18-2": [
            {"udid": "AAA-111", "name": "iPhone 16 Pro", "state": "Booted"},
            {"udid": "BBB-222", "name": "iPhone 16", "state": "Shutdown"},
        ],
        "com.apple.CoreSimulator.SimRuntime.iOS-17-5": [
            {"udid": "CCC-333", "name": "iPad Air", "state": "Booted"},
        ],
    }
})


class FakeRunner:
    """Records simctl invocations and replays canned results."""

    def __init__(self, results=None):
        self.calls = []
        self.results = results or {}
        self.default = (0, "", "")

    async def __call__(self, *args, timeout=20.0):
        self.calls.append(args)
        for key, result in self.results.items():
            if key in args:
                return result
        return self.default


class TestParseBooted:
    def test_returns_only_booted_devices(self):
        devices = parse_booted(BOOTED)
        assert {d.udid for d in devices} == {"AAA-111", "CCC-333"}

    def test_reads_names(self):
        assert any(d.name == "iPhone 16 Pro" for d in parse_booted(BOOTED))

    def test_derives_the_ios_version_from_the_runtime(self):
        versions = {d.udid: d.ios_version for d in parse_booted(BOOTED)}
        assert versions["AAA-111"] == "18.2"
        assert versions["CCC-333"] == "17.5"

    def test_marks_them_as_simulators(self):
        for device in parse_booted(BOOTED):
            assert device.kind == KIND_SIMULATOR
            assert device.transport == TRANSPORT_SIMCTL
            assert device.is_simulator

    def test_tolerates_junk(self):
        assert parse_booted("not json") == []
        assert parse_booted("{}") == []
        assert parse_booted(json.dumps({"devices": {}})) == []

    def test_skips_entries_with_no_udid(self):
        payload = json.dumps({"devices": {"x.iOS-18-0": [{"name": "n", "state": "Booted"}]}})
        assert parse_booted(payload) == []


class TestListing:
    @pytest.mark.asyncio
    async def test_lists_booted_simulators(self):
        runner = FakeRunner({"list": (0, BOOTED, "")})
        assert len(await list_simulators(runner)) == 2

    @pytest.mark.asyncio
    async def test_empty_when_simctl_fails(self):
        runner = FakeRunner({"list": (127, "", "xcrun not found")})
        assert await list_simulators(runner) == []


class TestSession:
    @pytest.mark.asyncio
    async def test_opens_the_first_booted_simulator(self):
        session = SimulatorSession(FakeRunner({"list": (0, BOOTED, "")}))
        info = await session.open()
        assert info.udid == "AAA-111"
        assert session.is_open

    @pytest.mark.asyncio
    async def test_opens_a_named_simulator(self):
        session = SimulatorSession(FakeRunner({"list": (0, BOOTED, "")}))
        assert (await session.open("CCC-333")).name == "iPad Air"

    @pytest.mark.asyncio
    async def test_reports_when_nothing_is_booted(self):
        session = SimulatorSession(FakeRunner({"list": (0, json.dumps({"devices": {}}), "")}))
        with pytest.raises(DeviceError) as caught:
            await session.open()
        assert caught.value.code == "no_simulator"
        assert "Xcode" in caught.value.message

    @pytest.mark.asyncio
    async def test_reports_an_unknown_simulator(self):
        session = SimulatorSession(FakeRunner({"list": (0, BOOTED, "")}))
        with pytest.raises(DeviceError):
            await session.open("ZZZ-999")

    @pytest.mark.asyncio
    async def test_sets_a_location_through_simctl(self):
        runner = FakeRunner({"list": (0, BOOTED, "")})
        session = SimulatorSession(runner)
        await session.open()
        await session.set_location(Coord(48.8584, 2.2945))
        assert ("location", "AAA-111", "set", "48.8584,2.2945") in runner.calls

    @pytest.mark.asyncio
    async def test_clears_through_simctl(self):
        runner = FakeRunner({"list": (0, BOOTED, "")})
        session = SimulatorSession(runner)
        await session.open()
        await session.clear()
        assert ("location", "AAA-111", "clear") in runner.calls

    @pytest.mark.asyncio
    async def test_setting_without_opening_is_an_error(self):
        with pytest.raises(DeviceError):
            await SimulatorSession(FakeRunner()).set_location(Coord(1.0, 2.0))

    @pytest.mark.asyncio
    async def test_a_shutdown_simulator_is_reported_clearly(self):
        runner = FakeRunner({"list": (0, BOOTED, "")})
        session = SimulatorSession(runner)
        await session.open()
        runner.results["location"] = (1, "", "Unable to find device")
        with pytest.raises(DeviceError) as caught:
            await session.set_location(Coord(1.0, 2.0))
        assert caught.value.code == "no_simulator"
        # The stale session is dropped so the next call re-selects.
        assert not session.is_open

    @pytest.mark.asyncio
    async def test_other_failures_surface_the_detail(self):
        runner = FakeRunner({"list": (0, BOOTED, "")})
        session = SimulatorSession(runner)
        await session.open()
        runner.results["location"] = (1, "", "something specific went wrong")
        with pytest.raises(DeviceError, match="something specific"):
            await session.set_location(Coord(1.0, 2.0))

    @pytest.mark.asyncio
    async def test_clearing_an_unopened_session_is_harmless(self):
        await SimulatorSession(FakeRunner()).clear()

    @pytest.mark.asyncio
    async def test_close_releases_the_selection(self):
        session = SimulatorSession(FakeRunner({"list": (0, BOOTED, "")}))
        await session.open()
        await session.close()
        assert not session.is_open
