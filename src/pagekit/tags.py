"""Tags a page writes and the build replaces with generated content.

To add one, write a function that takes the tag's attributes and the page's headings and returns
HTML, then list it in _TAGS with the attributes it accepts. <pk-diagram> is handled in diagrams.py,
because it reads files and keeps a cache.
"""

from __future__ import annotations

import html
import re
from collections.abc import Callable
from dataclasses import dataclass
from html.parser import HTMLParser


class TagError(Exception):
    pass


@dataclass
class Heading:
    level: int
    id: str
    text: str


@dataclass
class _Found:
    level: int
    offset: int
    tag_length: int
    id: str
    text: str
    skip: bool


_TAG_RE = re.compile(r"<pk-([a-z][a-z0-9-]*)((?:\s+[a-z-]+(?:=\"[^\"]*\")?)*)\s*(?:/>|>\s*</pk-\1>)", re.IGNORECASE)
_OPEN_TAG_RE = re.compile(r"<pk-(?!diagram\b)([a-z][a-z0-9-]*)", re.IGNORECASE)
_ATTR_RE = re.compile(r"([a-z-]+)(?:=\"([^\"]*)\")?", re.IGNORECASE)
_HEADING_RE = re.compile(r"^h([1-6])$")
_NOT_SLUG_RE = re.compile(r"[^a-z0-9]+")
_NO_CONTENTS = "data-pk-no-contents"


class _Headings(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[_Found] = []
        self.ids: set[str] = set()
        self._current: _Found | None = None
        self._text: list[str] = []
        self._line_starts = [0]
        for match in re.finditer(r"\n", source):
            self._line_starts.append(match.end())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        match = _HEADING_RE.match(tag)
        if match:
            line, column = self.getpos()
            self._current = _Found(
                int(match.group(1)),
                self._line_starts[line - 1] + column,
                len(self.get_starttag_text() or ""),
                str(values.get("id") or ""),
                "",
                _NO_CONTENTS in values,
            )
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._current:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._current and _HEADING_RE.match(tag):
            self._current.text = " ".join("".join(self._text).split())
            self.found.append(self._current)
            self._current = None


def _slug(text: str, taken: set[str]) -> str:
    base = _NOT_SLUG_RE.sub("-", text.lower()).strip("-") or "section"
    candidate, number = base, 2
    while candidate in taken:
        candidate, number = f"{base}-{number}", number + 1
    taken.add(candidate)
    return candidate


def _with_ids(source: str) -> tuple[str, list[Heading]]:
    """Give every heading an id, since the links need one. Ids already on the page are kept."""
    parser = _Headings(source)
    parser.feed(source)
    parser.close()
    updated = source
    for item in reversed(parser.found):
        if item.id or item.skip or not item.text:
            continue
        item.id = _slug(item.text, parser.ids)
        at = item.offset + len(f"<h{item.level}")
        updated = f'{updated[:at]} id="{item.id}"{updated[at:]}'
    return updated, [Heading(f.level, f.id, f.text) for f in parser.found if not f.skip and f.text]


def _contents(attrs: dict[str, str], headings: list[Heading]) -> str:
    raw = attrs.get("max-level", "3")
    if not raw.isdigit() or not 1 <= int(raw) <= 6:
        raise TagError(f'<pk-contents>: max-level must be a number from 1 to 6, not "{raw}"')
    max_level = int(raw)
    # The page title is the only h1 on a normal page, so a list of contents starts below it.
    min_level = 1 if max_level == 1 else 2
    shown = [h for h in headings if min_level <= h.level <= max_level]
    if not shown:
        raise TagError(f"<pk-contents>: no headings from h{min_level} to h{max_level} on this page")
    title = attrs.get("title", "Contents")
    label = html.escape(title or "Contents", quote=True)
    parts = [f'<nav class="pk-contents" aria-label="{label}">']
    if title:
        parts.append(f'<p class="pk-contents-title">{html.escape(title)}</p>')
    depth: list[int] = []
    for heading in shown:
        if depth and heading.level <= depth[-1]:
            while depth and heading.level < depth[-1]:
                parts.append("</li></ol>")
                depth.pop()
            if depth:
                parts.append("</li>")
        if not depth or heading.level > depth[-1]:
            parts.append("<ol>")
            depth.append(heading.level)
        parts.append(f'<li><a href="#{html.escape(heading.id, quote=True)}">{html.escape(heading.text)}</a>')
    parts.append("</li></ol>" * len(depth))
    parts.append("</nav>")
    return "".join(parts)


_TAGS: dict[str, tuple[Callable[[dict[str, str], list[Heading]], str], set[str]]] = {
    "contents": (_contents, {"max-level", "title"}),
}


def expand_tags(source: str) -> str:
    """Replace each generated tag in a page's content. A page with none comes back untouched."""
    if not _OPEN_TAG_RE.search(source):
        return source
    updated, headings = _with_ids(source)

    def replace(match: re.Match) -> str:
        name = match.group(1).lower()
        if name == "diagram":
            return match.group(0)
        if name not in _TAGS:
            raise TagError(f"unknown tag <pk-{name}>: available tags are {', '.join(f'<pk-{t}>' for t in sorted(_TAGS))}")
        render, allowed = _TAGS[name]
        attrs = {key.lower(): value for key, value in _ATTR_RE.findall(match.group(2))}
        unknown = sorted(set(attrs) - allowed)
        if unknown:
            raise TagError(f"<pk-{name}> has no attribute {unknown[0]!r}: it takes {', '.join(sorted(allowed))}")
        return render(attrs, headings)

    expanded = _TAG_RE.sub(replace, updated)
    leftover = _OPEN_TAG_RE.search(expanded)
    if leftover:
        raise TagError(f'<pk-{leftover.group(1)}> is malformed: write it as <pk-{leftover.group(1)} name="value"></pk-{leftover.group(1)}>')
    return expanded
