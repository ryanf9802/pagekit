"""Lucide icons, vendored as one file. A page embeds only the icons it uses, so it stays offline."""

from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from importlib import resources

_ICON_TAG_RE = re.compile(r"""<i\s+data-icon\s*=\s*["']([a-z0-9-]+)["']\s*(?:aria-label\s*=\s*["']([^"']*)["']\s*)?>\s*</i>""")
_SEARCH_LIMIT = 60


class IconError(Exception):
    pass


@lru_cache(maxsize=1)
def _icons() -> dict:
    return json.loads(resources.files("pagekit").joinpath("static/lucide-icons.json").read_text())["icons"]


def icon_svg(name: str, label: str | None = None) -> str:
    icon = _icons().get(name)
    if icon is None:
        raise IconError(f"no icon named {name!r}: search with pagekit icons WORD")
    access = f'role="img" aria-label="{html.escape(label)}"' if label else 'aria-hidden="true"'
    return (
        f'<svg class="pk-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" {access}>'
        f'{icon["body"]}</svg>'
    )


def expand_icons(document: str) -> str:
    """Replace each <i data-icon="name"></i> with that icon's SVG."""
    return _ICON_TAG_RE.sub(lambda m: icon_svg(m.group(1), m.group(2)), document)


def search_icons(query: str) -> list[str]:
    """Exact tags and name matches lead, then partial tags, so common words find common icons."""
    words = query.lower().split()
    exact, named, partial = [], [], []
    for name, icon in sorted(_icons().items()):
        tags = [tag.lower() for tag in icon["tags"]]
        if all(word in tags or word in name.split("-") for word in words):
            exact.append(name)
        elif all(word in name for word in words):
            named.append(name)
        elif all(word in name or any(word in tag for tag in tags) for word in words):
            partial.append(name)
    return (exact + named + partial)[:_SEARCH_LIMIT]
