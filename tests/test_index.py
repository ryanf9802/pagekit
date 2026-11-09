"""The page index: one compact row per page, saved pages first, and nothing that draws a picture of a page."""

from __future__ import annotations

import http.client
import re
import subprocess
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from pagekit.browser import find_chrome
from pagekit.pages import build_page, new_page, pages_root
from pagekit.profiles import init_profile, load_profile
from pagekit.server import make_server

REAL_CHROME = find_chrome()  # Found now, since the home fixture hides anything installed under the real home.


@pytest.fixture
def port(home: Path) -> Iterator[int]:
    server = make_server("127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


def get(port: int, path: str) -> tuple[int, bytes]:
    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", path)
    response = connection.getresponse()
    return response.status, response.read()


def built_page(slug: str, title: str, profile=None, pinned: bool = False):
    profile = profile or load_profile()
    page, _ = new_page(profile, slug, title, f"About {title}", "slots")
    page.content.write_text("<h2>Section</h2>")
    build_page(profile, page)
    if pinned:
        page.meta["pinned"] = True
        page.write_meta()
    return page


def has_profile_column(dom: str) -> bool:
    """The list carries the class only when there is more than one profile. The style rules name it too, so look at the list."""
    return bool(re.search(r'<ul[^>]*class="[^"]*ix-has-profile', dom))


def dump_index(port: int, tmp_path: Path) -> str:
    command = [
        str(REAL_CHROME), "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=4000",
        f"--user-data-dir={tmp_path / 'chrome'}", "--dump-dom", f"http://127.0.0.1:{port}/",
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL, timeout=90)
    return result.stdout


def test_the_index_is_a_list_of_rows_with_the_days_left_and_no_pictures(home: Path, port: int) -> None:
    index = get(port, "/")[1].decode()
    assert 'a.className = "ix-row"' in index and 'li.className = "ix-head"' in index
    assert '"in " + days + " days"' in index and '"tomorrow"' in index and '"today"' in index
    # Saved pages first, and a saved page says so where the days would be.
    assert '"Saved"' in index and 'filter(function (p) { return p.pinned; })' in index
    assert "/api/thumb" not in index and "ix-thumb" not in index and 'loading = "lazy"' not in index and "<img" not in index.split("<main")[1]


def test_nothing_draws_a_picture_of_a_page(home: Path, port: int) -> None:
    page = built_page("demo", "Demo")
    assert get(port, "/api/thumb/default/demo")[0] == 404
    assert get(port, "/api/thumb/default/demo?scheme=dark")[0] == 404
    assert not list(page.dir.glob("*thumb*")) and not list(page.dir.glob(".thumb-*"))


@pytest.mark.skipif(not REAL_CHROME, reason="needs Chrome or Chromium")
def test_a_real_browser_lists_saved_pages_first_with_days_left(home: Path, port: int, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PAGEKIT_CHROME", str(REAL_CHROME))
    built_page("recent", "Recent one")
    built_page("saved", "Saved one", pinned=True)
    dom = dump_index(port, tmp_path)
    assert len(re.findall(r'class="ix-item"', dom)) == 2
    # Saved first, though the other was updated no earlier.
    assert dom.index("Saved one") < dom.index("Recent one")
    assert '<span class="ix-status ix-saved">Saved</span>' in dom and ">in 30 days<" in dom
    assert "About Saved one" not in dom and "About Recent one" not in dom
    # One profile: its name is not repeated on every row, and nothing draws a picture.
    assert not has_profile_column(dom) and 'class="ix-profile"' not in dom and "ix-thumb" not in dom
    assert re.search(r'class="ix-head"[^>]*>.*?Page.*?Updated.*?Expires', dom, re.DOTALL)
    assert "Summary" not in dom and "ix-summary" not in dom


@pytest.mark.skipif(not REAL_CHROME, reason="needs Chrome or Chromium")
def test_a_real_browser_adds_a_profile_column_only_when_there_are_several(
    home: Path, port: int, tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("PAGEKIT_CHROME", str(REAL_CHROME))
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    built_page("one", "Default page")
    built_page("two", "Acme page", profile=load_profile(repo))
    dom = dump_index(port, tmp_path)
    assert has_profile_column(dom) and 'class="ix-profile">acme<' in dom and 'class="ix-profile">default<' in dom
    assert "Profile" in dom


@pytest.mark.skipif(not REAL_CHROME, reason="needs Chrome or Chromium")
def test_a_saved_copy_is_a_place_and_not_a_second_profile(home: Path, port: int, tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PAGEKIT_CHROME", str(REAL_CHROME))
    built_page("one", "Default page")
    saved = pages_root() / "saved"
    saved.mkdir(parents=True)
    (saved / "kept.html").write_text("<html><title>A saved copy</title></html>")
    dom = dump_index(port, tmp_path)
    assert "A saved copy" in dom and len(re.findall(r'class="ix-item"', dom)) == 2
    assert not has_profile_column(dom)
