"""Route playback: where a simulated device sits at a given moment.

`RoutePlayer` is a pure function of elapsed time. It owns no clock and no
thread, so playback can be tested at any instant without waiting for one. The
server supplies real time; tests supply whatever they like.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .geo import Coord, point_at_distance, total_distance

# Metres per second. Rough real-world averages including the stops that make
# movement look human rather than like a constant-velocity dot.
SPEED_PRESETS: dict[str, float] = {
    "walk": 1.4,   # ~5 km/h
    "bike": 4.2,   # ~15 km/h
    "drive": 13.4, # ~48 km/h
}


@dataclass(frozen=True)
class RoutePlayer:
    coords: Sequence[Coord]
    speed_mps: float
    loop: bool = False

    def __post_init__(self) -> None:
        if not self.coords:
            raise ValueError("a route needs at least one coordinate")
        if self.speed_mps <= 0:
            raise ValueError("speed_mps must be positive")

    @property
    def length_m(self) -> float:
        return total_distance(self.coords)

    @property
    def duration_s(self) -> float:
        return self.length_m / self.speed_mps

    def _elapsed_to_distance(self, elapsed_s: float) -> float:
        """Distance travelled at `elapsed_s`, wrapping if this route loops."""
        if elapsed_s <= 0:
            return 0.0

        length = self.length_m
        travelled = elapsed_s * self.speed_mps

        # A degenerate route has nowhere to wrap to, so looping is a no-op.
        if self.loop and length > 0:
            return travelled % length
        return travelled

    def position_at(self, elapsed_s: float) -> Coord:
        """Where the device should appear at `elapsed_s` into playback."""
        return point_at_distance(self.coords, self._elapsed_to_distance(elapsed_s))

    def progress_at(self, elapsed_s: float) -> float:
        """Fraction of the route covered, clamped to 0..1."""
        length = self.length_m
        if length == 0:
            return 1.0
        return min(1.0, max(0.0, self._elapsed_to_distance(elapsed_s) / length))

    def is_finished(self, elapsed_s: float) -> bool:
        """True once a non-looping route has reached its end."""
        if self.loop:
            return False
        return elapsed_s >= self.duration_s
