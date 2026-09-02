"""Geodesic helpers for route playback.

Pure functions over WGS-84 latitude/longitude. No device access, no clock, no
global state, so every path here is directly testable.

Distances are metres, bearings are degrees clockwise from true north.
"""

from __future__ import annotations

import math
import random
from typing import NamedTuple, Sequence

# Mean Earth radius (IUGG). Route playback spans metres, not continents, so the
# spherical model is far more precision than the simulated GPS fix needs.
EARTH_RADIUS_M = 6_371_008.8


class Coord(NamedTuple):
    lat: float
    lon: float


def haversine(a: Coord, b: Coord) -> float:
    """Great-circle distance between two coordinates, in metres."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlon = math.radians(b.lon - a.lon)

    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def bearing(a: Coord, b: Coord) -> float:
    """Initial bearing from `a` to `b`, in degrees clockwise from north."""
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlon = math.radians(b.lon - a.lon)

    y = math.sin(dlon) * math.cos(lat2)
    x = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return math.degrees(math.atan2(y, x)) % 360.0


def total_distance(coords: Sequence[Coord]) -> float:
    """Length of a polyline, in metres."""
    return sum(haversine(a, b) for a, b in zip(coords, coords[1:]))


def point_at_distance(coords: Sequence[Coord], distance_m: float) -> Coord:
    """The point `distance_m` along a polyline, clamped to its endpoints.

    Interpolates linearly within the segment it lands in. Route polylines arrive
    from MapKit with vertices metres apart, where the difference between linear
    and great-circle interpolation is far below GPS resolution.
    """
    if not coords:
        raise ValueError("cannot walk an empty route")
    if len(coords) == 1 or distance_m <= 0:
        return coords[0]

    remaining = distance_m
    for start, end in zip(coords, coords[1:]):
        leg = haversine(start, end)
        if leg == 0.0:
            continue
        if remaining <= leg:
            f = remaining / leg
            return Coord(
                start.lat + (end.lat - start.lat) * f,
                start.lon + (end.lon - start.lon) * f,
            )
        remaining -= leg

    return coords[-1]


def densify(coords: Sequence[Coord], spacing_m: float) -> list[Coord]:
    """Resample a polyline to points roughly `spacing_m` apart.

    Both original endpoints are preserved; the final gap is whatever remainder
    is left over and so may be shorter than the requested spacing.
    """
    if spacing_m <= 0:
        raise ValueError("spacing_m must be positive")
    if len(coords) < 2:
        return list(coords)

    total = total_distance(coords)
    points = [coords[0]]

    walked = spacing_m
    while walked < total:
        points.append(point_at_distance(coords, walked))
        walked += spacing_m

    points.append(coords[-1])
    return points


def jitter(coord: Coord, radius_m: float, rng: random.Random | None = None) -> Coord:
    """Displace a coordinate by a random offset within `radius_m`.

    A perfectly motionless fix is a giveaway that a location is simulated; a few
    metres of wander reads like a real GPS receiver sitting still.
    """
    if radius_m < 0:
        raise ValueError("radius_m cannot be negative")
    if radius_m == 0:
        return coord

    rand = rng or random
    # sqrt keeps samples uniform over the disc rather than clustered at the centre.
    distance = radius_m * math.sqrt(rand.random())
    theta = rand.uniform(0, 2 * math.pi)

    dlat = (distance * math.cos(theta)) / EARTH_RADIUS_M
    dlon = (distance * math.sin(theta)) / (EARTH_RADIUS_M * math.cos(math.radians(coord.lat)))

    return Coord(coord.lat + math.degrees(dlat), coord.lon + math.degrees(dlon))
