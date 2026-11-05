from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

from pagekit.browser import find_chrome
from pagekit.diagrams import DiagramError, parse_source, themed_svg
from pagekit.pages import PageError, build_page, check_page, new_page
from pagekit.profiles import load_profile

SOURCE = """---
title: What happens <next>
desc: A record is updated when it matches.
---
flowchart TB
  q["Matches?"]
  q -->|Yes| u["Updated"]
  class q strong
  class u accent
"""
RAW = (
    '<svg id="flow" width="100%" viewBox="0 0 518.3 200.4" style="max-width: 518.3px;" role="graphics-document document" '
    'aria-roledescription="flowchart-v2"><style>#flow{fill:#333}</style>'
    '<filter id="s"><feFlood flood-color="#000000"/></filter>'
    '<g class="node default strong flowchart-label" style="fill:#111"><rect style="stroke:#222" fill="#000000"/></g>'
    '<path class="edge-thickness-normal flowchart-link" style="stroke-width:2"/></svg>'
)
FAKE_CHROME = """#!/bin/sh
count="$CHROME_LOG"
echo x >> "$count"
printf '%s' '<html><textarea id="out">&lt;svg id="x" style="max-width: 300px;"&gt;&lt;g class="node accent"&gt;&lt;/g&gt;&lt;/svg&gt;</textarea></html>'
"""


def test_source_needs_a_title_and_description() -> None:
    assert parse_source("a.mmd", SOURCE)[:2] == ("What happens <next>", "A record is updated when it matches.")
    with pytest.raises(DiagramError, match="title"):
        parse_source("a.mmd", "flowchart TB\n  a --> b\n")


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("classDef x fill:#111", "no classDef"),
        ("style a fill:#111", "no style"),
        ("linkStyle 0 stroke:#111", "no linkStyle"),
        ("class a purple", "unknown tone"),
        ("a:::purple --> b", "unknown tone"),
    ],
)
def test_source_cannot_set_its_own_colors(line: str, message: str) -> None:
    with pytest.raises(DiagramError, match=message):
        parse_source("a.mmd", f"---\ntitle: T\ndesc: D\n---\nflowchart TB\n  {line}\n")


def test_only_flowcharts_are_supported() -> None:
    with pytest.raises(DiagramError, match="only flowchart"):
        parse_source("a.mmd", "---\ntitle: T\ndesc: D\n---\nsequenceDiagram\n  a->>b: hi\n")


def test_themed_svg_removes_mermaid_styling_and_adds_alt_text() -> None:
    svg = themed_svg(RAW, "flow", "A <title>", "A description")
    assert "<filter" not in svg and "flood-color" not in svg
    assert "<style" not in svg and "#111" not in svg and "#000000" not in svg and "#333" not in svg
    assert re.findall(r'style="([^"]*)"', svg) == ["--pk-diagram-h:200px;--pk-diagram-w:518px"]
    assert 'class="pk-diagram-node pk-diagram-tone-strong"' in svg
    assert 'class="pk-diagram-wide"' in svg
    assert 'class="pk-diagram-flowchart-link"' in svg
    assert 'role="img" aria-labelledby="flow-t flow-d"' in svg
    assert '<title id="flow-t">A &lt;title&gt;</title>' in svg
    assert "graphics-document" not in svg


def page_with_diagram():
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    (page.assets / "flow.mmd").write_text(SOURCE)
    page.content.write_text('<pk-diagram src="assets/flow.mmd"><p class="pk-diagram-note">Note.</p></pk-diagram>')
    return profile, page


@pytest.fixture
def chrome(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    script = tmp_path / "fake-chrome"
    script.write_text(FAKE_CHROME)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    log = tmp_path / "draws"
    monkeypatch.setenv("PAGEKIT_CHROME", str(script))
    monkeypatch.setenv("CHROME_LOG", str(log))
    return log


@pytest.mark.posix
def test_build_expands_the_tag_and_counts_the_source_as_used(chrome: Path) -> None:
    profile, page = page_with_diagram()
    build_page(profile, page)
    document = page.index.read_text()
    assert "<pk-diagram" not in document
    assert '<figcaption>What happens &lt;next&gt;</figcaption>' in document
    assert 'class="pk-diagram-note">Note.</p></figure>' in document
    result = check_page(profile, page)
    assert result.ok and result.warnings == []


@pytest.mark.posix
def test_tag_class_goes_on_the_figure(chrome: Path) -> None:
    profile, page = page_with_diagram()
    page.content.write_text('<pk-diagram src="assets/flow.mmd" class="glance-left"></pk-diagram>')
    build_page(profile, page)
    assert '<figure class="pk-diagram glance-left" id="diagram-flow">' in page.index.read_text()


@pytest.mark.posix
def test_diagrams_redraw_only_when_the_source_changes(chrome: Path) -> None:
    profile, page = page_with_diagram()
    build_page(profile, page)
    build_page(profile, page)
    assert len(chrome.read_text().splitlines()) == 1
    (page.assets / "flow.mmd").write_text(SOURCE.replace("Updated", "Changed"))
    build_page(profile, page)
    assert len(chrome.read_text().splitlines()) == 2
    assert len(list((page.dir / ".diagram-cache").glob("*.svg"))) == 1


def test_build_fails_clearly_on_a_missing_source_or_browser(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PAGEKIT_CHROME", raising=False)
    monkeypatch.setenv("PATH", str(tmp_path))
    profile, page = page_with_diagram()
    with pytest.raises(PageError, match="needs Chrome"):
        build_page(profile, page)
    page.content.write_text('<pk-diagram src="assets/gone.mmd"></pk-diagram>')
    with pytest.raises(PageError, match="missing diagram source"):
        build_page(profile, page)


# Found before the fixture swaps the home folder, where Playwright's browsers live.
REAL_CHROME = find_chrome()


@pytest.mark.skipif(REAL_CHROME is None, reason="needs a local Chrome or Chromium")
def test_real_mermaid_draws_a_themed_diagram(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGEKIT_CHROME", REAL_CHROME or "")
    profile, page = page_with_diagram()
    build_page(profile, page)
    document = page.index.read_text()
    figure = document[document.index('<figure class="pk-diagram"') :].split("</figure>")[0]
    assert "pk-diagram-tone-strong" in figure and "pk-diagram-tone-accent" in figure
    assert "Matches?" in figure and "<style" not in figure
    assert not re.findall(r"#[0-9a-fA-F]{3,8}\\b", figure.replace("url(#", ""))
    assert check_page(profile, page).ok
