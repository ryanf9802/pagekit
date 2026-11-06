"""The version stamp on built pages, and rebuilding the pages an update leaves behind."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import pagekit.cli as cli_module
import pagekit.pages as pages_module
from pagekit.cli import main
from pagekit.pages import Page, build_page, new_page, stale_pages
from pagekit.profiles import init_profile, load_profile, profile_named


def at_version(monkeypatch: pytest.MonkeyPatch, version: str) -> None:
    monkeypatch.setattr(pages_module, "build_version", lambda: version)
    monkeypatch.setattr(cli_module, "build_version", lambda: version)


def make(slug: str = "demo", body: str = "<p>Hello</p>", profile=None) -> Page:
    profile = profile or load_profile()
    page, _ = new_page(profile, slug, "Demo", "One line", "slots")
    page.content.write_text(body, encoding="utf-8")
    build_page(profile, page)
    return page


def stamped(page: Page) -> str:
    match = re.search(r'id="pagekit-meta">(.*?)</script>', page.index.read_text(encoding="utf-8"))
    return json.loads(match.group(1)).get("version", "")


def repo_profile(home: Path, extra: str = "") -> Path:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "profile.toml").write_text(f'name = "acme"\nextends = "builtin"\nfooter = "Acme internal"\n{extra}')
    return repo


def test_a_build_stamps_the_version_in_the_page_and_the_footer(home: Path, monkeypatch) -> None:
    at_version(monkeypatch, "1.2.3")
    page = make()
    assert stamped(page) == "1.2.3"
    assert "<span>v1.2.3</span>" in page.index.read_text(encoding="utf-8")


def test_the_footer_shows_the_number_and_not_the_product_name(home: Path, monkeypatch) -> None:
    at_version(monkeypatch, "1.2.3")
    footer = re.search(r"<span>v1\.2\.3</span>", make().index.read_text(encoding="utf-8"))
    assert footer and "pagekit v" not in footer.string


def test_a_profile_can_leave_the_version_out_of_the_footer_and_the_page_still_records_it(home: Path, monkeypatch) -> None:
    at_version(monkeypatch, "1.2.3")
    repo = repo_profile(home, "version_stamp = false\n")
    page = make(profile=load_profile(repo))
    assert "<span>v1.2.3</span>" not in page.index.read_text(encoding="utf-8")
    assert stamped(page) == "1.2.3"


def test_an_unknown_version_is_not_shown(home: Path, monkeypatch) -> None:
    at_version(monkeypatch, "unknown")
    assert "<span>vunknown</span>" not in make().index.read_text(encoding="utf-8")


def test_stale_pages_are_those_built_with_another_version_or_none(home: Path, monkeypatch) -> None:
    at_version(monkeypatch, "1.0.0")
    old = make("old")
    current = make("current")
    at_version(monkeypatch, "1.1.0")
    current_page = make("current")
    unversioned = make("unversioned")
    unversioned.index.write_text(
        unversioned.index.read_text(encoding="utf-8").replace('"version": "1.1.0", ', ""), encoding="utf-8"
    )
    new_page(load_profile(), "draft", "Draft", "", "slots")
    names = {page.slug for page in stale_pages("1.1.0")}
    assert names == {"old", "unversioned"}
    assert current_page.slug not in names and current.slug == "current" and old.slug == "old"


def test_an_unknown_current_version_marks_nothing_stale(home: Path, monkeypatch) -> None:
    at_version(monkeypatch, "1.0.0")
    make()
    assert stale_pages("unknown") == []


def test_rebuild_all_rebuilds_stale_pages_and_leaves_current_ones(home: Path, monkeypatch, capsys) -> None:
    at_version(monkeypatch, "1.0.0")
    page = make("one")
    at_version(monkeypatch, "1.1.0")
    fresh = make("two")
    before = fresh.index.read_text(encoding="utf-8")
    assert main(["rebuild", "--all"]) == 0
    out = capsys.readouterr().out
    assert "default/one: rebuilt" in out and "default/two" not in out and "rebuilt 1, skipped 0, failed 0" in out
    assert stamped(page) == "1.1.0"
    assert fresh.index.read_text(encoding="utf-8") == before


def test_rebuild_all_when_nothing_is_stale(home: Path, monkeypatch, capsys) -> None:
    at_version(monkeypatch, "1.0.0")
    make()
    assert main(["rebuild", "--all"]) == 0
    assert "every built page is at version 1.0.0" in capsys.readouterr().out


def test_rebuild_all_dry_run_lists_pages_and_changes_nothing(home: Path, monkeypatch, capsys) -> None:
    at_version(monkeypatch, "1.0.0")
    page = make()
    at_version(monkeypatch, "1.1.0")
    assert main(["rebuild", "--all", "--dry-run"]) == 0
    assert "would rebuild" in capsys.readouterr().out
    assert stamped(page) == "1.0.0"


def test_rebuild_all_keeps_answers_because_the_content_is_unchanged(home: Path, monkeypatch) -> None:
    at_version(monkeypatch, "1.0.0")
    page = make(body='<input name="a.text">')
    rev = re.search(r'"rev": "(\w+)"', page.index.read_text(encoding="utf-8")).group(1)
    at_version(monkeypatch, "1.1.0")
    assert main(["rebuild", "--all"]) == 0
    assert f'"rev": "{rev}"' in page.index.read_text(encoding="utf-8")


def test_rebuild_all_skips_a_page_whose_profile_does_not_apply_here(home: Path, monkeypatch, capsys) -> None:
    at_version(monkeypatch, "1.0.0")
    repo = repo_profile(home)
    page = make("acme-page", profile=load_profile(repo))
    at_version(monkeypatch, "1.1.0")
    assert main(["rebuild", "--all"]) == 0
    out = capsys.readouterr().out
    assert "acme/acme-page: skipped, profile acme does not apply here" in out and "skipped 1" in out
    assert stamped(page) == "1.0.0"
    # From inside the repo, the profile applies.
    monkeypatch.chdir(repo)
    assert main(["rebuild", "--all"]) == 0
    assert stamped(page) == "1.1.0"


def test_rebuild_all_reports_a_page_that_no_longer_builds_and_carries_on(home: Path, monkeypatch, capsys) -> None:
    at_version(monkeypatch, "1.0.0")
    bad = make("bad")
    good = make("good")
    bad.content.write_text("<p>An id such as <uuid> reads as a tag</p>", encoding="utf-8")
    at_version(monkeypatch, "1.1.0")
    assert main(["rebuild", "--all"]) == 1
    out = capsys.readouterr().out
    assert "default/bad: failed" in out and "default/good: rebuilt" in out and "failed 1" in out
    assert stamped(good) == "1.1.0" and stamped(bad) == "1.0.0"


def test_rebuild_needs_all(home: Path) -> None:
    with pytest.raises(SystemExit):
        main(["rebuild"])


def test_profile_named_finds_the_builtin_the_personal_and_the_repo_profile(home: Path) -> None:
    assert profile_named("default").name == "default"
    assert profile_named("missing") is None
    repo = repo_profile(home)
    assert profile_named("acme") is None
    assert profile_named("acme", repo).name == "acme"
