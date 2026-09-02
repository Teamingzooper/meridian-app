"""End-to-end preflight: walk the whole chain and report where it breaks.

Each check prints a line and either continues or stops with the one thing to go
fix. Running this is the fastest way to tell a cable problem from a Developer
Mode problem from an iOS-version problem.
"""

from __future__ import annotations

import asyncio
import platform
import sys
from contextlib import AsyncExitStack

from .device import LocationSession
from .errors import DeviceError, classify
from .geo import Coord

OK = "  ok "
FAIL = "FAIL "
INFO = "     "

# Somewhere unmistakable, so a glance at Maps on the device confirms the write.
PROBE = Coord(48.858370, 2.294481)  # Eiffel Tower


def _line(marker: str, text: str) -> None:
    print(f"{marker} {text}", flush=True)


async def run() -> int:
    _line(INFO, "Meridian preflight")
    print()

    if platform.system() != "Darwin":
        _line(FAIL, "Meridian's no-root tunnel is macOS only.")
        return 1
    _line(OK, f"macOS {platform.mac_ver()[0]}")

    # 1. Is anything plugged in at all?
    try:
        from pymobiledevice3.usbmux import list_devices

        devices = await asyncio.wait_for(list_devices(), timeout=15)
    except Exception as exc:
        _line(FAIL, f"Could not reach usbmuxd: {exc}")
        return 1

    if not devices:
        _line(FAIL, "No iPhone found. Connect it with a USB cable and unlock it.")
        return 1
    _line(OK, f"{len(devices)} device(s) visible over USB")

    # 2. Can we get a tunnel, and which kind?
    session = LocationSession()
    try:
        info = await session.open()
    except DeviceError as exc:
        _line(FAIL, exc.message)
        return 1
    except Exception as exc:
        _line(FAIL, classify(exc).message)
        return 1

    _line(OK, f"tunnel up via {info.transport}" + ("  (no root needed)" if info.transport == "native" else ""))
    _line(OK, f"device: {info.name}, iOS {info.ios_version}")
    _line(OK, "developer disk image mounted and DVT channel open")

    # 3. Actually move it, then put it back.
    try:
        await session.set_location(PROBE)
        _line(OK, f"wrote a test location ({PROBE.lat}, {PROBE.lon}) — check Maps on the phone")
        await asyncio.sleep(2)
        await session.clear()
        _line(OK, "cleared it again; the phone has its real GPS back")
    except DeviceError as exc:
        _line(FAIL, exc.message)
        return 1
    finally:
        await session.close()

    print()
    _line(INFO, "All good. Meridian can drive this device.")
    return 0


def main() -> int:
    try:
        return asyncio.run(run())
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
