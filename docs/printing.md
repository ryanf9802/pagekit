# Printing and PDFs

## Printing

Pages print in light colors, with the header and footer repeated on every sheet, page numbers, collapsed sections
opened, and wide tables and code wrapped rather than clipped. The layout does not depend on the print dialog's
margin setting: the body prints as a table whose header and footer groups repeat.

For this to hold in your own work:

- Keep a profile's dark tokens under `@media screen and (prefers-color-scheme: dark)`.
- Use `<thead>` so a table's header row repeats across sheets.

## Bookmarked PDFs

The browser's print dialog does not add bookmarks, so pagekit can generate a tagged PDF with bookmarks from the
page's headings:

- **Download PDF**, in the header of a served page, includes answers typed on the page.
- `pagekit pdf SLUG [--out FILE]` does the same from the command line.

Both use local Chrome or Chromium. Set `$PAGEKIT_CHROME` to override the search. With none found, the button does
not appear. Tagging makes these PDFs larger than Ctrl+P output.

## Margins

Generated PDFs default to `0.15in 0.25in` (top and bottom, then sides). A profile can set its own with `pdf_margin`
in `profile.toml`, using one to four values in CSS order. Ctrl+P keeps the margins set in the theme.

## Keeping PDFs small

- Embed static fonts in `fonts.css`. Variable fonts embed as much larger Type 3 fonts.
- Add `logo-print.png` to a profile, since a vector logo is redrawn on every sheet.
- Add `NAME-print.png` for [complex icons](icons.md#size-in-pdfs) used many times.
