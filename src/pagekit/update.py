"""Update pagekit from its clone: pull, refresh the install if needed, and restart the server."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .pages import server_running

BRANCH = "main"
SERVICE = "pagekit.service"
_GIT_TIMEOUT_SECONDS = 60


class UpdateError(Exception):
    pass


@dataclass
class UpdateResult:
    commits: list[str] = field(default_factory=list)
    new_skills: list[Path] = field(default_factory=list)
    reinstalled: bool = False
    # What the running server did: "", "restarted", or "restart by hand".
    server: str = ""


def clone_dir() -> Path | None:
    """The clone this editable install runs from. A plain install has none."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / ".git").exists() and (root / "pyproject.toml").is_file() else None


def _git(root: Path, *args: str) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), *args],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=_GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"git {args[0]} could not run: {exc}") from exc
    if result.returncode != 0:
        raise UpdateError(f"git {args[0]} failed: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def _lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.strip()]


def _require_clone(root: Path | None) -> Path:
    if root is None:
        raise UpdateError("this install has no clone to update from: see docs/getting-started.md to install from one")
    return root


def pending_commits(root: Path | None = None) -> list[str]:
    """Fetches, and lists what an update would bring in. Changes nothing else."""
    clone = _require_clone(root or clone_dir())
    _git(clone, "fetch", "origin", BRANCH)
    return _lines(_git(clone, "log", "--format=%s", f"HEAD..origin/{BRANCH}"))


def _restart_server() -> str:
    if not server_running():
        return ""
    systemctl = shutil.which("systemctl")
    if systemctl:
        active = subprocess.run([systemctl, "--user", "is-active", SERVICE], capture_output=True, stdin=subprocess.DEVNULL)
        if active.returncode == 0:
            restarted = subprocess.run([systemctl, "--user", "restart", SERVICE], capture_output=True, stdin=subprocess.DEVNULL)
            if restarted.returncode == 0:
                return "restarted"
    return "restart by hand"


def update(root: Path | None = None) -> UpdateResult:
    clone = _require_clone(root or clone_dir())
    if _git(clone, "status", "--porcelain"):
        raise UpdateError(f"{clone} has uncommitted changes: commit or discard them, then update again")
    branch = _git(clone, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != BRANCH:
        raise UpdateError(f"{clone} is on {branch}: switch it to {BRANCH}, then update again")
    before = _git(clone, "rev-parse", "HEAD")
    _git(clone, "pull", "--ff-only", "origin", BRANCH)
    after = _git(clone, "rev-parse", "HEAD")
    if before == after:
        return UpdateResult()
    result = UpdateResult(commits=_lines(_git(clone, "log", "--format=%s", f"{before}..{after}")))
    added = _git(clone, "diff", "--name-only", "--diff-filter=A", before, after, "--", "src/pagekit/skills")
    result.new_skills = [clone / Path(name).parent for name in _lines(added) if Path(name).name == "SKILL.md"]
    # An editable install follows the clone, so only new dependencies need a reinstall.
    if _git(clone, "diff", "--name-only", before, after, "--", "pyproject.toml"):
        uv = shutil.which("uv")
        if not uv:
            raise UpdateError(f"pyproject.toml changed and uv is not on PATH: run uv tool install --editable {clone} --force")
        done = subprocess.run(
            [uv, "tool", "install", "--editable", str(clone), "--force"],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
        )
        if done.returncode != 0:
            raise UpdateError(f"reinstall failed: {done.stderr.strip()}")
        result.reinstalled = True
    result.server = _restart_server()
    return result
