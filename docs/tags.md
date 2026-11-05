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

## Adding a tag

Tags live in `src/pagekit/tags.py`. A tag is a function that takes its attributes and the page's headings and returns
HTML, plus an entry in `_TAGS` naming the attributes it accepts. Anything it needs for styling goes in the theme with
a `pk-` class.
