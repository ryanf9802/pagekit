"""Tags a page writes and the build replaces with generated content.

To add one, write a function that takes the tag's attributes and the page's headings and returns
HTML, then list it in _TAGS with the attributes it accepts. <pk-diagram> and <pk-chart> are handled in
diagrams.py and charts.py, because they read files. A tag that takes lines of content, like <pk-table>,
is listed in _BODY_TAGS instead: its function also gets the body and the page line the body starts on.
"""

from __future__ import annotations

import html
import math
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
    line: int = 0


_TAG_RE = re.compile(
    r"<pk-([a-z][a-z0-9-]*)((?:\s+[a-z-]+(?:=\"[^\"]*\")?)*)\s*(?:/>|>(.*?)</pk-\1>)", re.IGNORECASE | re.DOTALL
)
_FILE_TAGS = {"diagram", "chart"}
_OPEN_TAG_RE = re.compile(r"<pk-(?!(?:diagram|chart)\b)([a-z][a-z0-9-]*)", re.IGNORECASE)
_ATTR_RE = re.compile(r"([a-z-]+)(?:=\"([^\"]*)\")?", re.IGNORECASE)
_HEADING_RE = re.compile(r"^h([1-6])$")
_NOT_SLUG_RE = re.compile(r"[^a-z0-9]+")
_NO_CONTENTS = "data-pk-no-contents"


class _Headings(HTMLParser):
    def __init__(self, source: str) -> None:
        super().__init__(convert_charrefs=True)
        self.found: list[_Found] = []
        self.ids: set[str] = set()
        self.items: list[tuple[int, str]] = []
        self._item_line = 0
        self._item_text: list[str] = []
        self._current: _Found | None = None
        self._text: list[str] = []
        self._line_starts = [0]
        for match in re.finditer(r"\n", source):
            self._line_starts.append(match.end())

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.add(str(values["id"]))
        line, column = self.getpos()
        if tag in ("figure", "article") and values.get("id"):
            self.items.append((line, str(values["id"])))
        if tag == "span" and "pk-id" in str(values.get("class") or "").split():
            self._item_line, self._item_text = line, []
        match = _HEADING_RE.match(tag)
        if match:
            self._current = _Found(
                int(match.group(1)),
                self._line_starts[line - 1] + column,
                len(self.get_starttag_text() or ""),
                str(values.get("id") or ""),
                "",
                _NO_CONTENTS in values,
                line,
            )
            self._text = []

    def handle_data(self, data: str) -> None:
        if self._current:
            self._text.append(data)
        if self._item_line:
            self._item_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self._item_line and tag == "span":
            if text := " ".join("".join(self._item_text).split()):
                self.items.append((self._item_line, text))
            self._item_line = 0
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


def outline(source: str) -> list[tuple[int, int, str]]:
    """The h2 to h4 headings and item IDs of a page's content as (line, level, text), in page order.

    The level is 0 for an item ID.
    """
    parser = _Headings(source)
    parser.feed(source)
    parser.close()
    rows = [(f.line, f.level, f.text) for f in parser.found if 2 <= f.level <= 4 and f.text]
    rows.extend((line, 0, text) for line, text in parser.items)
    return sorted(rows, key=lambda row: row[0])


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


# The drawing is stretched to the width of its tile, so x runs the full width and only y has padding.
# Strokes do not scale (see theme.css), which keeps the line even and the end dot round.
_SPARK_W, _SPARK_H, _SPARK_PAD = 96, 28, 3
_SPARK_MIN_POINTS, _SPARK_MAX_POINTS = 2, 60


def _number(value: float) -> str:
    return f"{value:g}"


def _spark(attrs: dict[str, str], headings: list[Heading]) -> str:
    raw = attrs.get("values", "")
    try:
        values = [float(part) for part in raw.split(",")] if raw.strip() else []
    except ValueError:
        raise TagError(f'<pk-spark>: values must be numbers separated by commas, not "{raw}"') from None
    if not _SPARK_MIN_POINTS <= len(values) <= _SPARK_MAX_POINTS or not all(math.isfinite(v) for v in values):
        raise TagError(f"<pk-spark>: values needs {_SPARK_MIN_POINTS} to {_SPARK_MAX_POINTS} numbers, e.g. values=\"3,5,4,8\"")
    low, high = min(values), max(values)
    span = high - low
    inner_h = _SPARK_H - 2 * _SPARK_PAD
    points = []
    for index, value in enumerate(values):
        x = _SPARK_W * index / (len(values) - 1)
        y = _SPARK_PAD + inner_h * (0.5 if span == 0 else 1 - (value - low) / span)
        points.append((x, y))
    line = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
    end_x, end_y = points[-1]
    summary = f"{len(values)} points, from {_number(values[0])} to {_number(values[-1])}, low {_number(low)}, high {_number(high)}"
    label = attrs.get("label", "").strip()
    text = html.escape(f"{label}: {summary}" if label else f"Trend: {summary}", quote=True)
    return (
        f'<svg class="pk-spark" viewBox="0 0 {_SPARK_W} {_SPARK_H}" height="{_SPARK_H}" preserveAspectRatio="none" '
        f'role="img" aria-label="{text}"><polyline class="pk-spark-line" points="{line}"/>'
        f'<line class="pk-spark-end" x1="{end_x:.1f}" y1="{end_y:.1f}" x2="{end_x:.1f}" y2="{end_y:.1f}"/></svg>'
    )


_CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")


def _table(attrs: dict[str, str], body: str, first_line: int) -> str:
    """Lines of cells split by |, as the same markup the table component shows."""
    if "<pk-table" in body.lower():
        raise TagError("<pk-table> is not closed before the next <pk-table> starts: end each one with </pk-table>")
    rows: list[tuple[int, list[str]]] = []
    for offset, line in enumerate(body.split("\n")):
        if line.strip():
            cells = [cell.replace("\\|", "|").strip() for cell in _CELL_SPLIT_RE.split(line)]
            rows.append((first_line + offset, cells))
    if not rows:
        raise TagError(f"<pk-table> on line {first_line}: no rows; write one line per row with cells split by |")
    header: list[str] | None = None
    if "no-header" not in attrs:
        header = rows.pop(0)[1]
    width = len(header) if header is not None else max(len(cells) for _, cells in rows)
    for number, cells in rows:
        if len(cells) > width:
            raise TagError(
                f"<pk-table> line {number}: {len(cells)} cells but the table has {width} columns; "
                "write a literal | inside a cell as \\|"
            )
    out = ['<div class="pk-table-wrap">', "  <table>"]
    if header is not None:
        out.append("    <thead><tr>" + "".join(f"<th>{cell}</th>" for cell in header) + "</tr></thead>")
    out.append("    <tbody>")
    for _, cells in rows:
        cells = cells + [""] * (width - len(cells))
        out.append("      <tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")
    out += ["    </tbody>", "  </table>", "</div>"]
    return "\n".join(out)


_BODY_TAGS: dict[str, tuple[Callable[[dict[str, str], str, int], str], set[str]]] = {
    "table": (_table, {"no-header"}),
}

_TAGS: dict[str, tuple[Callable[[dict[str, str], list[Heading]], str], set[str]]] = {
    "contents": (_contents, {"max-level", "title"}),
    "spark": (_spark, {"values", "label"}),
}


def expand_tags(source: str) -> str:
    """Replace each generated tag in a page's content. A page with none comes back untouched."""
    if not _OPEN_TAG_RE.search(source):
        return source
    updated, headings = _with_ids(source)
    source = updated

    def replace(match: re.Match) -> str:
        name = match.group(1).lower()
        if name in _FILE_TAGS:
            return match.group(0)
        if name not in _TAGS and name not in _BODY_TAGS:
            names = sorted([*_TAGS, *_BODY_TAGS])
            raise TagError(f"unknown tag <pk-{name}>: available tags are {', '.join(f'<pk-{t}>' for t in names)}")
        allowed = _TAGS[name][1] if name in _TAGS else _BODY_TAGS[name][1]
        attrs = {key.lower(): value for key, value in _ATTR_RE.findall(match.group(2))}
        unknown = sorted(set(attrs) - allowed)
        if unknown:
            raise TagError(f"<pk-{name}> has no attribute {unknown[0]!r}: it takes {', '.join(sorted(allowed))}")
        body = match.group(3) or ""
        if name in _BODY_TAGS:
            return _BODY_TAGS[name][0](attrs, body, source.count("\n", 0, match.start(3)) + 1)
        if body.strip():
            raise TagError(f"<pk-{name}> takes no content: write it as <pk-{name}></pk-{name}>")
        return _TAGS[name][0](attrs, headings)

    expanded = _TAG_RE.sub(replace, source)
    leftover = _OPEN_TAG_RE.search(expanded)
    if leftover and leftover.group(1).lower() in _BODY_TAGS:
        raise TagError(f"<pk-{leftover.group(1)}> is never closed: end it with </pk-{leftover.group(1)}>")
    if leftover:
        raise TagError(f'<pk-{leftover.group(1)}> is malformed: write it as <pk-{leftover.group(1)} name="value"></pk-{leftover.group(1)}>')
    return expanded
