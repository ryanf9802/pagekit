from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pagekit.library import (
    ComponentError,
    add_component,
    find_component,
    library_css_for,
    library_dir,
    list_components,
)
from pagekit.pages import PageError, build_page, check_page, new_page
from pagekit.profiles import init_profile, load_profile

CSS = ".field-map { color: var(--pk-text); }\n.field-map-row { padding: 2px; }\n"
HTML = '<!-- Field map. --><table class="field-map"></table>\n'


def source(tmp_path: Path, html: str = HTML, css: str | None = CSS) -> Path:
    folder = tmp_path / "draft"
    folder.mkdir(exist_ok=True)
    (folder / "component.html").write_text(html)
    if css is not None:
        (folder / "component.css").write_text(css)
    return folder


def page_with(body: str):
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    page.content.write_text(body)
    build_page(profile, page)
    return profile, page


def test_core_components_all_say_when_to_use_them(home: Path) -> None:
    core = [c for c in list_components(load_profile()) if c.source == "core"]
    names = {c.name for c in core}
    assert {"callout", "diagram", "divider", "table", "grid", "finding-card", "decision-card", "figure"} <= names
    assert all(c.when and "<" not in c.when for c in core)


def test_bundled_components_ship_with_pagekit_and_add_css_only_when_used(home: Path) -> None:
    profile = load_profile()
    assert find_component(profile, "contents-card").source == "bundled"
    assert ".page-break" in library_css_for('<div class="page-break"></div>', profile)
    assert ".page-break" not in library_css_for('<div class="pk-card"></div>', profile)


def test_a_library_copy_wins_over_a_bundled_component(home: Path, tmp_path: Path) -> None:
    folder = tmp_path / "mine"
    folder.mkdir()
    (folder / "component.html").write_text('<div class="in-short">Mine</div>')
    add_component(load_profile(), "in-short", "My own version", folder)
    component = find_component(load_profile(), "in-short")
    assert (component.source, component.when) == ("library", "My own version")


def test_add_saves_to_the_library_and_lists_it(home: Path, tmp_path: Path) -> None:
    profile = load_profile()
    target = add_component(profile, "field-map", "Source to target mappings", source(tmp_path))
    assert target == library_dir() / "field-map"
    component = find_component(profile, "field-map")
    assert (component.source, component.when) == ("library", "Source to target mappings")
    assert component.css and "field-map-row" in component.css.read_text()
    assert not [p for p in library_dir().iterdir() if p.name.startswith(".")]


def test_one_library_serves_every_profile(home: Path, tmp_path: Path) -> None:
    add_component(load_profile(), "field-map", "x", source(tmp_path))
    repo = home / "repo"
    init_profile(repo / ".pagekit" / "profile", "acme", "builtin", "Acme")
    assert find_component(load_profile(repo), "field-map").source == "library"


def test_existing_name_needs_update_and_core_names_are_refused(home: Path, tmp_path: Path) -> None:
    profile = load_profile()
    add_component(profile, "field-map", "x", source(tmp_path))
    with pytest.raises(ComponentError, match="already in the library"):
        add_component(profile, "field-map", "y", source(tmp_path))
    add_component(profile, "field-map", "y", source(tmp_path), update=True)
    assert find_component(profile, "field-map").when == "y"
    folder = source(tmp_path, '<div class="callout"></div>', ".callout { color: var(--pk-text); }")
    with pytest.raises(ComponentError, match="core component"):
        add_component(profile, "callout", "z", folder)


@pytest.mark.parametrize(
    ("html", "css", "message"),
    [
        (HTML, ".field-map { color: #fff; }", "hard-code"),
        (HTML, ".field-map { color: rgb(1, 2, 3); }", "hard-code"),
        (HTML, ".pk-card { padding: 1px; }", "must start with"),
        (HTML, ".other { padding: 1px; }", "must start with"),
        ('<div style="color: red"></div>', None, "inline"),
        ("<style>x{}</style>", None, "inline"),
    ],
)
def test_add_refuses_what_would_break_consistency(
    home: Path, tmp_path: Path, html: str, css: str | None, message: str
) -> None:
    with pytest.raises(ComponentError, match=message):
        add_component(load_profile(), "field-map", "x", source(tmp_path, html, css))
    assert not (library_dir() / "field-map").exists()


@pytest.mark.parametrize("name", ["pk-thing", "Bad Name", "../up"])
def test_add_refuses_bad_names(home: Path, tmp_path: Path, name: str) -> None:
    with pytest.raises(ComponentError, match="invalid"):
        add_component(load_profile(), name, "x", source(tmp_path))


def test_build_adds_css_only_for_components_the_page_uses(home: Path, tmp_path: Path) -> None:
    add_component(load_profile(), "field-map", "x", source(tmp_path))
    _, used = page_with('<table class="field-map"></table>')
    assert "field-map-row" in used.index.read_text()
    _, unused = page_with("<p>Nothing</p>")
    assert "field-map-row" not in unused.index.read_text()


def test_check_warns_on_styling_that_bypasses_components(home: Path, tmp_path: Path) -> None:
    profile, page = page_with('<div style="margin:1px" class="made-up"></div><style>.x{}</style>')
    result = check_page(profile, page)
    assert result.ok
    text = "\n".join(result.warnings)
    assert "1 inline style" in text and "1 <style> block" in text and "made-up" in text

    add_component(profile, "field-map", "x", source(tmp_path))
    profile, page = page_with('<div class="pk-callout"></div><table class="field-map"></table>')
    assert check_page(profile, page).warnings == []


@pytest.mark.parametrize("heading", ["<h1>Title</h1>", '<H1 class="pk-x">Title</H1>'])
def test_check_warns_when_content_repeats_the_title_as_an_h1(home: Path, heading: str) -> None:
    profile, page = page_with(f"{heading}<p>Body</p>")
    result = check_page(profile, page)
    assert result.ok
    assert any(warning.startswith("content.html has an <h1>") for warning in result.warnings)


@pytest.mark.parametrize("body", ["<h2>Section</h2>", "<!-- <h1>Old</h1> --><h2>Section</h2>", "<header>Not a heading</header>"])
def test_check_does_not_warn_without_an_h1(home: Path, body: str) -> None:
    profile, page = page_with(body)
    assert check_page(profile, page).warnings == []


def test_a_new_page_scaffold_does_not_warn_about_an_h1(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "fresh", "Fresh", None, "slots")
    assert "<h1>" in page.content.read_text()
    build_page(profile, page)
    assert not any("<h1>" in warning for warning in check_page(profile, page).warnings)


def test_free_mode_skips_consistency_warnings(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "free", "Free", None, "free")
    page.content.write_text(page.content.read_text().replace("<main", '<main style="margin:1px"').replace("<main", "<h1>Title</h1><main", 1))
    build_page(profile, page)
    assert check_page(profile, page).warnings == []


@pytest.mark.posix
def test_add_commits_only_its_own_folder_when_in_git(home: Path, tmp_path: Path) -> None:
    def git(*args: str) -> str:
        return subprocess.run(
            ["git", "-C", str(home), *args],
            capture_output=True,
            text=True,
            check=True,
            stdin=subprocess.DEVNULL,
        ).stdout

    git("init", "-q")
    git("config", "user.name", "t")
    git("config", "user.email", "t@example.com")
    (home / "other.txt").write_text("unrelated")
    git("add", "other.txt")
    add_component(load_profile(), "field-map", "x", source(tmp_path))
    assert "pagekit: add component field-map" in git("log", "--format=%s")
    assert "other.txt" not in git("show", "--name-only", "--format=", "HEAD")
    assert "A  other.txt" in git("status", "--short")


def test_add_works_outside_git(home: Path, tmp_path: Path) -> None:
    assert add_component(load_profile(), "field-map", "x", source(tmp_path)).is_dir()


@pytest.mark.parametrize("tag", ["<template ID from the fields panel>", "<uuid>"])
def test_a_raw_tag_in_content_fails_the_build_with_its_line(home: Path, tag: str) -> None:
    profile, page = page_with("<p>Fine</p>")
    good = page.index.read_text()
    page.content.write_text(f"<p>Fine</p>\n<p>Set {tag} here</p>")
    with pytest.raises(PageError, match=r"line 2: `<(template|uuid)[^`]*>` is read as an HTML tag.*&lt; and &gt;"):
        build_page(profile, page)
    assert page.index.read_text() == good
    page.index.touch()
    assert any("is read as an HTML tag" in error for error in check_page(profile, page).errors)


@pytest.mark.parametrize(
    "body",
    [
        "<p>Use &lt;template ID from the fields panel&gt; and &lt;uuid&gt;</p>",
        "<!-- <uuid> --><script>if (a<b) x = '<uuid>'</script>",
        '<div class="pk-callout">x</div><my-widget>x</my-widget><p>a < b</p>',
        '<svg viewBox="0 0 1 1"><defs><linearGradient id="g"><stop/></linearGradient></defs><path d="M0 0"/></svg>',
        "<table><tbody><tr><td><kbd>x</kbd></td></tr></tbody></table>",
    ],
)
def test_escaped_text_and_valid_elements_pass_the_tag_check(home: Path, body: str) -> None:
    profile, page = page_with(body)
    assert check_page(profile, page).ok


def test_svg_shapes_are_unknown_tags_outside_an_svg(home: Path) -> None:
    profile, page = page_with("<p>ok</p>")
    page.content.write_text("<path d='M0 0'/>")
    with pytest.raises(PageError, match="<path"):
        build_page(profile, page)
