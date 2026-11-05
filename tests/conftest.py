from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """An isolated home, pages root, and working directory for each test."""
    root = tmp_path / "home"
    root.mkdir()
    monkeypatch.setenv("HOME", str(root))
    monkeypatch.delenv("PAGEKIT_HOME", raising=False)
    monkeypatch.delenv("PAGEKIT_PROFILE", raising=False)
    monkeypatch.delenv("PAGEKIT_TTL_DAYS", raising=False)
    monkeypatch.chdir(root)
    return root
