"""Generates the slopfence logo SVGs in this folder.

The wordmark is JetBrains Mono Bold (SIL Open Font License 1.1) converted to paths,
so the SVGs render the same everywhere without the font installed.

Usage (needs `pip install fonttools` and the font file):
    python docs/brand/build.py path/to/JetBrainsMono-Bold.ttf
"""

from __future__ import annotations

import sys
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).parent

# Palette (Tailwind violet + lime), tuned for contrast on light and dark backgrounds.
FENCE = "#8B5CF6"
FENCE_DARK = "#6D28D9"
SLOP = "#A3E635"
SLOP_DARK = "#65A30D"
INK_LIGHT_BG = {"slop": "#4D7C0F", "fence": "#6D28D9"}
INK_DARK_BG = {"slop": "#A3E635", "fence": "#A78BFA"}
NIGHT = "#1E1E2E"


def fmt(v: float) -> str:
    s = f"{v:.1f}"
    return s.rstrip("0").rstrip(".") if "." in s else s


def text_path(font: TTFont, text: str, size: float, x: float, baseline: float) -> tuple[str, float]:
    """SVG path data for `text` with its baseline at `baseline`; returns (path, end x)."""
    glyphs = font.getGlyphSet()
    cmap = font.getBestCmap()
    scale = size / font["head"].unitsPerEm
    parts = []
    for ch in text:
        name = cmap[ord(ch)]
        pen = SVGPathPen(glyphs, ntos=fmt)
        glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, baseline)))
        parts.append(pen.getCommands())
        x += glyphs[name].width * scale
    return " ".join(parts), x


def icon(dx: float = 0, dy: float = 0) -> str:
    """The fence-and-slop mark in a 128x128 box: slop splattered onto a picket fence."""
    rails = "".join(
        f'<rect x="20" y="{y}" width="88" height="10" rx="3" fill="{FENCE_DARK}"/>'
        for y in (50, 88)
    )
    pickets = "".join(
        f'<path d="M{cx - 9} 34 L{cx} 20 L{cx + 9} 34 L{cx + 9} 108 Q{cx + 9} 114 {cx + 3} 114 '
        f'L{cx - 3} 114 Q{cx - 9} 114 {cx - 9} 108 Z" fill="{FENCE}"/>'
        for cx in (40, 64, 88)
    )
    # A splat across the first two boards, with drips running down them.
    splat = (
        f'<path d="M27 44 C24 33 37 26 46 31 C54 24 70 30 67 42 C72 46 70 55 64 56 '
        f"L64 70 Q64 76 60.5 76 Q57 76 57 70 L57 58 C53 60 49 60 46 58 "
        f"L44 58 L44 94 Q44 100 40 100 Q36 100 36 94 L36 58 C30 59 26 55 28 50 "
        f'C24 49 24 46 27 44 Z" fill="{SLOP}"/>'
        f'<circle cx="21" cy="33" r="3.5" fill="{SLOP}"/>'
        f'<circle cx="74" cy="27" r="2.6" fill="{SLOP}"/>'
        f'<circle cx="49" cy="66" r="2.4" fill="{SLOP}"/>'
        f'<ellipse cx="39" cy="38" rx="5" ry="3.2" fill="#F7FEE7" opacity="0.75" '
        f'transform="rotate(-20 39 38)"/>'
    )
    return f'<g transform="translate({fmt(dx)} {fmt(dy)})">{rails}{pickets}{splat}</g>'


def svg(width: float, height: float, body: str, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{fmt(width)}" height="{fmt(height)}" '
        f'viewBox="0 0 {fmt(width)} {fmt(height)}" role="img" aria-label="{title}">'
        f"<title>{title}</title>{body}</svg>\n"
    )


def wordmark(font: TTFont, x: float, baseline: float, size: float, ink: dict) -> tuple[str, float]:
    slop, mid = text_path(font, "slop", size, x, baseline)
    fence, end = text_path(font, "fence", size, mid, baseline)
    return f'<path d="{slop}" fill="{ink["slop"]}"/><path d="{fence}" fill="{ink["fence"]}"/>', end


def main(font_path: str) -> None:
    font = TTFont(font_path)
    size, gap = 66, 20
    # Horizontal logo: icon + wordmark, baseline aligned to the bottom rail.
    for name, ink in (("logo-light", INK_LIGHT_BG), ("logo-dark", INK_DARK_BG)):
        words, end = wordmark(font, 128 + gap, 94, size, ink)
        (HERE / f"{name}.svg").write_text(svg(end + 4, 128, icon() + words, "slopfence"))

    # Square icon on a dark rounded tile (avatars, favicons).
    tile = f'<rect width="128" height="128" rx="28" fill="{NIGHT}"/>'
    (HERE / "icon.svg").write_text(svg(128, 128, tile + icon(0, -3), "slopfence"))

    # Social preview card, 1280x640 (GitHub's recommended size).
    words, end = wordmark(font, 0, 0, 150, INK_DARK_BG)
    word_w = end
    total_w = 128 * 2.2 + 40 + word_w
    left = (1280 - total_w) / 2
    tagline, tag_end = text_path(font, "a quality gate for AI-assisted code", 40, 0, 0)
    card = (
        f'<rect width="1280" height="640" fill="{NIGHT}"/>'
        f'<g transform="translate({fmt(left)} 170) scale(2.2)">{icon()}</g>'
        f'<g transform="translate({fmt(left + 128 * 2.2 + 40)} 390)">{words}</g>'
        f'<path transform="translate({fmt((1280 - tag_end) / 2)} 520)" d="{tagline}" '
        f'fill="#A6ADC8"/>'
    )
    (HERE / "social-preview.svg").write_text(svg(1280, 640, card, "slopfence"))


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
