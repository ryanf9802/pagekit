from __future__ import annotations

from pathlib import Path

import pytest

from pagekit.profiles import (
    ProfileError,
    init_profile,
    load_profile,
    local_profile_dir,
    personal_dir,
    projects_file,
    register_project,
)


def test_no_profile_falls_back_to_builtin(home: Path) -> None:
    profile = load_profile()
    assert profile.name == "default"
    assert "--pk-accent" in profile.tokens()


def test_personal_profile_applies_anywhere_under_home(home: Path) -> None:
    init_profile(personal_dir(), "personal", "builtin", "Me")
    project = home / "a" / "b"
    project.mkdir(parents=True)
    assert load_profile(project).name == "personal"


def test_project_profile_wins_and_extends_personal(home: Path) -> None:
    init_profile(personal_dir(), "personal", "builtin", "Me")
    (personal_dir() / "theme.css").write_text(":root { --pk-from-personal: 1; }")
    repo = home / "repo"
    init_profile(repo / ".pagekit" / "profile", "acme", "personal", "Acme")
    worktree = repo / ".claude" / "worktrees" / "feature"
    worktree.mkdir(parents=True)

    profile = load_profile(worktree)

    assert profile.name == "acme"
    assert profile.config["brand"] == "Acme"
    assert "--pk-from-personal" in profile.tokens()
    assert profile.config["ascii_only"] is True  # inherited from the built-in
    assert load_profile(home).name == "personal"


def test_local_project_mapping_adds_nothing_to_the_project(home: Path) -> None:
    init_profile(personal_dir(), "personal", "builtin", "Me")
    repo = home / "repo"
    worktree = repo / ".claude" / "worktrees" / "feature"
    worktree.mkdir(parents=True)
    init_profile(local_profile_dir("acme"), "acme", "personal", "Acme")
    register_project(repo, local_profile_dir("acme"))
    register_project(repo, local_profile_dir("acme"))

    assert load_profile(repo).name == "acme"
    assert load_profile(worktree).name == "acme"
    assert load_profile(home).name == "personal"
    assert not (repo / ".pagekit").exists()
    assert projects_file().read_text().count("[[project]]") == 1


def test_committed_repo_profile_wins_over_a_mapping_at_the_same_folder(home: Path) -> None:
    repo = home / "repo"
    init_profile(repo / ".pagekit" / "profile", "committed", "builtin", "A")
    init_profile(local_profile_dir("mine"), "mine", "builtin", "B")
    register_project(repo, local_profile_dir("mine"))
    assert load_profile(repo).name == "committed"


def test_mapping_to_a_missing_profile_is_an_error(home: Path) -> None:
    repo = home / "repo"
    repo.mkdir()
    register_project(repo, home / "gone")
    with pytest.raises(ProfileError, match="no profile.toml"):
        load_profile(repo)


def test_shared_profile_works_for_someone_with_no_personal_profile(home: Path) -> None:
    repo = home / "repo"
    init_profile(repo / ".pagekit" / "profile", "acme", "personal", "Acme")
    assert load_profile(repo).name == "acme"


def test_nearest_template_wins_and_theme_concatenates(home: Path) -> None:
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "template.html").write_text("custom")
    profile = load_profile(repo)
    assert profile.read("template.html") == "custom"
    assert profile.theme().index("--pk-bg") < profile.theme().rindex("--pk-accent")


def test_explicit_override_beats_the_working_directory(home: Path) -> None:
    init_profile(personal_dir(), "personal", "builtin", "Me")
    repo = home / "repo"
    init_profile(repo / ".pagekit" / "profile", "acme", "personal", "Acme")
    assert load_profile(repo, override="personal").name == "personal"


def test_extends_loop_is_an_error(home: Path) -> None:
    first, second = home / "first", home / "second"
    init_profile(first, "first", str(second), "A")
    init_profile(second, "second", str(first), "B")
    with pytest.raises(ProfileError, match="loop"):
        load_profile(home, override=str(first))


@pytest.mark.parametrize("name", ["saved", "Has Caps", "../up", ""])
def test_bad_names_are_rejected(home: Path, name: str) -> None:
    with pytest.raises(ProfileError):
        init_profile(home / "p", name, "builtin", "X")


def test_init_never_overwrites(home: Path) -> None:
    directory = home / "p"
    init_profile(directory, "one", "builtin", "One")
    (directory / "theme.css").write_text("mine")
    assert init_profile(directory, "two", "builtin", "Two") == []
    assert (directory / "theme.css").read_text() == "mine"
