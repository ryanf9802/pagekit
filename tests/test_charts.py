from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from importlib import resources
from pathlib import Path

import pytest

from pagekit.charts import ChartError, column_path, draw_chart, nice_ticks, parse_spec, plain, row_path, short, tick_text
from pagekit.pages import PageError, build_page, check_page, new_page
from pagekit.profiles import load_profile

BAR = {
    "type": "bar",
    "title": "Pages per month",
    "desc": "Pages rose from 120 to 214.",
    "labels": ["Apr", "May", "Jun"],
    "series": [{"name": "Pages", "values": [120, 135, 214]}],
}
LINE = {
    "type": "line",
    "title": "Build time",
    "desc": "Build time fell.",
    "labels": ["W1", "W2", "W3"],
    "series": [{"name": "Median", "values": [3.9, 3.4, 3.1]}, {"name": "Slowest", "values": [7.2, 5.1, 4.0]}],
    "unit": " s",
    "x_label": "Week",
}
SCATTER = {
    "type": "scatter",
    "title": "Time against size",
    "desc": "Bigger pages are slower.",
    "series": [{"name": "Pages", "points": [[40, 2.9], [120, 3.4], [300, 5.0]]}],
    "x_label": "KB",
}
PIE = {
    "type": "pie",
    "title": "Pages by profile",
    "desc": "Half use the default profile.",
    "labels": ["Default", "Team", "Personal"],
    "series": [{"name": "Pages", "values": [107, 71, 36]}],
}
KINDS = {
    "bar": BAR,
    "horizontal": {**BAR, "horizontal": True},
    "line": LINE,
    "area": {**LINE, "type": "area", "series": LINE["series"][:1]},
    "scatter": SCATTER,
    "pie": PIE,
}


def build(spec: dict | str, body: str = '<pk-chart src="assets/c.json"></pk-chart>', more: dict[str, dict] | None = None) -> str:
    """Build a page with a chart (and any more data files) and return the document, after checking it has no errors."""
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", "One line", "slots")
    text = spec if isinstance(spec, str) else json.dumps(spec)
    (page.assets / "c.json").write_text(text, encoding="utf-8")
    for filename, other in (more or {}).items():
        (page.assets / filename).write_text(json.dumps(other), encoding="utf-8")
    page.content.write_text(body, encoding="utf-8")
    build_page(profile, page)
    assert check_page(profile, page).errors == []
    return page.index.read_text(encoding="utf-8")


def figure(document: str) -> str:
    found = re.search(r"<figure class=\"pk-chart.*?</figure>", document, re.DOTALL)
    assert found, "no chart figure in the page"
    return found.group(0)


def test_ticks_are_round_numbers_that_cover_the_data() -> None:
    assert nice_ticks(0, 214) == [0, 50, 100, 150, 200, 250]
    assert nice_ticks(3.1, 7.2) == [3, 4, 5, 6, 7, 8]
    assert nice_ticks(-3, 8)[0] <= -3 and nice_ticks(-3, 8)[-1] >= 8
    assert nice_ticks(5, 5)[0] <= 5 <= nice_ticks(5, 5)[-1]
    assert nice_ticks(0, 0) == [0, 0.2, 0.4, 0.6, 0.8, 1]


def test_an_axis_is_written_in_full_until_it_reaches_ten_thousand() -> None:
    assert tick_text([0, 1000, 2000], "") == ["0", "1,000", "2,000"]
    assert tick_text([0, 0.5, 1], "%") == ["0.0%", "0.5%", "1.0%"]
    assert tick_text([0, 10_000, 20_000], "") == ["0", "10K", "20K"]
    assert tick_text([0, 500_000, 1_000_000], "") == ["0", "500K", "1M"]


def test_numbers_are_written_exactly_in_tables_and_short_on_the_chart() -> None:
    assert plain(214.0) == "214" and plain(1234.5) == "1,234.5" and plain(3.1) == "3.1"
    assert short(950, "%") == "950%" and short(48_000, "") == "48K"


def test_a_column_is_square_at_its_baseline_and_rounded_at_its_end() -> None:
    up, down = column_path(10, 100, 40, 20), column_path(10, 100, 160, 20)
    for path in (up, down):
        assert path.startswith("M10,100 V") and path.endswith("V100 Z") and path.count("A") == 2
    assert "A4,4 0 0 1 14,40" in up and "A4,4 0 0 0 14,160" in down
    assert "A2,2" in column_path(10, 100, 98, 20)


def test_a_row_is_square_at_its_baseline_and_rounded_at_its_end() -> None:
    right, left = row_path(50, 200, 10, 20), row_path(50, 0, 10, 20)
    for path in (right, left):
        assert path.startswith("M50,10 H") and path.endswith("H50 Z") and path.count("A") == 2
    assert "A4,4 0 0 1 200,14" in right and "A4,4 0 0 0 0,14" in left


@pytest.mark.parametrize("kind", KINDS)
def test_every_chart_type_draws_themed_svg_with_alt_text_and_a_table(home: Path, kind: str) -> None:
    spec = KINDS[kind]
    chart = figure(build(spec))
    assert 'role="img"' in chart and "<title" in chart and spec["desc"] in chart
    assert f"<figcaption>{spec['title']}</figcaption>" in chart
    assert "Show the data as a table" in chart and "<table>" in chart
    # Colors live in the theme, so nothing in the drawing sets its own.
    assert not re.search(r'\b(?:fill|stroke|style)="', chart)
    assert "<pk-chart" not in chart and "<!-- Chart data: assets/c.json -->" in chart


def test_a_legend_names_two_or_more_series_and_a_single_series_has_none(home: Path) -> None:
    assert "pk-chart-legend" not in figure(build(BAR))
    legend = re.search(r'<ul class="pk-chart-legend">.*?</ul>', figure(build(LINE)), re.DOTALL)
    assert legend and "Median" in legend.group(0) and "Slowest" in legend.group(0)
    assert "pk-chart-s2" in legend.group(0)


@pytest.mark.parametrize("kind", ["bar", "line", "pie"])
def test_the_legend_shares_a_column_with_its_drawing_so_they_stay_together(home: Path, kind: str) -> None:
    # A bar or line chart only has a legend with two series.
    spec = PIE if kind == "pie" else {**KINDS[kind], "labels": LINE["labels"], "series": LINE["series"]}
    chart = figure(build(spec))
    assert re.search(r'<div class="pk-chart-plot"><svg .*?</svg><ul class="pk-chart-legend">.*?</ul></div>', chart, re.DOTALL)
    # The data table is outside that column, so it can use the card's full width.
    assert chart.index("</ul></div>") < chart.index('<details class="pk-chart-data">')


def test_charts_sit_side_by_side_in_a_grid_and_keep_their_own_ids(home: Path) -> None:
    body = '<div class="pk-grid"><pk-chart src="assets/c.json"></pk-chart><pk-chart src="assets/d.json"></pk-chart></div>'
    document = build(BAR, body, more={"d.json": {**LINE, "type": "area", "series": LINE["series"][:1]}})
    assert re.search(r'<div class="pk-grid"><figure class="pk-chart.*</figure><figure class="pk-chart.*</figure></div>', document, re.DOTALL)
    assert 'id="chart-c"' in document and 'id="chart-d"' in document


def test_the_theme_keeps_a_chart_whole_on_a_printed_sheet_and_its_legend_with_it() -> None:
    theme = resources.files("pagekit").joinpath("profile_default/theme.css").read_text(encoding="utf-8")
    assert re.search(r"@media print \{.*?\.pk-chart \{[^}]*break-inside: avoid", theme, re.DOTALL)
    assert re.search(r"@media print \{.*?\.pk-chart figcaption \{[^}]*break-after: avoid", theme, re.DOTALL)
    assert ".pk-chart-plot { max-width: 520px; margin: 0 auto; }" in theme


def test_a_pie_legend_gives_each_slice_its_amount_and_share(home: Path) -> None:
    legend = re.search(r'<ul class="pk-chart-legend">.*?</ul>', figure(build(PIE)), re.DOTALL)
    assert legend and "Default" in legend.group(0) and "107, 50%" in legend.group(0) and "36, 17%" in legend.group(0)


def test_a_single_series_bar_chart_labels_each_bar_and_grouped_bars_do_not(home: Path) -> None:
    assert figure(build(BAR)).count('class="pk-chart-value"') == 3
    grouped = {**BAR, "series": [BAR["series"][0], {"name": "Last year", "values": [100, 110, 190]}]}
    assert 'class="pk-chart-value"' not in figure(build(grouped))


@pytest.mark.parametrize("y_label", ["", "Pages"])
def test_every_chart_type_starts_its_plot_at_the_same_height_so_a_row_of_them_lines_up(y_label: str) -> None:
    def top(spec: dict) -> float:
        svg = draw_chart("x.json", parse_spec("x.json", json.dumps({**spec, "y_label": y_label})))
        return min(float(y) for y in re.findall(r'class="pk-chart-grid" x1="[^"]*" y1="([^"]*)"', svg))

    # A single series bar chart prints its values above the bars, so it must not be the one that needs headroom.
    tops = {name: top(KINDS[name]) for name in ("bar", "horizontal", "line", "area", "scatter")}
    assert len(set(tops.values())) == 1, tops


def _geometry(spec: dict) -> dict:
    """Where a column-style chart's plot starts and stops, and its first and last mark, from the drawing itself."""
    svg = draw_chart("x.json", parse_spec("x.json", json.dumps(spec)))
    grid = re.search(r'class="pk-chart-grid" x1="([^"]*)" y1="[^"]*" x2="([^"]*)"', svg)
    first_last = re.search(r'<polyline class="pk-chart-line [^"]*" points="([^"]*)"', svg)
    bands = [(float(x), float(w)) for x, w in re.findall(r'<rect class="pk-chart-hit" x="([^"]*)" y="[^"]*" width="([^"]*)"', svg)]
    out = {"left": float(grid.group(1)), "right": float(grid.group(2)), "bands": bands, "svg": svg}
    if first_last:
        points = [tuple(map(float, p.split(","))) for p in first_last.group(1).split(" ")]
        out["first"], out["last"] = points[0][0], points[-1][0]
    return out


@pytest.mark.parametrize("kind", ["line", "area"])
def test_a_line_or_area_chart_runs_edge_to_edge(kind: str) -> None:
    geometry = _geometry(KINDS[kind])
    assert geometry["first"] == geometry["left"] and geometry["last"] == geometry["right"]


def test_a_bar_chart_keeps_a_gap_at_each_end_because_a_bar_needs_room() -> None:
    svg = _geometry(BAR)["svg"]
    first_bar = float(re.search(r'<path class="pk-chart-bar [^"]*" d="M([\d.]+),', svg).group(1))
    assert first_bar > _geometry(BAR)["left"] + 10


@pytest.mark.parametrize("kind", ["bar", "line", "area"])
def test_the_tooltip_bands_cover_the_plot_without_gaps_or_overlaps(kind: str) -> None:
    geometry = _geometry(KINDS[kind])
    bands = geometry["bands"]
    assert bands[0][0] == pytest.approx(geometry["left"]) and bands[-1][0] + bands[-1][1] == pytest.approx(geometry["right"])
    for (x, width), (next_x, _) in zip(bands, bands[1:], strict=False):
        assert x + width == pytest.approx(next_x, abs=0.2)


def test_a_wide_label_at_either_end_is_not_clipped_by_the_edge_of_the_drawing() -> None:
    spec = {**LINE, "labels": ["Week number one", "Week 2", "Week number three"]}
    svg = draw_chart("x.json", parse_spec("x.json", json.dumps(spec)))
    for x, label in re.findall(r'class="pk-chart-tick" x="([^"]*)" y="[^"]*" text-anchor="middle">(Week[^<]*)<', svg):
        half = len(label) * 6.8 / 2
        assert float(x) - half >= 0 and float(x) + half <= 420, label


class _Tips(HTMLParser):
    """Collects each data-tip the way a browser reads it, so escaping mistakes show up as wrong text."""

    def __init__(self) -> None:
        super().__init__()
        self.tips: list[dict] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "data-tip":
                self.tips.append(json.loads(value or ""))


def tips(chart: str) -> list[dict]:
    parser = _Tips()
    parser.feed(chart)
    return parser.tips


def test_every_chart_type_gives_each_mark_the_text_its_tooltip_shows(home: Path) -> None:
    counts = {name: len(tips(figure(build(KINDS[name])))) for name in KINDS}
    # One target for each label (bars, lines, areas), each point (scatter), and each slice (pie).
    assert counts == {"bar": 3, "horizontal": 3, "line": 3, "area": 3, "scatter": 3, "pie": 3}


def test_a_tooltip_names_the_label_and_gives_each_series_its_value_with_the_unit(home: Path) -> None:
    first = tips(figure(build(LINE)))[0]
    assert first == {"t": "W1", "r": [["Median", "3.9 s", 1], ["Slowest", "7.2 s", 2]]}


def test_a_scatter_tooltip_gives_the_series_and_both_values_and_a_pie_tooltip_the_share(home: Path) -> None:
    assert tips(figure(build(SCATTER)))[0] == {"t": "Pages", "r": [["X", "40", 0], ["Y", "2.9", 0]], "s": 1}
    assert tips(figure(build(PIE)))[0] == {"t": "Default", "r": [["Pages", "107", 1], ["Share", "50%", 0]]}


def test_tooltip_text_from_the_file_survives_quotes_angle_brackets_and_ampersands(home: Path) -> None:
    spec = {**BAR, "labels": ['say "hi" <b> & more', "b", "c"], "series": [{"name": 'a"b', "values": [1, 2, 3]}]}
    chart = figure(build(spec))
    assert tips(chart)[0] == {"t": 'say "hi" <b> & more', "r": [['a"b', "1", 1]]}
    assert "<b>" not in chart


def test_a_tooltip_target_is_a_transparent_shape_that_draws_nothing_of_its_own(home: Path) -> None:
    chart = figure(build(LINE))
    assert re.search(r'<g class="pk-chart-point"><line class="pk-chart-cross" [^>]*/><rect class="pk-chart-hit" ', chart)
    # Bars have no crosshair, and every shape is styled by class, so the drawing sets no color.
    assert "pk-chart-cross" not in figure(build(BAR))
    assert not re.search(r'\b(?:fill|stroke|style)="', chart)


def test_a_chart_can_take_focus_and_open_full_screen(home: Path) -> None:
    chart = figure(build(BAR))
    assert re.search(r'<svg class="pk-chart-svg" [^>]*role="img" tabindex="0"', chart)
    assert re.search(r'<button type="button" class="pk-chart-expand" aria-label="Open the chart full screen"><svg ', chart)


def test_the_page_script_shows_tooltips_and_adds_charts_to_the_full_screen_view(home: Path) -> None:
    document = build(BAR)
    for text in ('className = "pk-tip"', '"[data-tip]"', ".pk-chart-expand", 'PREVIEWABLE + ", .pk-chart-svg"', '"pk-chart-on"'):
        assert text in document


def test_the_theme_hides_the_tooltip_and_expand_button_in_print_and_styles_the_active_mark() -> None:
    theme = resources.files("pagekit").joinpath("profile_default/theme.css").read_text(encoding="utf-8")
    assert re.search(r"@media print \{.*?\.pk-chart-expand, \.pk-tip \{ display: none; \}", theme, re.DOTALL)
    # The script alone marks the active target, so a resting mouse never leaves a second highlight.
    assert ".pk-chart-point.pk-chart-on .pk-chart-hit {" in theme and ":hover" not in re.search(r"\.pk-chart-hit \{.*?\n\.pk-chart-expand", theme, re.DOTALL).group(0)


def test_a_click_on_a_chart_leaves_no_focus_box_but_keyboard_focus_still_gets_a_ring() -> None:
    theme = resources.files("pagekit").joinpath("profile_default/theme.css").read_text(encoding="utf-8")
    plain_focus = theme.index(".pk-chart-svg:focus { outline: none; }")
    # The ring rule must come later, so it wins when both match: that is a keyboard focus.
    assert plain_focus < theme.index(".pk-chart-svg:focus-visible { outline: 2px solid var(--pk-accent);")


def test_a_unit_keeps_its_leading_space_on_the_axis_and_in_the_table(home: Path) -> None:
    chart = figure(build(LINE))
    assert ">3 s</text>" in chart and "<td>3.9 s</td>" in chart


def test_text_from_the_file_is_escaped(home: Path) -> None:
    chart = figure(build({**BAR, "title": "A <b> & B", "labels": ["<i>", "b", "c"]}))
    assert "A &lt;b&gt; &amp; B" in chart and "&lt;i&gt;" in chart and "<b>" not in chart and "<i>" not in chart


def test_a_horizontal_chart_grows_with_its_rows(home: Path) -> None:
    def height(count: int) -> int:
        spec = {**KINDS["horizontal"], "labels": [f"Row {i}" for i in range(count)]}
        spec["series"] = [{"name": "Pages", "values": list(range(1, count + 1))}]
        return int(re.search(r'viewBox="0 0 \d+ (\d+)"', build(spec)).group(1))

    assert height(8) > height(3)


def test_a_note_and_a_class_ride_with_the_chart(home: Path) -> None:
    chart = figure(build(BAR, '<pk-chart src="assets/c.json" class="wide"><p>Sample numbers.</p></pk-chart>'))
    assert chart.startswith('<figure class="pk-chart pk-chart-of-bar wide"') and chart.endswith("<p>Sample numbers.</p></figure>")


def test_a_missing_data_file_stops_the_build(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", "One line", "slots")
    page.content.write_text('<pk-chart src="assets/none.json"></pk-chart>', encoding="utf-8")
    with pytest.raises(PageError, match="missing chart data: assets/none.json"):
        build_page(profile, page)


@pytest.mark.parametrize("body", ["<pk-chart></pk-chart>", '<pk-chart src="assets/c.json">', '<pk-chart src="c.json"></pk-chart>'])
def test_a_malformed_chart_tag_stops_the_build(home: Path, body: str) -> None:
    with pytest.raises(PageError, match="malformed"):
        build(BAR, body)


def _spec(base: dict, **changes: object) -> dict:
    spec = json.loads(json.dumps(base))
    for key, value in changes.items():
        if value is None:
            spec.pop(key, None)
        else:
            spec[key] = value
    return spec


def _series(count: int, length: int = 3) -> list[dict]:
    return [{"name": f"S{i}", "values": [1 + i] * length} for i in range(count)]


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        ("{not json", "not valid JSON"),
        ('{"type": "bar", "series": [{"name": "a", "values": [NaN]}]}', "not valid JSON"),
        ("[1, 2]", "one JSON object"),
        (_spec(BAR, colour="red"), "unknown key 'colour'"),
        (_spec(BAR, type=None), "type must be one of"),
        (_spec(BAR, type="donut"), "type must be one of"),
        (_spec(BAR, title=None), "title is required"),
        (_spec(BAR, desc=""), "desc is required"),
        (_spec(BAR, unit="a long unit"), "unit is text of at most 8"),
        (_spec(LINE, horizontal=True), "only a bar chart takes it"),
        (_spec(BAR, horizontal="yes"), "true or false"),
        (_spec(BAR, series=None), "at least one series"),
        (_spec(BAR, labels=["a", 2, "c"]), "labels must be a list of text"),
        (_spec(BAR, series=[{"name": "a", "values": [1, 2]}]), "needs 3 numbers"),
        (_spec(BAR, series=[{"name": "a", "values": [1, "2", 3]}]), "needs 3 numbers"),
        (_spec(BAR, series=[{"name": "a", "values": [1, True, 3]}]), "needs 3 numbers"),
        (_spec(BAR, series=[{"name": "a", "values": [1, 2, 3], "colour": "red"}]), "no key 'colour'"),
        (_spec(BAR, series=[{"values": [1, 2, 3]}]), "a series name is required"),
        (_spec(BAR, series=_series(7)), "at most 6 series"),
        (_spec(LINE, series=_series(7)), "at most 6 series"),
        (_spec(LINE, type="area", series=_series(4)), "at most 3 series"),
        (_spec(BAR, series=[{"name": "a", "values": [1, 2, 3]}, {"name": "a", "values": [1, 2, 3]}]), "different from each other"),
        (_spec(LINE, labels=["W1"], series=_series(1, 1)), "needs 2 to 120 labels"),
        (_spec(SCATTER, labels=["a"]), "no labels"),
        (_spec(SCATTER, series=[{"name": "a", "points": [[1, 2, 3]]}]), "needs points, a list of"),
        (_spec(SCATTER, series=[{"name": "a", "points": []}]), "needs points, a list of"),
        (_spec(SCATTER, series=_series(2)), "no key 'values'"),
        (_spec(SCATTER, series=[{"name": f"S{i}", "points": [[1, 2]]} for i in range(4)]), "at most 3 series"),
        (_spec(SCATTER, series=[{"name": "a", "points": [[1, 2]] * 1001}]), "at most 1000 points"),
        (_spec(PIE, labels=["a", "b"], series=[{"name": "p", "values": [1, 2]}]), "two slices"),
        (_spec(PIE, labels=list("abcdefg"), series=_series(1, 7)), "needs 3 to 6 labels"),
        (_spec(PIE, series=[{"name": "p", "values": [5, -1, 2]}]), "must not be negative"),
        (_spec(PIE, series=[{"name": "p", "values": [0, 0, 0]}]), "more than zero"),
        (_spec(PIE, series=_series(2)), "one series"),
    ],
)
def test_a_mistake_in_the_data_says_what_to_fix(spec: dict | str, message: str) -> None:
    text = spec if isinstance(spec, str) else json.dumps(spec)
    with pytest.raises(ChartError, match=message):
        parse_spec("c.json", text)


def test_a_pie_with_one_slice_left_draws_a_whole_circle(home: Path) -> None:
    chart = figure(build({**PIE, "series": [{"name": "Pages", "values": [10, 0, 0]}]}))
    assert "<circle" in chart and chart.count("pk-chart-slice") == 1


def test_the_theme_sets_all_eight_series_colors_for_light_and_dark() -> None:
    theme = resources.files("pagekit").joinpath("profile_default/theme.css").read_text(encoding="utf-8")
    for number in range(1, 9):
        assert theme.count(f"--pk-series-{number}:") == 2
        assert f".pk-chart-s{number} {{ --pk-chart-color: var(--pk-series-{number}); }}" in theme
