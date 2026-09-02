"""Turning a polyline into movement that doesn't look computer-generated.

Constant velocity is the giveaway: real travel eases away from a stop, slows into
corners, and never holds an exact speed. `MotionProfile` maps elapsed time to
distance along a route with those three effects applied.

It works by sampling the route, deciding a speed multiplier at each sample, then
integrating `dt = ds / v` into a time axis. Position lookup is a binary search
over that axis, so playback stays cheap no matter how the profile is shaped.
"""

from __future__ import annotations

import bisect
import math
from typing import Sequence

from .geo import Coord, bearing, haversine, point_at_distance, total_distance

# Roughly a pace, which is finer than any GPS fix will resolve.
SAMPLE_SPACING_M = 2.0
MAX_SAMPLES = 20_000

# Never fully stop mid-route: a zero multiplier would take infinite time to cross.
MIN_SPEED_FACTOR = 0.12


def _turn_angle(previous: Coord, corner: Coord, following: Coord) -> float:
    """How sharply the path turns at `corner`, in degrees from straight on."""
    incoming = bearing(previous, corner)
    outgoing = bearing(corner, following)
    delta = abs(outgoing - incoming) % 360.0
    return 360.0 - delta if delta > 180.0 else delta


class MotionProfile:
    """A time-to-distance mapping for one route."""

    def __init__(
        self,
        coords: Sequence[Coord],
        cruise_mps: float,
        ease_m: float = 12.0,
        corner_threshold_deg: float = 35.0,
        wobble: float = 0.07,
    ) -> None:
        if cruise_mps <= 0:
            raise ValueError("cruise_mps must be positive")
        if not 0.0 <= wobble < 1.0:
            raise ValueError("wobble must be in [0, 1)")

        self._coords = list(coords)
        self._cruise = cruise_mps
        self._ease_m = max(0.0, ease_m)
        self._corner_threshold = corner_threshold_deg
        self._wobble = wobble

        self._length = total_distance(self._coords)
        self._corners = self._find_corners()
        self._distances, self._times = self._integrate()

    # ------------------------------------------------------------------ shape

    @property
    def length_m(self) -> float:
        return self._length

    @property
    def duration_s(self) -> float:
        return self._times[-1] if self._times else 0.0

    def _find_corners(self) -> list[tuple[float, float]]:
        """Distances along the route where it turns, paired with the turn angle."""
        corners: list[tuple[float, float]] = []
        travelled = 0.0

        for index in range(1, len(self._coords) - 1):
            previous, corner, following = self._coords[index - 1: index + 2]
            travelled += haversine(previous, corner)

            leg_in = haversine(previous, corner)
            leg_out = haversine(corner, following)
            # Bearing is meaningless across a zero-length leg.
            if leg_in <= 0.0 or leg_out <= 0.0:
                continue

            angle = _turn_angle(previous, corner, following)
            if angle >= self._corner_threshold:
                corners.append((travelled, angle))

        return corners

    def speed_factor_at(self, distance_m: float) -> float:
        """Speed multiplier at a point along the route, in (0, 1]."""
        if self._length <= 0:
            return 1.0

        distance = min(max(distance_m, 0.0), self._length)
        factor = 1.0

        # Ease away from the start and into the finish.
        if self._ease_m > 0:
            from_start = distance / self._ease_m
            from_end = (self._length - distance) / self._ease_m
            edge = min(1.0, from_start, from_end)
            # Smoothstep, so acceleration itself starts and ends gently.
            factor *= MIN_SPEED_FACTOR + (1 - MIN_SPEED_FACTOR) * (edge * edge * (3 - 2 * edge))

        # Slow into corners, more sharply the tighter the turn.
        for corner_distance, angle in self._corners:
            # A turn's influence reaches about a second of travel either side.
            reach = max(4.0, self._cruise * 1.5)
            offset = abs(distance - corner_distance)
            if offset < reach:
                severity = min(1.0, angle / 120.0)
                nearness = 1.0 - (offset / reach)
                factor *= 1.0 - (severity * nearness * 0.55)

        # A gentle wander so the speed is never exactly constant.
        if self._wobble:
            factor *= 1.0 + self._wobble * math.sin(distance / 37.0)

        return max(MIN_SPEED_FACTOR, min(1.0 + self._wobble, factor))

    # -------------------------------------------------------------- integration

    def _integrate(self) -> tuple[list[float], list[float]]:
        """Build matched distance and time axes by walking the route."""
        if self._length <= 0:
            return [0.0], [0.0]

        steps = min(MAX_SAMPLES, max(2, int(self._length / SAMPLE_SPACING_M)))
        step = self._length / steps

        distances = [0.0]
        times = [0.0]
        elapsed = 0.0

        for index in range(1, steps + 1):
            here = index * step
            # Midpoint speed over the step is a closer estimate than either end.
            speed = self._cruise * self.speed_factor_at(here - step / 2)
            elapsed += step / speed
            distances.append(here)
            times.append(elapsed)

        return distances, times

    # ------------------------------------------------------------------ lookup

    def distance_at(self, elapsed_s: float) -> float:
        """How far along the route the traveller is at `elapsed_s`."""
        if elapsed_s <= 0 or self._length <= 0:
            return 0.0
        if elapsed_s >= self.duration_s:
            return self._length

        index = bisect.bisect_left(self._times, elapsed_s)
        if index == 0:
            return 0.0

        before_t, after_t = self._times[index - 1], self._times[index]
        before_d, after_d = self._distances[index - 1], self._distances[index]

        span = after_t - before_t
        if span <= 0:
            return after_d

        fraction = (elapsed_s - before_t) / span
        return before_d + (after_d - before_d) * fraction

    def position_at(self, elapsed_s: float) -> Coord:
        return point_at_distance(self._coords, self.distance_at(elapsed_s))
