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


CARDS = """<h2>Findings</h2>
<article class="pk-card" id="F-01">
  <header><span class="pk-id">F-01</span> Title</header>
</article>
<article class="pk-card pk-decision" id="D-01">
  <p><span class="pk-id">D-01</span></p>
</article>
<figure id="fig-1">
  <img src="x.png" alt="">
  <figcaption><span class="pk-id">fig-1</span> caption</figcaption>
</figure>
<table><tr><td><span class="pk-id">T-01</span></td></tr></table>
<figure id="fig-2"><figcaption><span class="pk-id">fig-9</span></figcaption></figure>
<p>See <span class="pk-id">F-01</span> above.</p>
"""


def test_outline_lists_a_card_or_figure_id_once_on_the_element(home, capsys) -> None:
    _write(home, capsys, CARDS, "--profile", "builtin")
    out = _run(capsys, "outline", "demo", "--profile", "builtin")
    assert out.splitlines() == [
        "content.html: 14 lines",
        "   1  h2  Findings",
        "   2  F-01",
        "   5  D-01",
        "   8  fig-1",
        "  12  T-01",
        "  13  fig-2",
        "  13  fig-9",
        "  14  F-01",
    ]


def test_outline_keeps_a_span_after_its_element_closed(home, capsys) -> None:
    body = '<article id="F-01"><div><p>x</p></div></article>\n<p><span class="pk-id">F-01</span></p>\n'
    _write(home, capsys, body, "--profile", "builtin")
    out = _run(capsys, "outline", "demo", "--profile", "builtin")
    assert out.splitlines()[1:] == ["   1  F-01", "   2  F-01"]
