"""The update flow, against a real origin and clone."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

import pagekit.update as update_module
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


@pytest.fixture
def repos(tmp_path: Path, monkeypatch) -> tuple[Path, Path]:
    origin = tmp_path / "origin.git"
    author = tmp_path / "author"
    clone = tmp_path / "clone"
    git(tmp_path, "init", "-q", "--bare", "-b", "main", str(origin))
    git(tmp_path, "clone", "-q", str(origin), str(author))
    git(author, "switch", "-q", "-c", "main")
    commit(author, "pyproject.toml", "[project]\n", "first")
    git(author, "push", "-q", "origin", "main")
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
    before = git(clone, "rev-parse", "HEAD")
    assert main(["update", "--check"]) == 0
    assert "add a feature" in capsys.readouterr().out
    assert git(clone, "rev-parse", "HEAD") == before


def test_update_pulls_and_names_changes_and_new_skills(repos, capsys) -> None:
    author, clone = repos
    commit(author, "src/pagekit/skills/new-one/SKILL.md", "x", "add a skill")
    git(author, "push", "-q", "origin", "main")
    assert main(["update"]) == 0
    out = capsys.readouterr().out
    assert "add a skill" in out and f"link it for your agent: {clone / 'src/pagekit/skills/new-one'}" in out
    assert "reinstalled" not in out
    assert (clone / "src/pagekit/skills/new-one/SKILL.md").is_file()


def test_changed_dependencies_reinstall(repos, monkeypatch) -> None:
    author, clone = repos
    commit(author, "pyproject.toml", "[project]\nname = 'x'\n", "add a dependency")
    git(author, "push", "-q", "origin", "main")
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
    (clone / "pyproject.toml").write_text("mine")
    before = git(clone, "rev-parse", "HEAD")
    with pytest.raises(UpdateError, match="uncommitted"):
        update()
    assert (clone / "pyproject.toml").read_text() == "mine" and git(clone, "rev-parse", "HEAD") == before


def test_untracked_files_such_as_agent_worktrees_do_not_stop_the_update(repos) -> None:
    author, clone = repos
    commit(author, "a.txt", "x", "add a feature")
    git(author, "push", "-q", "origin", "main")
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
    commit(clone, "b.txt", "y", "mine")
    before = git(clone, "rev-parse", "HEAD")
    with pytest.raises(UpdateError, match="pull failed"):
        update()
    assert git(clone, "rev-parse", "HEAD") == before


def test_server_restart_uses_the_service_or_says_so(repos, monkeypatch, capsys) -> None:
    author, _ = repos
    commit(author, "a.txt", "x", "change")
    git(author, "push", "-q", "origin", "main")
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
