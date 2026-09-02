"""A live location-simulation channel against a connected iPhone.

The simulated location holds only while the DVT channel stays open — that is why
`pymobiledevice3 developer dvt simulate-location set` appears to hang, and why
shelling out to it per update cannot work. `LocationSession` keeps the channel
open explicitly via an `AsyncExitStack` and pushes coordinates down it.

Two transports get us to the device, tried in order:

* **native** — piggybacks Apple's own `remoted` tunnel through `remotepairingd`.
  macOS only, needs no root, and coexists with Xcode. This is the normal path.
* **tunneld** — pymobiledevice3's own tunnel daemon, which does need root. Only
  reached when the native path is unavailable.

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

# Where pymobiledevice3's tunneld publishes its tunnels, when we need it at all.
DEFAULT_TUNNELD_ADDRESS = ("127.0.0.1", 49151)

TRANSPORT_NATIVE = "native"
TRANSPORT_TUNNELD = "tunneld"


@dataclass(frozen=True)
class DeviceInfo:
    udid: str
    name: str
    ios_version: str
    transport: str = TRANSPORT_NATIVE

    def as_dict(self) -> dict:
        return {
            "udid": self.udid,
            "name": self.name,
            "iosVersion": self.ios_version,
            "transport": self.transport,
        }


def _describe(rsd: Any, transport: str) -> DeviceInfo:
    """Pull identity off an RSD, tolerating attributes that move between releases."""
    name = ""
    for attr in ("device_name", "name"):
        name = getattr(rsd, attr, "") or ""
        if name:
            break
    if not name:
        # Fall back to the hardware identifier, e.g. "iPhone16,2".
        name = getattr(rsd, "product_type", "") or "iPhone"

    return DeviceInfo(
        udid=getattr(rsd, "udid", "") or "",
        name=name,
        ios_version=getattr(rsd, "product_version", "") or "",
        transport=transport,
    )


class LocationSession:
    """One open DVT location channel, plus the transport that carries it."""

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

    # ----------------------------------------------------------------- transport

    async def _open_native(self, stack: AsyncExitStack, udid: Optional[str]) -> Any:
        """Apple's own tunnel via remotepairingd. No root, coexists with Xcode."""
        from pymobiledevice3.remote.native_tunnel import NativeRemotedTunnel

        tunnel = NativeRemotedTunnel(serial=udid)
        rsd = await stack.enter_async_context(tunnel)
        logger.info("using Apple's native tunnel (no root)")
        return rsd

    async def _open_tunneld(self, stack: AsyncExitStack, udid: Optional[str]) -> Any:
        """pymobiledevice3's own tunnel daemon, which must already be running as root."""
        from pymobiledevice3.tunneld.api import get_tunneld_devices

        rsds = await get_tunneld_devices(self._tunneld_address)
        if not rsds:
            raise no_device()

        chosen = None
        if udid:
            chosen = next((r for r in rsds if getattr(r, "udid", None) == udid), None)
        else:
            chosen = rsds[0]

        # Close the tunnels we are not going to use.
        for rsd in rsds:
            if rsd is not chosen:
                with suppress(Exception):
                    await rsd.close()

        if chosen is None:
            raise no_device()

        stack.push_async_callback(lambda: self._safe_close(chosen))
        logger.info("using tunneld at %s:%d", *self._tunneld_address)
        return chosen

    @staticmethod
    async def _safe_close(rsd: Any) -> None:
        with suppress(Exception):
            await rsd.close()

    async def _open_transport(self, stack: AsyncExitStack, udid: Optional[str]) -> tuple[Any, str]:
        """Get a connected RSD, preferring the path that needs no privileges."""
        try:
            return await self._open_native(stack, udid), TRANSPORT_NATIVE
        except DeviceError:
            raise
        except Exception as native_failure:
            logger.info("native tunnel unavailable (%s); trying tunneld", native_failure)

        try:
            return await self._open_tunneld(stack, udid), TRANSPORT_TUNNELD
        except DeviceError:
            raise
        except Exception as exc:
            raise classify(exc) from exc

    # -------------------------------------------------------------------- device

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
            lockdown = await create_using_usbmux(serial=udid or None)
            await auto_mount(lockdown)
        except Exception as exc:
            error = classify(exc)
            # "Already mounted" surfaces as a generic failure; let DVT be the judge.
            if error.code == "unknown":
                logger.debug("auto-mount reported: %s", exc)
            else:
                raise error from exc

        self._mounted_udids.add(udid)

    async def _attach(self, stack: AsyncExitStack, rsd: Any) -> Any:
        """Open DvtProvider + LocationSimulation on the given stack."""
        from pymobiledevice3.services.dvt.instruments.dvt_provider import DvtProvider
        from pymobiledevice3.services.dvt.instruments.location_simulation import (
            LocationSimulation,
        )

        dvt = await stack.enter_async_context(DvtProvider(rsd))
        return await stack.enter_async_context(LocationSimulation(dvt))

    async def open(self, udid: Optional[str] = None) -> DeviceInfo:
        """Connect and open the location channel, mounting the DDI if required."""
        async with self._lock:
            if self.is_open:
                assert self._info is not None
                return self._info

            stack = AsyncExitStack()
            try:
                rsd, transport = await self._open_transport(stack, udid)
                info = _describe(rsd, transport)

                try:
                    simulation = await self._attach(stack, rsd)
                except Exception as first_failure:
                    # DVT refuses to attach when the DDI isn't mounted. Mount, retry once.
                    logger.debug("DVT attach failed (%s); trying a DDI mount", first_failure)
                    try:
                        await self._mount_ddi(info.udid)
                        simulation = await self._attach(stack, rsd)
                    except DeviceError:
                        raise
                    except Exception as exc:
                        raise classify(exc) from exc
            except BaseException:
                await stack.aclose()
                raise

            self._stack = stack
            self._simulation = simulation
            self._info = info
            logger.info(
                "location channel open on %s (iOS %s) over %s",
                info.name, info.ios_version, info.transport,
            )
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
