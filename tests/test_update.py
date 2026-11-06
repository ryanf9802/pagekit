"""The update flow, against a real origin and clone."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

import pagekit.update as update_module
import pagekit.version as version_module
from pagekit.cli import main
from pagekit.update import UpdateError, clone_dir, pending_commits, update


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
        cwd=cwd, check=True, capture_output=True, text=True,
    ).stdout.strip()


def commit(repo: Path, relative: str, text: str, message: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


def release(repo: Path, tag: str) -> None:
    git(repo, "tag", tag)
    git(repo, "push", "-q", "origin", tag)


@pytest.fixture
def repos(tmp_path: Path, monkeypatch, home: Path) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    author = tmp_path / "author"
    clone = tmp_path / "clone"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", "-q", str(origin), str(author))
    git(author, "switch", "-q", "-c", "main")
    commit(author, "pyproject.toml", "[project]\n", "first")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.0")
    git(tmp_path, "clone", "-q", str(origin), str(clone))
    monkeypatch.setattr(update_module, "clone_dir", lambda: clone)
    monkeypatch.setattr(update_module, "server_running", lambda: False)
    return author, clone


def test_up_to_date(repos, capsys) -> None:
    assert main(["update"]) == 0
    assert "up to date" in capsys.readouterr().out


def test_check_lists_changes_without_pulling(repos, capsys) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "add a feature")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    before = git(clone, "rev-parse", "HEAD")
    assert main(["update", "--check"]) == 0
    assert "add a feature" in capsys.readouterr().out
    assert git(clone, "rev-parse", "HEAD") == before


def test_update_pulls_and_names_changes_and_new_skills(repos, capsys) -> None:
    author, clone = repos
    commit(author, "src/pagekit/skills/new-one/SKILL.md", "x", "add a skill")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    assert main(["update"]) == 0
    out = capsys.readouterr().out
    assert "updated pagekit 0.1.0 -> 0.1.1 with 1 change(s)" in out and "add a skill" in out and f"link it for your agent: {clone / 'src/pagekit/skills/new-one'}" in out
    assert "reinstalled" not in out
    assert (clone / "src/pagekit/skills/new-one/SKILL.md").is_file()


def version_line(capsys) -> str:
    with pytest.raises(SystemExit) as stop:
        main(["--version"])
    assert stop.value.code == 0
    return capsys.readouterr().out.strip()


def test_version_at_a_release_is_the_release(repos, capsys) -> None:
    assert version_line(capsys) == "pagekit 0.1.0"


def test_version_past_a_release_counts_the_commits_and_names_the_commit(repos, capsys) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "one")
    commit(author, "b.txt", "x", "two")
    git(author, "push", "-q", "origin", "main")
    assert main(["update", "--main"]) == 0
    capsys.readouterr()
    short = git(clone, "rev-parse", "--short", "HEAD")
    line = version_line(capsys)
    assert line == f"pagekit 0.1.0+2.g{short}"
    # A local version label, so a tool can order it among the releases.
    assert re.fullmatch(r"pagekit \d+(\.\d+)*\+[0-9a-z]+(\.[0-9a-z]+)*", line)


def test_version_marks_uncommitted_changes(repos, capsys) -> None:
    _, clone = repos
    (clone / "pyproject.toml").write_text("[project]\nname = 'changed'\n")
    assert version_line(capsys).endswith(".dirty")


def test_version_is_read_at_run_time_so_an_update_is_reflected_at_once(repos, capsys) -> None:
    author, _ = repos
    commit(author, "a.txt", "x", "add a feature")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    assert version_line(capsys) == "pagekit 0.1.0"
    assert main(["update"]) == 0
    capsys.readouterr()
    assert version_line(capsys) == "pagekit 0.1.1"


def test_a_plain_install_reports_its_package_version(repos, monkeypatch, capsys) -> None:
    monkeypatch.setattr(update_module, "clone_dir", lambda: None)
    monkeypatch.setattr(version_module.importlib.metadata, "version", lambda name: "9.9.9")
    assert version_line(capsys) == "pagekit 9.9.9"


def test_a_clone_git_cannot_read_falls_back_to_the_package_version(repos, monkeypatch, capsys) -> None:
    def broken(*args, **kwargs):
        raise UpdateError("git describe failed")

    monkeypatch.setattr(update_module, "version_of", broken)
    monkeypatch.setattr(version_module.importlib.metadata, "version", lambda name: "9.9.9")
    assert version_line(capsys) == "pagekit 9.9.9"


def test_the_package_version_is_the_installed_version_and_not_a_stored_number() -> None:
    import pagekit

    assert pagekit.__version__ == str(update_module.installed_version())
    with pytest.raises(AttributeError):
        pagekit.not_a_thing  # noqa: B018


def test_update_names_both_versions_when_following_main(repos, capsys) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "one")
    git(author, "push", "-q", "origin", "main")
    assert main(["update", "--main"]) == 0
    short = git(clone, "rev-parse", "--short", "HEAD")
    assert f"updated pagekit 0.1.0 -> 0.1.0+1.g{short} with 1 change(s)" in capsys.readouterr().out


def test_up_to_date_names_the_version(repos, capsys) -> None:
    assert main(["update"]) == 0
    assert "pagekit 0.1.0 is up to date" in capsys.readouterr().out


def test_check_names_the_version_an_update_would_move_to(repos, capsys) -> None:
    author, _ = repos
    commit(author, "a.txt", "x", "add a feature")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    assert main(["update", "--check"]) == 0
    assert "1 update(s) available (0.1.0 -> 0.1.1): run pagekit update" in capsys.readouterr().out


def test_check_when_following_main_names_how_far_past_the_release_it_would_move(repos, capsys) -> None:
    author, _ = repos
    commit(author, "a.txt", "x", "one")
    commit(author, "b.txt", "x", "two")
    git(author, "push", "-q", "origin", "main")
    short = git(author, "rev-parse", "--short", "HEAD")
    assert main(["update", "--check", "--main"]) == 0
    assert f"2 update(s) available (0.1.0 -> 0.1.0+2.g{short}): run pagekit update" in capsys.readouterr().out


def test_changed_dependencies_reinstall(repos, monkeypatch) -> None:
    author, clone = repos
    commit(author, "pyproject.toml", "[project]\nname = 'x'\n", "add a dependency")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    calls = []
    real_run = subprocess.run

    def fake_run(command, *args, **kwargs):
        if command[0] == "fake-uv":
            calls.append(command)
            return subprocess.CompletedProcess(command, 0, "", "")
        return real_run(command, *args, **kwargs)

    monkeypatch.setattr(update_module.shutil, "which", lambda name: "fake-uv" if name == "uv" else None)
    monkeypatch.setattr(update_module.subprocess, "run", fake_run)
    assert update().reinstalled
    assert calls == [["fake-uv", "tool", "install", "--editable", str(clone), "--force"]]


def test_uncommitted_changes_stop_the_update_and_stay(repos) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "add a feature")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    (clone / "pyproject.toml").write_text("mine")
    before = git(clone, "rev-parse", "HEAD")
    with pytest.raises(UpdateError, match="uncommitted"):
        update()
    assert (clone / "pyproject.toml").read_text() == "mine" and git(clone, "rev-parse", "HEAD") == before


def test_untracked_files_such_as_agent_worktrees_do_not_stop_the_update(repos) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "add a feature")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    (clone / ".claude" / "worktrees").mkdir(parents=True)
    (clone / ".claude" / "worktrees" / "note.txt").write_text("keep")
    assert update().commits == ["add a feature"]
    assert (clone / ".claude" / "worktrees" / "note.txt").read_text() == "keep"


def test_another_branch_stops_the_update(repos, capsys) -> None:
    _, clone = repos
    git(clone, "switch", "-q", "-c", "work")
    assert main(["update"]) == 1
    assert "is on work" in capsys.readouterr().err


def test_diverged_clone_is_not_overwritten(repos) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "theirs")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    commit(clone, "b.txt", "y", "mine")
    before = git(clone, "rev-parse", "HEAD")
    with pytest.raises(UpdateError, match="merge failed"):
        update()
    assert git(clone, "rev-parse", "HEAD") == before


def test_server_restart_uses_the_service_or_says_so(repos, monkeypatch, capsys) -> None:
    author, _ = repos
    commit(author, "a.txt", "x", "change")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    monkeypatch.setattr(update_module, "server_running", lambda: True)
    monkeypatch.setattr(update_module.shutil, "which", lambda name: None)
    assert main(["update"]) == 0
    assert "still running the old version" in capsys.readouterr().out


def test_an_install_with_no_clone_says_so(repos, monkeypatch) -> None:
    monkeypatch.setattr(update_module, "clone_dir", lambda: None)
    with pytest.raises(UpdateError, match="no clone"):
        pending_commits()


def test_this_install_finds_its_clone() -> None:
    assert clone_dir() == Path(update_module.__file__).resolve().parents[2]


def test_unreleased_commits_on_main_are_not_installed(repos, capsys) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "not released yet")
    git(author, "push", "-q", "origin", "main")
    before = git(clone, "rev-parse", "HEAD")
    assert main(["update", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out
    assert main(["update"]) == 0
    assert "up to date" in capsys.readouterr().out
    assert git(clone, "rev-parse", "HEAD") == before


def test_main_flag_follows_main(repos, capsys) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "not released yet")
    git(author, "push", "-q", "origin", "main")
    assert main(["update", "--check", "--main"]) == 0
    assert "not released yet" in capsys.readouterr().out
    assert update(follow="main").commits == ["not released yet"]
    assert (clone / "a.txt").is_file()


def test_newest_release_wins_by_version_not_by_name(repos) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "nine")
    release(author, "v0.1.9")
    commit(author, "b.txt", "y", "ten")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.10")
    assert update().commits == ["ten", "nine"]
    assert git(clone, "rev-parse", "HEAD") == git(author, "rev-parse", "v0.1.10")


def test_a_clone_ahead_of_the_release_is_not_moved_back(repos, capsys) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "not released yet")
    git(author, "push", "-q", "origin", "main")
    update(follow="main")
    before = git(clone, "rev-parse", "HEAD")
    assert main(["update"]) == 0
    assert "up to date" in capsys.readouterr().out
    assert git(clone, "rev-parse", "HEAD") == before


def unreleased_commit(author: Path) -> None:
    commit(author, "a.txt", "x", "not released yet")
    git(author, "push", "-q", "origin", "main")


def set_follow(home: Path, text: str) -> Path:
    path = home / ".pagekit" / "update.toml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_the_settings_file_makes_a_machine_follow_main(repos, home, capsys) -> None:
    author, clone = repos
    unreleased_commit(author)
    path = set_follow(home, 'follow = "main"\n')
    assert main(["update"]) == 0
    out = capsys.readouterr().out
    assert f"following main, as set in {path}" in out and "not released yet" in out
    assert (clone / "a.txt").is_file()


def test_flags_beat_the_settings_file(repos, home, capsys) -> None:
    author, clone = repos
    unreleased_commit(author)
    set_follow(home, 'follow = "main"\n')
    assert main(["update", "--releases", "--check"]) == 0
    out = capsys.readouterr().out
    assert "following main" not in out and "up to date" in out
    set_follow(home, 'follow = "releases"\n')
    assert main(["update", "--main", "--check"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("following main\n") and "not released yet" in out
    assert not (clone / "a.txt").exists()


def test_a_file_without_follow_means_releases(repos, home, capsys) -> None:
    author, _ = repos
    unreleased_commit(author)
    set_follow(home, "")
    assert main(["update", "--check"]) == 0
    assert "up to date" in capsys.readouterr().out


@pytest.mark.parametrize("text", ['follow = "latest"\n', "follow = 3\n", "follow = \n"])
def test_a_bad_settings_file_is_an_error_that_names_it(repos, home, text, capsys) -> None:
    path = set_follow(home, text)
    before = git(repos[1], "rev-parse", "HEAD")
    assert main(["update"]) == 1
    assert str(path) in capsys.readouterr().err
    assert git(repos[1], "rev-parse", "HEAD") == before


def test_both_flags_together_are_refused(repos, capsys) -> None:
    with pytest.raises(SystemExit):
        main(["update", "--main", "--releases"])
    assert "not allowed with" in capsys.readouterr().err


def test_no_release_yet_points_to_the_main_flag(repos, tmp_path, monkeypatch, capsys) -> None:
    git(tmp_path / "origin.git", "tag", "-d", "v0.1.0")
    fresh = tmp_path / "fresh"
    git(tmp_path, "clone", "-q", str(tmp_path / "origin.git"), str(fresh))
    monkeypatch.setattr(update_module, "clone_dir", lambda: fresh)
    assert main(["update"]) == 1
    err = capsys.readouterr().err
    assert "no release has been published yet" in err and "--main" in err


def test_update_says_how_many_pages_were_built_with_an_older_version(repos, monkeypatch, capsys) -> None:
    author, _ = repos
    commit(author, "src/pagekit/feature.txt", "x", "add a feature")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    monkeypatch.setattr("pagekit.cli.stale_pages", lambda current: ["one", "two"])
    assert main(["update"]) == 0
    assert "2 page(s) were built with an older version and keep their old look: run pagekit rebuild --all" in capsys.readouterr().out


def test_update_is_quiet_about_pages_when_none_are_stale(repos, monkeypatch, capsys) -> None:
    author, _ = repos
    commit(author, "src/pagekit/feature.txt", "x", "add a feature")
    git(author, "push", "-q", "origin", "main")
    release(author, "v0.1.1")
    monkeypatch.setattr("pagekit.cli.stale_pages", lambda current: [])
    assert main(["update"]) == 0
    assert "rebuild --all" not in capsys.readouterr().out
