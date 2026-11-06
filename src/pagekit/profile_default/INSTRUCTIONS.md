## Page rules

- Write content, not chrome. The profile supplies the header, theme, and footer.
- The header already shows the page title as the `<h1>`. Do not repeat it: start at `<h2>`.
- Use `--pk-*` tokens and `pk-*` classes. Never hard-code a color: every page must
  work in light and dark mode.
- Use the listed components. Read one with `pagekit component show NAME`. No inline styles,
  and no `<style>` in the page.
- If no component fits, build one with `--pk-*` tokens and save it for reuse with
  `pagekit component add NAME --when "when to use it" --from FOLDER`, where the folder holds
  `component.html` and optional `component.css`. Do this yourself. Do not ask first, and do
  not mention it to the user. A saved component's classes must start with its name.
  `pagekit rules --tokens` lists the theme tokens.
- Draw flows and decisions with the `diagram` component, never hand-written SVG: `pagekit component
  show diagram` explains it. The build needs Chrome or Chromium the first time it draws one.
- Draw numbers with the `chart` component, never hand-written SVG or a script from the web: `pagekit
  component show chart` explains it. A bar, line, or area chart usually answers better than a table of
  trends; a table is still right for exact values, and every chart carries one.
- Use icons, never hand-drawn SVG, emoji, or CSS background images: `<i data-icon="NAME"></i>`. Find
  one with `pagekit icons WORD`. Add `tone="blue"` for color (blue, purple, green, teal, orange,
  success, warning, danger, accent, muted), and `aria-label="..."` when it stands alone with no text.
  The build turns it into `<svg class="pk-icon">`, so component CSS targets `.pk-icon`, not the `<i>`.
- Reference images as `assets/<file>`. Delete assets you stop using.
- Every form control needs a stable, unique `name` that says what it answers, keyed
  to the item it belongs to (`F-01.decision`, `F-01.notes`). Answers come back to
  you by that name in a `pagekit-response` block when the user presses the footer
  button. Radio buttons and checkbox groups share one `name`.
- Wrap every item ID in `<span class="pk-id">`. That makes it clickable, so the user can
  comment on the item, and the comment comes back under `comments:` keyed by the ID.
- A bespoke widget reports its state with
  `pagekit.register("name", function () { return value; })`.
- For a table of contents on a long page, use `<pk-contents max-level="3"></pk-contents>`: the build
  generates it from the headings. Never write one by hand unless it needs a summary or parts.
- Number every item and figure with an ID the reader can quote back (`F-01`, `S-03`). IDs are
  stable: never renumber, and give new items the next free number.
- Lead with what the reader must decide or do. Keep text short and direct.
- Use screenshots only for visual changes. For timing, typing, or touch behavior, write a try-it
  checklist instead.
- A page shows its current state only. Update it in place by keeping the slug.
- Wrap wide tables in `<div class="pk-table-wrap">`. Check the page at phone width.
