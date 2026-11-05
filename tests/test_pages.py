from __future__ import annotations

import base64
import os
import re
import stat
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from pagekit.pages import (
    Page,
    PageError,
    build_page,
    check_page,
    load_page,
    new_page,
    pack_page,
    pages_root,
    prune_if_due,
    prune_pages,
    save_page,
)
from pagekit.profiles import Profile, init_profile, load_profile

NAMED_FORM = '<input name="a.text"><textarea name="a.notes"></textarea>'


def make(profile: Profile, slug: str = "demo", body: str = "<p>Hello</p>", mode: str = "slots") -> Page:
    page, _ = new_page(profile, slug, "Demo", "One line", mode)
    if mode == "slots":
        page.content.write_text(body)
    build_page(profile, page)
    return page


def age(page: Page, days: float) -> None:
    stamp = datetime.now(timezone.utc) - timedelta(days=days)
    page.meta["updated"] = stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    page.write_meta()


def errors(profile: Profile, page: Page) -> str:
    return "\n".join(check_page(profile, page).errors)


def test_build_composes_a_self_contained_page(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    document = page.index.read_text()
    assert page.dir == home / "pages" / "default" / "demo"
    assert "<title>Demo</title>" in document and "<p>Hello</p>" in document and "--pk-accent" in document
    assert 'id="pk-export"' in document and "window.pagekit" in document
    assert 'class="pk-summary">One line' in document
    assert check_page(profile, page).ok


def test_new_is_idempotent_and_keeps_content(home: Path) -> None:
    profile = load_profile()
    page = make(profile, body="<p>Mine</p>")
    again, created = new_page(profile, "demo", None, None, "slots")
    assert not created and again.dir == page.dir
    assert again.content.read_text() == "<p>Mine</p>"
    assert again.meta["title"] == "Demo"


def test_new_needs_a_title_and_a_valid_slug(home: Path) -> None:
    profile = load_profile()
    with pytest.raises(PageError, match="title"):
        new_page(profile, "fresh", None, None, "slots")
    with pytest.raises(PageError, match="slug"):
        new_page(profile, "../escape", "T", None, "slots")


def test_content_placeholders_are_left_as_written(home: Path) -> None:
    profile = load_profile()
    page = make(profile, body="<code>{{footer}}</code>")
    assert "<code>{{footer}}</code>" in page.index.read_text()


def test_answers_key_survives_a_restyle_but_not_a_content_change(home: Path) -> None:
    profile = load_profile()

    def rev(page: Page) -> str:
        return re.search(r'"rev": "(\w+)"', page.index.read_text()).group(1)

    page = make(profile, body="<p>One</p>")
    first = rev(page)
    build_page(profile, page)
    assert rev(page) == first
    page.content.write_text("<p>Two</p>")
    build_page(profile, page)
    assert rev(page) != first


def test_title_is_escaped(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "x", "<script>alert(1)</script>", None, "slots")
    build_page(profile, page)
    assert "<title>&lt;script&gt;" in page.index.read_text()


def test_free_mode_needs_head_and_footer(home: Path) -> None:
    profile = load_profile()
    page = make(profile, slug="free", mode="free")
    assert check_page(profile, page).ok
    page.content.write_text("<html><body>no slots</body></html>")
    with pytest.raises(PageError, match="head"):
        build_page(profile, page)


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("<input>", "no name or id"),
        ("<textarea></textarea>", "no name or id"),
        ("<div contenteditable>x</div>", "no name or id"),
        ('<input name="a"><input name="a">', "share the name"),
        ('<script src="https://evil.example/x.js"></script>', "not in allowed_hosts"),
        ('<img src="//evil.example/x.png">', "not in allowed_hosts"),
        ("<style>@import 'https://evil.example/x.css';</style>", "not in allowed_hosts"),
        ('<img src="assets/gone.png">', "missing asset"),
        ("<p>café</p>", "non-ASCII"),
    ],
)
def test_check_catches(home: Path, body: str, message: str) -> None:
    profile = load_profile()
    assert message in errors(profile, make(profile, body=body))


@pytest.mark.parametrize(
    "body",
    [
        NAMED_FORM,
        '<input type="radio" name="r" value="a"><input type="radio" name="r" value="b">',
        '<input type="checkbox" name="c" value="a"><input type="checkbox" name="c" value="b">',
        '<input type="hidden"><button type="button">x</button><input type="submit">',
        '<div contenteditable="false">x</div>',
        '<script src="https://cdn.jsdelivr.net/npm/x@1.0.0/x.js"></script>',
        '<a href="https://example.com/">external links are fine</a>',
    ],
)
def test_check_allows(home: Path, body: str) -> None:
    profile = load_profile()
    assert errors(profile, make(profile, body=body)) == ""


def test_check_flags_unused_assets_and_stale_builds(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    (page.assets / "orphan.png").write_bytes(b"x")
    assert "unused asset: assets/orphan.png" in errors(profile, page)
    (page.assets / "orphan.png").unlink()
    future = time.time() + 5
    os.utime(page.content, (future, future))
    assert "stale" in errors(profile, page)


def test_wide_fixed_width_is_a_warning_not_an_error(home: Path) -> None:
    profile = load_profile()
    result = check_page(profile, make(profile, body='<div style="width: 1200px">x</div>'))
    assert result.ok and "1200px" in result.warnings[0]


def test_required_footer_is_enforced(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "profile.toml").write_text('name = "acme"\nextends = "builtin"\nfooter = "Acme internal"\n')
    profile = load_profile(repo)
    page = make(profile)
    assert "Acme internal" in page.index.read_text()
    page.index.write_text(page.index.read_text().replace("Acme internal", ""))
    assert "required footer" in errors(profile, page)


def test_logo_is_inlined(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "logo.svg").write_text("<svg/>")
    page = make(load_profile(repo))
    encoded = base64.b64encode(b"<svg/>").decode()
    assert f"data:image/svg+xml;base64,{encoded}" in page.index.read_text()


def test_pack_inlines_assets(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "shot", "Shot", None, "slots")
    (page.assets / "a b.png").write_bytes(b"png")
    page.content.write_text('<img src="assets/a%20b.png"><div style="background:url(assets/a%20b.png)"></div>')
    build_page(profile, page)
    assert check_page(profile, page).ok  # an encoded name still counts as used
    document = pack_page(page).read_text()
    assert "assets/" not in document.split("</style>")[-1].split("<script>")[0]
    assert document.count("base64,cG5n") == 2


def test_pack_inlines_a_stylesheet_url(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "css", "Css", None, "slots")
    (page.assets / "bg.png").write_bytes(b"png")
    page.content.write_text('<style>.x{background:url("assets/bg.png")}</style>')
    build_page(profile, page)
    assert check_page(profile, page).ok
    assert 'url("data:image/png;base64,cG5n")' in pack_page(page).read_text()


def test_pack_refuses_a_stale_build(home: Path) -> None:
    page = make(load_profile())
    future = time.time() + 5
    os.utime(page.content, (future, future))
    with pytest.raises(PageError, match="stale"):
        pack_page(page)


def test_prune_removes_only_old_unpinned_pages(home: Path) -> None:
    profile = load_profile()
    old, recent, pinned = (make(profile, slug=s) for s in ("old", "recent", "pinned"))
    age(old, 31)
    age(recent, 29)
    age(pinned, 400)
    pinned.meta["pinned"] = True
    pinned.write_meta()

    assert prune_pages(dry_run=True) == [old.dir]
    assert old.dir.exists()
    assert prune_pages() == [old.dir]
    assert not old.dir.exists() and recent.dir.exists() and pinned.dir.exists()


def test_prune_never_touches_folders_it_did_not_create(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    age(page, 400)
    stray = pages_root() / "default" / "not-a-page"
    stray.mkdir()
    saved = pages_root() / "saved"
    saved.mkdir()
    (saved / "keep.html").write_text("x")
    assert prune_pages() == [page.dir]
    assert stray.exists() and (saved / "keep.html").exists()


def test_prune_follows_no_symlinks(home: Path) -> None:
    target = home / "precious"
    target.mkdir()
    (target / "page.toml").write_text('slug = "x"\nprofile = "default"\nupdated = "2000-01-01T00:00:00Z"\n')
    (pages_root() / "default").mkdir(parents=True)
    (pages_root() / "default" / "link").symlink_to(target)
    assert prune_pages() == []
    assert target.exists()


def test_ttl_zero_disables_prune(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PAGEKIT_TTL_DAYS", "0")
    page = make(load_profile())
    age(page, 400)
    assert prune_pages() == []


def test_prune_if_due_runs_once_within_the_throttle(home: Path) -> None:
    profile = load_profile()
    first = make(profile, slug="first")
    age(first, 31)
    prune_if_due()
    assert not first.dir.exists()
    second = make(profile, slug="second")
    age(second, 31)
    prune_if_due()
    assert second.dir.exists()


def test_save_defaults_to_the_saved_folder_with_no_next_step(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    result = save_page(profile, page)
    assert result.path == pages_root() / "saved" / "demo.html"
    assert result.instructions == ""
    assert load_page(profile, "demo").meta["pinned"] is True
    age(page, 400)
    assert prune_pages() == []
    assert result.path.exists()


def test_save_follows_the_profile_and_prints_its_next_step(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    target = home / "vault"
    script = home / "where"
    script.write_text(f"#!/bin/sh\necho {target}\n")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    (directory / "profile.toml").write_text(
        f'name = "acme"\nextends = "builtin"\n[save]\nroot_command = "{script}"\nsubdir = "Attachments/Pages"\n'
    )
    (directory / "SAVE.md").write_text("Link {{file}} for {{title}} at {{url}}.")
    profile = load_profile(repo)
    page = make(profile)

    result = save_page(profile, page)

    assert result.path == target / "Attachments" / "Pages" / "demo.html"
    assert result.path.read_text().startswith("<!doctype html>")
    assert result.instructions == "Link demo.html for Demo at http://localhost:8766/p/acme/demo/."


def test_save_refuses_a_failing_page(home: Path) -> None:
    profile = load_profile()
    page = make(profile, body="<input>")
    with pytest.raises(PageError, match="no name"):
        save_page(profile, page)
    assert not load_page(profile, "demo").meta["pinned"]


def test_save_updates_its_own_copy_but_never_another_file(home: Path) -> None:
    profile = load_profile()
    page = make(profile)
    first = save_page(profile, page)
    page.content.write_text("<p>Second</p>")
    build_page(profile, page)
    assert "Second" in save_page(profile, page).path.read_text()

    first.path.write_text("someone else's file")
    with pytest.raises(PageError, match="different page"):
        save_page(profile, page)
    assert first.path.read_text() == "someone else's file"
