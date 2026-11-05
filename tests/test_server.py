from __future__ import annotations

import http.client
import json
import threading
from collections.abc import Iterator
from pathlib import Path

import pytest

from pagekit.pages import PageError, build_page, new_page, pages_root, set_public_url
from pagekit.profiles import load_profile
from pagekit.server import make_server


@pytest.fixture
def port(home: Path) -> Iterator[int]:
    server = make_server("127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()


def request(port: int, path: str, headers: dict | None = None) -> tuple[int, bytes, http.client.HTTPResponse]:
    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request("GET", path, headers=headers or {})
    response = connection.getresponse()
    return response.status, response.read(), response


def built_page(home: Path):
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo <b>", "A summary", "slots")
    page.content.write_text('<img src="assets/a.png">')
    (page.assets / "a.png").write_bytes(b"png")
    build_page(profile, page)
    return page


def test_index_and_api_list_pages(home: Path, port: int) -> None:
    built_page(home)
    status, body, _ = request(port, "/")
    assert status == 200 and b"--pk-accent" in body
    status, body, _ = request(port, "/api/pages")
    entry = json.loads(body)[0]
    assert entry["url"] == "/p/default/demo/"
    assert entry["title"] == "Demo <b>"
    assert entry["expires"] is not None


def test_serves_page_and_assets(home: Path, port: int) -> None:
    built_page(home)
    status, _, response = request(port, "/p/default/demo")
    assert status == 302 and response.headers["Location"] == "/p/default/demo/"
    status, body, _ = request(port, "/p/default/demo/")
    assert status == 200 and b"pk-export" in body
    status, body, response = request(port, "/p/default/demo/assets/a.png")
    assert status == 200 and body == b"png" and response.headers["Content-Type"] == "image/png"


@pytest.mark.parametrize(
    "path",
    [
        "/p/default/demo/../../../secret.txt",
        "/p/default/demo/%2e%2e/%2e%2e/%2e%2e/secret.txt",
        "/p/default/demo/page.toml",
        "/p/default/demo/content.html",
        "/p/default/missing/",
        "/saved/../secret.txt",
    ],
)
def test_refuses_anything_else(home: Path, port: int, path: str) -> None:
    built_page(home)
    (home / "pages" / "secret.txt").write_text("secret")
    (home / "secret.txt").write_text("secret")
    status, body, _ = request(port, path)
    assert status == 404 and b"secret" not in body


def test_foreign_host_and_origin_are_rejected(home: Path, port: int) -> None:
    status, _, _ = request(port, "/api/pages", {"Host": "evil.example"})
    assert status == 403
    status, _, _ = request(port, "/api/pages", {"Host": "localhost:1", "Origin": "http://evil.example"})
    assert status == 403


def test_saved_copies_are_listed_and_served(home: Path, port: int) -> None:
    saved = pages_root() / "saved"
    saved.mkdir(parents=True)
    (saved / "kept.html").write_text("<html><title>Kept &amp; safe</title></html>")
    status, body, _ = request(port, "/api/pages")
    entry = json.loads(body)[0]
    assert entry["title"] == "Kept & safe" and entry["expires"] is None
    status, body, _ = request(port, entry["url"])
    assert status == 200 and b"Kept" in body


def test_public_address_is_refused_until_set_up_then_only_that_name(home: Path, port: int) -> None:
    host = "pages.example.ts.net"
    assert request(port, "/api/pages", {"Host": host})[0] == 403
    set_public_url(f"https://{host}/")
    assert request(port, "/api/pages", {"Host": host})[0] == 200
    assert request(port, "/api/pages", {"Host": host, "Origin": f"https://{host}"})[0] == 200
    assert request(port, "/api/pages", {"Host": "127.0.0.1:8766", "Origin": f"https://{host}"})[0] == 200
    assert request(port, "/api/pages", {"Host": "other.example.ts.net"})[0] == 403
    assert request(port, "/api/pages", {"Host": host, "Origin": "https://evil.example"})[0] == 403


@pytest.mark.parametrize("url", ["http://pages.example.ts.net", "pages.example.ts.net", "https://host/path"])
def test_public_url_must_be_plain_https(home: Path, url: str) -> None:
    with pytest.raises(PageError, match="public URL"):
        set_public_url(url)


def test_page_reports_a_phone_link_only_when_set_up(home: Path) -> None:
    page = built_page(home)
    assert page.phone_url() == ""
    set_public_url("https://pages.example.ts.net")
    assert page.phone_url() == "https://pages.example.ts.net/p/default/demo/"


def test_index_can_be_installed_as_an_app(home: Path, port: int) -> None:
    status, body, _ = request(port, "/")
    assert status == 200 and b'rel="manifest"' in body
    assert b"<title>pagekit</title>" in body and b"<h1>pagekit</h1>" in body
    status, body, response = request(port, "/manifest.webmanifest")
    manifest = json.loads(body)
    assert status == 200 and response.headers["Content-Type"] == "application/manifest+json"
    assert manifest["display"] == "standalone" and manifest["start_url"] == "/"
    assert manifest["name"] == manifest["short_name"] == "pagekit"
    for icon in manifest["icons"]:
        status, body, response = request(port, icon["src"])
        assert status == 200 and response.headers["Content-Type"] == "image/png" and body.startswith(b"\x89PNG")
