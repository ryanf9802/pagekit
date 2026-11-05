"""Find and merge profiles. The profile comes from where the agent works, never from an account.

Lookup: walk up from the working directory to the nearest `.pagekit/profile/` or
folder mapped in `~/.pagekit/projects.toml`. That naturally ends at
`~/.pagekit/profile/` for anything under the home folder. Outside the home folder
the personal profile is the fallback, then the built-in.
"""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

PROFILE_SUBDIR = Path(".pagekit") / "profile"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
RESERVED_NAMES = {"saved"}
TOKEN_RE = re.compile(r"(--pk-[a-z0-9-]+)\s*:")


class ProfileError(Exception):
    pass


def builtin_dir() -> Path:
    return Path(str(resources.files("pagekit").joinpath("profile_default")))


def personal_dir() -> Path:
    return Path.home() / PROFILE_SUBDIR


def _deep_merge(base: dict, over: dict) -> dict:
    merged = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _read_toml(directory: Path) -> dict:
    path = directory / "profile.toml"
    try:
        return tomllib.loads(path.read_text())
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{path}: {exc}") from exc


def projects_file() -> Path:
    return Path.home() / ".pagekit" / "projects.toml"


def local_profile_dir(name: str) -> Path:
    return Path.home() / ".pagekit" / "profiles" / name


def _project_profiles() -> dict[Path, Path]:
    """Personal project-to-profile mappings: applied like a repo profile, never committed."""
    path = projects_file()
    try:
        entries = tomllib.loads(path.read_text()).get("project", [])
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{path}: {exc}") from exc
    return {
        Path(str(e["path"])).expanduser().resolve(): Path(str(e["profile"])).expanduser()
        for e in entries
        if "path" in e and "profile" in e
    }


def register_project(project: Path, profile_dir: Path) -> None:
    """Map a project folder to a personal profile. Later entries for a path are not added."""
    if project.resolve() in _project_profiles():
        return
    path = projects_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = path.read_text() if path.exists() else ""
    entry = f'[[project]]\npath = "{project.resolve()}"\nprofile = "{profile_dir}"\n'
    path.write_text(f"{existing.rstrip()}\n\n{entry}".lstrip())


def find_profile_dir(cwd: Path | None = None) -> Path:
    """The nearest profile for this directory, without resolving `extends`."""
    start = (cwd or Path.cwd()).resolve()
    projects = _project_profiles()
    for directory in (start, *start.parents):
        candidate = directory / PROFILE_SUBDIR
        if (candidate / "profile.toml").is_file():
            return candidate
        if directory in projects:
            if not (projects[directory] / "profile.toml").is_file():
                raise ProfileError(f"{projects_file()}: no profile.toml in {projects[directory]}")
            return projects[directory]
    if (personal_dir() / "profile.toml").is_file():
        return personal_dir()
    return builtin_dir()


def _resolve_extends(value: str, directory: Path) -> Path:
    if value == "builtin":
        return builtin_dir()
    if value == "personal":
        # A shared profile may extend "personal" for people who have none.
        return personal_dir() if (personal_dir() / "profile.toml").is_file() else builtin_dir()
    target = Path(value).expanduser()
    if not target.is_absolute():
        target = directory / target
    if not (target / "profile.toml").is_file():
        raise ProfileError(f"{directory}: extends {value!r}, but {target} has no profile.toml")
    return target


def _chain(nearest: Path) -> list[Path]:
    """Layers from the built-in up to the nearest profile."""
    chain: list[Path] = []
    current = nearest
    while True:
        resolved = current.resolve()
        if resolved in chain:
            raise ProfileError(f"profile extends loop at {current}")
        chain.append(resolved)
        if resolved == builtin_dir().resolve():
            break
        default = "builtin" if resolved == personal_dir().resolve() else "personal"
        current = _resolve_extends(str(_read_toml(resolved).get("extends", default)), resolved)
    chain.reverse()
    return chain


@dataclass
class Profile:
    name: str
    dirs: list[Path]  # built-in first, nearest last
    config: dict = field(default_factory=dict)

    @property
    def nearest(self) -> Path:
        return self.dirs[-1]

    def file(self, relative: str) -> Path | None:
        """The nearest layer's copy of a file."""
        for directory in reversed(self.dirs):
            path = directory / relative
            if path.is_file():
                return path
        return None

    def read(self, relative: str, default: str = "") -> str:
        path = self.file(relative)
        return path.read_text() if path else default

    def concat(self, relative: str) -> str:
        """Every layer's copy of a file, built-in first. Later layers override in CSS."""
        parts = []
        for directory in self.dirs:
            path = directory / relative
            if path.is_file():
                parts.append(path.read_text().strip())
        return "\n\n".join(p for p in parts if p)

    def theme(self) -> str:
        return self.concat("theme.css")

    def instructions(self) -> str:
        return self.concat("INSTRUCTIONS.md")

    def tokens(self) -> list[str]:
        return sorted(set(TOKEN_RE.findall(self.theme())))


def _named_dir(name: str, cwd: Path) -> Path:
    """Explicit override: `personal`, `builtin`, or a profile directory."""
    if name == "builtin":
        return builtin_dir()
    if name == "personal":
        return personal_dir() if (personal_dir() / "profile.toml").is_file() else builtin_dir()
    target = Path(name).expanduser()
    if not target.is_absolute():
        target = cwd / target
    if not (target / "profile.toml").is_file():
        raise ProfileError(f"no profile.toml in {target}")
    return target


def load_profile(cwd: Path | None = None, override: str | None = None) -> Profile:
    where = cwd or Path.cwd()
    override = override or os.environ.get("PAGEKIT_PROFILE") or None
    nearest = _named_dir(override, where) if override else find_profile_dir(where)
    dirs = _chain(nearest)
    config: dict = {}
    for directory in dirs:
        config = _deep_merge(config, _read_toml(directory))
    name = str(config.get("name", ""))
    if not NAME_RE.match(name) or name in RESERVED_NAMES:
        raise ProfileError(f"{nearest}: invalid profile name {name!r}")
    return Profile(name=name, dirs=dirs, config=config)


_STARTER_TOML = """name = "{name}"
extends = "{extends}"
brand = "{brand}"
footer = "{brand}"

# Where `pagekit save` puts a page. Default: ~/pages/saved.
# [save]
# root = "~/somewhere/durable"
# root_command = "command-that-prints-a-path"   # used instead of root
# subdir = "Pages"
"""

_STARTER_THEME = """/* Override only what differs. Redefine tokens for both light and dark.
   Keep "screen and" on the dark block so pages always print in light colors. */
:root {
  --pk-accent: #1f6feb;
}
@media screen and (prefers-color-scheme: dark) {
  :root {
    --pk-accent: #8fb0f0;
  }
}
"""

_STARTER_INSTRUCTIONS = """## {brand} pages

Add content and voice rules for agents here. They are printed by `pagekit new`.
Add a SAVE.md next to this file to have agents write a matching document after
`pagekit save`; `pagekit save` prints it with the placeholders filled in.
"""


def init_profile(directory: Path, name: str, extends: str, brand: str) -> list[Path]:
    """Scaffold a profile. Never overwrites an existing file."""
    if not NAME_RE.match(name) or name in RESERVED_NAMES:
        raise ProfileError(f"invalid profile name {name!r}")
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    starters = {
        "profile.toml": _STARTER_TOML.format(name=name, extends=extends, brand=brand),
        "theme.css": _STARTER_THEME,
        "INSTRUCTIONS.md": _STARTER_INSTRUCTIONS.format(brand=brand),
    }
    for filename, content in starters.items():
        path = directory / filename
        if not path.exists():
            path.write_text(content)
            written.append(path)
    return written
