from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from pagekit.library import (
    ComponentError,
    add_component,
    find_component,
    library_components,
    library_css_for,
    library_dir,
    list_components,
)
from pagekit.pages import build_page, check_page, new_page
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


def test_free_mode_skips_consistency_warnings(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "free", "Free", None, "free")
    page.content.write_text(page.content.read_text().replace("<main", '<main style="margin:1px"'))
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
