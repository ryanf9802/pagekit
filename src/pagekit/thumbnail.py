"""Page thumbnails for the index, drawn by headless Chromium the first time one is asked for and kept beside the page."""

from __future__ import annotations

import subprocess
import tempfile
import threading
import uuid
from pathlib import Path

from .browser import find_chrome
from .pages import Page, PageError

_TIMEOUT_SECONDS = 30
# The first screen of a desktop browser, drawn at half size: a 500 by 350 picture. Chrome does not go below 0.5.
_WINDOW = "1000,700"
_SCALE = "0.5"
# One picture for each theme the index can be in, kept beside the page. The dark one is drawn only when it is wanted.
THUMBNAIL_NAMES = {"light": "thumb.png", "dark": "thumb-dark.png"}
THUMBNAIL_NAME = THUMBNAIL_NAMES["light"]
# One browser at a time, so an index showing many pages never starts them all at once.
_LOCK = threading.Lock()


def _fresh(target: Path, page: Page) -> bool:
    return target.is_file() and target.stat().st_mtime >= page.index.stat().st_mtime


def ensure_thumbnail(page: Page, scheme: str = "light") -> Path:
    """The page's thumbnail in `light` or `dark`, drawn now when there is none or the page has been rebuilt since."""
    if scheme not in THUMBNAIL_NAMES:
        raise PageError(f"no such thumbnail theme: {scheme!r}")
    if not page.index.is_file():
        raise PageError(f"not built: run pagekit build {page.slug}")
    target = page.dir / THUMBNAIL_NAMES[scheme]
    if _fresh(target, page):
        return target
    chrome = find_chrome()
    if not chrome:
        raise PageError("no Chrome or Chromium found: set PAGEKIT_CHROME to its path")
    with _LOCK:
        if _fresh(target, page):  # Another request drew it while this one waited.
            return target
        output = page.dir / f".thumb-{uuid.uuid4().hex}.png"
        try:
            with tempfile.TemporaryDirectory(prefix="pagekit-chrome-") as profile:
                command = [
                    chrome,
                    "--headless=new",
                    "--no-sandbox",
                    "--disable-gpu",
                    "--hide-scrollbars",
                    "--virtual-time-budget=2000",
                    f"--window-size={_WINDOW}",
                    f"--force-device-scale-factor={_SCALE}",
                    f"--user-data-dir={profile}",
                    # Makes the page's own dark styles apply, the way a dark system setting would.
                    *(["--force-dark-mode"] if scheme == "dark" else []),
                    f"--screenshot={output}",
                    page.index.as_uri(),
                ]
                try:
                    result = subprocess.run(
                        command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                        stdin=subprocess.DEVNULL, timeout=_TIMEOUT_SECONDS,
                    )
                except (OSError, subprocess.TimeoutExpired) as exc:
                    raise PageError(f"thumbnail failed: {exc}") from exc
            if result.returncode != 0 or not output.is_file() or output.stat().st_size == 0:
                raise PageError(f"thumbnail failed: {result.stderr.strip()[-300:] or 'no output'}")
            output.replace(target)
        finally:
            output.unlink(missing_ok=True)
    return target
