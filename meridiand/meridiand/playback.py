"""Elapsed-time bookkeeping across pause and resume.

Splitting this out from the engine keeps the awkward part — time that stops and
starts — free of threads and clocks. `now` is always passed in, so a test can
step through an hour of playback instantly.
"""

from __future__ import annotations

from typing import Optional

from .geo import Coord
from .route import RoutePlayer


class Playback:
    """A `RoutePlayer` plus a stopwatch that can be paused."""

    def __init__(self, player: RoutePlayer, now: float = 0.0) -> None:
        self._player = player
        self._accumulated = 0.0
        self._running_since: Optional[float] = now

    @property
    def player(self) -> RoutePlayer:
        return self._player

    @property
    def is_paused(self) -> bool:
        return self._running_since is None

    def elapsed(self, now: float) -> float:
        """Seconds of playback so far, excluding time spent paused."""
        if self._running_since is None:
            return self._accumulated
        return self._accumulated + max(0.0, now - self._running_since)

    def pause(self, now: float) -> None:
        if self._running_since is None:
            return
        self._accumulated += max(0.0, now - self._running_since)
        self._running_since = None

    def resume(self, now: float) -> None:
        if self._running_since is None:
            self._running_since = now

    def seek(self, fraction: float, now: float) -> None:
        """Jump to a fraction of the route, preserving the paused/running state."""
        fraction = min(1.0, max(0.0, fraction))
        self._accumulated = self._player.duration_s * fraction
        if self._running_since is not None:
            self._running_since = now

    def position(self, now: float) -> Coord:
        return self._player.position_at(self.elapsed(now))

    def progress(self, now: float) -> float:
        return self._player.progress_at(self.elapsed(now))

    def is_finished(self, now: float) -> bool:
        return self._player.is_finished(self.elapsed(now))
