"""The running sidecar: one event loop, one device channel, one driver task.

The HTTP server is synchronous and pymobiledevice3 is asynchronous, so the async
half lives on a dedicated loop in a background thread. Every public method here
is synchronous and safe to call from the server thread; each hands a coroutine to
that loop and waits for it.

All mutable state is touched only from inside the loop thread, which is what
keeps this free of locks beyond the session's own.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Optional, Sequence

from .device import (
    DEFAULT_TUNNELD_ADDRESS,
    KIND_DEVICE,
    KIND_SIMULATOR,
    LocationSession,
    list_physical_devices,
)
from .errors import DeviceError, classify
from .geo import Coord, jitter, total_distance
from .playback import Playback
from .route import RoutePlayer
from .simulator import SimulatorSession, list_simulators

logger = logging.getLogger(__name__)

MODE_IDLE = "idle"
MODE_FIXED = "fixed"
MODE_ROUTE = "route"

# Real GPS receivers report about once a second. Matching that keeps the
# simulated track from looking mechanically smooth.
DEFAULT_TICK_HZ = 1.0

# How long a synchronous caller waits for the loop thread. Opening a channel can
# involve mounting a developer disk image, which is slow the first time.
CALL_TIMEOUT_S = 180.0


class Engine:
    def __init__(
        self,
        tunneld_address: tuple[str, int] = DEFAULT_TUNNELD_ADDRESS,
        tick_hz: float = DEFAULT_TICK_HZ,
        jitter_m: float = 0.0,
    ) -> None:
        if tick_hz <= 0:
            raise ValueError("tick_hz must be positive")

        self._tunneld_address = tunneld_address
        self._session: Any = LocationSession(tunneld_address)
        #: (udid, kind) the user picked, or None to take whatever is attached.
        self._selected: Optional[tuple[str, str]] = None
        self._tick_interval = 1.0 / tick_hz
        self._jitter_m = jitter_m

        self._mode = MODE_IDLE
        self._target: Optional[Coord] = None
        self._playback: Optional[Playback] = None
        self._last_error: Optional[DeviceError] = None
        self._last_pushed: Optional[Coord] = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None
        self._driver: Optional[asyncio.Task] = None
        self._ready = threading.Event()

    # ---------------------------------------------------------------- lifecycle

    def start(self) -> None:
        """Spin up the loop thread and its driver task."""
        if self._thread is not None:
            return

        self._thread = threading.Thread(target=self._run_loop, name="meridian-loop", daemon=True)
        self._thread.start()
        self._ready.wait(timeout=10.0)

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._driver = loop.create_task(self._drive())
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            loop.close()

    def shutdown(self) -> None:
        """Stop driving and close the device channel."""
        if self._loop is None:
            return
        try:
            self._submit(self._shutdown_async())
        except Exception:
            logger.debug("shutdown encountered an error", exc_info=True)
        self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread is not None:
            self._thread.join(timeout=5.0)

    async def _shutdown_async(self) -> None:
        if self._driver is not None:
            self._driver.cancel()
        await self._session.close()

    def _submit(self, coro) -> Any:
        """Run a coroutine on the loop thread and wait for its result."""
        if self._loop is None:
            raise RuntimeError("engine not started")
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=CALL_TIMEOUT_S)

    # ------------------------------------------------------------------ driving

    async def _drive(self) -> None:
        """Push the current position to the device, forever, on a tick."""
        while True:
            try:
                await self._tick()
            except asyncio.CancelledError:
                raise
            except DeviceError as exc:
                self._last_error = exc
                if not exc.recoverable:
                    # Nothing will change until the user acts, so stop pushing.
                    self._mode = MODE_IDLE
                    logger.warning("halting playback: %s", exc.message)
            except Exception as exc:  # pragma: no cover - defensive
                self._last_error = classify(exc)
                logger.debug("unexpected driver error", exc_info=True)

            await asyncio.sleep(self._tick_interval)

    async def _tick(self) -> None:
        if self._mode == MODE_IDLE:
            return

        now = time.monotonic()
        coord = self._current_coord(now)
        if coord is None:
            return

        if not self._session.is_open:
            await self._open_session()

        await self._session.set_location(coord)
        self._last_pushed = coord
        self._last_error = None

        # A finished one-shot route holds its final position rather than snapping back.
        if self._mode == MODE_ROUTE and self._playback is not None and self._playback.is_finished(now):
            logger.info("route complete; holding at destination")
            self._target = self._playback.position(now)
            self._playback = None
            self._mode = MODE_FIXED

    def _current_coord(self, now: float) -> Optional[Coord]:
        if self._mode == MODE_ROUTE and self._playback is not None:
            coord = self._playback.position(now)
        elif self._mode == MODE_FIXED and self._target is not None:
            coord = self._target
        else:
            return None

        return jitter(coord, self._jitter_m) if self._jitter_m > 0 else coord

    # ------------------------------------------------------------- sync commands

    def list_devices(self) -> dict:
        """Everything Meridian could drive: attached hardware and booted simulators."""
        physical, simulators = self._submit(self._gather_devices())
        return {
            "devices": [d.as_dict() for d in physical + simulators],
            "selected": (
                {"udid": self._selected[0], "kind": self._selected[1]}
                if self._selected else None
            ),
        }

    async def _gather_devices(self) -> tuple[list, list]:
        # Both listings are independent, so run them together rather than in turn.
        physical, simulators = await asyncio.gather(
            list_physical_devices(), list_simulators(), return_exceptions=True
        )
        return (
            physical if isinstance(physical, list) else [],
            simulators if isinstance(simulators, list) else [],
        )

    def select_device(self, udid: Optional[str], kind: str = KIND_DEVICE) -> dict:
        """Choose which device to drive, swapping backend if the kind changed."""
        if kind not in (KIND_DEVICE, KIND_SIMULATOR):
            raise ValueError(f"unknown device kind '{kind}'")

        self._submit(self._apply_selection(udid, kind))
        return self.status()

    async def _apply_selection(self, udid: Optional[str], kind: str) -> None:
        await self._session.close()

        # A simulator speaks simctl and a phone speaks DVT, so the backend swaps.
        wanted_simulator = kind == KIND_SIMULATOR
        have_simulator = isinstance(self._session, SimulatorSession)
        if wanted_simulator != have_simulator:
            self._session = (
                SimulatorSession() if wanted_simulator
                else LocationSession(self._tunneld_address)
            )

        self._selected = (udid, kind) if udid else None
        self._mode = MODE_IDLE
        self._target = None
        self._playback = None
        self._last_pushed = None
        self._last_error = None

        await self._open_session()

    async def _open_session(self) -> None:
        """Open the current backend against the selected device."""
        udid = self._selected[0] if self._selected else None
        await self._session.open(udid)

    def connect(self) -> dict:
        """Open the device channel eagerly so the UI can report device details."""
        self._submit(self._open_session())
        self._last_error = None
        return self.status()

    def set_fixed(self, lat: float, lon: float) -> dict:
        """Hold the device at a single point."""
        coord = Coord(lat, lon)
        self._submit(self._apply_fixed(coord))
        return self.status()

    async def _apply_fixed(self, coord: Coord) -> None:
        if not self._session.is_open:
            await self._open_session()
        self._mode = MODE_FIXED
        self._target = coord
        self._playback = None
        # Push immediately so the UI does not wait out a tick for feedback.
        await self._session.set_location(
            jitter(coord, self._jitter_m) if self._jitter_m > 0 else coord
        )
        self._last_pushed = coord
        self._last_error = None

    def play_route(
        self, coords: Sequence[Coord], speed_mps: float, loop: bool = False,
        realistic: bool = True,
    ) -> dict:
        """Start walking the device along a polyline."""
        player = RoutePlayer(
            list(coords), speed_mps=speed_mps, loop=loop, realistic=realistic
        )
        self._submit(self._apply_route(player))
        return self.status()

    async def _apply_route(self, player: RoutePlayer) -> None:
        if not self._session.is_open:
            await self._open_session()
        self._mode = MODE_ROUTE
        self._playback = Playback(player, now=time.monotonic())
        self._target = None
        self._last_error = None

    def pause(self) -> dict:
        self._submit(self._mutate_playback("pause"))
        return self.status()

    def resume(self) -> dict:
        self._submit(self._mutate_playback("resume"))
        return self.status()

    async def _mutate_playback(self, action: str) -> None:
        if self._playback is None:
            return
        getattr(self._playback, action)(time.monotonic())

    def stop(self) -> dict:
        """End playback, holding wherever the device currently is."""
        self._submit(self._apply_stop())
        return self.status()

    async def _apply_stop(self) -> None:
        if self._playback is not None:
            self._target = self._playback.position(time.monotonic())
            self._playback = None
            self._mode = MODE_FIXED

    def clear(self) -> dict:
        """Release the device back to its real GPS."""
        self._submit(self._apply_clear())
        return self.status()

    async def _apply_clear(self) -> None:
        self._mode = MODE_IDLE
        self._target = None
        self._playback = None
        self._last_pushed = None
        await self._session.clear()
        self._last_error = None

    # -------------------------------------------------------------------- status

    def status(self) -> dict:
        now = time.monotonic()
        info = self._session.info

        route: Optional[dict] = None
        if self._playback is not None:
            player = self._playback.player
            route = {
                "progress": round(self._playback.progress(now), 4),
                "paused": self._playback.is_paused,
                "loop": player.loop,
                "speedMps": player.speed_mps,
                "lengthM": round(player.length_m, 1),
                "durationS": round(player.duration_s, 1),
                "remainingS": round(max(0.0, player.duration_s - self._playback.elapsed(now)), 1),
            }

        return {
            "engine": "running",
            "connected": self._session.is_open,
            "device": info.as_dict() if info else None,
            "mode": self._mode,
            "location": (
                {"lat": self._last_pushed.lat, "lon": self._last_pushed.lon}
                if self._last_pushed
                else None
            ),
            "route": route,
            "jitterM": self._jitter_m,
            "error": self._last_error.as_dict() if self._last_error else None,
        }

    def set_jitter(self, radius_m: float) -> dict:
        if radius_m < 0:
            raise ValueError("jitter radius cannot be negative")
        self._jitter_m = radius_m
        return self.status()
