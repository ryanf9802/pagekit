"""Icons, stored once per page. Each use points at one shared symbol, so hundreds stay small in a PDF.

Lucide ships in one file, and a profile can add its own in icons/NAME.svg, with an optional
icons/NAME-dark.svg for dark mode and icons/NAME-print.png for print. A page embeds only the icons
it uses, so it stays offline. A plain icon costs about 110 bytes per use in a PDF, but Chromium redraws
a complex vector on every use, about 1 KB each for a gradient logo. An image is stored once.
"""

from __future__ import annotations

import base64
import html
import json
import re
import struct
from functools import lru_cache
from importlib import resources
from pathlib import Path

_ICON_TAG_RE = re.compile(r"""<i\s+([^<>]*?\bdata-icon\s*=\s*["'][^"']*["'][^<>]*?)\s*>\s*</i>""")
_ATTR_RE = re.compile(r"""([\w-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_SEARCH_LIMIT = 60
_PREFIX = "pk-i-"
TONES = {"blue", "purple", "green", "teal", "orange", "success", "warning", "danger", "accent", "muted"}
_LUCIDE_SYMBOL = (
    'fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"'
)


class IconError(Exception):
    pass


@lru_cache(maxsize=1)
def _icons() -> dict:
    return json.loads(resources.files("pagekit").joinpath("static/lucide-icons.json").read_text(encoding="utf-8"))["icons"]


def _inline_style_rules(svg: str, path: Path) -> str:
    """Move a drawing tool's <style> rules onto their elements, so class names cannot collide."""
    rules: dict[str, str] = {}
    for block in re.findall(r"<style[^>]*>(.*?)</style>", svg, re.DOTALL):
        for selectors, body in re.findall(r"([^{}]+)\{([^{}]*)\}", block):
            declarations = " ".join(body.split()).rstrip(";")
            for selector in selectors.split(","):
                selector = selector.strip()
                if not re.fullmatch(r"\.[\w-]+", selector):
                    raise IconError(f"{path}: only plain .class rules are supported in <style>, not {selector!r}")
                existing = rules.get(selector[1:])
                rules[selector[1:]] = f"{existing}; {declarations}" if existing else declarations
    svg = re.sub(r"<style[^>]*>.*?</style>", "", svg, flags=re.DOTALL)

    def element(match: re.Match) -> str:
        tag = match.group(0)
        names = re.search(r'\sclass="([^"]*)"', tag)
        if not names:
            return tag
        styles = [rules[name] for name in names.group(1).split() if name in rules]
        tag = tag.replace(names.group(0), "", 1)
        if not styles:
            return tag
        return re.sub(r"^(<[\w:-]+)", lambda m: f'{m.group(1)} style="{"; ".join(styles)}"', tag, count=1)

    return re.sub(r"<[\w:-]+\b[^>]*>", element, svg)


def _custom_symbol(path: Path, symbol_id: str) -> str:
    svg = path.read_text(encoding="utf-8")
    if re.search(r"<script\b", svg, re.IGNORECASE):
        raise IconError(f"{path}: an icon cannot contain a script")
    svg = re.sub(r"<\?xml.*?\?>|<!--.*?-->", "", svg, flags=re.DOTALL)
    svg = _inline_style_rules(svg, path)
    opening = re.search(r"<svg\b([^>]*)>", svg)
    if not opening:
        raise IconError(f"{path}: not an SVG")
    box = re.search(r'viewBox="([^"]+)"', opening.group(1))
    if box:
        view_box = box.group(1)
    else:
        size = [re.search(rf'\b{key}="([\d.]+)', opening.group(1)) for key in ("width", "height")]
        if not all(size):
            raise IconError(f"{path}: needs a viewBox, or a width and height")
        view_box = f"0 0 {size[0].group(1)} {size[1].group(1)}"
    body = svg[opening.end() : svg.rindex("</svg>")]
    # Ids are namespaced, so two icons' gradients never collide.
    for found in set(re.findall(r'\bid="([^"]+)"', body)):
        new = f"{symbol_id}-{found}"
        body = body.replace(f'id="{found}"', f'id="{new}"')
        body = body.replace(f"url(#{found})", f"url(#{new})")
        body = re.sub(rf'(href=")#{re.escape(found)}"', rf'\g<1>#{new}"', body)
    return f'<symbol id="{symbol_id}" viewBox="{view_box}">{" ".join(body.split())}</symbol>'


def _print_symbol(path: Path, symbol_id: str) -> str:
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise IconError(f"{path}: must be a PNG")
    width, height = struct.unpack(">II", data[16:24])
    uri = "data:image/png;base64," + base64.b64encode(data).decode()
    return (
        f'<symbol id="{symbol_id}" viewBox="0 0 {width} {height}">'
        f'<image href="{uri}" width="{width}" height="{height}"/></symbol>'
    )


def custom_icons(profile) -> dict[str, dict[str, Path]]:
    """A profile's icons/NAME.svg files, nearest layer winning, with any dark and print versions."""
    found: dict[str, dict[str, Path]] = {}
    for directory in profile.dirs if profile else []:
        folder = directory / "icons"
        if not folder.is_dir():
            continue
        for path in sorted(folder.glob("*.svg")):
            if path.stem.endswith("-dark"):
                continue
            found[path.stem] = {"light": path}
            dark = folder / f"{path.stem}-dark.svg"
            if dark.is_file():
                found[path.stem]["dark"] = dark
            printed = folder / f"{path.stem}-print.png"
            if printed.is_file():
                found[path.stem]["print"] = printed
    return found


def expand_icons(document: str, profile=None) -> str:
    """Replace each <i data-icon="name"> with a reference, and add one symbol per icon used."""
    custom = custom_icons(profile)
    symbols: dict[str, str] = {}

    def lucide_use(name: str) -> str:
        symbol_id = f"{_PREFIX}{name}"
        body = _icons()[name]["body"]
        symbols.setdefault(symbol_id, f'<symbol id="{symbol_id}" viewBox="0 0 24 24" {_LUCIDE_SYMBOL}>{body}</symbol>')
        return f'<use href="#{symbol_id}"/>'

    def custom_uses(name: str) -> tuple[str, str]:
        light_id = f"{_PREFIX}{name}"
        files = custom[name]
        if light_id not in symbols:
            symbols[light_id] = _custom_symbol(files["light"], light_id)
        if len(files) == 1:
            return f'<use href="#{light_id}"/>', ""
        uses = f'<use class="pk-icon-light" href="#{light_id}"/>'
        if "dark" in files:
            dark_id = f"{light_id}-dark"
            symbols.setdefault(dark_id, _custom_symbol(files["dark"], dark_id))
            uses += f'<use class="pk-icon-dark" href="#{dark_id}"/>'
        if "print" in files:
            print_id = f"{light_id}-print"
            symbols.setdefault(print_id, _print_symbol(files["print"], print_id))
            uses += f'<use class="pk-icon-print" href="#{print_id}"/>'
        return uses, " pk-icon-paired"

    def tag(match: re.Match) -> str:
        attrs = {key: double or single for key, double, single in _ATTR_RE.findall(match.group(1))}
        name = attrs["data-icon"]
        tone = attrs.get("tone", "")
        if tone and tone not in TONES:
            raise IconError(f"unknown icon tone {tone!r}: use {', '.join(sorted(TONES))}")
        extra = ""
        if name in custom:
            uses, extra = custom_uses(name)
        elif name in _icons():
            uses = lucide_use(name)
        else:
            raise IconError(f"no icon named {name!r}: search with pagekit icons WORD")
        classes = f"pk-icon{extra}" + (f" pk-icon-{tone}" if tone else "")
        label = attrs.get("aria-label")
        access = f'role="img" aria-label="{html.escape(label)}"' if label else 'aria-hidden="true"'
        return f'<svg class="{classes}" {access}>{uses}</svg>'

    document = _ICON_TAG_RE.sub(tag, document)
    if not symbols:
        return document
    # Hidden by size, not display:none, which would break gradients inside symbols.
    sprite = f'<svg class="pk-sprite" aria-hidden="true">{"".join(symbols.values())}</svg>'
    end = document.rfind("</body>")
    return f"{document}{sprite}" if end < 0 else f"{document[:end]}{sprite}\n{document[end:]}"


def search_icons(query: str, profile=None) -> list[str]:
    """The profile's own icons, then exact tags and name matches, then partial tags."""
    words = query.lower().split()
    own = [name for name in custom_icons(profile) if all(word in name for word in words)]
    exact, named, partial = [], [], []
    for name, icon in sorted(_icons().items()):
        tags = [tag.lower() for tag in icon["tags"]]
        if all(word in tags or word in name.split("-") for word in words):
            exact.append(name)
        elif all(word in name for word in words):
            named.append(name)
        elif all(word in name or any(word in tag for tag in tags) for word in words):
            partial.append(name)
    return (own + exact + named + partial)[:_SEARCH_LIMIT]
