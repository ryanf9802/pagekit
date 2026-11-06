from __future__ import annotations

from pathlib import Path

import pytest

from pagekit.cli import main

BODY = """<h1>Title</h1>
<h2>Overview</h2>
<p><span class="pk-id">F-01</span> first</p>
<h3>Where the tokens go</h3>
<figure id="fig-1"></figure>
<p><span class="pk-id">F-02</span></p>
<h4>Detail</h4>
<h5>Too deep</h5>
"""


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    assert main(list(argv)) == 0
    return capsys.readouterr().out


def _write(home: Path, capsys, body: str, *extra: str) -> None:
    out = _run(capsys, "new", "demo", "--title", "Demo", *extra)
    path = Path(next(x for x in out.splitlines() if x.startswith("write: "))[len("write: ") :])
    path.write_text(body, encoding="utf-8")


def test_outline_lists_headings_and_ids_with_lines(home, capsys) -> None:
    _write(home, capsys, BODY, "--profile", "builtin")
    out = _run(capsys, "outline", "demo", "--profile", "builtin")
    assert out.splitlines() == [
        "content.html: 8 lines",
        "   2  h2  Overview",
        "   3  F-01",
        "   4    h3  Where the tokens go",
        "   5  fig-1",
        "   6  F-02",
        "   7      h4  Detail",
    ]


def test_outline_of_a_page_without_headings(home, capsys) -> None:
    _write(home, capsys, "<p>plain</p>\n", "--profile", "builtin")
    assert _run(capsys, "outline", "demo", "--profile", "builtin") == "content.html: 1 lines\n"


def test_outline_works_in_free_mode(home, capsys) -> None:
    body = "<!doctype html><html><head>{{head}}</head><body>\n<h2>Café</h2>\n{{footer}}</body></html>\n"
    _write(home, capsys, body, "--profile", "builtin", "--mode", "free")
    out = _run(capsys, "outline", "demo", "--profile", "builtin")
    assert "   2  h2  Café" in out.splitlines()


def test_outline_of_an_unknown_slug_fails(home, capsys) -> None:
    assert main(["outline", "nope", "--profile", "builtin"]) == 1
    assert "nope" in capsys.readouterr().err
