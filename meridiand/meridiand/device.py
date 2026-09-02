"""A live location-simulation channel against a connected iPhone.

The simulated location holds only while the DVT channel stays open — that is why
`pymobiledevice3 developer dvt simulate-location set` appears to hang, and why
shelling out to it per update cannot work. `LocationSession` keeps the channel
open explicitly via an `AsyncExitStack` and pushes coordinates down it.

Every pymobiledevice3 failure leaves here as a `DeviceError` carrying a next step.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import AsyncExitStack, suppress
from dataclasses import dataclass
from typing import Any, Optional

from .errors import DeviceError, classify, no_device
from .geo import Coord

logger = logging.getLogger(__name__)

# Where pymobiledevice3's tunneld publishes its active tunnels.
DEFAULT_TUNNELD_ADDRESS = ("127.0.0.1", 49151)


@dataclass(frozen=True)
class DeviceInfo:
    udid: str
    name: str
    ios_version: str

    def as_dict(self) -> dict:
        return {"udid": self.udid, "name": self.name, "iosVersion": self.ios_version}


def _describe(rsd: Any) -> DeviceInfo:
    """Pull identity off an RSD, tolerating attributes that move between releases."""
    udid = getattr(rsd, "udid", "") or ""
    version = getattr(rsd, "product_version", "") or ""

    name = ""
    for attr in ("device_name", "name"):
        name = getattr(rsd, attr, "") or ""
        if name:
            break
    if not name:
        # Fall back to the hardware identifier, e.g. "iPhone16,2".
        name = getattr(rsd, "product_type", "") or "iPhone"

    return DeviceInfo(udid=udid, name=name, ios_version=version)


class LocationSession:
    """One open DVT location channel, plus the reconnect logic around it."""

    def __init__(self, tunneld_address: tuple[str, int] = DEFAULT_TUNNELD_ADDRESS) -> None:
        self._tunneld_address = tunneld_address
        self._stack: Optional[AsyncExitStack] = None
        self._simulation: Any = None
        self._info: Optional[DeviceInfo] = None
        self._lock = asyncio.Lock()
        self._mounted_udids: set[str] = set()

    @property
    def is_open(self) -> bool:
        return self._simulation is not None

    @property
    def info(self) -> Optional[DeviceInfo]:
        return self._info

    async def _discover(self, udid: Optional[str]) -> Any:
        """Find a tunnelled device, or raise a DeviceError explaining why not."""
        from pymobiledevice3.tunneld.api import get_tunneld_devices

        try:
            rsds = await get_tunneld_devices(self._tunneld_address)
        except Exception as exc:
            raise classify(exc) from exc

        if not rsds:
            raise no_device()

        if udid:
            for rsd in rsds:
                if getattr(rsd, "udid", None) == udid:
                    return rsd
            raise no_device()

        return rsds[0]

    async def _mount_ddi(self, udid: str) -> None:
        """Mount the developer disk image, which DVT needs before it will attach.

        Mounting persists until the device reboots, so this is attempted once per
        device per session and only after DVT has actually refused to open.
        """
        if udid in self._mounted_udids:
            return

        from pymobiledevice3.lockdown import create_using_usbmux
        from pymobiledevice3.services.mobile_image_mounter import auto_mount

        logger.info("mounting developer disk image on %s", udid)
        try:
            lockdown = await create_using_usbmux(serial=udid)
            await auto_mount(lockdown)
        except Exception as exc:
            error = classify(exc)
            # "Already mounted" surfaces as a generic failure; DVT will confirm.
            if error.code == "unknown":
                logger.debug("auto-mount reported: %s", exc)
            else:
                raise error from exc

        self._mounted_udids.add(udid)

    async def _attach(self, rsd: Any) -> None:
        """Open DvtProvider + LocationSimulation and hold them open."""
        from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
        from pymobiledevice3.services.dvt.instruments.location_simulation import (
            LocationSimulation,
        )

        stack = AsyncExitStack()
        try:
            dvt = await stack.enter_async_context(DvtProvider(rsd))
            self._simulation = await stack.enter_async_context(LocationSimulation(dvt))
        except BaseException:
            await stack.aclose()
            raise

        self._stack = stack

    async def open(self, udid: Optional[str] = None) -> DeviceInfo:
        """Connect and open the location channel, mounting the DDI if required."""
        async with self._lock:
            if self.is_open:
                assert self._info is not None
                return self._info

            rsd = await self._discover(udid)
            info = _describe(rsd)

            try:
                await self._attach(rsd)
            except Exception as first_failure:
                # DVT refuses to attach when the DDI isn't mounted. Mount, retry once.
                logger.debug("DVT attach failed (%s); trying a DDI mount", first_failure)
                try:
                    await self._mount_ddi(info.udid)
                except DeviceError:
                    raise
                except Exception as exc:
                    raise classify(exc) from exc

                try:
                    await self._attach(rsd)
                except Exception as exc:
                    raise classify(exc) from exc

            self._info = info
            logger.info("location channel open on %s (iOS %s)", info.name, info.ios_version)
            return info

    async def set_location(self, coord: Coord) -> None:
        """Push a coordinate to the device."""
        if not self.is_open:
            raise no_device()
        try:
            await self._simulation.set(coord.lat, coord.lon)
        except Exception as exc:
            # A dead channel cannot be reused; drop it so the next call reconnects.
            await self._teardown()
            raise classify(exc) from exc

    async def clear(self) -> None:
        """Hand the device back its real GPS."""
        if not self.is_open:
            return
        try:
            await self._simulation.clear()
        except Exception as exc:
            await self._teardown()
            raise classify(exc) from exc

    async def _teardown(self) -> None:
        self._simulation = None
        self._info = None
        if self._stack is not None:
            stack, self._stack = self._stack, None
            with suppress(Exception):
                await stack.aclose()

    async def close(self) -> None:
        """Close the channel. Does not clear the simulated location."""
        async with self._lock:
            await self._teardown()
