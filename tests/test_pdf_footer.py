"""Checks a real PDF in pixels. Text extraction is not enough: a page number can be hidden while its text is still in the file."""

from __future__ import annotations

from pathlib import Path

import pytest

from pagekit.browser import find_chrome
from pagekit.pages import build_page, new_page
from pagekit.pdf import render_pdf
from pagekit.profiles import load_profile

pymupdf = pytest.importorskip("pymupdf")

BAND_POINTS = 28  # The footer's line, inside the bottom of the standard 0.15in margin.
CHROME = find_chrome()  # Found now, since the home fixture hides anything installed under the real home.


def dark_pixels(sheet, left: float, right: float) -> int:
    rect = sheet.rect
    clip = pymupdf.Rect(rect.width * left, rect.height - BAND_POINTS, rect.width * right, rect.height)
    samples = sheet.get_pixmap(dpi=100, clip=clip, colorspace=pymupdf.csGRAY).samples
    return sum(1 for value in samples if value < 160)


@pytest.mark.skipif(not CHROME, reason="needs Chrome or Chromium")
def test_every_sheet_shows_its_footer_and_page_number(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGEKIT_CHROME", str(CHROME))
    profile = load_profile()
    page, _ = new_page(profile, "footer-check", "Footer check", None, "slots")
    page.content.write_text("<p>Line of text.</p>\n" * 400, encoding="utf-8")
    build_page(profile, page)
    target = tmp_path / "out.pdf"
    render_pdf(page, target)
    with pymupdf.open(target) as document:
        assert len(document) > 1, "the page must run to several sheets to test the repeat"
        for number, sheet in enumerate(document, 1):
            assert dark_pixels(sheet, 0, 0.62) > 40, f"sheet {number} has no footer text"
            assert dark_pixels(sheet, 0.62, 1) > 15, f"sheet {number} has no page number"
