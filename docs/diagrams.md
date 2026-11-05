# Diagrams

Write Mermaid flowcharts as source files, and pagekit draws them into the page as plain SVG that follows the
theme in light mode, dark mode, and print.

## Adding one

Create `assets/NAME.mmd`, with a title and description at the top for readers and screen readers:

```text
---
title: How a request moves
desc: The browser calls the API, which reads from the database.
---
flowchart TD
  browser[Browser] --> api[API]
  api --> db[(Database)]
  class api accent
```

Then add it to the page. Anything inside the tag becomes a note below the diagram:

```html
<pk-diagram src="assets/NAME.mmd"></pk-diagram>
```

## Rules

- Flowcharts only.
- No `classDef`, `style`, or `linkStyle`, because colors come from the theme. Use `class NODE TONE` instead.
- Tones are strong, neutral, accent, danger, and muted.

`pagekit component show diagram` has the full rules.

## How it works

The build draws each diagram once with the vendored Mermaid in local Chrome or Chromium, using the profile's font
to measure text, and caches the result beside the page. A build needs a browser only when a diagram has changed.
The output has no Mermaid styling or script, so the page stays offline. A wide diagram scrolls on a phone rather
than shrinking its text.

Mermaid's MIT license is in `src/pagekit/static/mermaid-LICENSE`.
