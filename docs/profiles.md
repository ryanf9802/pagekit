# Profiles

A profile holds everything specific to you or your organization: brand, colors, fonts, writing rules, and
what happens when a page is saved. pagekit itself ships neutral, so a profile can make it entirely yours.

## Choosing a profile

The profile comes from where the agent works, never from an account. pagekit walks up from the working
directory to the nearest `.pagekit/profile/` or folder mapped in `~/.pagekit/projects.toml`, which under the
home folder ends at `~/.pagekit/profile/`. Git worktrees nested inside a repository find its profile the same
way. Override with `--profile` or `$PAGEKIT_PROFILE`.

Run `pagekit profile` to see which profile applies and what it is made of.

## Creating one

```bash
cd ~/workspace/acme
pagekit init --name acme --brand "Acme"           # .pagekit/profile here: commit it to share with a team
pagekit init --name acme --brand "Acme" --local   # or kept in ~/.pagekit/profiles/acme, nothing in the project
```

A profile extends `personal` by default, which falls back to the built-in profile for people who have no
personal one. Use `--extends builtin` to start clean.

## Files

| File | Purpose | When layered |
| --- | --- | --- |
| `profile.toml` | Settings, listed below | Deep merge |
| `theme.css` | `--pk-*` tokens and styles, redefined for light and dark | Concatenated |
| `fonts.css` | `@font-face` rules with embedded static fonts, so pages work offline and PDFs stay small | Concatenated |
| `head.html` | Extra head tags | Concatenated |
| `INSTRUCTIONS.md` | Content and voice rules, printed by `pagekit new` | Concatenated |
| `template.html` | Page shell with `{{head}}`, `{{logo}}`, `{{brand}}`, `{{title}}`, `{{summary}}`, `{{content}}`, and `{{footer}}` | Nearest wins |
| `logo.svg`, `logo-dark.svg` | Header icon, with an optional dark-mode version | Nearest wins |
| `logo-print.png` | The full logo as one image for print, which saves about 3 to 5 KB per PDF sheet over a vector logo | Nearest wins |
| `wordmark.svg` | Drawn name beside the icon, replacing the typed `brand`; dark ink, inverted to white in dark mode | Nearest wins |
| `icons/` | [Your own icons](icons.md#your-own-icons) | Nearest wins, by name |
| `components/*.html` | Components specific to this profile; prefer the [shared ones](components.md) | Nearest wins, by name |
| `SAVE.md` | Steps printed after `pagekit save`, such as writing a matching document | Nearest wins |

## Settings

| Key in `profile.toml` | Meaning |
| --- | --- |
| `name` | The profile's name, and its folder under the pages root |
| `extends` | The profile to build on: `personal`, `builtin`, or a path |
| `brand` | Name in the header, unless `wordmark.svg` replaces it |
| `footer` | Footer text, required on every page |
| `copyright` | Adds a copyright notice for this holder to the footer |
| `ascii_only` | Treat non-ASCII characters as an error |
| `allowed_hosts` | Hosts a page may load external resources from |
| `pdf_margin` | Margins for [generated PDFs](printing.md#bookmarked-pdfs) |
| `[save]` | Where saved pages go, [below](#saving) |
| `[send]` | How `pagekit send` shares a page, [below](#send) |
| `[checks]` | A check every build must pass, [below](#checks) |

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

The command runs without a shell, in the page's folder, with the built `index.html` and the page folder as its
last two arguments. A non-zero exit prints its output as errors and fails the command. A failed build keeps
the page's last good version, or leaves no page if it is new, and `pagekit save` refuses a page that fails.

## Commands in profiles

`root_command`, `[send]`, and `[checks]` all run commands that the profile names. Read a profile before using
it from a repository you do not trust.
