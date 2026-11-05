from __future__ import annotations

import http.client
import json
import stat
import threading
from pathlib import Path

import pytest

from pagekit.pages import PageError, build_page, new_page
from pagekit.pdf import find_chrome, render_pdf
from pagekit.profiles import init_profile, load_profile
from pagekit.server import make_server

# Writes the argument after --print-to-pdf=, and keeps what it was asked to render.
FAKE_CHROME = """#!/bin/sh
for arg in "$@"; do
  case "$arg" in
    --print-to-pdf=*) out="${arg#--print-to-pdf=}" ;;
    file://*) src="${arg#file://}" ;;
  esac
done
echo "$*" > "$CHROME_LOG.args"
cp "$src" "$CHROME_LOG.html"
printf '%%PDF-fake' > "$out"
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


def built_page():
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    page.content.write_text("<h2>Section</h2>")
    build_page(profile, page)
    return page


@pytest.mark.posix
def test_render_asks_for_bookmarks_and_leaves_no_temp_files(chrome: Path, tmp_path: Path) -> None:
    page = built_page()
    target = render_pdf(page, tmp_path / "out.pdf")
    assert target.read_bytes() == b"%PDF-fake"
    assert "--generate-pdf-document-outline" in Path(f"{chrome}.args").read_text()
    assert not list(page.dir.glob(".print-*"))
    assert not list(tmp_path.glob(".out.pdf.*"))


@pytest.mark.posix
def test_generated_pdfs_use_their_own_margins_and_ctrl_p_keeps_its_own(chrome: Path, tmp_path: Path) -> None:
    page = built_page()
    render_pdf(page, tmp_path / "out.pdf")
    rendered = Path(f"{chrome}.html").read_text()
    assert "@page { margin: 0.15in 0.25in; }" in rendered
    assert rendered.index("margin: 12mm 15mm") < rendered.index("margin: 0.15in 0.25in")
    assert "margin: 0.15in 0.25in; }" not in page.index.read_text()
    assert "pdf_margin" not in page.meta


@pytest.mark.posix
def test_a_profile_can_set_its_own_pdf_margin(chrome: Path, tmp_path: Path, home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "profile.toml").write_text('name = "acme"\nextends = "builtin"\npdf_margin = "1in"\n')
    profile = load_profile(repo)
    page, _ = new_page(profile, "x", "X", None, "slots")
    build_page(profile, page)
    render_pdf(page, tmp_path / "out.pdf")
    assert "@page { margin: 1in; }" in Path(f"{chrome}.html").read_text()


@pytest.mark.posix
def test_answers_reach_the_render_safely(chrome: Path, tmp_path: Path) -> None:
    page = built_page()
    render_pdf(page, tmp_path / "out.pdf", {"a": "</script><script>alert(1)</script>"})
    html = Path(f"{chrome}.html").read_text()
    assert "window.pagekitPrintState" in html
    assert "alert(1)</script>" not in html
    assert "window.pagekitPrintState = " not in page.index.read_text()


def test_no_browser_is_a_clear_error(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAGEKIT_CHROME", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    assert find_chrome() is None
    with pytest.raises(PageError, match="no Chrome"):
        render_pdf(built_page(), tmp_path / "out.pdf")


def request(port: int, method: str, path: str, body: bytes = b"", headers: dict | None = None):
    connection = http.client.HTTPConnection("127.0.0.1", port)
    connection.request(method, path, body=body, headers=headers or {})
    response = connection.getresponse()
    return response.status, response.read(), response


@pytest.fixture
def port(chrome: Path):
    server = make_server("127.0.0.1", 0)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield server.server_address[1]
    server.shutdown()


@pytest.mark.posix
def test_server_builds_the_pdf_with_answers(chrome: Path, port: int) -> None:
    built_page()
    assert json.loads(request(port, "GET", "/api/pdf")[1]) == {"available": True}
    status, body, response = request(port, "POST", "/api/pdf/default/demo", b'{"a.notes": "hello"}')
    assert status == 200 and body == b"%PDF-fake"
    assert response.headers["Content-Type"] == "application/pdf"
    assert 'filename="demo.pdf"' in response.headers["Content-Disposition"]
    assert "hello" in Path(f"{chrome}.html").read_text()


@pytest.mark.parametrize(
    ("path", "body", "headers", "code"),
    [
        ("/api/pdf/default/missing", b"{}", {}, 404),
        ("/api/pdf/saved/demo", b"{}", {}, 404),
        ("/api/pdf/default/demo", b"not json", {}, 400),
        ("/api/pdf/default/demo", b"{}", {"Origin": "http://evil.example"}, 403),
        ("/api/pdf/../../secret", b"{}", {}, 404),
    ],
)
def test_server_refuses_bad_requests(chrome: Path, port: int, path: str, body: bytes, headers: dict, code: int) -> None:
    built_page()
    assert request(port, "POST", path, body, headers)[0] == code
