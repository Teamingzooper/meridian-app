"""Location simulation for Xcode's iOS Simulator.

Simulators speak `simctl`, not the DVT channel a physical device uses, so this is
a separate backend behind the same small interface. It is also simpler: `simctl`
sets a location that persists without holding anything open, so there is no
session to keep alive.

Every subprocess call goes through an injected runner, which keeps the whole
module testable without a booted simulator.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable, Optional

from .device import KIND_SIMULATOR, TRANSPORT_SIMCTL, DeviceInfo
from .errors import DeviceError
from .geo import Coord

logger = logging.getLogger(__name__)

# (returncode, stdout, stderr)
Runner = Callable[..., Awaitable[tuple[int, str, str]]]


async def run_simctl(*args: str, timeout: float = 20.0) -> tuple[int, str, str]:
    """Invoke `xcrun simctl`, returning its exit code and output."""
    try:
        process = await asyncio.create_subprocess_exec(
            "xcrun", "simctl", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except FileNotFoundError:
        return 127, "", "xcrun not found"
    except asyncio.TimeoutError:
        return 124, "", "simctl timed out"

    return process.returncode or 0, stdout.decode(errors="replace"), stderr.decode(errors="replace")


def parse_booted(document: str) -> list[DeviceInfo]:
    """Read `simctl list devices booted -j` output into device records."""
    try:
        payload = json.loads(document)
    except (json.JSONDecodeError, TypeError):
        return []

    found: list[DeviceInfo] = []
    for runtime, entries in (payload.get("devices") or {}).items():
        # Runtime identifiers look like com.apple.CoreSimulator.SimRuntime.iOS-18-2.
        version = runtime.rsplit(".", 1)[-1].replace("iOS-", "").replace("-", ".")
        for entry in entries or []:
            if entry.get("state") != "Booted":
                continue
            udid = entry.get("udid") or ""
            if not udid:
                continue
            found.append(DeviceInfo(
                udid=udid,
                name=entry.get("name") or "Simulator",
                ios_version=version,
                transport=TRANSPORT_SIMCTL,
                kind=KIND_SIMULATOR,
            ))
    return found


async def list_simulators(runner: Optional[Runner] = None) -> list[DeviceInfo]:
    """Booted simulators. Shut-down ones cannot take a location, so are omitted."""
    run = runner or run_simctl
    code, stdout, _ = await run("list", "devices", "booted", "-j")
    if code != 0:
        return []
    return parse_booted(stdout)


class SimulatorSession:
    """The simulator counterpart to `LocationSession`.

    Presents the same surface so the engine does not care which it is driving.
    """

    def __init__(self, runner: Optional[Runner] = None) -> None:
        self._run: Runner = runner or run_simctl
        self._info: Optional[DeviceInfo] = None

    @property
    def is_open(self) -> bool:
        return self._info is not None

    @property
    def info(self) -> Optional[DeviceInfo]:
        return self._info

    async def open(self, udid: Optional[str] = None) -> DeviceInfo:
        simulators = await list_simulators(self._run)
        if not simulators:
            raise DeviceError(
                "no_simulator",
                "No booted simulator. Start one in Xcode, then try again.",
                True,
            )

        if udid:
            chosen = next((s for s in simulators if s.udid == udid), None)
            if chosen is None:
                raise DeviceError(
                    "no_simulator", "That simulator isn't booted any more.", True
                )
        else:
            chosen = simulators[0]

        self._info = chosen
        logger.info("driving simulator %s (iOS %s)", chosen.name, chosen.ios_version)
        return chosen

    async def set_location(self, coord: Coord) -> None:
        if self._info is None:
            raise DeviceError("no_simulator", "No simulator selected.", True)

        code, _, stderr = await self._run(
            "location", self._info.udid, "set", f"{coord.lat},{coord.lon}"
        )
        if code != 0:
            raise self._failure(stderr)

    async def clear(self) -> None:
        if self._info is None:
            return
        code, _, stderr = await self._run("location", self._info.udid, "clear")
        if code != 0:
            raise self._failure(stderr)

    def _failure(self, stderr: str) -> DeviceError:
        detail = stderr.strip().splitlines()[-1] if stderr.strip() else ""
        if "Unable to find" in detail or "not booted" in detail.lower():
            self._info = None
            return DeviceError(
                "no_simulator", "That simulator is no longer booted.", True
            )
        return DeviceError(
            "simulator_failed",
            f"The simulator refused the location{': ' + detail if detail else '.'}",
            True,
        )

    async def close(self) -> None:
        # simctl holds nothing open, so there is nothing to tear down.
        self._info = None
