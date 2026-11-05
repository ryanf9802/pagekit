"""Update pagekit from its clone: move to the newest release, refresh the install if needed, and restart the server."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .pages import server_running

BRANCH = "main"
# Every release is a tag like v0.1.7, made by CI once a merge to main has passed.
RELEASE_TAGS = "v[0-9]*"
SERVICE = "pagekit.service"
_GIT_TIMEOUT_SECONDS = 60


class UpdateError(Exception):
    pass


@dataclass
class UpdateResult:
    # The release moved to, or "" when following main.
    version: str = ""
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


def _fetch_target(clone: Path, follow_main: bool) -> tuple[str, str]:
    """Fetches, and names what to move to: the newest release, or origin/main. Returns (ref, release name or "")."""
    _git(clone, "fetch", "--tags", "origin", BRANCH)
    if follow_main:
        return f"origin/{BRANCH}", ""
    releases = _lines(_git(clone, "tag", "--list", RELEASE_TAGS, "--sort=-version:refname"))
    if not releases:
        raise UpdateError("no release has been published yet: run pagekit update --main to follow main instead")
    return releases[0], releases[0]


def pending_commits(root: Path | None = None, follow_main: bool = False) -> list[str]:
    """Fetches, and lists what an update would bring in. Changes nothing else."""
    clone = _require_clone(root or clone_dir())
    target, _ = _fetch_target(clone, follow_main)
    return _lines(_git(clone, "log", "--format=%s", f"HEAD..{target}"))


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


def update(root: Path | None = None, follow_main: bool = False) -> UpdateResult:
    clone = _require_clone(root or clone_dir())
    # Untracked files are left alone by a pull, and agent worktrees often sit inside a clone.
    if _git(clone, "status", "--porcelain", "--untracked-files=no"):
        raise UpdateError(f"{clone} has uncommitted changes: commit or discard them, then update again")
    branch = _git(clone, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != BRANCH:
        raise UpdateError(f"{clone} is on {branch}: switch it to {BRANCH}, then update again")
    target, version = _fetch_target(clone, follow_main)
    before = _git(clone, "rev-parse", "HEAD")
    # A clone already ahead of the release stays where it is, so an update never moves backwards.
    _git(clone, "merge", "--ff-only", target)
    after = _git(clone, "rev-parse", "HEAD")
    if before == after:
        return UpdateResult()
    result = UpdateResult(version=version, commits=_lines(_git(clone, "log", "--format=%s", f"{before}..{after}")))
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
