---
name: create-page
description: Create or update a local, consistently branded HTML page with pagekit, including forms whose answers the user copies back into the session. Use when the user asks for a "page", or a skill says to build one; when the user says to save or keep a page; and when pasted text contains a `pagekit-response` block.
---

# Create a page

The profile comes from the working directory, so run every command from the project the
page belongs to. The profile owns the theme, header, and footer. To change how pages look,
use the `setup-profile` skill.

## Steps

1. Scaffold, or reopen to update in place (same slug, same path and URL):

   ```bash
   pagekit new <slug> --title "<Title>" --summary "<one line>"
   ```

   Read everything it prints: the file to write, the components, and the profile's rules,
   which you must follow. If it lists other profiles here, pick the one whose `when` fits
   the page, without asking, and add `--profile NAME` to every command for that page.
   Reopening prints only the paths: `pagekit rules` shows the rules again.

   To update a page, change `content.html` with targeted edits, never a full rewrite.
   `pagekit outline <slug>` lists headings and item IDs with line numbers, so you can Read
   only the slice you need.

2. Write the body to the printed `content.html`, and put images in `assets/`. Use
   `--mode free` on a new page only for something the shell gets in the way of: there
   `content.html` is the whole document and must keep `{{head}}` and `{{footer}}`.

3. Build. This also runs the checks; fix every error and warning, then build again:

   ```bash
   pagekit build <slug>
   ```

4. Look at it before reporting. Run `pagekit check --browser <slug>`: it loads the page at
   390 px wide in light and dark mode, prints any horizontal overflow and console errors,
   and exits non-zero on either. Fix and rebuild until it passes. Open a browser only for
   a visual look, or add `--screenshot PATH` for a full-page image.

5. When the server is up, report the printed `url:` and no other link. Otherwise run
   `pagekit send <slug>` to hand over the file (a `file://` path does not reach another
   machine), or give the `pagekit pack` file if the profile has no send command.

## Components

`pagekit component show NAME...` prints one or several: name every component you need in one
call. When none fits, save what you build:

```bash
pagekit component add NAME --when "one line on when to use it" --from FOLDER
```

The folder holds `component.html` and optional `component.css`. Run `pagekit rules --tokens`
for the theme tokens the styles may use. Use `--update` only for an improvement that suits
every page using the component.

## Collecting input

A page with controls has a footer button that copies their state. Add controls (the
`decision-card` component), then tell the user to press the button and paste the result.
It comes back like this; read it as the user's reply:

````text
```pagekit-response
page: pr-1462-review
title: PR 1462 Review
profile: acme
source: /home/you/pages/acme/pr-1462-review/index.html
built: 2026-11-04T18:02:11Z
fields:
  F-01.fix: true
  D-01.choice: option-b
  D-01.notes: |
    Multi-line notes are indented
    under the name.
comments:
  S-05: what happened here?
```
````

`comments:` appears only when there are some: each is a question or instruction about the
item whose ID is the key. Empty values mean unanswered, not "no". `source` is the page: read
`content.html` beside it for what each name refers to. Act only on what the answers say, and
rebuild the same slug to show the result. Changing `content.html` clears answers and comments
the user has not exported, so collect them first. A rebuild with unchanged content keeps them.

## Sharing and keeping

- `pagekit pdf <slug>` writes a bookmarked PDF; served pages have a **Download PDF** button.
- `pagekit pack <slug>` writes one self-contained file; `pagekit send <slug>` hands it to the
  profile's share command.
- Pages are deleted 30 days after their last update. When the user says to save or keep a
  page, run `pagekit save <slug>` and follow any `required next step` it prints, in the same
  turn.
- `pagekit ls` lists pages, in `~/pages/<profile>/<slug>/`. Never edit `index.html`: the next
  build replaces it.
