"""Components: the core set in this repo, plus a library that grows in the user's home.

Agents save anything new to the library as they work, with no user involved. A library
component uses only theme tokens, so it takes on the look of whichever profile uses it.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

from .profiles import NAME_RE, Profile

_CLASS_ATTR_RE = re.compile(r"""\bclass\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_CSS_CLASS_RE = re.compile(r"\.([a-zA-Z][\w-]*)")
_CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.DOTALL)
_CSS_URL_RE = re.compile(r"url\([^)]*\)")
_HARD_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|oklch|lab|lch)\(")
_INLINE_STYLE_RE = re.compile(r"<[^>]*\sstyle\s*=", re.IGNORECASE)
_STYLE_TAG_RE = re.compile(r"<style\b", re.IGNORECASE)
_FIRST_COMMENT_RE = re.compile(r"\s*<!--\s*(.*?)\s*-->", re.DOTALL)
_GIT_TIMEOUT_SECONDS = 20


class ComponentError(Exception):
    pass


@dataclass
class Component:
    name: str
    when: str
    source: str  # core, profile, library, or bundled
    html: Path
    css: Path | None = None


def library_dir() -> Path:
    return Path.home() / ".pagekit" / "library"


def css_classes(css: str) -> set[str]:
    return set(_CSS_CLASS_RE.findall(_CSS_URL_RE.sub("", _CSS_COMMENT_RE.sub("", css))))


def html_classes(document: str) -> set[str]:
    found: set[str] = set()
    for double, single in _CLASS_ATTR_RE.findall(document):
        found.update((double or single).split())
    return found


def _when_from_html(path: Path) -> str:
    match = _FIRST_COMMENT_RE.match(path.read_text(encoding="utf-8"))
    return " ".join(match.group(1).split()) if match else ""


def bundled_dir() -> Path:
    return Path(str(resources.files("pagekit").joinpath("components")))


def library_components() -> list[Component]:
    """The user's library, then the ones shipped with pagekit. A user's copy wins by name."""
    found: dict[str, Component] = {}
    for component in [*_folder_components(library_dir(), "library"), *_folder_components(bundled_dir(), "bundled")]:
        found.setdefault(component.name, component)
    return list(found.values())


def _folder_components(root: Path, source: str) -> list[Component]:
    if not root.is_dir():
        return []
    components = []
    for folder in sorted(root.iterdir()):
        html = folder / "component.html"
        if not html.is_file():
            continue
        css = folder / "component.css"
        try:
            when = str(tomllib.loads((folder / "component.toml").read_text(encoding="utf-8")).get("when", ""))
        except (OSError, tomllib.TOMLDecodeError):
            when = ""
        components.append(Component(folder.name, when, source, html, css if css.is_file() else None))
    return components


def list_components(profile: Profile) -> list[Component]:
    """Core and profile components, then the library and bundled set. Core names cannot be reused."""
    found: dict[str, Component] = {}
    for index, directory in enumerate(profile.dirs):
        folder = directory / "components"
        if folder.is_dir():
            source = "core" if index == 0 else "profile"
            for path in sorted(folder.glob("*.html")):
                css = path.with_suffix(".css")
                found[path.stem] = Component(path.stem, _when_from_html(path), source, path, css if css.is_file() else None)
    for component in library_components():
        found.setdefault(component.name, component)
    return sorted(found.values(), key=lambda c: ({"core": 0, "profile": 1, "library": 2, "bundled": 3}[c.source], c.name))


def find_component(profile: Profile, name: str) -> Component:
    for component in list_components(profile):
        if component.name == name:
            return component
    raise ComponentError(f"no component named {name!r}: see pagekit component list")


def _validate(name: str, when: str, html: str, css: str) -> None:
    if not NAME_RE.match(name) or name.startswith("pk-"):
        raise ComponentError(f"invalid component name {name!r}: use lowercase letters, digits, and hyphens, not pk-")
    if not " ".join(when.split()):
        raise ComponentError("give --when one line on when to use this component")
    if _INLINE_STYLE_RE.search(html) or _STYLE_TAG_RE.search(html):
        raise ComponentError("component.html cannot have inline styles or <style>: put them in component.css")
    if _HARD_COLOR_RE.search(_CSS_COMMENT_RE.sub("", css)):
        raise ComponentError("component.css cannot hard-code colors: use --pk-* tokens so every profile can restyle it")
    foreign = sorted(c for c in css_classes(css) if c != name and not c.startswith(f"{name}-"))
    if foreign:
        raise ComponentError(f"every class in component.css must start with {name!r}, not: {', '.join(foreign)}")


def _commit_quietly(path: Path, message: str) -> None:
    """Commit only this path when the library is in a git repo. Never pushes, never blocks."""
    real = path.resolve()

    def git(*args: str, cwd: Path) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["git", "-C", str(cwd), *args],
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
            stdin=subprocess.DEVNULL,
            timeout=_GIT_TIMEOUT_SECONDS,
        )

    try:
        top = git("rev-parse", "--show-toplevel", cwd=real.parent)
        if top.returncode != 0:
            return
        root = Path(top.stdout.strip())
        relative = str(real.relative_to(root))
        git("add", "--", relative, cwd=root)
        git("commit", "-q", "-m", message, "--", relative, cwd=root)
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return


def add_component(profile: Profile, name: str, when: str, source: Path, update: bool = False) -> Path:
    html_path = source / "component.html"
    css_path = source / "component.css"
    if not html_path.is_file():
        raise ComponentError(f"{source} has no component.html")
    html = html_path.read_text(encoding="utf-8")
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    _validate(name, when, html, css)
    existing = next((c for c in list_components(profile) if c.name == name), None)
    if existing and existing.source in ("core", "profile"):
        raise ComponentError(f"{name!r} is a {existing.source} component: use it, or pick another name")
    if existing and existing.source == "library" and not update:
        raise ComponentError(f"{name!r} is already in the library: use it, or pass --update to change it for every page")
    target = library_dir() / name
    target.parent.mkdir(parents=True, exist_ok=True)
    # Built beside the target and renamed in, so sessions never see half a component.
    staging = Path(tempfile.mkdtemp(prefix=f".{name}-", dir=target.parent))
    try:
        (staging / "component.html").write_text(html, encoding="utf-8")
        if css:
            (staging / "component.css").write_text(css, encoding="utf-8")
        (staging / "component.toml").write_text(f"when = {json.dumps(' '.join(when.split()))}\n", encoding="utf-8")
        os.chmod(staging, 0o755)
        if update and target.exists():
            shutil.rmtree(target)
        try:
            staging.rename(target)
        except OSError as exc:
            raise ComponentError(f"{name!r} was just added by another session: use it") from exc
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    _commit_quietly(target, f"pagekit: {'update' if update else 'add'} component {name}")
    return target


def library_css_for(document: str, profile: Profile) -> str:
    """CSS for only the library and profile components this page uses, so the theme does not grow."""
    used = html_classes(document)
    parts = []
    for component in list_components(profile):
        if component.css and css_classes(component.css.read_text(encoding="utf-8")) & used:
            css = component.css.read_text(encoding="utf-8").strip()
            parts.append(f"/* component: {component.name} */\n{css}")
    return "\n".join(parts)


def library_classes(profile: Profile) -> set[str]:
    found: set[str] = set()
    for component in list_components(profile):
        if component.css:
            found |= css_classes(component.css.read_text(encoding="utf-8"))
    return found


def consistency_warnings(profile: Profile, document: str) -> list[str]:
    """Styling that bypasses the shared components. Warnings, so one-off fixes are not blocked."""
    warnings = []
    inline = len(_INLINE_STYLE_RE.findall(document))
    if inline:
        warnings.append(f"{inline} inline style(s): use a component, or save a new one with pagekit component add")
    tags = len(_STYLE_TAG_RE.findall(document))
    if tags:
        warnings.append(f"{tags} <style> block(s) in the page: use a component, or save a new one with pagekit component add")
    undefined = sorted(html_classes(document) - css_classes(profile.theme()) - library_classes(profile))
    if undefined:
        warnings.append(f"classes no theme or component defines: {', '.join(undefined)}")
    return warnings
