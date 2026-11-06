# Writing pages

## The workflow

1. `pagekit new SLUG --title T` creates the page, or reopens an existing one to update it in place, keeping
   its path and link. It prints the file to write and the profile's rules.
2. Write the body to `content.html`, and put images in `assets/`.
3. `pagekit build SLUG` composes `index.html` and runs the checks. Fix what they report and build again.

Never edit `index.html`: the next build replaces it.

## Modes

- `slots`, the default, fills the profile's template, so the header and footer take care of themselves.
- `free` makes `content.html` the whole document, for something bespoke the template gets in the way of.
  It must contain `{{head}}` and `{{footer}}`.

Choose with `--mode` when creating the page.

## Images

Reference images as `assets/<file>`. The build adds a width and height to each PNG, JPEG, GIF, or WebP that
lacks them, so a page holds its layout while lazy images load. Images still scale to fit the page.

Any image or diagram opens full screen when clicked or tapped, with no setup. Tap again to zoom, use the
arrows or swipe to move between them, and press Esc, the close button, or the phone's back button to leave.
Images inside a link keep following the link. A [chart](charts.md#tooltips-and-full-screen) opens from the button at its
top right instead, since a tap on a chart shows its tooltip.

## Checks

Every build runs these checks, and `pagekit check` runs them alone.

**Errors** fail the command:

- A missing title, viewport, theme, export button, or required footer
- External resources outside the profile's `allowed_hosts`
- Non-ASCII characters, when the profile sets `ascii_only`
- Form controls with no name, or two controls sharing a name
- Missing or unused assets
- Text such as `<uuid>` or `<template ...>` in `content.html`, which browsers read as a tag and which hides the rest of the page; write `&lt;` and `&gt;` to show it
- A failing [profile check](profiles.md#checks)

**Warnings** do not:

- A fixed width over 390 px
- An `<h1>` in `content.html`, because the header already shows the page title
- Inline styles and `<style>` blocks
- Classes that no theme or component defines

Free-mode pages skip the last three. Real phone-width layout needs a browser, so run `pagekit check --browser SLUG`.
It loads the built page in headless Chrome at 390 px, in light and dark mode, and prints whether
`document.documentElement.scrollWidth` exceeds the window width, the elements that overflow (at most 5; tables, code,
and wide diagrams that scroll on their own are ignored), and any console errors. It exits 1 if anything is wrong.
`--screenshot PATH` also writes a full-page PNG. It needs Chrome, found the same way as for diagrams and PDFs.

## Sharing

- **A link**, when the [page index](serving.md) is running. Builds print it.
- **One file:** `pagekit pack SLUG` writes a self-contained file with images embedded.
- **Your own channel:** `pagekit send SLUG` packs the page and runs the profile's
  [send command](profiles.md#send).
- **A PDF:** see [Printing and PDFs](printing.md).

## Saving and expiry

`pagekit prune` deletes pages not updated for 30 days. Set `PAGEKIT_TTL_DAYS` to change that, or `0` to turn
it off. So that expiry needs no daemon, `new` and `build` run it about once a day, and the server runs it
every 10 minutes.

`pagekit save SLUG` keeps a page: it copies the page to the profile's
[save location](profiles.md#saving) and pins the working copy with `pinned = true` in its `page.toml`. Pinned
pages and saved copies are never pruned.
