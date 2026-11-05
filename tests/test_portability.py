"""Windows defaults differ from Linux in ways that tests on Linux cannot see, so these guard them directly."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

import pagekit
from pagekit.browser import find_chrome
from pagekit.cli import main
from pagekit.profiles import init_profile, load_profile, register_project

SOURCE = Path(pagekit.__file__).parent
TEXT_CALL_RE = re.compile(r"\.(?:read_text|write_text)\(|\btext=True\b")


@pytest.mark.parametrize("path", sorted(SOURCE.glob("*.py")), ids=lambda p: p.name)
def test_every_text_call_names_its_encoding(path: Path) -> None:
    """Windows defaults to a legacy code page, but TOML and browsers expect UTF-8."""
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if TEXT_CALL_RE.search(line):
            assert 'encoding="utf-8"' in line, f"{path.name}:{number}: {line.strip()}"


def test_a_project_path_with_backslashes_is_written_as_valid_toml(home: Path) -> None:
    project = home / "back\\slash"
    project.mkdir(parents=True)
    directory = home / "profiles\\acme"
    init_profile(directory, "acme", "builtin", "Acme")
    register_project(project, directory)
    assert load_profile(project).name == "acme"


def test_a_brand_with_accents_round_trips(home: Path) -> None:
    directory = home / "profile"
    init_profile(directory, "acme", "builtin", "Caf\u00e9")
    assert tomllib.loads((directory / "profile.toml").read_bytes().decode("utf-8"))["brand"] == "Caf\u00e9"


@pytest.mark.parametrize(
    "relative", ["Google/Chrome/Application/chrome.exe", "Microsoft/Edge/Application/msedge.exe"]
)
def test_finds_browsers_where_windows_installs_them(
    home: Path, monkeypatch: pytest.MonkeyPatch, relative: str
) -> None:
    monkeypatch.delenv("PAGEKIT_CHROME", raising=False)
    monkeypatch.setattr("pagekit.browser.shutil.which", lambda name: None)
    monkeypatch.setattr("pagekit.browser._MAC_CHROME", str(home / "none"))
    target = home / "Program Files" / relative
    target.parent.mkdir(parents=True)
    target.touch()
    monkeypatch.setenv("ProgramFiles", str(home / "Program Files"))
    assert find_chrome() == str(target)


def test_install_service_explains_itself_without_systemd(
    home: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr("pagekit.cli.shutil.which", lambda name: None)
    assert main(["install-service"]) == 1
    message = capsys.readouterr().err
    assert "systemd" in message and "pagekit serve" in message
    assert not (home / ".config" / "systemd").exists()
