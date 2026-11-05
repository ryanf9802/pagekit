"""Bookmarked PDFs through headless Chromium. A print dialog cannot add bookmarks; this can."""

from __future__ import annotations

import json
import subprocess
import tempfile
import uuid
from pathlib import Path

from .browser import find_chrome
from .pages import Page, PageError

_TIMEOUT_SECONDS = 120
DEFAULT_PDF_MARGIN = "0.15in 0.25in"


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
    document = page.index.read_text(encoding="utf-8").replace("</head>", f"{additions}\n</head>", 1)
    # Beside the original, so its relative asset links still resolve.
    working = page.dir / f".print-{uuid.uuid4().hex}.html"
    output = target.with_name(f".{target.name}.{uuid.uuid4().hex}")
    try:
        working.write_text(document, encoding="utf-8")
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
                    command, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=_TIMEOUT_SECONDS
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
