# Profiles

A profile holds everything specific to you or your organization: brand, colors, fonts, writing rules, and
what happens when a page is saved. pagekit ships with [its own brand](#the-default-brand), and a profile can replace
any of it to make pages entirely yours.

## Choosing a profile

The profile comes from where the agent works, never from an account. pagekit walks up from the working
directory to the nearest `.pagekit/profile/` or folder mapped in `~/.pagekit/projects.toml`. With neither, it uses
your personal profile at `~/.pagekit/profile/` if you have one, and otherwise the built-in profile. Git worktrees
nested inside a repository find its profile the same way. Override with `--profile` or `$PAGEKIT_PROFILE`.

Run `pagekit profile` to see which profile applies and what it is made of.

## Creating one

To have an agent do this, ask it to "set up a pagekit profile for this repo" or to "set up my personal pagekit
profile". It uses the `setup-profile` skill. By hand, from the folder the profile is for:

```bash
cd ~/workspace/acme
pagekit init --brand "Acme"           # .pagekit/profile here: commit it to share with a team
pagekit init --brand "Acme" --local   # or kept in ~/.pagekit/profiles/acme, nothing in the project
pagekit init --personal               # ~/.pagekit/profile, used wherever no other profile applies
```

`init` writes only what you ask for. The name defaults to the folder's name, and without `--brand` the profile keeps
the pagekit logo and footer. A profile extends the built-in profile by default, so a committed profile looks the same
for everyone. Use `--extends personal` to build on your personal profile instead, which falls back to the built-in
profile for people who have none.

## More than one profile in a repo

A repo can offer several, such as one for internal pages and one for customer documents. `.pagekit/profile/` stays the
default, and the rest go in `.pagekit/profiles/`:

```bash
pagekit init --also --name acme-public --when "Customer or public facing documents"
```

Give every profile a `when` in its `profile.toml`. `pagekit new` and `pagekit profile` print the other choices with their
`when`, and agents use that to pick one without asking. A profile that others extend and that has no `when` is treated
as a shared base, so it is not offered. Select one by name from anywhere in the repo:

```bash
pagekit new report --profile acme-public
```

## Overrides

Some settings belong to one machine: a command only you have, or a folder in your home. A committed profile cannot hold
those, so they live outside the repo and pagekit layers them on top of whichever profile applies:

```text
~/.pagekit/overrides/all/       every profile
~/.pagekit/overrides/acme/      only the profile named acme
```

Because they are keyed by profile name and never in the repo, they cannot be committed by accident, need no `.gitignore`
entry, and work in every worktree and clone.

An override can hold only `profile.toml` with `[save]` or `[send]`, `SAVE.md`, and `INSTRUCTIONS.md`, whose rules are
added to the profile's. pagekit refuses anything else, so an override cannot change how a shared profile looks or
remove a check it requires. `pagekit profile` lists any that apply.

A profile in a repo that names a path on this machine gets a warning on every build, as that path will not exist for
teammates.

## Files

| File | Purpose | When layered |
| --- | --- | --- |
| `profile.toml` | Settings, listed below | Deep merge |
| `theme.css` | `--pk-*` tokens and styles, redefined for light and dark | Concatenated |
| `fonts.css` | `@font-face` rules with embedded static fonts, added with `pagekit font add`, so pages work offline and PDFs stay small | Concatenated, without the built-in font once a profile has its own |
| `head.html` | Extra head tags | Concatenated |
| `INSTRUCTIONS.md` | Content and voice rules, printed by `pagekit new` | Concatenated |
| `template.html` | Page shell with `{{head}}`, `{{logo}}`, `{{brand}}`, `{{title}}`, `{{summary}}`, `{{content}}`, and `{{footer}}` | Nearest wins |
| `logo.svg`, `logo-dark.svg` | Header icon, with an optional dark-mode version | Nearest wins |
| `favicon.svg` | Browser tab icon; without one, the tab uses `logo.svg` | Nearest wins |
| `logo-print.png` | The full logo as one image for print, which saves about 3 to 5 KB per PDF sheet over a vector logo | Nearest wins |
| `wordmark.svg` | Drawn name beside the icon, replacing the typed `brand`; dark ink, inverted to white in dark mode | Nearest wins |
| `icons/` | [Your own icons](icons.md#your-own-icons) | Nearest wins, by name |
| `components/*.html`, `components/*.css` | Components specific to this profile, with optional styles included only on pages that use them; prefer the [shared ones](components.md) | Nearest wins, by name |
| `SAVE.md` | Steps printed after `pagekit save`, such as writing a matching document | Nearest wins |

## The default brand

With no profile, pages carry the pagekit logo, name, and ember colors. Every part can be overridden:

- **Colors and type** inherit like any theme. Redefine `--pk-*` tokens in `theme.css`, for light and dark, and the
  rest stays. A profile that sets no colors of its own keeps ember.
- **The logo goes as a set.** A profile that sets its own `brand`, or adds any logo file, gets none of pagekit's
  logo, wordmark, print logo, or tab icon, so "Acme" never appears beside the pagekit mark. Set `brand = ""` to show
  no name or logo at all.
- **The footer** reads "Made with pagekit" (with pagekit linked to the repo) until a profile sets `footer`. `pagekit init --brand` sets it to the brand.
- **The header and footer** are the same on every page, and a profile changes them in one place. Restyle them in
  `theme.css`, such as `.pk-logo { width: 30px; height: 30px; }`, or replace the layout in `template.html`.
- **The light and dark toggle** is a header icon that cycles between following the system, light, and dark. The
  choice is remembered in the browser and applies to every page. It works by switching the theme's
  `@media screen and (prefers-color-scheme: dark)` rules on or off, so any profile's theme works with no extra
  rules, and printing stays light. The page's root gets `data-theme="light"` or `"dark"` while a choice is made,
  for styles that need it. Set `theme_toggle = false` to leave it out.
- **The page index** at the server root uses the same header and footer with the built-in profile, because it lists
  pages from every profile.

| Color | Light | Dark |
| --- | --- | --- |
| Logo ink | `#1b1b1f` | `#f2efe9` |
| Logo ember | `#e5532d` | `#ff7a50` |
| `--pk-accent` | `#c8431c` | `#ff7a50` |

`--pk-accent` is darker than the logo's ember in light mode so links and button text stay readable. Text is IBM Plex
Sans and code is IBM Plex Mono, both embedded so pages and PDFs look the same on every machine, which adds about 103 KB
to a page. A profile with its own `fonts.css`, or that sets `--pk-font` in `theme.css`, does not carry Plex Sans. One
that sets `--pk-mono` does not carry Plex Mono. The wordmark is Space Grotesk SemiBold,
drawn as outlines. Source files for other uses are in [`docs/brand/`](brand/), and `scripts/build_brand.py` regenerates all of them.

## Settings

| Key in `profile.toml` | Meaning |
| --- | --- |
| `name` | The profile's name, and its folder under the pages root |
| `extends` | The profile to build on: `builtin` (the default), `personal`, or a path |
| `when` | One line on which pages this profile is for, which agents use to [choose between profiles](#more-than-one-profile-in-a-repo) |
| `brand` | Name in the header, unless `wordmark.svg` replaces it |
| `footer` | Footer text, required on every page |
| `copyright` | Adds a copyright notice for this holder to the footer |
| `theme_toggle` | Set to `false` to leave the light and dark toggle out of the header |
| `version_stamp` | Set to `false` to leave the version number out of the footer. Pages still record it for `pagekit rebuild --all` |
| `ascii_only` | Treat non-ASCII characters as an error |
| `allowed_hosts` | Hosts a page may load external resources from |
| `interactive` | Set to `false` for pages sent to outside readers: no Copy state button and no comments on item IDs |
| `pdf_margin` | Margins for [generated PDFs](printing.md#bookmarked-pdfs) |
| `[save]` | Where saved pages go, [below](#saving) |
| `[send]` | How `pagekit send` shares a page, [below](#send) |
| `[checks]` | A check every build must pass, [below](#checks) |
| `[[banned]]` | Words a page may not use, [below](#banned-wording) |

## Saving

`[save]` sets where `pagekit save` copies a page: `root`, or `root_command` (a command that prints a path, run
without a shell, only on save), plus an optional `subdir`. The default is `~/pages/saved`.

```toml
[save]
root = "~/Documents/pages"
subdir = "reports"
```

`SAVE.md` can direct an agent to do more after a save, such as filing a matching note. It may use `{{file}}`,
`{{path}}`, `{{title}}`, `{{summary}}`, `{{url}}`, `{{content}}`, and `{{profile}}`.

## Send

`[send]` names the command `pagekit send` hands the packed page to. Use whatever you share files with. It runs
without a shell, and `{file}`, `{title}`, and `{slug}` are filled in for each argument.

```toml
[send]
command = ["rclone", "copy", "{file}", "remote:pages"]
```

Without a command, `pagekit send` says so, and `pagekit pack` still writes the file.

## Checks

A profile can require its own check on every `pagekit build` and `pagekit check`:

```toml
[checks]
command = ["python3", "/path/to/lint.py"]
```

To keep the script with a profile in a repo, write `{profile}/checks/lint.py`, which points to the folder of the
profile that sets the command.

The command runs without a shell, in the page's folder, with the built `index.html` and the page folder as its
last two arguments. A non-zero exit prints its output as errors and fails the command. A failed build keeps
the page's last good version, or leaves no page if it is new, and `pagekit save` refuses a page that fails.

## Banned wording

A profile can list words its pages must never use, with no script. Each `pattern` is a regular expression, matched
against the words a reader sees in the built page, including text in diagrams, and ignoring case unless
`case_sensitive = true`. A match fails the build, and `why` appears in the message.

```toml
[[banned]]
pattern = "\\bTBD\\b"
why = "state what is true now"
```

## Commands in profiles

`root_command`, `[send]`, and `[checks]` all run commands that the profile names. Read a profile before using
it from a repository you do not trust.
