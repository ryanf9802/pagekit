"""Finding a local Chrome or Chromium, which PDFs and diagrams both render with."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path

_CHROME_NAMES = ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome", "msedge")
_MAC_CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


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
