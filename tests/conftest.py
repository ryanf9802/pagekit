from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    if os.name == "nt":
        skip = pytest.mark.skip(reason="uses a POSIX shell script or symlink")
        for item in items:
            if item.get_closest_marker("posix"):
                item.add_marker(skip)


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated home, pages root, and working directory for each test."""
    root = tmp_path / "home"
    root.mkdir()
    # Windows finds the home folder through USERPROFILE, not HOME.
    monkeypatch.setenv("HOME", str(root))
    monkeypatch.setenv("USERPROFILE", str(root))
    monkeypatch.delenv("PAGEKIT_HOME", raising=False)
    monkeypatch.delenv("PAGEKIT_PROFILE", raising=False)
    monkeypatch.delenv("PAGEKIT_TTL_DAYS", raising=False)
    # Where Windows installs browsers, so a test decides whether one exists.
    for folder in ("ProgramFiles", "ProgramFiles(x86)", "LocalAppData"):
        monkeypatch.delenv(folder, raising=False)
    monkeypatch.chdir(root)
    return root
