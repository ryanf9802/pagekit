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
| `profile.toml` | name, `extends`, brand, footer, `ascii_only`, `allowed_hosts`, `[save]` | deep merge |
| `theme.css` | `--pk-*` tokens and styles; redefine tokens for light and dark | concatenated |
| `head.html` | extra head tags, such as a web font | concatenated |
| `INSTRUCTIONS.md` | content and voice rules, printed by `pagekit new` | concatenated |
| `template.html` | page shell with `{{head}}`, `{{logo}}`, `{{brand}}`, `{{title}}`, `{{summary}}`, `{{content}}`, `{{footer}}` | nearest wins |
| `logo.svg`, `logo-dark.svg` | header icon, with an optional dark-mode version | nearest wins |
| `wordmark.svg` | drawn name beside the icon, replacing the typed `brand`; dark ink, inverted to white in dark mode | nearest wins |
| `components/*.html` | snippets agents copy and adapt | nearest wins, by name |
| `SAVE.md` | steps printed after `pagekit save`, such as writing a matching document | nearest wins |

A profile extends `personal` by default, which falls back to the built-in for people
who have no personal profile. `SAVE.md` may use `{{file}}`, `{{path}}`, `{{title}}`,
`{{summary}}`, `{{url}}`, `{{content}}`, and `{{profile}}`.

`[save]` sets where saved pages go: `root`, or `root_command` (a command that prints a
path, run without a shell, only on `pagekit save`), plus an optional `subdir`. The default
is `~/pages/saved`. Because `root_command` runs a command named by the profile, read a
profile before using it from a repo you do not trust.

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
unused assets. A fixed width over 390 px is a warning. Real phone-width layout needs a
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
```
````

Password and hidden inputs are never exported. Answers survive a reload and a style-only
rebuild in `localStorage`, and reset when `content.html` changes.

## Printing

Pages print in light colors, with the header and footer repeated on every sheet, page
numbers, collapsed sections opened, and wide tables and code wrapped rather than clipped.
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
