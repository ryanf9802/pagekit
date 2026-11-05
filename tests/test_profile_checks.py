from __future__ import annotations

import stat
from pathlib import Path

import pytest

from pagekit.cli import main
from pagekit.pages import PageError, check_page, load_page, new_page, save_page
from pagekit.profiles import init_profile, load_profile

PASSING = "#!/bin/sh\necho \"$1 $2 $(pwd)\" > \"$CHECK_LOG\"\nexit 0\n"
FAILING = "#!/bin/sh\necho 'internal wording: TW-1'\necho 'unmarked field' >&2\nexit 3\n"


@pytest.fixture
def repo(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    project = home / "repo"
    init_profile(project / ".pagekit" / "profile", "acme", "builtin", "Acme")
    monkeypatch.chdir(project)
    monkeypatch.setenv("CHECK_LOG", str(tmp_path / "log"))
    return project


def set_check(repo: Path, tmp_path: Path, body: str | None, command: str | None = None) -> None:
    lines = 'name = "acme"\nextends = "builtin"\n'
    if body is not None:
        script = tmp_path / "check.sh"
        script.write_text(body)
        script.chmod(script.stat().st_mode | stat.S_IEXEC)
        command = f'["{script}"]'
    if command:
        lines += f"[checks]\ncommand = {command}\n"
    (repo / ".pagekit" / "profile" / "profile.toml").write_text(lines)


def make_page(body: str = "<p>One</p>"):
    page, _ = new_page(load_profile(), "demo", "Demo", None, "slots")
    page.content.write_text(body)
    return page


@pytest.mark.posix
def test_passing_check_gets_the_built_page_and_can_read_its_folder(repo: Path, tmp_path: Path) -> None:
    set_check(repo, tmp_path, PASSING)
    page = make_page()
    (page.assets / "fields.json").write_text("{}")
    page.content.write_text('<a href="assets/fields.json">Fields</a>')
    assert main(["build", "demo"]) == 0
    logged = (tmp_path / "log").read_text().split()
    assert logged == [str(page.index), str(page.dir), str(page.dir.resolve())]


@pytest.mark.posix
def test_failing_check_fails_the_build_and_shows_its_output(repo: Path, tmp_path: Path, capsys) -> None:
    set_check(repo, tmp_path, FAILING)
    make_page()
    assert main(["build", "demo"]) == 1
    output = capsys.readouterr().out
    assert "profile check: internal wording: TW-1" in output
    assert "profile check: unmarked field" in output
    assert "not updated" in output


@pytest.mark.posix
def test_a_refused_build_keeps_the_last_good_page(repo: Path, tmp_path: Path) -> None:
    set_check(repo, tmp_path, PASSING)
    page = make_page("<p>Good</p>")
    assert main(["build", "demo"]) == 0
    set_check(repo, tmp_path, FAILING)
    page.content.write_text("<p>Bad</p>")
    assert main(["build", "demo"]) == 1
    document = page.index.read_text()
    assert "<p>Good</p>" in document and "<p>Bad</p>" not in document


@pytest.mark.posix
def test_a_new_page_that_is_refused_has_no_index(repo: Path, tmp_path: Path) -> None:
    set_check(repo, tmp_path, FAILING)
    page = make_page()
    assert main(["build", "demo"]) == 1
    assert not page.index.exists()


@pytest.mark.posix
def test_check_and_save_also_run_it(repo: Path, tmp_path: Path) -> None:
    set_check(repo, tmp_path, PASSING)
    make_page()
    assert main(["build", "demo"]) == 0
    set_check(repo, tmp_path, FAILING)
    assert main(["check", "demo"]) == 1
    profile = load_profile()
    page = load_page(profile, "demo")
    assert check_page(profile, page).hook_failed
    with pytest.raises(PageError, match="internal wording"):
        save_page(profile, page)


@pytest.mark.parametrize(
    ("command", "message"),
    [('"not a list"', "must be a list"), ('["/no/such/command"]', "could not run")],
)
def test_a_broken_check_fails_rather_than_passing_silently(repo: Path, tmp_path: Path, capsys, command: str, message: str) -> None:
    set_check(repo, tmp_path, None, command)
    make_page()
    assert main(["build", "demo"]) == 1
    assert message in capsys.readouterr().out


def test_no_check_configured_changes_nothing(repo: Path, tmp_path: Path) -> None:
    set_check(repo, tmp_path, None)
    make_page()
    assert main(["build", "demo"]) == 0
