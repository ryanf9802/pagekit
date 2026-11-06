---
name: create-page
description: Create or update a local, consistently branded HTML page with pagekit, including forms whose answers the user copies back into the session. Use when the user asks for a "page", or a skill says to build one; when the user says to save or keep a page; and when pasted text contains a `pagekit-response` block.
---

# Create a page

The profile comes from the working directory, so run every command from the project the
page belongs to. Do not hand-roll chrome: the profile owns the theme, header, and footer.
To change how pages look in a project or for the user, use the `setup-profile` skill.

## Steps

1. Scaffold, or reopen to update in place (same slug, same path and URL):

   ```bash
   pagekit new <slug> --title "<Title>" --summary "<one line>"
   ```

   Read everything it prints. It names the file to write, the theme tokens, the
   components to use, and the profile's rules, which you must follow. If it lists other
   profiles here, pick the one whose `when` fits the page, without asking, and add
   `--profile NAME` to every command for that page.

   Reopening a page that already exists prints only the paths and a note that the rules
   are unchanged. Run `pagekit rules` (with the same `--profile`) to see them again, for
   example after the conversation was compacted.

   To update a page, change its `content.html` with targeted edits (the Edit tool). Never
   write the whole file again: a rewrite costs the page's full length in output for a
   small change. Run `pagekit outline <slug>` to list the headings and item IDs with
   their line numbers, then Read only the slice you need (offset and limit).

2. Write the page body to the printed `content.html`, and put images in `assets/`.
   Use `--mode free` on a new page only for something bespoke that the shell gets in the
   way of: there `content.html` is the whole document and must keep `{{head}}` and
   `{{footer}}`.

3. Build. This also runs the checks; fix every error and warning, then build again:

   ```bash
   pagekit build <slug>
   ```

4. Look at it before reporting. Open the printed URL in a browser, including at 390 px
   wide, where `document.documentElement.scrollWidth` must not exceed the window width,
   and in dark mode. `pagekit check` cannot see layout.

5. When the server is up, report the printed `url:` and no other link. Otherwise run
   `pagekit send <slug>` to hand the user the file: a `file://` path does not reach a browser
   on another machine. If the profile has no send command, give them the `pagekit pack` file.

## Components

Build from the listed components; `pagekit component show NAME` prints one. When none fits,
build what the page needs and save it so the next page can reuse it:

```bash
pagekit component add NAME --when "one line on when to use it" --from FOLDER
```

The folder holds `component.html` and optional `component.css`. The styles use only `--pk-*`
tokens, and every class starts with the component's name. Saving is housekeeping: do it
without asking, and do not mention it in chat, in a report, or on the page. Use `--update`
only to improve a component in a way that suits every page using it.

## Collecting input

A page with controls or comments has a footer button that copies their state. To get answers from
the user, add controls with stable names keyed to item IDs (the `decision-card` component),
then tell them to press the button and paste the result.

Answers come back like this; read it as the user's reply:

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

`comments:` appears only when there are some. The user can click any `pk-id` item ID on the
page to comment on it, so wrap every ID in `<span class="pk-id">`. Treat each comment as a
question or instruction about that item.

Empty values mean unanswered, not "no". `source` is the page: read `content.html` beside it
for what each name refers to. Act only on what the answers say, and rebuild the same slug to
show the result. Changing `content.html` clears answers and comments the user has not exported,
so collect them first. A rebuild with unchanged content keeps them.

## Sharing and keeping

- `pagekit pdf <slug>` writes a bookmarked PDF, and served pages have a **Download PDF** button.
- `pagekit pack <slug>` writes one self-contained file. `pagekit send <slug>` hands that file
  to the command the profile sets for sharing.
- Pages are deleted 30 days after their last update. When the user says to save or keep a
  page, run `pagekit save <slug>` and follow any `required next step` it prints, in the same
  turn.
- `pagekit ls` lists pages. A page's folder is `~/pages/<profile>/<slug>/`; do not edit
  `index.html` directly, since the next build replaces it.
