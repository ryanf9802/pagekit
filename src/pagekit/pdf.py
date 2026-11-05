"""Bookmarked PDFs through headless Chromium. A print dialog cannot add bookmarks; this can."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from pathlib import Path

from .pages import Page, PageError

_CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge")
_MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
_TIMEOUT_SECONDS = 120
DEFAULT_PDF_MARGIN = "0.15in 0.25in"


def find_chrome() -> str | None:
    configured = os.environ.get("PAGEKIT_CHROME")
    if configured:
        return configured
    for name in _CHROME_NAMES:
        path = shutil.which(name)
        if path:
            return path
    if Path(_MAC_CHROME).is_file():
        return _MAC_CHROME
    # Playwright's browsers are versioned folders, and older ones get removed, so take the newest.
    cache = Path.home() / ".cache" / "ms-playwright"
    found = sorted(
        cache.glob("chromium-*/chrome-*/chrome"),
        key=lambda p: int(m.group(1)) if (m := re.search(r"chromium-(\d+)", str(p))) else 0,
    )
    return str(found[-1]) if found else None


def render_pdf(page: Page, target: Path, state: dict | None = None) -> Path:
    """Write a tagged, bookmarked PDF. `state` carries answers held in the user's browser."""
    chrome = find_chrome()
    if not chrome:
        raise PageError("no Chrome or Chromium found: set PAGEKIT_CHROME to its path")
    if not page.index.is_file():
        raise PageError(f"not built: run pagekit build {page.slug}")
    margin = str(page.meta.get("pdf_margin") or DEFAULT_PDF_MARGIN)
    # Last in the head, so it wins over the profile's Ctrl+P margins.
    additions = f"<style>@page {{ margin: {margin}; }}</style>"
    if state:
        payload = json.dumps(state).replace("<", "\\u003c")
        additions += f"<script>window.pagekitPrintState = {payload};</script>"
    document = page.index.read_text().replace("</head>", f"{additions}\n</head>", 1)
    # Beside the original, so its relative asset links still resolve.
    working = page.dir / f".print-{uuid.uuid4().hex}.html"
    output = target.with_name(f".{target.name}.{uuid.uuid4().hex}")
    try:
        working.write_text(document)
        with tempfile.TemporaryDirectory(prefix="pagekit-chrome-") as profile:
            command = [
                chrome,
                "--headless=new",
                "--no-sandbox",
                "--disable-gpu",
                "--no-pdf-header-footer",
                "--generate-pdf-document-outline",
                "--virtual-time-budget=8000",
                f"--user-data-dir={profile}",
                f"--print-to-pdf={output}",
                working.as_uri(),
            ]
            try:
                result = subprocess.run(
                    command, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=_TIMEOUT_SECONDS
                )
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise PageError(f"PDF generation failed: {exc}") from exc
        if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
            raise PageError(f"PDF generation failed: {result.stderr.strip()[-300:] or 'no output'}")
        output.replace(target)
    finally:
        working.unlink(missing_ok=True)
        output.unlink(missing_ok=True)
    return target
