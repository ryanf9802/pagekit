## Page rules

- Write content, not chrome. The profile supplies the header, theme, and footer.
- Use `--pk-*` tokens and `pk-*` classes. Never hard-code a color: every page must
  work in light and dark mode.
- Reference images as `assets/<file>`. Delete assets you stop using.
- Every form control needs a stable, unique `name` that says what it answers, keyed
  to the item it belongs to (`F-01.decision`, `F-01.notes`). Answers come back to
  you by that name in a `pagekit-response` block when the user presses the footer
  button. Radio buttons and checkbox groups share one `name`.
- Wrap every item ID in `<span class="pk-id">`. That makes it clickable, so the user can
  comment on the item, and the comment comes back under `comments:` keyed by the ID.
- A bespoke widget reports its state with
  `pagekit.register("name", function () { return value; })`.
- A page shows its current state only. Update it in place by keeping the slug.
- Wrap wide tables in `<div class="pk-table-wrap">`. Check the page at phone width.
