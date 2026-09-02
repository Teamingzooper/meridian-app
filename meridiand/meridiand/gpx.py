"""Reading and writing GPX, the interchange format for routes.

Real-world GPX is inconsistent: some files carry the GPX 1.1 namespace, some
none at all, and a route may arrive as a track (`trk`), a route (`rte`) or a bare
list of waypoints (`wpt`). This reads all of them and writes the well-formed
version, so a route built here opens anywhere else.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Sequence
from xml.sax.saxutils import escape

from .geo import Coord

GPX_NAMESPACE = "http://www.topografix.com/GPX/1/1"

# A GPS track of any sane length is far below this. The cap keeps a hostile or
# corrupt file from being parsed into memory wholesale.
MAX_GPX_BYTES = 32 * 1024 * 1024
MAX_POINTS = 100_000


class GpxError(ValueError):
    """A GPX document that cannot be read as a route."""


@dataclass
class GpxRoute:
    name: str = "Imported route"
    points: list[Coord] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.points)


def _localname(tag: str) -> str:
    """Strip any XML namespace, since GPX files disagree about using one."""
    return tag.rsplit("}", 1)[-1].lower()


def _find_child_text(element: ET.Element, name: str) -> str:
    for child in element:
        if _localname(child.tag) == name and child.text:
            return child.text.strip()
    return ""


def _point_from(element: ET.Element) -> Coord | None:
    """Read a lat/lon pair off a trkpt, rtept or wpt element."""
    try:
        lat = float(element.attrib["lat"])
        lon = float(element.attrib["lon"])
    except (KeyError, ValueError, TypeError):
        return None

    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None
    return Coord(lat, lon)


def _collect(root: ET.Element, container: str, point_tag: str) -> list[Coord]:
    """Gather every point under elements of a given container type, in order."""
    points: list[Coord] = []
    for element in root.iter():
        if _localname(element.tag) != container:
            continue
        for descendant in element.iter():
            if _localname(descendant.tag) != point_tag:
                continue
            point = _point_from(descendant)
            if point is not None:
                points.append(point)
    return points


def parse_gpx(text: str) -> GpxRoute:
    """Read a GPX document into an ordered route.

    Tracks are preferred over routes, and routes over loose waypoints, because a
    file carrying several of them almost always means the track to be the path.
    """
    if len(text.encode("utf-8", "ignore")) > MAX_GPX_BYTES:
        raise GpxError("that GPX file is too large to read")

    try:
        root = ET.fromstring(text)
    except ET.ParseError as exc:
        raise GpxError(f"not valid GPX: {exc}") from exc

    # trkseg lives inside trk, so collecting on trk covers multi-segment tracks.
    points = _collect(root, "trk", "trkpt")
    if not points:
        points = _collect(root, "rte", "rtept")
    if not points:
        points = [
            p for p in (_point_from(e) for e in root.iter() if _localname(e.tag) == "wpt")
            if p is not None
        ]

    if not points:
        raise GpxError("that GPX file has no usable points")
    if len(points) > MAX_POINTS:
        raise GpxError(f"that route has more than {MAX_POINTS:,} points")

    name = ""
    for container in ("trk", "rte", "metadata"):
        for element in root.iter():
            if _localname(element.tag) == container:
                name = _find_child_text(element, "name")
                if name:
                    break
        if name:
            break

    return GpxRoute(name=name or "Imported route", points=points)


def write_gpx(points: Sequence[Coord] | Iterable[Coord], name: str = "Meridian route") -> str:
    """Render points as a GPX 1.1 track."""
    coords = list(points)
    if not coords:
        raise GpxError("cannot write a GPX file with no points")

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<gpx version="1.1" creator="Meridian" xmlns="{GPX_NAMESPACE}">',
        "  <metadata>",
        f"    <name>{escape(name)}</name>",
        f"    <time>{stamp}</time>",
        "  </metadata>",
        "  <trk>",
        f"    <name>{escape(name)}</name>",
        "    <trkseg>",
    ]
    lines.extend(
        f'      <trkpt lat="{c.lat:.7f}" lon="{c.lon:.7f}"></trkpt>' for c in coords
    )
    lines += ["    </trkseg>", "  </trk>", "</gpx>", ""]
    return "\n".join(lines)
