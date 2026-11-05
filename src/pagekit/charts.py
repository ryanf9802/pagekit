"""Data charts as themed inline SVG, drawn at build time so pages stay offline.

An author writes assets/NAME.json and <pk-chart src="assets/NAME.json"></pk-chart>. The build draws the
chart in plain Python, with no browser and no script. Every color comes from a class styled in the theme
through --pk-* tokens, so a chart follows the theme in light mode, dark mode, and print.

To add a chart type, write a function that takes the checked spec and returns the SVG's inner markup, then
list it in _DRAW and in _TYPES, with the series cap it needs in _MAX_SERIES.
"""

from __future__ import annotations

import html
import json
import math
import re
from pathlib import Path


class ChartError(Exception):
    pass


_TAG_RE = re.compile(
    r"""<pk-chart\s+src\s*=\s*["']assets/([a-z0-9][a-z0-9-]*\.json)["']"""
    r"""(?:\s+class\s*=\s*["']([^"']*)["'])?\s*>(.*?)</pk-chart>""",
    re.DOTALL,
)
_TYPES = ("bar", "line", "area", "scatter", "pie")
_KEYS = {"type", "title", "desc", "labels", "series", "x_label", "y_label", "unit", "horizontal"}
_SERIES_KEYS = {"category": {"name", "values"}, "scatter": {"name", "points"}}
# Past these the colors stop being easy to tell apart. Scatter and area overlap, so they cap at three.
_MAX_SERIES = {"bar": 6, "line": 6, "area": 3, "scatter": 3}
_MAX_LABELS = {"bar": 30, "line": 120, "area": 120}
_MAX_POINTS = 1000
_PIE_SLICES = (3, 6)
_UNIT_MAX = 8

# Drawing sizes are in SVG units. The chart scales to its container, so text is about 10px on a phone.
_W = 420
_H = 260
_HEADROOM = 16
_BAR_MAX = 24
_BAR_H = 20
_GAP = 2
_ROUND = 4
_TEXT_W = 6.8


def _reject_constant(name: str) -> None:
    raise ValueError(f"{name} is not a number")


def _is_number(value: object) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and math.isfinite(value)


def _text(value: object, key: str, name: str, required: bool = False) -> str:
    if value is None or value == "":
        if required:
            raise ChartError(f"assets/{name}: {key} is required")
        return ""
    if not isinstance(value, str) or not value.strip():
        raise ChartError(f"assets/{name}: {key} must be text")
    return value.strip()


def parse_spec(name: str, source: str) -> dict:
    """Read and check a chart's JSON. Every mistake says what to fix."""
    try:
        spec = json.loads(source, parse_constant=_reject_constant)
    except ValueError as exc:
        raise ChartError(f"assets/{name}: not valid JSON ({exc})") from None
    if not isinstance(spec, dict):
        raise ChartError(f"assets/{name}: the file must hold one JSON object")
    unknown = sorted(set(spec) - _KEYS)
    if unknown:
        raise ChartError(f"assets/{name}: unknown key {unknown[0]!r}: it takes {', '.join(sorted(_KEYS))}")
    kind = spec.get("type")
    if kind not in _TYPES:
        raise ChartError(f"assets/{name}: type must be one of {', '.join(_TYPES)}, not {kind!r}")
    spec["title"] = _text(spec.get("title"), "title", name, required=True)
    spec["desc"] = _text(spec.get("desc"), "desc", name, required=True)
    for key in ("x_label", "y_label"):
        spec[key] = _text(spec.get(key), key, name)
    # Kept as written, because a leading space is part of a unit such as " s".
    spec["unit"] = spec.get("unit") or ""
    if not isinstance(spec["unit"], str) or len(spec["unit"]) > _UNIT_MAX:
        raise ChartError(f"assets/{name}: unit is text of at most {_UNIT_MAX} characters, such as % or ' s'")
    if "horizontal" in spec and (kind != "bar" or not isinstance(spec["horizontal"], bool)):
        raise ChartError(f"assets/{name}: horizontal is true or false, and only a bar chart takes it")
    spec.setdefault("horizontal", False)
    series = spec.get("series")
    if not isinstance(series, list) or not series:
        raise ChartError(f"assets/{name}: series must be a list with at least one series")
    if kind == "scatter":
        _check_scatter(name, spec, series)
    else:
        _check_categories(name, spec, series)
    if kind == "pie":
        _check_pie(name, spec)
    elif len(series) > _MAX_SERIES[kind]:
        raise ChartError(
            f"assets/{name}: a {kind} chart takes at most {_MAX_SERIES[kind]} series, because more colors are hard to tell "
            "apart: fold the smallest into one called Other, or draw several charts"
        )
    names = [s["name"] for s in series]
    if len(set(names)) != len(names):
        raise ChartError(f"assets/{name}: series names must be different from each other")
    return spec


def _check_series_keys(name: str, kind: str, series: list) -> None:
    allowed = _SERIES_KEYS["scatter" if kind == "scatter" else "category"]
    for item in series:
        if not isinstance(item, dict):
            raise ChartError(f"assets/{name}: each series is an object with {' and '.join(sorted(allowed))}")
        unknown = sorted(set(item) - allowed)
        if unknown:
            raise ChartError(f"assets/{name}: a series has no key {unknown[0]!r}: it takes {', '.join(sorted(allowed))}")
        item["name"] = _text(item.get("name"), "a series name", name, required=True)


def _check_categories(name: str, spec: dict, series: list) -> None:
    kind = spec["type"]
    labels = spec.get("labels")
    if not isinstance(labels, list) or not all(isinstance(label, str) and label.strip() for label in labels):
        raise ChartError(f"assets/{name}: labels must be a list of text, one for each value")
    need = {"line": 2, "area": 2, "pie": _PIE_SLICES[0]}.get(kind, 1)
    most = _MAX_LABELS.get(kind, _PIE_SLICES[1])
    if kind == "pie" and len(labels) == 2:
        raise ChartError(f"assets/{name}: a pie of two slices says less than two numbers: use kpi tiles, or a bar chart")
    if not need <= len(labels) <= most:
        raise ChartError(f"assets/{name}: a {kind} chart needs {need} to {most} labels, not {len(labels)}")
    spec["labels"] = [label.strip() for label in labels]
    _check_series_keys(name, kind, series)
    for item in series:
        values = item.get("values")
        if not isinstance(values, list) or len(values) != len(labels) or not all(_is_number(v) for v in values):
            raise ChartError(f"assets/{name}: series {item['name']!r} needs {len(labels)} numbers in values, one for each label")


def _check_scatter(name: str, spec: dict, series: list) -> None:
    if "labels" in spec:
        raise ChartError(f"assets/{name}: a scatter chart has no labels: give each series its points as [x, y] pairs")
    _check_series_keys(name, "scatter", series)
    total = 0
    for item in series:
        points = item.get("points")
        ok = isinstance(points, list) and points
        ok = ok and all(isinstance(p, list) and len(p) == 2 and all(_is_number(v) for v in p) for p in points)
        if not ok:
            raise ChartError(f"assets/{name}: series {item['name']!r} needs points, a list of [x, y] number pairs")
        total += len(points)
    if total > _MAX_POINTS:
        raise ChartError(f"assets/{name}: a scatter chart takes at most {_MAX_POINTS} points, not {total}")


def _check_pie(name: str, spec: dict) -> None:
    if len(spec["series"]) != 1:
        raise ChartError(f"assets/{name}: a pie chart has one series, whose values are the slices")
    values = spec["series"][0]["values"]
    if any(v < 0 for v in values) or sum(values) <= 0:
        raise ChartError(f"assets/{name}: pie values must not be negative, and must add up to more than zero")


# --- numbers on the page ---------------------------------------------------------------------------------


def _step(span: float, count: int) -> float:
    raw = span / max(count, 1)
    exponent = math.floor(math.log10(raw))
    fraction = raw / 10**exponent
    for nice in (1, 2, 5, 10):
        if fraction <= nice:
            return nice * 10**exponent
    return 10 ** (exponent + 1)


def nice_ticks(low: float, high: float, count: int = 5) -> list[float]:
    """Round axis values that cover low to high."""
    if high == low:
        high = low + (abs(low) or 1)
    step = _step(high - low, count)
    first = math.floor(low / step + 1e-9) * step
    last = math.ceil(high / step - 1e-9) * step
    return [round(first + i * step, 10) for i in range(round((last - first) / step) + 1)]


def plain(value: float) -> str:
    """A number as written in a table: exact, with thousands separators."""
    return f"{value:,.10g}"


def compact(value: float) -> str:
    for size, suffix in ((1e9, "B"), (1e6, "M"), (1e3, "K")):
        if abs(value) >= size:
            return f"{round(value / size, 2):g}{suffix}"
    return plain(value)


def short(value: float, unit: str) -> str:
    return f"{compact(value) if abs(value) >= 10_000 else plain(value)}{unit}"


def tick_text(ticks: list[float], unit: str) -> list[str]:
    """One style for a whole axis: in full under 10,000, compact once it reaches that."""
    big = max(abs(t) for t in ticks) >= 10_000
    step = abs(ticks[1] - ticks[0]) if len(ticks) > 1 else 1
    places = min(4, max(0, -math.floor(math.log10(step))))
    return [(compact(t) if big else f"{t:,.{places}f}") + unit for t in ticks]


def _f(value: float) -> str:
    text = f"{value:.1f}"
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return "0" if text in ("", "-0") else text


def _esc(text: str) -> str:
    return html.escape(text, quote=True)


def _width(text: str) -> float:
    return _TEXT_W * len(text)


def _clip(text: str, limit: int) -> str:
    """Cut a long name short with three dots. They are ASCII, because a page's own text must be (ascii_only)."""
    return text if len(text) <= limit else text[: limit - 3].rstrip() + "..."


# --- shapes ----------------------------------------------------------------------------------------------


def _label(x: float, y: float, text: str, css: str, anchor: str = "middle") -> str:
    return f'<text class="{css}" x="{_f(x)}" y="{_f(y)}" text-anchor="{anchor}">{_esc(text)}</text>'


def _line(css: str, x1: float, y1: float, x2: float, y2: float) -> str:
    return f'<line class="{css}" x1="{_f(x1)}" y1="{_f(y1)}" x2="{_f(x2)}" y2="{_f(y2)}"/>'


def column_path(x: float, base: float, end: float, width: float) -> str:
    """A column that is square at its baseline and rounded at its far end."""
    r = min(_ROUND, width / 2, abs(end - base))
    sweep, near = (1, end + r) if end < base else (0, end - r)
    return (
        f"M{_f(x)},{_f(base)} V{_f(near)} A{_f(r)},{_f(r)} 0 0 {sweep} {_f(x + r)},{_f(end)} "
        f"H{_f(x + width - r)} A{_f(r)},{_f(r)} 0 0 {sweep} {_f(x + width)},{_f(near)} V{_f(base)} Z"
    )


def row_path(base: float, end: float, y: float, height: float) -> str:
    """A bar that is square at its baseline and rounded at its far end."""
    r = min(_ROUND, height / 2, abs(end - base))
    sweep, near = (1, end - r) if end > base else (0, end + r)
    return (
        f"M{_f(base)},{_f(y)} H{_f(near)} A{_f(r)},{_f(r)} 0 0 {sweep} {_f(end)},{_f(y + r)} "
        f"V{_f(y + height - r)} A{_f(r)},{_f(r)} 0 0 {sweep} {_f(near)},{_f(y + height)} H{_f(base)} Z"
    )


def _top(spec: dict) -> float:
    """Where the plot starts. The same for every type, so charts of different types line up in a row.

    The headroom is where a bar chart prints its value labels; the other types leave it empty.
    """
    return 10 + (16 if spec["y_label"] else 0) + _HEADROOM


def _key(index: int) -> str:
    return f"pk-chart-s{index + 1}"


def _tip(title: str, rows: list[tuple[str, str, int]], swatch: int = 0) -> str:
    """The text a tooltip shows, as the data-tip attribute that the page script reads.

    Each row is a name, a value, and the series number whose color marks it (0 for none). The script only
    displays this, so a page without it, in print or a PDF, shows the plain chart.
    """
    data: dict = {"t": title, "r": [list(row) for row in rows]}
    if swatch:
        data["s"] = swatch
    return f' data-tip="{_esc(json.dumps(data, separators=(",", ":"), ensure_ascii=False))}"'


def _hit(css: str, x: float, y: float, width: float, height: float, tip: str) -> str:
    return f'<rect class="{css}" x="{_f(x)}" y="{_f(y)}" width="{_f(width)}" height="{_f(height)}"{tip}/>'


def _range(spec: dict, zero: bool) -> tuple[float, float]:
    values = [v for s in spec["series"] for v in s["values"]]
    low, high = min(values), max(values)
    return (min(low, 0), max(high, 0)) if zero else (low, high)


# --- chart types -----------------------------------------------------------------------------------------


def _draw_columns(spec: dict) -> tuple[str, int]:
    kind, labels, series, unit = spec["type"], spec["labels"], spec["series"], spec["unit"]
    ticks = nice_ticks(*_range(spec, zero=kind != "line"))
    texts = tick_text(ticks, unit)
    labelled = kind == "bar" and len(series) == 1 and len(labels) <= 12
    # A line or area runs edge to edge, with its first and last points on the edges of the plot. A bar needs room
    # on both sides, so each label owns a band and the bars sit in the middle. Either way the labels sit under
    # the marks, so an end label's margin grows to keep it from being clipped at the edge of the drawing.
    edge_to_edge = kind != "bar"
    # The axis numbers sit a little further out when a point can land on the edge, so a dot never touches one.
    gap = 10 if edge_to_edge else 6
    left = 4 + gap + max(_width(t) for t in texts)
    right = 12
    if edge_to_edge:
        left, right = max(left, _width(labels[0]) / 2 + 4), max(right, _width(labels[-1]) / 2 + 4)
    top = _top(spec)
    bottom = 26 + (18 if spec["x_label"] else 0)
    x0, x1, y0, y1 = left, _W - right, top, _H - bottom
    low, high = ticks[0], ticks[-1]

    def at(value: float) -> float:
        return y1 - (value - low) / (high - low) * (y1 - y0)

    # The distance between neighbouring marks, and where label i's mark is.
    slot = (x1 - x0) / (len(labels) - 1 if edge_to_edge else len(labels))

    def pos(i: int) -> float:
        return x0 + slot * i if edge_to_edge else x0 + slot * (i + 0.5)

    out = []
    if spec["y_label"]:
        out.append(_label(4, 12, spec["y_label"], "pk-chart-axis-title", "start"))
    for tick, text in zip(ticks, texts, strict=True):
        out += [_line("pk-chart-grid", x0, at(tick), x1, at(tick)), _label(x0 - gap, at(tick) + 4, text, "pk-chart-tick", "end")]
    base = at(0) if low <= 0 <= high else y1
    out.append(_line("pk-chart-axis", x0, base, x1, base))
    every = max(1, math.ceil((max(_width(label) for label in labels) + 8) / slot))
    out += [_label(pos(i), y1 + 16, label, "pk-chart-tick") for i, label in enumerate(labels) if i % every == 0]
    if spec["x_label"]:
        out.append(_label((x0 + x1) / 2, _H - 4, spec["x_label"], "pk-chart-axis-title"))

    # One band for each label, over the whole plot, so the reader never has to hit a thin bar or a small dot.
    hits = []
    for i, label in enumerate(labels):
        rows = [(item["name"], plain(item["values"][i]) + unit, j + 1) for j, item in enumerate(series)]
        cross = "" if kind == "bar" else _line("pk-chart-cross", pos(i), y0, pos(i), y1)
        # The band covers half the way to each neighbour, and stops at the edge of the plot.
        start, end = max(x0, pos(i) - slot / 2), min(x1, pos(i) + slot / 2)
        band = _hit("pk-chart-hit", start, y0 - _HEADROOM, end - start, y1 - y0 + _HEADROOM, _tip(label, rows))
        hits.append(f'<g class="pk-chart-point">{cross}{band}</g>')

    if kind == "bar":
        thick = min(_BAR_MAX, (slot * 0.72 - _GAP * (len(series) - 1)) / len(series))
        group = len(series) * thick + _GAP * (len(series) - 1)
        for i in range(len(labels)):
            start = pos(i) - group / 2
            for j, item in enumerate(series):
                value = item["values"][i]
                if value == 0:
                    continue
                x = start + j * (thick + _GAP)
                out.append(f'<path class="pk-chart-bar {_key(j)}" d="{column_path(x, at(0), at(value), thick)}"/>')
                if labelled:
                    out.append(_label(x + thick / 2, at(value) - 5 if value > 0 else at(value) + 15, short(value, unit), "pk-chart-value"))
        return "".join(out + hits), _H

    dots = []
    for j, item in enumerate(series):
        points = [(pos(i), at(v)) for i, v in enumerate(item["values"])]
        path = " ".join(f"{_f(x)},{_f(y)}" for x, y in points)
        if kind == "area":
            edge = f"M{_f(points[0][0])},{_f(base)} L{path.replace(' ', ' L')} L{_f(points[-1][0])},{_f(base)} Z"
            out.append(f'<path class="pk-chart-wash {_key(j)}" d="{edge}"/>')
        out.append(f'<polyline class="pk-chart-line {_key(j)}" points="{path}"/>')
        shown = points if len(points) <= 12 else points[-1:]
        dots += [f'<circle class="pk-chart-dot {_key(j)}" cx="{_f(x)}" cy="{_f(y)}" r="4"/>' for x, y in shown]
    return "".join(out + dots + hits), _H


def _draw_rows(spec: dict) -> tuple[str, int]:
    labels, series, unit = spec["labels"], spec["series"], spec["unit"]
    ticks = nice_ticks(*_range(spec, zero=True))
    texts = tick_text(ticks, unit)
    shown = [_clip(label, 24) for label in labels]
    labelled = len(series) == 1
    left = 10 + min(max(_width(label) for label in shown), 160)
    tips = [short(v, unit) for item in series for v in item["values"]]
    right = 12 + (max(_width(t) for t in tips) + 6 if labelled else 0)
    top = _top(spec)
    bottom = 26 + (18 if spec["x_label"] else 0)
    slot = len(series) * _BAR_H + _GAP * (len(series) - 1) + 14
    height = top + slot * len(labels) + bottom
    x0, x1, y0, y1 = left, _W - right, top, height - bottom
    low, high = ticks[0], ticks[-1]

    def at(value: float) -> float:
        return x0 + (value - low) / (high - low) * (x1 - x0)

    out = []
    if spec["y_label"]:
        out.append(_label(4, 12, spec["y_label"], "pk-chart-axis-title", "start"))
    for tick, text in zip(ticks, texts, strict=True):
        out += [_line("pk-chart-grid", at(tick), y0, at(tick), y1), _label(at(tick), y1 + 16, text, "pk-chart-tick")]
    base = at(0) if low <= 0 <= high else x0
    out.append(_line("pk-chart-axis", base, y0, base, y1))
    if spec["x_label"]:
        out.append(_label((x0 + x1) / 2, height - 4, spec["x_label"], "pk-chart-axis-title"))
    hits = []
    for i, label in enumerate(shown):
        top_of_row = y0 + slot * i + 7
        group = len(series) * _BAR_H + _GAP * (len(series) - 1)
        rows = [(item["name"], plain(item["values"][i]) + unit, j + 1) for j, item in enumerate(series)]
        band = _hit("pk-chart-hit", x0, y0 + slot * i, _W - x0, slot, _tip(labels[i], rows))
        hits.append(f'<g class="pk-chart-point">{band}</g>')
        out.append(_label(x0 - 8, top_of_row + group / 2 + 4, label, "pk-chart-tick", "end"))
        for j, item in enumerate(series):
            value = item["values"][i]
            y = top_of_row + j * (_BAR_H + _GAP)
            if value != 0:
                out.append(f'<path class="pk-chart-bar {_key(j)}" d="{row_path(at(0), at(value), y, _BAR_H)}"/>')
            if labelled:
                tip, anchor = (at(value) + 6, "start") if value >= 0 else (at(value) - 6, "end")
                out.append(_label(tip, y + _BAR_H / 2 + 4, short(value, unit), "pk-chart-value", anchor))
    return "".join(out + hits), round(height)


def _draw_scatter(spec: dict) -> tuple[str, int]:
    series, unit = spec["series"], spec["unit"]
    xs = [p[0] for s in series for p in s["points"]]
    ys = [p[1] for s in series for p in s["points"]]
    xticks, yticks = nice_ticks(min(xs), max(xs)), nice_ticks(min(ys), max(ys))
    ytexts, xtexts = tick_text(yticks, unit), tick_text(xticks, "")
    left = 10 + max(_width(t) for t in ytexts)
    top = _top(spec)
    bottom = 26 + (18 if spec["x_label"] else 0)
    x0, x1, y0, y1 = left, _W - 16, top, _H - bottom

    def at_x(value: float) -> float:
        return x0 + (value - xticks[0]) / (xticks[-1] - xticks[0]) * (x1 - x0)

    def at_y(value: float) -> float:
        return y1 - (value - yticks[0]) / (yticks[-1] - yticks[0]) * (y1 - y0)

    out = []
    if spec["y_label"]:
        out.append(_label(4, 12, spec["y_label"], "pk-chart-axis-title", "start"))
    for tick, text in zip(yticks, ytexts, strict=True):
        out += [_line("pk-chart-grid", x0, at_y(tick), x1, at_y(tick)), _label(x0 - 6, at_y(tick) + 4, text, "pk-chart-tick", "end")]
    for tick, text in zip(xticks, xtexts, strict=True):
        out += [_line("pk-chart-grid", at_x(tick), y0, at_x(tick), y1), _label(at_x(tick), y1 + 16, text, "pk-chart-tick")]
    out.append(_line("pk-chart-axis", x0, y1, x1, y1))
    if spec["x_label"]:
        out.append(_label((x0 + x1) / 2, _H - 4, spec["x_label"], "pk-chart-axis-title"))
    for j, item in enumerate(series):
        out += [
            f'<circle class="pk-chart-dot {_key(j)}" cx="{_f(at_x(x))}" cy="{_f(at_y(y))}" r="4.5"/>' for x, y in item["points"]
        ]
    # A larger target around each dot, drawn last so it is on top.
    for j, item in enumerate(series):
        for x, y in item["points"]:
            tip = _tip(item["name"], [("X", plain(x), 0), ("Y", plain(y) + unit, 0)], swatch=j + 1)
            out.append(f'<circle class="pk-chart-hit pk-chart-hit-dot {_key(j)}" cx="{_f(at_x(x))}" cy="{_f(at_y(y))}" r="10"{tip}/>')
    return "".join(out), _H


def _draw_pie(spec: dict) -> tuple[str, int]:
    values, unit = spec["series"][0]["values"], spec["unit"]
    total, centre, radius = sum(values), 100, 98
    drawn = [(i, v) for i, v in enumerate(values) if v > 0]

    def tip(i: int, value: float) -> str:
        rows = [(spec["series"][0]["name"], plain(value) + unit, i + 1), ("Share", _share(value, total), 0)]
        return _tip(spec["labels"][i], rows)

    if len(drawn) == 1:
        i, value = drawn[0]
        return f'<circle class="pk-chart-slice {_key(i)}" cx="{centre}" cy="{centre}" r="{radius}"{tip(i, value)}/>', 200
    out, angle = [], -math.pi / 2
    for i, value in drawn:
        sweep = value / total * 2 * math.pi
        x1, y1 = centre + radius * math.cos(angle), centre + radius * math.sin(angle)
        x2, y2 = centre + radius * math.cos(angle + sweep), centre + radius * math.sin(angle + sweep)
        big = 1 if sweep > math.pi else 0
        path = f"M{centre},{centre} L{_f(x1)},{_f(y1)} A{radius},{radius} 0 {big} 1 {_f(x2)},{_f(y2)} Z"
        out.append(f'<path class="pk-chart-slice {_key(i)}" d="{path}"{tip(i, value)}/>')
        angle += sweep
    return "".join(out), 200


def _draw(spec: dict) -> tuple[str, int, int]:
    """The SVG's inner markup, its height, and its width."""
    kind = spec["type"]
    if kind == "pie":
        inner, height = _draw_pie(spec)
        return inner, height, 200
    if kind == "scatter":
        inner, height = _draw_scatter(spec)
    elif kind == "bar" and spec["horizontal"]:
        inner, height = _draw_rows(spec)
    else:
        inner, height = _draw_columns(spec)
    return inner, height, _W


# --- the figure ------------------------------------------------------------------------------------------


def _share(value: float, total: float) -> str:
    percent = value / total * 100
    return "<1%" if 0 < percent < 0.5 else f"{percent:.0f}%"


def _legend(spec: dict) -> str:
    unit = spec["unit"]
    if spec["type"] == "pie":
        values = spec["series"][0]["values"]
        total = sum(values)
        items = [
            f'<li><span class="pk-chart-key {_key(i)}" aria-hidden="true"></span>{_esc(label)}'
            f'<span class="pk-chart-legend-value">{_esc(plain(v) + unit)}, {_share(v, total)}</span></li>'
            for i, (label, v) in enumerate(zip(spec["labels"], values, strict=True))
        ]
    elif len(spec["series"]) > 1:
        items = [
            f'<li><span class="pk-chart-key {_key(i)}" aria-hidden="true"></span>{_esc(s["name"])}</li>'
            for i, s in enumerate(spec["series"])
        ]
    else:
        return ""
    return f'<ul class="pk-chart-legend">{"".join(items)}</ul>'


def _table(spec: dict) -> str:
    unit = spec["unit"]
    if spec["type"] == "scatter":
        head = ["Series", "X", "Y"]
        rows = [[s["name"], plain(x), plain(y) + unit] for s in spec["series"] for x, y in s["points"]]
    elif spec["type"] == "pie":
        values = spec["series"][0]["values"]
        head = ["Slice", spec["series"][0]["name"], "Share"]
        rows = [[label, plain(v) + unit, _share(v, sum(values))] for label, v in zip(spec["labels"], values, strict=True)]
    else:
        head = [spec["x_label"] or "Category"] + [s["name"] for s in spec["series"]]
        rows = [[label] + [plain(s["values"][i]) + unit for s in spec["series"]] for i, label in enumerate(spec["labels"])]
    top = "".join(f"<th>{_esc(h)}</th>" for h in head)
    body = "".join("<tr>" + "".join(f"<td>{_esc(cell)}</td>" for cell in row) + "</tr>" for row in rows)
    return (
        '<details class="pk-chart-data"><summary>Show the data as a table</summary>'
        f'<div class="pk-table-wrap"><table><thead><tr>{top}</tr></thead><tbody>{body}</tbody></table></div></details>'
    )


def draw_chart(name: str, spec: dict, extra: str = "", note: str = "") -> str:
    """One chart as a figure: title, drawing, legend, a table of the data, and any note."""
    chart_id = name[: -len(".json")]
    inner, height, width = _draw(spec)
    kind = f"pk-chart-of-{spec['type']}"
    svg = (
        f'<svg class="pk-chart-svg" viewBox="0 0 {width} {height}" role="img" tabindex="0" '
        f'aria-labelledby="{chart_id}-t {chart_id}-d"><title id="{chart_id}-t">{_esc(spec["title"])}</title>'
        f'<desc id="{chart_id}-d">{_esc(spec["desc"])}</desc>{inner}</svg>'
    )
    return (
        f'<figure class="{_esc(f"pk-chart {kind} {extra}".strip())}" id="chart-{chart_id}">'
        f"<figcaption>{_esc(spec['title'])}</figcaption><!-- Chart data: assets/{name} -->"
        '<button type="button" class="pk-chart-expand" aria-label="Open the chart full screen">'
        '<i data-icon="maximize-2"></i></button>'
        f'<div class="pk-chart-plot">{svg}{_legend(spec)}</div>{_table(spec)}{note}</figure>'
    )


def expand_charts(document: str, page_dir: Path) -> str:
    """Replace each <pk-chart> with its figure. Anything inside the tag becomes a note below the chart."""

    def figure(match: re.Match) -> str:
        filename, extra, note = match.group(1), match.group(2) or "", match.group(3).strip()
        source = page_dir / "assets" / filename
        if not source.is_file():
            raise ChartError(f"missing chart data: assets/{filename}")
        spec = parse_spec(filename, source.read_text(encoding="utf-8"))
        return draw_chart(filename, spec, extra, note)

    expanded = _TAG_RE.sub(figure, document)
    if re.search(r"<pk-chart\b", expanded):
        raise ChartError('<pk-chart> is malformed: write it as <pk-chart src="assets/NAME.json"></pk-chart>, with a lowercase name')
    return expanded
