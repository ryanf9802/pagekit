"""Find and merge profiles. The profile comes from where the agent works, never from an account.

Lookup: walk up from the working directory to the nearest `.pagekit/profile/` or
folder mapped in `~/.pagekit/projects.toml`. That naturally ends at
`~/.pagekit/profile/` for anything under the home folder. Outside the home folder
the personal profile is the fallback, then the built-in.
"""

from __future__ import annotations

import json
import os
import re
import tomllib
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path

PROFILE_SUBDIR = Path(".pagekit") / "profile"
EXTRA_PROFILES_SUBDIR = Path(".pagekit") / "profiles"
NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,80}$")
RESERVED_NAMES = {"saved", "all"}
TOKEN_RE = re.compile(r"(--pk-[a-z0-9-]+)\s*:")
FONT_TOKEN_RE = re.compile(r"--pk-font\s*:")
MONO_TOKEN_RE = re.compile(r"--pk-mono\s*:")
BRAND_FILE_LIMIT_BYTES = 40 * 1024
FONTS_LIMIT_BYTES = 200 * 1024
_SLIM_ADVICE = {False: "use a simpler file", True: "embed fewer weights"}
BRAND_FILES = ("logo.svg", "logo-dark.svg", "wordmark.svg", "logo-print.png", "favicon.svg")
# Overrides change how pagekit behaves on one machine, never how a page looks or what it must pass.
OVERRIDE_KEYS = {"save", "send"}
OVERRIDE_FILES = {"profile.toml", "INSTRUCTIONS.md", "SAVE.md"}
_MACHINE_PATH_RE = re.compile(r"(?<![\w./-])(?:~/|/home/|/Users/|/mnt/[a-z]/|[A-Za-z]:\\)")


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
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except tomllib.TOMLDecodeError as exc:
        raise ProfileError(f"{path}: {exc}") from exc


def overrides_dir() -> Path:
    return Path.home() / ".pagekit" / "overrides"


def projects_file() -> Path:
    return Path.home() / ".pagekit" / "projects.toml"


def local_profile_dir(name: str) -> Path:
    return Path.home() / ".pagekit" / "profiles" / name


def _project_profiles() -> dict[Path, Path]:
    """Personal project-to-profile mappings: applied like a repo profile, never committed."""
    path = projects_file()
    try:
        entries = tomllib.loads(path.read_text(encoding="utf-8")).get("project", [])
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
    existing = path.read_text(encoding="utf-8") if path.exists() else ""
    entry = f"[[project]]\npath = {json.dumps(str(project.resolve()))}\nprofile = {json.dumps(str(profile_dir))}\n"
    path.write_text(f"{existing.rstrip()}\n\n{entry}".lstrip(), encoding="utf-8")


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


def repo_profiles(cwd: Path | None = None) -> dict[str, Path]:
    """Every profile a repo offers, by name: its default and those in .pagekit/profiles."""
    start = (cwd or Path.cwd()).resolve()
    home = Path.home().resolve()
    for directory in (start, *start.parents):
        # The home folder's .pagekit/profiles is a private store, not choices for this folder.
        if directory == home:
            break
        default = directory / PROFILE_SUBDIR
        extras = directory / EXTRA_PROFILES_SUBDIR
        candidates = [default] if (default / "profile.toml").is_file() else []
        if extras.is_dir():
            candidates += sorted(path for path in extras.iterdir() if (path / "profile.toml").is_file())
        if candidates:
            return {str(_read_toml(path).get("name", path.name)): path for path in candidates}
    return {}


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
        current = _resolve_extends(str(_read_toml(resolved).get("extends", "builtin")), resolved)
    chain.reverse()
    return chain


def _strings(value: object) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, dict):
        value = list(value.values())
    if isinstance(value, list):
        return [text for item in value for text in _strings(item)]
    return []


@dataclass
class Profile:
    name: str
    dirs: list[Path]  # built-in first, then the profile's layers, then any overrides
    config: dict = field(default_factory=dict)
    overrides: list[Path] = field(default_factory=list)

    @property
    def nearest(self) -> Path:
        """The profile's own folder, where its settings belong."""
        return self.dirs[-1 - len(self.overrides)]

    def file(self, relative: str) -> Path | None:
        """The nearest layer's copy of a file."""
        for directory in reversed(self.dirs):
            path = directory / relative
            if path.is_file():
                return path
        return None

    def has_own_brand(self) -> bool:
        """Whether a layer above the built-in names a brand or draws a logo of its own."""
        if str(self.config.get("brand", "")) != str(_read_toml(self.dirs[0]).get("brand", "")):
            return True
        return any((directory / name).is_file() for directory in self.dirs[1:] for name in BRAND_FILES)

    def brand_file(self, relative: str) -> Path | None:
        """A drawn brand asset. The built-in's go together, so "Acme" never shows pagekit's logo."""
        path = self.file(relative)
        if path and path.parent == self.dirs[0] and self.has_own_brand():
            return None
        return path

    def brand_weights(self) -> list[tuple[str, int]]:
        """What each brand file adds to every page, in bytes, once embedded."""
        weights = []
        for name in BRAND_FILES:
            path = self.brand_file(name)
            if path:
                weights.append((name, path.stat().st_size * 4 // 3))
        fonts = self.fonts()
        if fonts:
            weights.append(("fonts.css", len(fonts.encode())))
        return weights

    def brand_warnings(self) -> list[str]:
        warnings = []
        for name, size in self.brand_weights():
            limit = FONTS_LIMIT_BYTES if name == "fonts.css" else BRAND_FILE_LIMIT_BYTES
            if size > limit:
                warnings.append(f"{name} adds {size // 1024} KB to every page (limit {limit // 1024} KB): {_SLIM_ADVICE[name == 'fonts.css']}")
        return warnings

    def read(self, relative: str, default: str = "") -> str:
        path = self.file(relative)
        return path.read_text(encoding="utf-8") if path else default

    def concat(self, relative: str, dirs: list[Path] | None = None) -> str:
        """Every layer's copy of a file, built-in first. Later layers override in CSS."""
        parts = []
        for directory in self.dirs if dirs is None else dirs:
            path = directory / relative
            if path.is_file():
                parts.append(path.read_text(encoding="utf-8").strip())
        return "\n\n".join(p for p in parts if p)

    def fonts(self) -> str:
        """Embedded fonts. A profile with its own text or code font does not also carry the built-in one's bytes."""
        above = self.dirs[1:]
        theme = self.concat("theme.css", above)
        parts = []
        if not (any((d / "fonts.css").is_file() for d in above) or FONT_TOKEN_RE.search(theme)):
            parts.append(self.concat("fonts.css", self.dirs[:1]))
        if not MONO_TOKEN_RE.search(theme):
            parts.append(self.concat("fonts-mono.css", self.dirs[:1]))
        parts.append(self.concat("fonts.css", above))
        return "\n\n".join(part for part in parts if part)

    def theme(self) -> str:
        return self.concat("theme.css")

    def instructions(self) -> str:
        return self.concat("INSTRUCTIONS.md")

    def tokens(self) -> list[str]:
        return sorted(set(TOKEN_RE.findall(self.theme())))

    def checks_layer(self) -> Path:
        """The layer whose [checks] applies, which {profile} in its command points to."""
        for directory in reversed(self.dirs):
            if _read_toml(directory).get("checks", {}).get("command"):
                return directory
        return self.nearest

    def machine_path_warnings(self) -> list[str]:
        """Paths in a profile kept in a repo, which would not exist on a teammate's machine."""
        private = (Path.home() / ".pagekit").resolve()
        warnings = []
        for directory in self.dirs[1 : len(self.dirs) - len(self.overrides)]:
            if directory.is_relative_to(private):
                continue
            texts = {"profile.toml": _strings(_read_toml(directory))}
            for name in ("SAVE.md", "INSTRUCTIONS.md"):
                if (directory / name).is_file():
                    texts[name] = (directory / name).read_text(encoding="utf-8").splitlines()
            for name, lines in texts.items():
                for line in lines:
                    if _MACHINE_PATH_RE.search(line):
                        warnings.append(
                            f"{directory / name} names a path on this machine, which teammates will not have: "
                            f"{line.strip()[:80]}. Move it to {overrides_dir() / self.name}"
                        )
        return warnings


def _named_dir(name: str, cwd: Path) -> Path:
    """Explicit override: `personal`, `builtin`, or a profile directory."""
    if name == "builtin":
        return builtin_dir()
    if name == "personal":
        return personal_dir() if (personal_dir() / "profile.toml").is_file() else builtin_dir()
    offered = repo_profiles(cwd)
    if name in offered:
        return offered[name]
    target = Path(name).expanduser()
    if not target.is_absolute():
        target = cwd / target
    if not (target / "profile.toml").is_file():
        raise ProfileError(f"no profile.toml in {target}")
    return target


def _override_layers(name: str) -> list[Path]:
    """This machine's additions to a profile, for all profiles and then for this one."""
    layers = []
    for folder in (overrides_dir() / "all", overrides_dir() / name):
        if not folder.is_dir():
            continue
        allowed = ", ".join(sorted(OVERRIDE_FILES))
        for path in folder.iterdir():
            if path.name not in OVERRIDE_FILES and not path.name.startswith("."):
                raise ProfileError(f"{path}: overrides can only hold {allowed}")
        keys = set(_read_toml(folder)) - OVERRIDE_KEYS
        if keys:
            raise ProfileError(
                f"{folder / 'profile.toml'}: overrides can only set {', '.join(sorted(OVERRIDE_KEYS))}, "
                f"not {', '.join(sorted(keys))}"
            )
        layers.append(folder)
    return layers


def load_profile(cwd: Path | None = None, override: str | None = None, overrides: bool = True) -> Profile:
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
    layers = _override_layers(name) if overrides else []
    for directory in layers:
        config = _deep_merge(config, _read_toml(directory))
    return Profile(name=name, dirs=[*dirs, *layers], config=config, overrides=layers)


def profile_named(name: str, cwd: Path | None = None) -> Profile | None:
    """The profile with this name that applies from here: this folder's, the repo's others, the personal, or the built-in."""
    where = cwd or Path.cwd()
    for override in (None, *(str(path) for path in repo_profiles(where).values()), "personal", "builtin"):
        try:
            profile = load_profile(where, override=override)
        except ProfileError:
            continue
        if profile.name == name:
            return profile
    return None


_STARTER_BRAND = """brand = {brand}
footer = {brand}
"""

_STARTER_TOML = """name = "{name}"
extends = "{extends}"
{when_line}{brand_lines}
# Where `pagekit save` puts a page. Default: ~/pages/saved.
# [save]
# root = "~/somewhere/durable"
# root_command = "command-that-prints-a-path"   # used instead of root
# subdir = "Pages"
"""

_STARTER_THEME = """/* Override only what differs. Redefine tokens for both light and dark.
   Keep "screen and" on the dark block so pages always print in light colors.

:root {
  --pk-accent: #1f6feb;
}
@media screen and (prefers-color-scheme: dark) {
  :root {
    --pk-accent: #8fb0f0;
  }
}
*/
"""

_STARTER_INSTRUCTIONS = """## {brand} pages

Add content and voice rules for agents here. They are printed by `pagekit new`.
Add a SAVE.md next to this file to have agents write a matching document after
`pagekit save`; `pagekit save` prints it with the placeholders filled in.
"""


def _toml_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def init_profile(directory: Path, name: str, extends: str, brand: str = "", when: str = "") -> list[Path]:
    """Scaffold a profile. Never overwrites an existing file. Without a brand, it keeps the inherited one."""
    if not NAME_RE.match(name) or name in RESERVED_NAMES:
        raise ProfileError(f"invalid profile name {name!r}")
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    starters = {
        "profile.toml": _STARTER_TOML.format(
            name=name,
            extends=extends,
            when_line=f"when = {_toml_string(when)}\n" if when else "",
            brand_lines=_STARTER_BRAND.format(brand=_toml_string(brand)) if brand else "",
        ),
        "theme.css": _STARTER_THEME,
        "INSTRUCTIONS.md": _STARTER_INSTRUCTIONS.format(brand=brand or name),
    }
    for filename, content in starters.items():
        path = directory / filename
        if not path.exists():
            path.write_text(content, encoding="utf-8")
            written.append(path)
    return written
