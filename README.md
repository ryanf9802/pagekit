# pagekit

Local, self-contained HTML pages for coding agents. A profile supplies the theme,
header, footer, and content rules, so every page an agent makes looks like the same
system. Every page has a footer button that copies the state of its controls, so the
user can answer a form and paste the result back into the session.

- No dependencies (Python standard library only), Python 3.11+.
- The folder is the database: `~/pages/<profile>/<slug>/` (`$PAGEKIT_HOME` overrides).
- Every command works with the server down. A built page is a plain file.
- Unpinned pages are deleted 30 days after their last update.

## Install

```bash
uv tool install --editable .      # puts `pagekit` on PATH
pagekit init --personal --name personal --brand "Your Name"
ln -s "$PWD/src/pagekit/skills/create-page" ~/.claude/skills/create-page
```

Optional, the page index on `http://localhost:8766`:

```bash
pagekit install-service           # or: pagekit serve, in a spare terminal
```

Over SSH, add `LocalForward 8766 localhost:8766` to the client's `~/.ssh/config` and
restart the shared master (`ssh -O exit <host>`). Without the server, `pagekit send`
hands a page to [dropbucket](https://github.com/ryanf9802/dropbucket), and
`pagekit pack` writes one file to share however you like.

To open pages from another of your own devices, give the server a private address and tell pagekit:

```bash
tailscale serve --bg 8766
pagekit install-service --public-url https://HOST.TAILNET.ts.net
```

The server then accepts that one extra name, builds print a `phone:` link, and the index can be added
to a phone's home screen as an app (Chrome menu, then Add to Home screen). Use `tailscale serve`, never
`funnel`, which is public. The server still listens on localhost only.

## Profiles

The profile comes from where the agent works, never from an account. pagekit walks up
from the working directory to the nearest `.pagekit/profile/` or folder mapped in
`~/.pagekit/projects.toml`, which under the home folder ends at `~/.pagekit/profile/`.
Git worktrees nested inside a repo find that repo's profile the same way. Override with
`--profile` or `$PAGEKIT_PROFILE`.

```bash
cd ~/workspace/acme
pagekit init --name acme --brand "Acme"           # .pagekit/profile here: commit it to share with a team
pagekit init --name acme --brand "Acme" --local   # or personal: ~/.pagekit/profiles/acme, nothing added to the project
```

| File | Purpose | Merge |
| --- | --- | --- |
| `profile.toml` | name, `extends`, brand, footer, `copyright` (adds a copyright notice for that holder to the footer), `ascii_only`, `allowed_hosts`, `[save]` | deep merge |
| `theme.css` | `--pk-*` tokens and styles; redefine tokens for light and dark | concatenated |
| `fonts.css` | `@font-face` rules with embedded static fonts, so pages work offline and PDFs stay small | concatenated |
| `head.html` | extra head tags | concatenated |
| `INSTRUCTIONS.md` | content and voice rules, printed by `pagekit new` | concatenated |
| `template.html` | page shell with `{{head}}`, `{{logo}}`, `{{brand}}`, `{{title}}`, `{{summary}}`, `{{content}}`, `{{footer}}` | nearest wins |
| `logo.svg`, `logo-dark.svg` | header icon, with an optional dark-mode version | nearest wins |
| `logo-print.png` | the full logo as one image for print, which saves about 3 to 5 KB per PDF sheet over vector logos | nearest wins |
| `wordmark.svg` | drawn name beside the icon, replacing the typed `brand`; dark ink, inverted to white in dark mode | nearest wins |
| `components/*.html` | components specific to this profile; prefer the shared ones below | nearest wins, by name |
| `SAVE.md` | steps printed after `pagekit save`, such as writing a matching document | nearest wins |

A profile extends `personal` by default, which falls back to the built-in for people
who have no personal profile. `SAVE.md` may use `{{file}}`, `{{path}}`, `{{title}}`,
`{{summary}}`, `{{url}}`, `{{content}}`, and `{{profile}}`.

`[save]` sets where saved pages go: `root`, or `root_command` (a command that prints a
path, run without a shell, only on `pagekit save`), plus an optional `subdir`. The default
is `~/pages/saved`. Because `root_command` runs a command named by the profile, read a
profile before using it from a repo you do not trust.

## Components

There are three layers, and each has one job:

- **Core**, in this repo: callout, divider, table, grid, tile row, status, collapsed section,
  figure, before and after, finding card, and decision card. These change only by deliberate choice.
- **Your library**, in `~/.pagekit/library/`: anything an agent builds that core does not cover.
  Agents add to it as they work, with no user involved, and one library serves every profile.
- **Profiles**: look and writing rules. A profile restyles components through theme tokens
  rather than defining its own versions of them.

```text
pagekit component list [--json]
pagekit component show NAME
pagekit component add NAME --when TEXT --from FOLDER [--update]
```

`add` refuses hard-coded colors, inline styles, classes that do not start with the component's
name, and existing names unless `--update` is passed. A build adds a library component's CSS
only to pages that use it. When the library is in a git repo, `add` commits that folder
locally and never pushes.

## Icons

All Lucide icons (ISC license, `src/pagekit/static/lucide-LICENSE`) ship in one file, and a page
embeds only those it uses, so pages stay small and work offline. Refresh them with
`scripts/update_lucide.py`.

```text
pagekit icons WORD          search by name or tag
<i data-icon="NAME"></i>    use one in a page; an unknown name fails the build
```

## Agent workflow

```text
pagekit new SLUG --title T [--summary S] [--mode slots|free]
                          create the page, or reopen it to update in place;
                          prints the file to write and the house rules
pagekit build SLUG        compose index.html, then run the checks
pagekit check SLUG        run the checks only
pagekit pack SLUG         one self-contained file, images as data URIs
pagekit send SLUG         pack, then `dropbucket put`
pagekit save SLUG         keep it: copy to the save location, pin the working copy
pagekit ls [--json]       list pages, newest first
pagekit prune [--older-than-days N] [--dry-run]
pagekit profile           print the resolved profile
```

`slots` mode (the default) fills the profile's template. In `free` mode `content.html`
is the whole document and must contain `{{head}}` and `{{footer}}`.

## Checks

`pagekit build` fails on: a missing title or viewport, a missing theme, export button, or
required footer; external resources outside `allowed_hosts`; non-ASCII characters (when
`ascii_only`); form controls with no name; two controls sharing a name; and missing or
unused assets. A fixed width over 390 px, inline styles, `<style>` blocks, and classes that no
theme or component defines are warnings; free-mode pages skip the last three. Real phone-width layout needs a
browser, so the `create-page` skill tells agents to check it there.

## Copying answers back

The footer button copies every named `input`, `select`, `textarea`, `[contenteditable]`,
and `details[id]`, plus anything registered with `pagekit.register(name, getter)`:

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
comments:
  S-05: what happened here?
```
````

Any item ID marked `<span class="pk-id">` is clickable: it opens a floating comment box, stays
marked once commented, and reopens on another click. Comments are copied under `comments:`,
keyed by ID, and the footer shows a count that steps through them. They do not print.

Password and hidden inputs are never exported. Answers survive a reload and a style-only
rebuild in `localStorage`, and reset when `content.html` changes. Comments behave the same way.

## Answering

Clicking a selected radio option clears it, as does pressing Space on it. Closing or reloading
a page asks first when it has answers or comments that have not been copied. Browsers do not
let a page cancel Ctrl+W itself, so this prompt is the guard. Opening a collapsed section does
not count as a change.

## Getting around

Served pages show an **All pages** link on the right of the header, back to the index. A
downloaded, packed, or saved copy has no index, so it has no link. The link does not print.

## Bookmarked PDFs

The browser's print dialog does not add bookmarks. On a served page, **Download PDF** in the header
builds a tagged PDF with bookmarks from the page's headings, including answers typed on the page, and
`pagekit pdf SLUG [--out FILE]` does the same from the command line. Both use a local Chrome or
Chromium (`$PAGEKIT_CHROME` overrides the search); with none found, the button does not appear.
Tagging makes these PDFs larger than Ctrl+P output.
Their margins default to `0.15in 0.25in` (top and bottom, then sides). A profile can set its own with
`pdf_margin` in `profile.toml`. Ctrl+P keeps the margins in the theme.

## Printing

Pages print in light colors, with the header and footer repeated on every sheet, page
numbers, collapsed sections opened, and wide tables and code wrapped rather than clipped.
The layout does not depend on the print dialog's margin setting: the body prints as a table
whose header and footer groups repeat.
A profile's dark tokens must stay under `@media screen and (prefers-color-scheme: dark)`
for this to hold. Use `<thead>` so a table's header row repeats across sheets.

## Expiry

`pagekit prune` deletes pages not updated for 30 days (`$PAGEKIT_TTL_DAYS`, `0` disables).
So that expiry needs no daemon, `new` and `build` run it about once a day, and the server
runs it every 10 minutes. A page is kept when its `page.toml` has `pinned = true`, which
`pagekit save` sets. The saved copy is never touched.

## Develop

```bash
uv run --group dev pytest
```
