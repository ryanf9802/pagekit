# Charts

Write the numbers as a JSON file, and pagekit draws them into the page as plain SVG that follows the theme in light
mode, dark mode, and print. A chart needs no browser and no script, so the page stays one offline file.

## Adding one

Create `assets/NAME.json`, with a title and a description at the top for readers and screen readers:

```json
{
  "type": "line",
  "title": "Build time by week",
  "desc": "Median build time fell from 3.9 to 3.1 seconds over five weeks.",
  "labels": ["W1", "W2", "W3", "W4", "W5"],
  "series": [{ "name": "Median", "values": [3.9, 3.6, 3.4, 3.5, 3.1] }],
  "unit": " s"
}
```

Then add it to the page. Anything inside the tag becomes a note below the chart:

```html
<pk-chart src="assets/NAME.json"></pk-chart>
```

## Types

| `type` | For | Data |
| --- | --- | --- |
| `bar` | Comparing amounts. Add `"horizontal": true` for long names or a ranked list | `labels` and `series` |
| `line` | A trend over time | `labels` and `series` |
| `area` | One trend, with the space under it shaded | `labels` and `series` |
| `scatter` | Two measures against each other | `series`, each with `points`: `[[x, y], ...]` |
| `pie` | One whole split into 3 to 6 parts | `labels` and one series |

A pie is the weakest way to compare amounts, because the eye reads length more exactly than angle. To rank or compare
the parts, use a horizontal bar chart. A split into two parts reads better as two [KPI tiles](components.md), and
pagekit refuses a two slice pie.

## Fields

| Field | Meaning |
| --- | --- |
| `type`, `title`, `desc` | Required. The description is read aloud by screen readers, so say what the chart shows |
| `labels` | The names along the bottom (or the side of a horizontal bar), one for each value |
| `series` | One or more `{"name": ..., "values": [...]}`. A scatter series has `points` in place of `values` |
| `x_label`, `y_label` | Optional titles for the horizontal and vertical axes |
| `unit` | Optional text after each number, kept as written, such as `%` or `" s"` |

## Rules

- Colors come from the theme: eight `--pk-series-*` tokens, used in order. Do not set a color in the file.
- At most 6 series in a bar or line chart, and 3 in an area or scatter chart, because more colors are hard to tell
  apart. Fold the smallest into one series called Other, or draw two charts.
- Two or more series get a legend. Every chart has a "Show the data as a table" section with the exact values, which
  opens when the page is printed.
- A bar chart starts at zero. A line chart does not have to, so check the axis before reading a slope.
- A bar chart with one series labels each bar with its value (a vertical one up to 12 bars). Other charts leave the
  values to the axis and the table.
- Bars are at most 24 units thick with a rounded end, lines are 2px, and the chart scales down to a phone's width.

## How it works

The build reads the file, checks it, and draws the chart in Python, with no browser. A mistake stops the build with a
message saying what to fix. Colors, strokes, and text sizes are classes styled in the profile's theme, so a profile
that sets the `--pk-series-*` tokens restyles every chart.
