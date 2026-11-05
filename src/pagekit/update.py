"""Update pagekit from its clone: move to the newest release, refresh the install if needed, and restart the server."""

from __future__ import annotations

import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from .pages import server_running
from .version import Version, from_metadata, parse_describe

BRANCH = "main"
# Every release is a tag like v0.1.7, made by CI once a merge to main has passed.
RELEASE_TAGS = "v[0-9]*"
SERVICE = "pagekit.service"
_GIT_TIMEOUT_SECONDS = 60


class UpdateError(Exception):
    pass


@dataclass
class UpdateResult:
    # The version the clone was at, and the one it is at now, as printed by --version.
    before: str = ""
    after: str = ""
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


def update_settings_file() -> Path:
    return Path.home() / ".pagekit" / "update.toml"


def resolve_follow(flag: str | None = None) -> tuple[str, str]:
    """What to follow, "releases" or "main", and where that came from: "flag", "file", or "default"."""
    if flag:
        return flag, "flag"
    path = update_settings_file()
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return "releases", "default"
    except OSError as exc:
        raise UpdateError(f"{path} could not be read: {exc}") from exc
    try:
        value = tomllib.loads(text).get("follow")
    except tomllib.TOMLDecodeError as exc:
        raise UpdateError(f"{path} is not valid TOML: {exc}") from exc
    if value is None:
        return "releases", "default"
    if value not in ("releases", "main"):
        raise UpdateError(f'{path}: follow must be "releases" or "main", not {value!r}')
    return value, "file"


def _fetch_target(clone: Path, follow: str | None) -> str:
    """Fetches, and names what to move to: the newest release, or origin/main."""
    _git(clone, "fetch", "--tags", "origin", BRANCH)
    if resolve_follow(follow)[0] == "main":
        return f"origin/{BRANCH}"
    releases = _lines(_git(clone, "tag", "--list", RELEASE_TAGS, "--sort=-version:refname"))
    if not releases:
        raise UpdateError("no release has been published yet: run pagekit update --main to follow main instead")
    return releases[0]


def version_of(clone: Path, ref: str | None = None) -> Version:
    """The version at a commit, or of the clone's working tree (which can be dirty) when no commit is given."""
    describe = ["describe", "--tags", "--long", "--match", RELEASE_TAGS, "--always"]
    # git refuses --dirty together with a commit, and a commit has no working tree to be dirty.
    return parse_describe(_git(clone, *describe, ref or "--dirty"))


def installed_version() -> Version:
    """The version this install is at: read from its clone, so an update is reflected at once. A plain install has none."""
    clone = clone_dir()
    if clone is not None:
        try:
            return version_of(clone)
        except UpdateError:
            pass  # No git, or a clone git cannot read: the package's own version is the best left.
    return from_metadata()


@dataclass
class Pending:
    commits: list[str]
    # The version the clone is at, and the one an update would move it to.
    current: Version
    target: Version


def check(root: Path | None = None, follow: str | None = None) -> Pending:
    """Fetches, and says what an update would bring in. Changes nothing else."""
    clone = _require_clone(root or clone_dir())
    target = _fetch_target(clone, follow)
    commits = _lines(_git(clone, "log", "--format=%s", f"HEAD..{target}"))
    return Pending(commits, version_of(clone), version_of(clone, target))


def pending_commits(root: Path | None = None, follow: str | None = None) -> list[str]:
    return check(root, follow).commits


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


def update(root: Path | None = None, follow: str | None = None) -> UpdateResult:
    clone = _require_clone(root or clone_dir())
    # Untracked files are left alone by a pull, and agent worktrees often sit inside a clone.
    if _git(clone, "status", "--porcelain", "--untracked-files=no"):
        raise UpdateError(f"{clone} has uncommitted changes: commit or discard them, then update again")
    branch = _git(clone, "rev-parse", "--abbrev-ref", "HEAD")
    if branch != BRANCH:
        raise UpdateError(f"{clone} is on {branch}: switch it to {BRANCH}, then update again")
    target = _fetch_target(clone, follow)
    before = _git(clone, "rev-parse", "HEAD")
    was = version_of(clone)
    # A clone already ahead of the release stays where it is, so an update never moves backwards.
    _git(clone, "merge", "--ff-only", target)
    after = _git(clone, "rev-parse", "HEAD")
    if before == after:
        return UpdateResult(before=str(was), after=str(was))
    result = UpdateResult(
        before=str(was),
        after=str(version_of(clone)),
        commits=_lines(_git(clone, "log", "--format=%s", f"{before}..{after}")),
    )
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
