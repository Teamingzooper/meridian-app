#!/usr/bin/env python3
"""Render Meridian's app icon and build the .icns.

Original artwork: a globe drawn from meridian lines — the lines of longitude the
app is named for — with a single pin marking a chosen point.

Everything is drawn at 4x and downsampled, which is cheaper than fighting
Pillow's aliasing on curves.
"""

from __future__ import annotations

import math
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "assets"

SIZE = 1024
SS = 4  # supersample factor
C = SIZE * SS

MARGIN = int(C * 0.085)
RADIUS = int(C * 0.225)

BG_TOP = (17, 27, 46)
BG_BOTTOM = (28, 48, 92)
GLOBE = (96, 165, 250)
GLOBE_FAINT = (96, 165, 250, 110)
PIN = (52, 211, 153)
PIN_DARK = (16, 122, 88)


def gradient_background() -> Image.Image:
    """Vertical gradient clipped to a rounded square."""
    base = Image.new("RGB", (C, C), BG_TOP)
    draw = ImageDraw.Draw(base)
    for y in range(C):
        t = y / (C - 1)
        draw.line(
            [(0, y), (C, y)],
            fill=tuple(round(a + (b - a) * t) for a, b in zip(BG_TOP, BG_BOTTOM)),
        )

    mask = Image.new("L", (C, C), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [MARGIN, MARGIN, C - MARGIN, C - MARGIN], radius=RADIUS, fill=255
    )

    out = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    out.paste(base, (0, 0), mask)
    return out


def draw_globe(layer: Image.Image) -> None:
    """A sphere suggested by its meridians and two parallels."""
    draw = ImageDraw.Draw(layer)
    cx = cy = C // 2
    r = int(C * 0.275)
    width = max(1, int(C * 0.011))

    draw.ellipse([cx - r, cy - r, cx + r, cy + r], outline=GLOBE + (235,), width=width)

    # Meridians: ellipses of shrinking width read as longitude lines on a sphere.
    for fraction in (0.34, 0.68):
        rx = int(r * fraction)
        draw.ellipse(
            [cx - rx, cy - r, cx + rx, cy + r], outline=GLOBE_FAINT, width=width
        )
    draw.line([(cx, cy - r), (cx, cy + r)], fill=GLOBE_FAINT, width=width)

    # Parallels, spaced as they would foreshorten toward the poles.
    for offset in (0.42, -0.42):
        y = cy + int(r * offset)
        half = int(r * math.cos(math.asin(offset)))
        ry = max(width, int(r * 0.12))
        draw.ellipse(
            [cx - half, y - ry, cx + half, y + ry], outline=GLOBE_FAINT, width=width
        )
    draw.ellipse(
        [cx - r, cy - int(r * 0.20), cx + r, cy + int(r * 0.20)],
        outline=GLOBE_FAINT,
        width=width,
    )


def draw_pin(layer: Image.Image) -> None:
    """A teardrop marker: the point the phone is being told it is at."""
    draw = ImageDraw.Draw(layer)
    cx = C // 2
    head_y = int(C * 0.415)
    head_r = int(C * 0.105)
    tip_y = int(C * 0.635)

    # Skirt of the teardrop, meeting the head's tangents so the join is smooth.
    spread = head_r * 0.74
    draw.polygon(
        [(cx - spread, head_y + head_r * 0.60),
         (cx + spread, head_y + head_r * 0.60),
         (cx, tip_y)],
        fill=PIN,
    )
    draw.ellipse(
        [cx - head_r, head_y - head_r, cx + head_r, head_y + head_r], fill=PIN
    )
    hole = int(head_r * 0.40)
    draw.ellipse([cx - hole, head_y - hole, cx + hole, head_y + hole], fill=PIN_DARK)


def render() -> Image.Image:
    icon = gradient_background()
    art = Image.new("RGBA", (C, C), (0, 0, 0, 0))
    draw_globe(art)
    draw_pin(art)
    icon = Image.alpha_composite(icon, art)
    return icon.resize((SIZE, SIZE), Image.LANCZOS)


def build_icns(master: Image.Image) -> Path:
    iconset = ASSETS / "AppIcon.iconset"
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)

    for size in (16, 32, 128, 256, 512):
        master.resize((size, size), Image.LANCZOS).save(iconset / f"icon_{size}x{size}.png")
        master.resize((size * 2, size * 2), Image.LANCZOS).save(
            iconset / f"icon_{size}x{size}@2x.png"
        )

    icns = ASSETS / "AppIcon.icns"
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True
    )
    return icns


def main() -> int:
    ASSETS.mkdir(exist_ok=True)
    master = render()
    master.save(ASSETS / "icon-1024.png")
    icns = build_icns(master)
    print(f"wrote {ASSETS / 'icon-1024.png'}")
    print(f"wrote {icns}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
