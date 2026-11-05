from __future__ import annotations

from pathlib import Path

import pytest

from pagekit.cli import main
from pagekit.profiles import (
    ProfileError,
    init_profile,
    load_profile,
    local_profile_dir,
    overrides_dir,
    personal_dir,
    projects_file,
    repo_profiles,
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
    worktree = repo / ".worktrees" / "feature"
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
    worktree = repo / ".worktrees" / "feature"
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


def test_init_without_a_brand_keeps_the_pagekit_look(home: Path) -> None:
    directory = home / "work" / "repo" / ".pagekit" / "profile"
    init_profile(directory, "repo", "builtin")
    profile = load_profile(directory.parent.parent)
    assert profile.name == "repo"
    assert profile.config["brand"] == "pagekit" and profile.config["footer"] == "Made with pagekit"
    assert profile.brand_file("logo.svg") is not None
    # The starter theme is a commented example, so it changes nothing.
    starter = (directory / "theme.css").read_text()
    assert starter.startswith("/*") and starter.rstrip().endswith("*/") and starter.count("*/") == 1


def test_init_with_a_brand_replaces_the_pagekit_look(home: Path) -> None:
    directory = home / "work" / "repo" / ".pagekit" / "profile"
    init_profile(directory, "repo", "builtin", "Acme")
    profile = load_profile(directory.parent.parent)
    assert profile.config["brand"] == "Acme" and profile.config["footer"] == "Acme"
    assert profile.brand_file("logo.svg") is None


def test_a_profile_without_extends_ignores_the_personal_profile(home: Path) -> None:
    init_profile(personal_dir(), "personal", "builtin", "Me")
    repo = home / "work" / "repo"
    (repo / ".pagekit" / "profile").mkdir(parents=True)
    (repo / ".pagekit" / "profile" / "profile.toml").write_text('name = "repo"\n')
    profile = load_profile(repo)
    assert profile.config["brand"] == "pagekit"
    assert personal_dir().resolve() not in [d.resolve() for d in profile.dirs]


def test_init_command_defaults_the_name_and_extends_builtin(home: Path, monkeypatch) -> None:
    repo = home / "work" / "Acme Site"
    repo.mkdir(parents=True)
    monkeypatch.chdir(repo)
    assert main(["init"]) == 0
    text = (repo / ".pagekit" / "profile" / "profile.toml").read_text()
    assert 'name = "acme-site"' in text and 'extends = "builtin"' in text and "brand" not in text


def test_init_command_defaults_the_personal_name(home: Path, monkeypatch) -> None:
    monkeypatch.chdir(home)
    assert main(["init", "--personal"]) == 0
    assert load_profile(home).name == "personal"


def _repo(home: Path, name: str = "repo") -> Path:
    repo = home / "work" / name
    init_profile(repo / ".pagekit" / "profile", name, "builtin", "Acme")
    return repo


def _override(name: str, toml: str = "", **files: str) -> Path:
    folder = overrides_dir() / name
    folder.mkdir(parents=True)
    if toml:
        (folder / "profile.toml").write_text(toml)
    for filename, text in files.items():
        (folder / f"{filename}.md").write_text(text)
    return folder


def test_overrides_layer_on_top_of_a_committed_profile(home: Path) -> None:
    repo = _repo(home)
    _override("all", '[send]\ncommand = ["tool", "{file}"]\n')
    folder = _override("repo", '[save]\nroot = "~/mine"\n', SAVE="Do this.", INSTRUCTIONS="My rule.")
    profile = load_profile(repo)
    assert profile.config["send"]["command"] == ["tool", "{file}"]
    assert profile.config["save"]["root"] == "~/mine"
    assert profile.config["brand"] == "Acme"
    assert profile.read("SAVE.md") == "Do this."
    assert "My rule." in profile.instructions() and "Acme pages" in profile.instructions()
    assert profile.overrides[-1] == folder
    assert profile.nearest == (repo / ".pagekit" / "profile").resolve()


def test_overrides_apply_in_a_nested_worktree(home: Path) -> None:
    repo = _repo(home)
    _override("repo", '[save]\nroot = "~/mine"\n')
    worktree = repo / ".claude" / "worktrees" / "feature"
    init_profile(worktree / ".pagekit" / "profile", "repo", "builtin", "Acme")
    assert load_profile(worktree).config["save"]["root"] == "~/mine"


def test_overrides_for_another_profile_do_not_apply(home: Path) -> None:
    repo = _repo(home)
    _override("other", '[save]\nroot = "~/mine"\n')
    profile = load_profile(repo)
    assert "save" not in profile.config and profile.overrides == []


@pytest.mark.parametrize("toml", ['brand = "Mine"\n', 'footer = "Mine"\n', '[checks]\ncommand = ["true"]\n', 'name = "x"\n'])
def test_overrides_cannot_change_looks_or_checks(home: Path, toml: str) -> None:
    repo = _repo(home)
    _override("repo", toml)
    with pytest.raises(ProfileError, match="overrides can only set"):
        load_profile(repo)


@pytest.mark.parametrize("filename", ["theme.css", "logo.svg", "template.html", "fonts.css"])
def test_overrides_cannot_hold_look_files(home: Path, filename: str) -> None:
    repo = _repo(home)
    folder = overrides_dir() / "repo"
    folder.mkdir(parents=True)
    (folder / filename).write_text("x")
    with pytest.raises(ProfileError, match="overrides can only hold"):
        load_profile(repo)


def test_a_bad_override_does_not_stop_the_index_profile(home: Path) -> None:
    _override("all", 'brand = "Mine"\n')
    assert load_profile(override="builtin", overrides=False).config["brand"] == "pagekit"


def test_a_repo_offers_named_profiles_from_anywhere_inside(home: Path) -> None:
    repo = _repo(home)
    init_profile(repo / ".pagekit" / "profiles" / "repo-public", "repo-public", "builtin", "Acme", "Customer documents")
    below = repo / "src" / "deep"
    below.mkdir(parents=True)
    assert sorted(repo_profiles(below)) == ["repo", "repo-public"]
    assert load_profile(below).name == "repo"
    chosen = load_profile(below, override="repo-public")
    assert chosen.name == "repo-public" and chosen.config["when"] == "Customer documents"
    assert load_profile(below, override="repo").name == "repo"


def test_the_home_folders_private_profiles_are_not_choices(home: Path) -> None:
    init_profile(local_profile_dir("mine"), "mine", "builtin", "Mine")
    folder = home / "work"
    folder.mkdir()
    assert repo_profiles(folder) == {}
    assert repo_profiles(home) == {}


def test_all_is_not_a_profile_name(home: Path) -> None:
    with pytest.raises(ProfileError):
        init_profile(home / "p", "all", "builtin")


def test_profile_command_shows_when_overrides_and_other_profiles(home: Path, monkeypatch, capsys) -> None:
    repo = _repo(home)
    monkeypatch.chdir(repo)
    assert main(["init", "--also", "--name", "repo-public", "--when", 'Customer "public" docs']) == 0
    assert main(["init", "--also", "--name", "repo-bare"]) == 0
    folder = _override("repo", '[save]\nroot = "~/mine"\n')
    capsys.readouterr()
    assert main(["profile"]) == 0
    out = capsys.readouterr().out
    assert f"folder: {(repo / '.pagekit' / 'profile').resolve()}" in out
    assert f"overrides: {folder}" in out
    assert 'repo-public: Customer "public" docs' in out
    assert "repo-bare: no guidance yet" in out


def test_init_also_needs_a_name(home: Path, monkeypatch) -> None:
    repo = _repo(home)
    monkeypatch.chdir(repo)
    assert main(["init", "--also"]) == 1


def test_machine_paths_in_a_repo_profile_warn_but_private_ones_do_not(home: Path) -> None:
    repo = _repo(home)
    directory = repo / ".pagekit" / "profile"
    (directory / "profile.toml").write_text(
        'name = "repo"\nextends = "builtin"\n[save]\nroot = "~/vault"\n'
        '[checks]\ncommand = ["python3", "/home/me/lint.py"]\n'
    )
    warnings = load_profile(repo).machine_path_warnings()
    assert any("~/vault" in w for w in warnings) and any("/home/me/lint.py" in w for w in warnings)
    (directory / "profile.toml").write_text(
        'name = "repo"\nextends = "builtin"\nallowed_hosts = ["cdn.example.com"]\n'
        '[checks]\ncommand = ["python3", "{profile}/checks/lint.py"]\n'
    )
    assert load_profile(repo).machine_path_warnings() == []
    init_profile(local_profile_dir("mine"), "mine", "builtin", "Mine")
    (local_profile_dir("mine") / "SAVE.md").write_text("Copy to ~/vault.")
    assert load_profile(repo, override=str(local_profile_dir("mine"))).machine_path_warnings() == []
    _override("repo", '[save]\nroot = "~/vault"\n')
    (directory / "profile.toml").write_text('name = "repo"\nextends = "builtin"\n')
    assert load_profile(repo).machine_path_warnings() == []

