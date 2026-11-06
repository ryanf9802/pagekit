"""A page's own tab icon: set with `pagekit new --icon`, drawn from Lucide in the profile's accent."""

from __future__ import annotations

import base64
import re
from pathlib import Path

import pytest

from pagekit.cli import main
from pagekit.pages import PageError, _accent_colors, build_page, load_page, new_page, pages_root
from pagekit.profiles import init_profile, load_profile


def favicon(page) -> str:
    """The SVG the built page uses for its tab, or the empty string when it is not an inline SVG."""
    document = page.index.read_text(encoding="utf-8")
    found = re.search(r'rel="icon" href="data:image/svg\+xml;base64,([^"]+)"', document)
    return base64.b64decode(found.group(1)).decode() if found else ""


def repo_profile(home: Path, theme: str):
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "theme.css").write_text(theme)
    return load_profile(repo)


def test_a_page_with_an_icon_draws_it_as_its_tab_icon_in_the_accent(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots", "chart-bar")
    build_page(profile, page)
    svg = favicon(page)
    assert "<path" in svg and 'viewBox="0 0 24 24"' in svg
    # The built-in theme's accent, in light and in dark.
    assert 'stroke="#c8431c"' in svg and "stroke: #ff7a50" in svg


def test_a_page_without_an_icon_keeps_the_profile_icon(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    build_page(profile, page)
    assert 'viewBox="0 0 24 24"' not in favicon(page) and "6 6 52 52" in favicon(page)


def test_reopening_keeps_the_icon_and_an_empty_one_goes_back_to_the_profile(home: Path) -> None:
    profile = load_profile()
    new_page(profile, "demo", "Demo", None, "slots", "chart-bar")
    page, created = new_page(profile, "demo", None, "A new summary", "slots")
    assert not created and page.meta["icon"] == "chart-bar"
    page, _ = new_page(profile, "demo", None, None, "slots", "calendar")
    assert load_page(profile, "demo").meta["icon"] == "calendar"
    page, _ = new_page(profile, "demo", None, None, "slots", "")
    assert "icon" not in load_page(profile, "demo").meta
    build_page(profile, page)
    assert 'viewBox="0 0 24 24"' not in favicon(page)


def test_an_unknown_icon_is_refused_and_creates_nothing(home: Path) -> None:
    profile = load_profile()
    with pytest.raises(PageError, match="--icon: no Lucide icon named 'chart-barr'"):
        new_page(profile, "demo", "Demo", None, "slots", "chart-barr")
    assert not (pages_root() / "default" / "demo").exists()


def test_an_unknown_icon_suggests_near_names(home: Path) -> None:
    with pytest.raises(PageError, match="Did you mean: .*calendar"):
        new_page(load_profile(), "demo", "Demo", None, "slots", "calendar-")


def test_a_hand_edited_icon_that_does_not_exist_fails_the_build_and_names_the_file(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    page.meta["icon"] = "not-an-icon"
    page.write_meta()
    with pytest.raises(PageError, match=r"page\.toml: icon: no Lucide icon named 'not-an-icon'"):
        build_page(profile, load_page(profile, "demo"))


def test_the_ink_comes_from_the_profile_theme(home: Path) -> None:
    profile = repo_profile(
        home, ":root { --pk-accent: #123456; }\n@media screen and (prefers-color-scheme: dark) { :root { --pk-accent: #abcdef; } }\n"
    )
    page, _ = new_page(profile, "demo", "Demo", None, "slots", "sun")
    build_page(profile, page)
    svg = favicon(page)
    # The built-in theme comes first, so the profile's own accent is the last declaration and wins.
    assert 'stroke="#123456"' in svg and "stroke: #abcdef" in svg


def test_accent_colors_take_the_last_declaration_and_ignore_comments_and_other_blocks() -> None:
    theme = """
    /* --pk-accent: #000000; */
    :root { --pk-accent: #111111; }
    @media (max-width: 600px) { :root { --pk-accent: #222222; } }
    :root { --pk-accent: #333333; }
    @media screen and (prefers-color-scheme: dark) { :root { --pk-accent: #444444; } }
    """
    # A width block is not the light theme, so only the plain declarations count.
    assert _accent_colors(theme) == ("#333333", "#444444")


def test_accent_colors_fall_back_sensibly() -> None:
    assert _accent_colors(":root { --pk-accent: #123456; }") == ("#123456", "#123456")
    assert _accent_colors("body { color: red; }") == ("#1b1b1f", "#e5e5ea")
    # A value that is not a plain color never reaches the SVG.
    assert _accent_colors(':root { --pk-accent: red" onload="x; }') == ("#1b1b1f", "#e5e5ea")


def test_the_command_sets_the_icon_and_reports_an_unknown_one(home: Path, capsys) -> None:
    assert main(["new", "demo", "--title", "Demo", "--icon", "chart-bar"]) == 0
    assert load_page(load_profile(), "demo").meta["icon"] == "chart-bar"
    capsys.readouterr()
    assert main(["new", "other", "--title", "Other", "--icon", "nope-nope"]) == 1
    assert "--icon: no Lucide icon named 'nope-nope'" in capsys.readouterr().err
