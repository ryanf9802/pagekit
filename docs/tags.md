# Generated tags

A generated tag is one a page writes and the build replaces with content worked out from the page itself, so that
content cannot drift out of date. A tag with a mistake in it stops the build with a message saying what to fix.

## Table of contents

```html
<pk-contents></pk-contents>
<pk-contents max-level="2" title="In this report"></pk-contents>
```

The list is built from the page's headings, in order and nested by level, with each entry linking to its heading.

| Attribute | Meaning | Default |
| --- | --- | --- |
| `max-level` | The deepest heading to list: `2` for h2 only, up to `6` | `3` |
| `title` | The heading above the list. `title=""` leaves it out | `Contents` |

- The list starts at h2, since the h1 is the page title. `max-level="1"` lists h1 headings instead.
- A heading with no `id` gets one made from its text. An `id` already on a heading is kept, so existing links still work.
- Put `data-pk-no-contents` on a heading to leave it out.
- Only real headings count. The title of a collapsed section is not a heading, so it is not listed.

For a hand-written list that adds a summary or groups sections into parts, use the `contents-card` component.

## Sparkline

```html
<div class="pk-kpi">
  <div class="pk-kpi-value">3.1 s</div>
  <div class="pk-kpi-label">Median build time</div>
  <pk-spark values="3.9,3.6,3.4,3.5,3.1" label="Build time, last five weeks"></pk-spark>
</div>
```

A small trend line for a KPI tile, drawn as inline SVG in the theme's accent color, with a dot on the last value.

| Attribute | Meaning | Default |
| --- | --- | --- |
| `values` | 2 to 60 numbers separated by commas, oldest first | required |
| `label` | What the numbers are, read aloud by screen readers | `Trend` |

- The line is scaled to the tile, from the lowest value to the highest. It shows the shape, not the amounts, so keep
  the amounts in the tile's value and label.
- Screen readers hear the label followed by the first, last, lowest, and highest values.
- It works in light mode, dark mode, and print, and needs no browser or script.

## Compact table

```html
<pk-table>
ID | Idea | Finding
<span class="pk-id">N-01</span> | Shorten build output | 337 of 378 builds were clean.
N-02 | Cache the fonts | Saves <code>40 ms</code> a page.
</pk-table>
```

A table written as plain lines, turned into the same markup as the `table` component (the `pk-table-wrap` div, which
scrolls on a phone, with `thead` and `tbody`), so the theme styles it the same. It saves the `td`, `tr`, and close tags,
and a forgotten close tag can no longer break the page. Prefer it for many rows; keep the full markup for a cell that
needs attributes on the `td` itself.

| Attribute | Meaning | Default |
| --- | --- | --- |
| `no-header` | Every line is a body row, with no header | the first line is the header |

- One line is one row, and `|` splits the cells. Cells are trimmed and blank lines are ignored.
- Inline HTML in a cell is kept as written: `code`, `span`, `a`, `strong`, `<i data-icon="...">`.
- To show a literal `|` in a cell, write `\|`.
- A row with fewer cells than the header is padded with empty cells. A row with more is a build error naming its line.
  With `no-header`, the widest row sets the column count.
- A `<pk-table>` with no `</pk-table>` is a build error.

## Adding a tag

Tags live in `src/pagekit/tags.py`. A tag is a function that takes its attributes and the page's headings and returns
HTML, plus an entry in `_TAGS` naming the attributes it accepts. A tag that takes lines of content, such as `<pk-table>`, goes
in `_BODY_TAGS` and also receives its body. Anything it needs for styling goes in the theme with
a `pk-` class.
