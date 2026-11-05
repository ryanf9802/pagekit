"""Pages on disk: scaffold, build, check, pack, save, prune. The folder is the database."""

from __future__ import annotations

import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import shlex
import shutil
import socket
import subprocess
import time
import tomllib
from dataclasses import dataclass
from datetime import datetime, timezone
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path
from urllib.parse import unquote, urlsplit

from .profiles import NAME_RE, RESERVED_NAMES, Profile

DEFAULT_PORT = 8766
DEFAULT_TTL_DAYS = 30.0
PRUNE_THROTTLE_SECONDS = 86400
SAVED_DIR = "saved"
FALLBACK_NAME_ATTRS = ("data-pk-name", "name", "id")
NON_FIELD_INPUTS = {"button", "submit", "reset", "image", "hidden", "password"}
GROUP_INPUTS = {"radio", "checkbox"}
ASSET_ATTR_RE = re.compile(r"""(\b(?:src|href|poster)=)(["'])(assets/[^"']+)\2""")
ASSET_URL_RE = re.compile(r"""url\((["']?)(assets/[^)"']+)\1\)""")
CSS_EXTERNAL_RE = re.compile(r"""(?:url\(\s*["']?|@import\s+["'])((?:https?:)?//[^)"'\s]+)""")
WIDE_FIXED_RE = re.compile(r"(?<![-\w])(?:min-)?width\s*:\s*(\d{3,})px")
PLACEHOLDER_RE = re.compile(r"\{\{(\w+)\}\}")
PHONE_WIDTH_PX = 390
COPY_ICON = (
    '<svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true">'
    '<rect x="5.5" y="5.5" width="8" height="8" rx="1.5"/>'
    '<path d="M10.5 5.5v-2a1 1 0 0 0-1-1h-6a1 1 0 0 0-1 1v6a1 1 0 0 0 1 1h2"/></svg>'
)


class PageError(Exception):
    pass


def pages_root() -> Path:
    return Path(os.environ.get("PAGEKIT_HOME") or Path.home() / "pages").expanduser()


def ttl_days() -> float:
    try:
        return float(os.environ.get("PAGEKIT_TTL_DAYS", DEFAULT_TTL_DAYS))
    except ValueError:
        return DEFAULT_TTL_DAYS


def server_port() -> int:
    try:
        return int(os.environ.get("PAGEKIT_PORT", DEFAULT_PORT))
    except ValueError:
        return DEFAULT_PORT


def server_running(port: int | None = None) -> bool:
    with socket.socket() as sock:
        sock.settimeout(0.2)
        return sock.connect_ex(("127.0.0.1", port or server_port())) == 0


def default_session() -> str:
    name = os.environ.get("PAGEKIT_SESSION", "").strip()
    if not name and os.environ.get("CLAUDE_JOB_DIR"):
        name = Path(os.environ["CLAUDE_JOB_DIR"]).name
    if not name:
        name = os.environ.get("CLAUDE_CODE_SESSION_ID", "")[:8]
    return " ".join(name.split())[:40]


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_iso(value: str) -> float | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def _display_date(value: str) -> str:
    stamp = _parse_iso(value)
    return datetime.fromtimestamp(stamp).strftime("%m/%d/%Y") if stamp else ""


@dataclass
class Page:
    dir: Path
    meta: dict

    @property
    def slug(self) -> str:
        return self.meta["slug"]

    @property
    def profile(self) -> str:
        return self.meta["profile"]

    @property
    def content(self) -> Path:
        return self.dir / "content.html"

    @property
    def index(self) -> Path:
        return self.dir / "index.html"

    @property
    def assets(self) -> Path:
        return self.dir / "assets"

    @property
    def url_path(self) -> str:
        return f"/p/{self.profile}/{self.slug}/"

    def url(self) -> str:
        return f"http://localhost:{server_port()}{self.url_path}"

    def write_meta(self) -> None:
        lines = []
        for key, value in self.meta.items():
            rendered = str(value).lower() if isinstance(value, bool) else json.dumps(value)
            lines.append(f"{key} = {rendered}")
        (self.dir / "page.toml").write_text("\n".join(lines) + "\n")

    def expires_at(self) -> float | None:
        ttl = ttl_days()
        updated = _parse_iso(self.meta.get("updated", ""))
        if ttl <= 0 or self.meta.get("pinned") or updated is None:
            return None
        return updated + ttl * 86400

    def to_json(self) -> dict:
        return {
            "slug": self.slug,
            "profile": self.profile,
            "title": self.meta.get("title", self.slug),
            "summary": self.meta.get("summary", ""),
            "updated": self.meta.get("updated", ""),
            "session": self.meta.get("session", ""),
            "pinned": bool(self.meta.get("pinned")),
            "expires": self.expires_at(),
            "built": self.index.is_file(),
            "url": self.url_path,
            "path": str(self.index),
        }


def _validate_slug(slug: str) -> None:
    if not NAME_RE.match(slug):
        raise PageError(f"invalid slug {slug!r}: use lowercase letters, digits, and hyphens")


def _page_dir(profile_name: str, slug: str) -> Path:
    return pages_root() / profile_name / slug


def load_page_dir(directory: Path) -> Page:
    try:
        return Page(directory, tomllib.loads((directory / "page.toml").read_text()))
    except FileNotFoundError as exc:
        raise PageError(f"no page at {directory}") from exc
    except tomllib.TOMLDecodeError as exc:
        raise PageError(f"{directory}/page.toml: {exc}") from exc


def load_page(profile: Profile, slug: str) -> Page:
    _validate_slug(slug)
    return load_page_dir(_page_dir(profile.name, slug))


_SLOTS_SCAFFOLD = """<!-- Page body only. The profile adds the header, title, theme, and footer. -->
<section class="pk-section">
  <h2>Section</h2>
  <p>Content goes here.</p>
</section>
"""

_FREE_SCAFFOLD = """<!doctype html>
<html lang="en">
<head>
{{head}}
</head>
<body>
<main class="pk-main">
  <h1>{{title}}</h1>
</main>
{{footer}}
</body>
</html>
"""


def new_page(profile: Profile, slug: str, title: str | None, summary: str | None, mode: str) -> tuple[Page, bool]:
    """Create a page, or return the existing one so an update stays at the same path."""
    _validate_slug(slug)
    directory = _page_dir(profile.name, slug)
    if (directory / "page.toml").is_file():
        page = load_page_dir(directory)
        if title:
            page.meta["title"] = title
        if summary is not None:
            page.meta["summary"] = summary
        page.meta["updated"] = _now_iso()
        page.write_meta()
        return page, False
    if not title:
        raise PageError("a new page needs --title")
    (directory / "assets").mkdir(parents=True, exist_ok=True)
    now = _now_iso()
    page = Page(
        directory,
        {
            "slug": slug,
            "title": title,
            "summary": summary or "",
            "profile": profile.name,
            "mode": mode,
            "created": now,
            "updated": now,
            "session": default_session(),
            "pinned": False,
        },
    )
    page.write_meta()
    page.content.write_text(_FREE_SCAFFOLD if mode == "free" else _SLOTS_SCAFFOLD)
    return page, True


def _asset_text(name: str) -> str:
    return resources.files("pagekit").joinpath("static", name).read_text()


def _data_uri(path: Path) -> str:
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return f"data:{mime};base64,{base64.b64encode(path.read_bytes()).decode()}"


def _logo_html(profile: Profile, brand: str) -> str:
    logo = profile.file("logo.svg")
    dark = profile.file("logo-dark.svg")
    wordmark = profile.file("wordmark.svg")
    parts = []
    if logo:
        alt = "" if wordmark else html.escape(brand)
        source = f'<source media="screen and (prefers-color-scheme: dark)" srcset="{_data_uri(dark)}">' if dark else ""
        parts.append(f'<picture>{source}<img class="pk-logo" src="{_data_uri(logo)}" alt="{alt}"></picture>')
    if wordmark:
        parts.append(f'<img class="pk-wordmark" src="{_data_uri(wordmark)}" alt="{html.escape(brand)}">')
    return "".join(parts)


def _css_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")
    # Inside a <style> element, so "</style>" must never appear literally.
    return '"' + escaped.replace("<", "\\3c ") + '"'


def _print_logo(profile: Profile) -> str | None:
    """Icon and wordmark as one small image, since a margin box cannot size its own images."""
    icon = profile.file("logo.svg")
    wordmark = profile.file("wordmark.svg")
    if not icon and not wordmark:
        return None
    height = 22
    parts, x = [], 0
    if icon:
        parts.append(f'<image href="{_data_uri(icon)}" width="{height}" height="{height}"/>')
        x = height + 7
    if wordmark:
        box = re.search(r'viewBox="[\d.-]+[ ,]+[\d.-]+[ ,]+([\d.]+)[ ,]+([\d.]+)"', wordmark.read_text())
        ratio = float(box.group(1)) / float(box.group(2)) if box else 8.0
        word_height = 14
        word_width = round(word_height * ratio, 1)
        parts.append(
            f'<image href="{_data_uri(wordmark)}" x="{x}" y="{(height - word_height) / 2}" '
            f'width="{word_width}" height="{word_height}"/>'
        )
        x += word_width
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{x}" height="{height}" viewBox="0 0 {x} {height}">'
        + "".join(parts)
        + "</svg>"
    )
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def print_css(profile: Profile, title: str, footer_text: str, date: str) -> str:
    """The running header and footer, repeated on every printed sheet."""
    logo = _print_logo(profile)
    brand = str(profile.config.get("brand", ""))
    left = f'url("{logo}")' if logo else _css_string(brand)
    footer = " / ".join(part for part in (footer_text, f"Updated {date}") if part)
    text = 'font: 400 8.5pt system-ui, -apple-system, "Segoe UI", Roboto, sans-serif; color: #5b6270;'
    return f"""@page {{
  margin: 24mm 15mm 20mm;
  @top-left {{ content: {left}; vertical-align: bottom; padding-bottom: 3mm; white-space: nowrap; {text} }}
  @top-right {{ content: {_css_string(title)}; vertical-align: bottom; padding-bottom: 4mm; {text} }}
  @bottom-left {{ content: {_css_string(footer)}; vertical-align: top; padding-top: 4mm; {text} }}
  @bottom-right {{ content: "Page " counter(page) " of " counter(pages); vertical-align: top; padding-top: 4mm; {text} }}
}}"""


def _render(template: str, values: dict[str, str]) -> str:
    # One pass, so "{{...}}" inside page content is left as written.
    return PLACEHOLDER_RE.sub(lambda m: values.get(m.group(1), m.group(0)), template)


def build_page(profile: Profile, page: Page) -> None:
    built = _now_iso()
    page.meta["updated"] = built
    page.meta["profile"] = profile.name
    page.write_meta()
    title = html.escape(page.meta.get("title", page.slug))
    summary = page.meta.get("summary", "")
    brand = str(profile.config.get("brand", ""))
    footer_text = str(profile.config.get("footer", ""))
    export_meta = {
        "slug": page.slug,
        "title": page.meta.get("title", page.slug),
        "profile": profile.name,
        "source": str(page.index),
        "built": built,
        # Keys saved answers: a style-only rebuild keeps them, a content change resets them.
        "rev": hashlib.sha256(page.content.read_bytes()).hexdigest()[:12],
    }
    meta_json = json.dumps(export_meta).replace("<", "\\u003c")
    running_css = print_css(profile, page.meta.get("title", page.slug), footer_text, _display_date(built))
    head = "\n".join(
        part
        for part in (
            '<meta charset="utf-8">',
            '<meta name="viewport" content="width=device-width, initial-scale=1">',
            f"<title>{title}</title>",
            f'<script type="application/json" id="pagekit-meta">{meta_json}</script>',
            profile.concat("head.html"),
            f"<style>\n{profile.theme()}\n{running_css}\n</style>",
        )
        if part
    )
    footer = (
        '<footer class="pk-footer" data-pk-ignore>\n'
        '<div class="pk-footer-meta">'
        f"<span>{html.escape(footer_text)}</span>"
        f"<span>Updated {_display_date(built)}</span></div>\n"
        '<span id="pk-export-status" class="pk-visually-hidden" role="status"></span>\n'
        f'<button type="button" id="pk-export" class="pk-button">{COPY_ICON}'
        '<span id="pk-export-label">Copy page state for Claude</span></button>\n'
        f"</footer>\n<script>\n{_asset_text('export.js')}\n</script>"
    )
    values = {
        "head": head,
        "footer": footer,
        "title": title,
        "summary": f'<p class="pk-summary">{html.escape(summary)}</p>' if summary else "",
        "brand": html.escape(brand),
        "logo": _logo_html(profile, brand),
    }
    source = page.content.read_text()
    if page.meta.get("mode") == "free":
        for required in ("{{head}}", "{{footer}}"):
            if required not in source:
                raise PageError(f"{page.content}: a free-mode page must contain {required}")
        document = _render(source, values)
    else:
        # Content goes in last so its own "{{...}}" text is left as written.
        marker = "\x00pagekit-content\x00"
        document = _render(profile.read("template.html"), {**values, "content": marker}).replace(marker, source)
    page.index.write_text(document)


class _Scanner(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.title = ""
        self.has_viewport = False
        self.in_title = False
        self.in_style = False
        self.styles: list[str] = []
        self.external: list[str] = []
        self.unnamed: list[str] = []
        self.singles: dict[str, int] = {}
        self.asset_refs: set[str] = set()
        self.export_button = False

    def handle_starttag(self, tag, attrs):
        attr = {key: (value or "") for key, value in attrs}
        if tag == "title":
            self.in_title = True
        elif tag == "style":
            self.in_style = True
        elif tag == "meta" and attr.get("name") == "viewport":
            self.has_viewport = True
        elif tag == "button" and attr.get("id") == "pk-export":
            self.export_button = True
        for key in ("src", "href", "poster"):
            if attr.get(key, "").startswith("assets/"):
                self.asset_refs.add(unquote(attr[key].split("#")[0].split("?")[0]))
        ref = ""
        if tag in {"script", "img", "video", "audio", "source", "iframe", "embed"}:
            ref = attr.get("src", "")
        elif tag == "link" and "stylesheet" in attr.get("rel", ""):
            ref = attr.get("href", "")
        if ref and (urlsplit(ref).netloc or ref.startswith("//")):
            self.external.append(ref)
        self._scan_control(tag, attr)

    def _scan_control(self, tag: str, attr: dict[str, str]) -> None:
        kind = attr.get("type", "text").lower()
        is_input = tag == "input" and kind not in NON_FIELD_INPUTS
        editable = "contenteditable" in attr and attr["contenteditable"].lower() != "false"
        if not (is_input or tag in {"select", "textarea"} or editable) or "data-pk-ignore" in attr:
            return
        name = next((attr[key] for key in FALLBACK_NAME_ATTRS if attr.get(key)), "")
        if not name:
            self.unnamed.append(f"<{tag}>" + (f' labelled "{attr["placeholder"]}"' if attr.get("placeholder") else ""))
        elif not (tag == "input" and kind in GROUP_INPUTS):
            self.singles[name] = self.singles.get(name, 0) + 1

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False
        elif tag == "style":
            self.in_style = False

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif self.in_style:
            self.styles.append(data)


@dataclass
class CheckResult:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def check_page(profile: Profile, page: Page) -> CheckResult:
    """The mechanical gate. Phone-width layout needs a browser, so that stays a warning."""
    errors: list[str] = []
    warnings: list[str] = []
    if not page.index.is_file():
        return CheckResult([f"not built: run pagekit build {page.slug}"], [])
    if page.content.stat().st_mtime > page.index.stat().st_mtime:
        errors.append(f"stale: content.html changed after the last build, run pagekit build {page.slug}")
    document = page.index.read_text()
    scan = _Scanner()
    scan.feed(document)
    style_text = "\n".join(scan.styles)

    if not scan.title.strip():
        errors.append("missing <title>")
    if not scan.has_viewport:
        errors.append("missing viewport meta")
    if "prefers-color-scheme: dark" not in style_text:
        errors.append("no dark-mode styles: the profile theme is not in the page")
    if not (scan.export_button and "pagekit-meta" in document and "window.pagekit" in document):
        errors.append("export button or script missing")
    footer_text = html.escape(str(profile.config.get("footer", "")))
    if footer_text and footer_text not in document:
        errors.append(f"required footer text missing: {footer_text}")

    allowed = {str(host).lower() for host in profile.config.get("allowed_hosts", [])}
    external = scan.external + CSS_EXTERNAL_RE.findall(style_text)
    for ref in external:
        if urlsplit(ref if "//" in ref else f"//{ref}").netloc.lower() not in allowed:
            errors.append(f"external resource not in allowed_hosts: {ref}")

    if profile.config.get("ascii_only", True):
        for number, line in enumerate(document.splitlines(), 1):
            if not line.isascii():
                bad = next(ch for ch in line if not ch.isascii())
                errors.append(f"non-ASCII character {bad!r} on line {number} of index.html")
                break

    for control in scan.unnamed:
        errors.append(f"{control} has no name or id, so it cannot be exported")
    for name, count in scan.singles.items():
        if count > 1:
            errors.append(f"{count} controls share the name {name!r}, so the export would lose answers")

    for ref in sorted(scan.asset_refs | {m[1] for m in ASSET_URL_RE.findall(style_text)}):
        if not (page.dir / ref).is_file():
            errors.append(f"missing asset: {ref}")
    if page.assets.is_dir():
        decoded = unquote(document)
        for path in sorted(page.assets.rglob("*")):
            relative = path.relative_to(page.dir).as_posix()
            if path.is_file() and relative not in decoded:
                errors.append(f"unused asset: {relative}")

    for width in WIDE_FIXED_RE.findall(style_text + document):
        if int(width) > PHONE_WIDTH_PX:
            warnings.append(f"fixed width of {width}px may scroll sideways on a phone")
            break
    return CheckResult(errors, warnings)


def pack_page(page: Page) -> Path:
    """One self-contained HTML file with assets as data URIs, for sharing."""
    if not page.index.is_file():
        raise PageError(f"not built: run pagekit build {page.slug}")
    if page.content.stat().st_mtime > page.index.stat().st_mtime:
        raise PageError(f"stale: content.html changed after the last build, run pagekit build {page.slug}")
    assets_root = page.assets.resolve()

    def uri(ref: str) -> str | None:
        path = (page.dir / unquote(ref.split("#")[0].split("?")[0])).resolve()
        if not path.is_relative_to(assets_root) or not path.is_file():
            return None
        return _data_uri(path)

    def replace_attr(match: re.Match) -> str:
        data = uri(match.group(3))
        return f"{match.group(1)}{match.group(2)}{data}{match.group(2)}" if data else match.group(0)

    def replace_url(match: re.Match) -> str:
        data = uri(match.group(2))
        return f'url("{data}")' if data else match.group(0)

    document = ASSET_URL_RE.sub(replace_url, ASSET_ATTR_RE.sub(replace_attr, page.index.read_text()))
    target = page.dir / f"{page.slug}.pack.html"
    target.write_text(document)
    return target


def send_page(page: Page) -> str:
    """Hand the packed page to the user through dropbucket, when it is installed."""
    if not shutil.which("dropbucket"):
        raise PageError("dropbucket is not on PATH: share the file from pagekit pack instead")
    packed = pack_page(page)
    named = packed.with_name(f"{page.slug}.html")
    shutil.copyfile(packed, named)
    try:
        result = subprocess.run(
            ["dropbucket", "put", str(named), "--caption", page.meta.get("title", page.slug)],
            capture_output=True,
            text=True,
        )
    finally:
        named.unlink(missing_ok=True)
    if result.returncode != 0:
        raise PageError(f"dropbucket put failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _save_dir(profile: Profile) -> Path:
    save = profile.config.get("save", {})
    if save.get("root_command"):
        # Runs only on an explicit save, without a shell, from the profile you chose to use.
        result = subprocess.run(shlex.split(str(save["root_command"])), capture_output=True, text=True)
        root = result.stdout.strip()
        if result.returncode != 0 or not root:
            raise PageError(f"save.root_command failed: {result.stderr.strip() or 'no output'}")
        base = Path(root)
    elif save.get("root"):
        base = Path(str(save["root"])).expanduser()
    else:
        base = pages_root() / SAVED_DIR
    return base / str(save.get("subdir", ""))


def _embedded_identity(path: Path) -> tuple[str, str] | None:
    """The (profile, slug) a packed page was built from, read from its head."""
    with path.open(errors="replace") as handle:
        head = handle.read(8192)
    match = re.search(r'id="pagekit-meta">(.*?)</script>', head)
    if not match:
        return None
    try:
        meta = json.loads(match.group(1))
    except ValueError:
        return None
    return meta.get("profile", ""), meta.get("slug", "")


@dataclass
class SaveResult:
    path: Path
    instructions: str


def save_page(profile: Profile, page: Page) -> SaveResult:
    """Copy the packed page somewhere prune never looks, and pin the working copy."""
    result = check_page(profile, page)
    if not result.ok:
        raise PageError("fix these before saving:\n  " + "\n  ".join(result.errors))
    packed = pack_page(page)
    directory = _save_dir(profile)
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / f"{page.slug}.html"
    if target.exists() and _embedded_identity(target) != (page.profile, page.slug):
        raise PageError(f"{target} already exists and is a different page: rename the slug")
    shutil.copyfile(packed, target)
    page.meta["pinned"] = True
    page.write_meta()
    template = profile.read("SAVE.md")
    instructions = _render(
        template,
        {
            "file": target.name,
            "path": str(target),
            "title": page.meta.get("title", page.slug),
            "summary": page.meta.get("summary", ""),
            "url": page.url(),
            "content": str(page.content),
            "profile": profile.name,
        },
    )
    return SaveResult(target, instructions.strip())


def iter_pages() -> list[Page]:
    root = pages_root()
    if not root.is_dir():
        return []
    pages = []
    for profile_dir in sorted(root.iterdir()):
        if profile_dir.name in RESERVED_NAMES or not profile_dir.is_dir() or profile_dir.is_symlink():
            continue
        for directory in sorted(profile_dir.iterdir()):
            if directory.is_dir() and not directory.is_symlink() and (directory / "page.toml").is_file():
                try:
                    pages.append(load_page_dir(directory))
                except PageError:
                    continue
    pages.sort(key=lambda p: p.meta.get("updated", ""), reverse=True)
    return pages


def list_saved() -> list[dict]:
    """Copies under the saved folder of the pages root. Vault saves stay listed through their pin."""
    folder = pages_root() / SAVED_DIR
    if not folder.is_dir():
        return []
    saved = []
    for path in sorted(folder.glob("*.html"), key=lambda p: p.stat().st_mtime, reverse=True):
        with path.open(errors="replace") as handle:
            match = re.search(r"<title>(.*?)</title>", handle.read(8192))
        saved.append(
            {
                "slug": path.stem,
                "profile": SAVED_DIR,
                "title": html.unescape(match.group(1)) if match else path.stem,
                "summary": "",
                "updated": datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "session": "",
                "pinned": True,
                "expires": None,
                "built": True,
                "url": f"/saved/{path.name}",
                "path": str(path),
            }
        )
    return saved


def prune_pages(days: float | None = None, dry_run: bool = False) -> list[Path]:
    """Delete unpinned pages not updated for the TTL. Only page folders are ever touched."""
    ttl = ttl_days() if days is None else days
    if ttl <= 0:
        return []
    cutoff = time.time() - ttl * 86400
    removed = []
    for page in iter_pages():
        updated = _parse_iso(page.meta.get("updated", ""))
        if page.meta.get("pinned") or updated is None or updated >= cutoff:
            continue
        removed.append(page.dir)
        if not dry_run:
            shutil.rmtree(page.dir)
    return removed


def prune_if_due() -> None:
    """Expiry must work with no server running, so normal commands run it about once a day."""
    root = pages_root()
    stamp = root / ".last-prune"
    try:
        if stamp.exists() and time.time() - stamp.stat().st_mtime < PRUNE_THROTTLE_SECONDS:
            return
        root.mkdir(parents=True, exist_ok=True)
        stamp.touch()
        prune_pages()
    except OSError:
        pass
