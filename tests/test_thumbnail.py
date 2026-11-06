"""Index thumbnails: drawn on first request by a browser, kept beside the page, and the index showing them."""

from __future__ import annotations

import http.client
import os
import re
import stat
import struct
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from pagekit.browser import find_chrome
from pagekit.pages import PageError, build_page, new_page, pages_root
from pagekit.profiles import load_profile
from pagekit.server import make_server
from pagekit.thumbnail import THUMBNAIL_NAME, THUMBNAIL_NAMES, ensure_thumbnail

REAL_CHROME = find_chrome()  # Found now, since the home fixture hides anything installed under the real home.

# Writes the file named by --screenshot=, and counts how often it was asked to. FAKE_DELAY slows it down.
FAKE_CHROME = """#!/bin/sh
for arg in "$@"; do
  case "$arg" in
    --screenshot=*) out="${arg#--screenshot=}" ;;
  esac
done
echo run >> "$CHROME_LOG.calls"
echo "$*" > "$CHROME_LOG.args"
[ -n "$FAKE_DELAY" ] && sleep "$FAKE_DELAY"
[ -n "$FAKE_FAIL" ] && exit 1
printf '\\211PNG\\r\\n\\032\\nfake' > "$out"
"""


@pytest.fixture
def chrome(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "fake-chrome"
    script.write_text(FAKE_CHROME)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "chrome"
    monkeypatch.setenv("PAGEKIT_CHROME", str(script))
    monkeypatch.setenv("CHROME_LOG", str(log))
    return log


@pytest.fixture
def port(home: Path) -> Iterator[int]:
    server = make_server("127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def calls(log: Path) -> int:
    path = Path(f"{log}.calls")
    return len(path.read_text().splitlines()) if path.is_file() else 0


def built_page(slug: str = "demo", pinned: bool = False):
    profile = load_profile()
    page, _ = new_page(profile, slug, "Demo", "A summary", "slots")
    page.content.write_text("<h2>Section</h2>")
    build_page(profile, page)
    if pinned:
        page.meta["pinned"] = True
        page.write_meta()
    return page


def get(port: int, path: str) -> tuple[int, bytes, http.client.HTTPResponse]:
    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", path)
    response = connection.getresponse()
    return response.status, response.read(), response


@pytest.mark.posix
def test_the_first_request_draws_the_thumbnail_and_later_ones_reuse_it(chrome: Path, port: int) -> None:
    page = built_page()
    status, body, response = get(port, "/api/thumb/default/demo")
    assert status == 200 and body.startswith(b"\x89PNG") and response.headers["Content-Type"] == "image/png"
    assert (page.dir / THUMBNAIL_NAME).read_bytes() == body
    get(port, "/api/thumb/default/demo")
    assert calls(chrome) == 1


@pytest.mark.posix
def test_the_thumbnail_is_drawn_small_and_from_the_built_page(chrome: Path) -> None:
    page = built_page()
    ensure_thumbnail(page)
    args = Path(f"{chrome}.args").read_text()
    assert "--force-device-scale-factor=0.5" in args and "--window-size=1000,700" in args and page.index.as_uri() in args
    assert "--hide-scrollbars" in args and "--headless=new" in args


@pytest.mark.posix
def test_a_rebuilt_page_gets_a_new_thumbnail(chrome: Path) -> None:
    page = built_page()
    thumb = ensure_thumbnail(page)
    os.utime(thumb, (1, 1))  # Drawn before the page was last built.
    ensure_thumbnail(page)
    assert calls(chrome) == 2


@pytest.mark.posix
def test_the_dark_thumbnail_is_drawn_with_dark_mode_on_and_kept_apart_from_the_light_one(chrome: Path, port: int) -> None:
    page = built_page()
    get(port, "/api/thumb/default/demo")
    assert "--force-dark-mode" not in Path(f"{chrome}.args").read_text()
    status, body, _ = get(port, "/api/thumb/default/demo?scheme=dark")
    assert status == 200 and body.startswith(b"\x89PNG")
    assert "--force-dark-mode" in Path(f"{chrome}.args").read_text()
    assert (page.dir / THUMBNAIL_NAMES["dark"]).is_file() and (page.dir / THUMBNAIL_NAMES["light"]).is_file()
    # Each is drawn once, and the dark one only because it was asked for.
    get(port, "/api/thumb/default/demo?scheme=dark")
    get(port, "/api/thumb/default/demo?scheme=light")
    assert calls(chrome) == 2


@pytest.mark.posix
def test_only_the_theme_asked_for_is_drawn(chrome: Path, port: int) -> None:
    page = built_page()
    get(port, "/api/thumb/default/demo")
    assert not (page.dir / THUMBNAIL_NAMES["dark"]).exists()


@pytest.mark.posix
def test_an_unknown_theme_has_no_thumbnail(chrome: Path, port: int) -> None:
    built_page()
    assert get(port, "/api/thumb/default/demo?scheme=sepia")[0] == 404
    assert calls(chrome) == 0


@pytest.mark.posix
def test_requests_for_the_same_page_at_once_draw_it_once(chrome: Path, port: int, monkeypatch: pytest.MonkeyPatch) -> None:
    built_page()
    monkeypatch.setenv("FAKE_DELAY", "0.4")
    results: list[int] = []
    threads = [threading.Thread(target=lambda: results.append(get(port, "/api/thumb/default/demo")[0])) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert results == [200] * 4 and calls(chrome) == 1


@pytest.mark.posix
def test_the_thumbnail_may_be_kept_by_the_browser_and_other_responses_may_not(chrome: Path, port: int) -> None:
    built_page()
    assert get(port, "/api/thumb/default/demo")[2].headers["Cache-Control"] == "max-age=86400"
    assert get(port, "/api/pages")[2].headers["Cache-Control"] == "no-store"
    assert get(port, "/")[2].headers["Cache-Control"] == "no-store"


@pytest.mark.posix
def test_a_browser_that_fails_leaves_no_thumbnail_and_no_temporary_file(chrome: Path, port: int, monkeypatch) -> None:
    page = built_page()
    monkeypatch.setenv("FAKE_FAIL", "1")
    assert get(port, "/api/thumb/default/demo")[0] == 404
    assert not (page.dir / THUMBNAIL_NAME).exists() and not list(page.dir.glob(".thumb-*"))


def test_without_a_browser_there_is_no_thumbnail(home: Path, port: int, monkeypatch: pytest.MonkeyPatch) -> None:
    page = built_page()
    monkeypatch.setattr("pagekit.thumbnail.find_chrome", lambda: None)
    assert get(port, "/api/thumb/default/demo")[0] == 404
    with pytest.raises(PageError, match="no Chrome"):
        ensure_thumbnail(page)


@pytest.mark.posix
def test_unknown_unbuilt_and_saved_pages_have_no_thumbnail(chrome: Path, port: int) -> None:
    new_page(load_profile(), "draft", "Draft", None, "slots")
    saved = pages_root() / "saved"
    saved.mkdir(parents=True)
    (saved / "kept.html").write_text("<title>Kept</title>")
    for path in ("/api/thumb/default/draft", "/api/thumb/default/missing", "/api/thumb/saved/kept"):
        assert get(port, path)[0] == 404
    assert calls(chrome) == 0


def test_the_index_asks_for_thumbnails_groups_saved_pages_and_counts_days(home: Path, port: int) -> None:
    index = get(port, "/")[1].decode()
    assert "/api/thumb/" in index and "&v=" in index
    assert '"Expires in " + days + " days"' in index and "Expires tomorrow" in index and "Expires today" in index
    assert 'heading("Saved")' in index and 'heading("Recent")' in index and "Kept" not in index
    # The picture follows the theme the index is showing, including a change made with its toggle.
    assert '"?scheme=" + scheme()' in index and 'addEventListener("pagekit:theme", refreshThumbnails)' in index
    # A page with no browser to draw it simply has no picture.
    assert 'img.addEventListener("error", function () { box.remove(); })' in index


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    return struct.unpack(">II", data[16:24])


@pytest.mark.skipif(not REAL_CHROME, reason="needs Chrome or Chromium")
def test_a_real_browser_draws_a_500_by_350_picture(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGEKIT_CHROME", str(REAL_CHROME))
    assert png_size(ensure_thumbnail(built_page())) == (500, 350)


@pytest.mark.skipif(not REAL_CHROME, reason="needs Chrome or Chromium")
def test_the_index_shows_days_left_and_a_kept_group_in_a_real_browser(
    home: Path, port: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAGEKIT_CHROME", str(REAL_CHROME))
    built_page("recent")
    built_page("kept", pinned=True)
    command = [
        str(REAL_CHROME), "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=6000",
        f"--user-data-dir={tmp_path / 'chrome'}", "--dump-dom", f"http://127.0.0.1:{port}/",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL, timeout=90)
    dom = result.stdout
    assert len(re.findall(r'class="ix-item"', dom)) == 2
    assert 'class="ix-group">Saved<' in dom and 'class="ix-group">Recent<' in dom
    assert "Expires in 30 days" in dom and ">Saved</span>" in dom and "Kept" not in dom
    # With a single profile, its name is not repeated on every card.
    assert 'class="pk-badge">default<' not in dom
