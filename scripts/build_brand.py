#!/usr/bin/env python3
"""Regenerate every pagekit brand asset from the constants below.

The wordmark is Space Grotesk SemiBold turned into outlines, so pages need no web font. Get the font from
https://cdn.jsdelivr.net/npm/@fontsource/space-grotesk@5.2.10/files/space-grotesk-latin-600-normal.woff2

    uv run --with fonttools --with brotli python scripts/build_brand.py path/to/font.woff2

The PNGs are drawn with the Chrome that pagekit already finds for PDFs.
"""

from __future__ import annotations

import argparse
import base64
import re
import subprocess
import tempfile
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont

from pagekit.browser import find_chrome

ROOT = Path(__file__).resolve().parent.parent
PROFILE = ROOT / "src" / "pagekit" / "profile_default"
STATIC = ROOT / "src" / "pagekit" / "static"
DOCS = ROOT / "docs" / "brand"

# Ember. Light ink and flap, then the same pair for dark backgrounds.
INK, EMBER = "#1b1b1f", "#e5532d"
INK_DARK, EMBER_DARK = "#f2efe9", "#ff7a50"
ICON_BACKGROUND = "#16181c"

NAME = "pagekit"
TRACKING_EM = -0.02

# The mark: a page cut into a p, with its top-right corner folded over. Drawn on a 64 grid.
BODY = (
    "M15 6H40L54 20V35A5 5 0 0 1 49 40H32V53A5 5 0 0 1 27 58H15A5 5 0 0 1 10 53V11A5 5 0 0 1 15 6Z"
    "M25 20H35A3 3 0 0 1 38 23V27A3 3 0 0 1 35 30H25A3 3 0 0 1 22 27V23A3 3 0 0 1 25 20Z"
)
FLAP = "M40 6V15.33Q40 20 44.67 20H54Z"
SQUARE_VIEW = "6 6 52 52"
MARK_LEFT, MARK_TOP, MARK_WIDTH, MARK_HEIGHT = 10, 6, 44, 52


def mark_paths(body: str, flap: str) -> str:
    return f'<path fill="{body}" fill-rule="evenodd" d="{BODY}"/><path fill="{flap}" d="{FLAP}"/>'


def mark_svg(body: str, flap: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{SQUARE_VIEW}">{mark_paths(body, flap)}</svg>\n'


def favicon_svg() -> str:
    """One file that follows the browser's color scheme, for tabs and the index page."""
    style = (
        f"<style>.a{{fill:{INK}}}.b{{fill:{EMBER}}}"
        f"@media (prefers-color-scheme:dark){{.a{{fill:{INK_DARK}}}.b{{fill:{EMBER_DARK}}}}}</style>"
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{SQUARE_VIEW}">{style}'
        f'<path class="a" fill-rule="evenodd" d="{BODY}"/><path class="b" d="{FLAP}"/></svg>\n'
    )


def word_outline(font_path: Path) -> tuple[str, tuple[float, float, float, float]]:
    """The name as one path in units of 1 em = 100, y down and baseline at 0, with its bounds."""
    font = TTFont(font_path)
    glyphs, cmap = font.getGlyphSet(), font.getBestCmap()
    scale = 100 / font["head"].unitsPerEm
    outline = SVGPathPen(glyphs, ntos=lambda n: f"{n:.2f}".rstrip("0").rstrip("."))
    bounds = BoundsPen(glyphs)
    x = 0.0
    for character in NAME:
        name = cmap[ord(character)]
        for pen in (outline, bounds):
            glyphs[name].draw(TransformPen(pen, (scale, 0, 0, -scale, x, 0)))
        x += glyphs[name].width * scale + TRACKING_EM * 100
    return outline.getCommands(), bounds.bounds


def wordmark_svg(path: str, bounds: tuple[float, float, float, float]) -> str:
    left, top, right, bottom = bounds
    view = f"{left:.2f} {top:.2f} {right - left:.2f} {bottom - top:.2f}"
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{view}"><path fill="{INK}" d="{path}"/></svg>\n'


def lockup_svg(path: str, bounds: tuple[float, float, float, float], body: str, flap: str, word: str) -> tuple[str, float]:
    """The mark beside the name, with the aspect ratio of the result."""
    left, top, right, bottom = bounds
    mark_height = 118.0
    scale = mark_height / MARK_HEIGHT
    mark_width = MARK_WIDTH * scale
    gap = 26.0
    height = max(mark_height, bottom - top)
    word_x = mark_width + gap - left
    word_y = (height - (bottom - top)) / 2 - top
    width = mark_width + gap + (right - left)
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.2f} {height:.2f}">'
        f'<g transform="translate(0 {(height - mark_height) / 2:.2f}) scale({scale:.4f}) translate({-MARK_LEFT} {-MARK_TOP})">'
        f"{mark_paths(body, flap)}</g>"
        f'<path fill="{word}" transform="translate({word_x:.2f} {word_y:.2f})" d="{path}"/></svg>\n'
    )
    return svg, width / height


def screenshot(chrome: str, markup: str, width: int, height: int, target: Path) -> None:
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / "shot.html"
        page.write_text(
            f'<!doctype html><html><body style="margin:0;width:{width}px;height:{height}px;overflow:hidden;background:transparent">'
            f"{markup}</body></html>",
            encoding="utf-8",
        )
        subprocess.run(
            [
                chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-sandbox",
                f"--user-data-dir={folder}/profile", f"--window-size={width},{height}",
                "--default-background-color=00000000", f"--screenshot={target}", page.as_uri(),
            ],
            check=True,
            capture_output=True,
        )


def app_icon(chrome: str, size: int, target: Path) -> None:
    # Installed icons are masked to a shape, so the tile is full-bleed and the mark stays in the safe zone.
    # Drawn on a canvas of the exact size, because headless Chrome clips or rescales small window screenshots.
    side = round(size * 0.58)
    offset = (size - side) // 2
    svg = mark_svg(INK_DARK, EMBER_DARK).replace("<svg ", f'<svg width="{side}" height="{side}" ')
    source = "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()
    script = (
        f"var c=document.createElement('canvas');c.width=c.height={size};var x=c.getContext('2d');"
        f"x.fillStyle='{ICON_BACKGROUND}';x.fillRect(0,0,{size},{size});var i=new Image();"
        f"i.onload=function(){{x.drawImage(i,{offset},{offset},{side},{side});"
        "document.getElementById('out').textContent=c.toDataURL('image/png').split(',')[1]};"
        f"i.src='{source}';"
    )
    with tempfile.TemporaryDirectory() as folder:
        page = Path(folder) / "icon.html"
        page.write_text(f'<!doctype html><pre id="out"></pre><script>{script}</script>', encoding="utf-8")
        result = subprocess.run(
            [
                chrome, "--headless=new", "--disable-gpu", "--no-sandbox", f"--user-data-dir={folder}/profile",
                "--virtual-time-budget=3000", "--dump-dom", page.as_uri(),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    match = re.search(r'<pre id="out">([A-Za-z0-9+/=]+)</pre>', result.stdout)
    if not match:
        raise SystemExit(f"Chrome did not draw {target.name}")
    target.write_bytes(base64.b64decode(match.group(1)))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("font", type=Path, help="Space Grotesk SemiBold, as .woff2 or .ttf")
    args = parser.parse_args()
    chrome = find_chrome()
    if not chrome:
        raise SystemExit("needs Chrome or Chromium to draw the PNGs")

    path, bounds = word_outline(args.font)
    (PROFILE / "logo.svg").write_text(mark_svg(INK, EMBER), encoding="utf-8")
    (PROFILE / "logo-dark.svg").write_text(mark_svg(INK_DARK, EMBER_DARK), encoding="utf-8")
    (PROFILE / "favicon.svg").write_text(favicon_svg(), encoding="utf-8")
    (PROFILE / "wordmark.svg").write_text(wordmark_svg(path, bounds), encoding="utf-8")

    DOCS.mkdir(parents=True, exist_ok=True)
    light, aspect = lockup_svg(path, bounds, INK, EMBER, INK)
    dark, _ = lockup_svg(path, bounds, INK_DARK, EMBER_DARK, INK_DARK)
    (DOCS / "lockup.svg").write_text(light, encoding="utf-8")
    (DOCS / "lockup-dark.svg").write_text(dark, encoding="utf-8")
    (DOCS / "mark.svg").write_text(mark_svg(INK, EMBER), encoding="utf-8")
    (DOCS / "mark-dark.svg").write_text(mark_svg(INK_DARK, EMBER_DARK), encoding="utf-8")

    # Three times the 26 px print height, so it stays sharp on paper.
    height = 78
    width = round(height * aspect)
    sized = light.replace("<svg ", f'<svg width="{width}" height="{height}" style="display:block" ')
    screenshot(chrome, sized, width, height, PROFILE / "logo-print.png")

    app_icon(chrome, 192, STATIC / "icon-192.png")
    app_icon(chrome, 512, STATIC / "icon-512.png")


if __name__ == "__main__":
    main()
