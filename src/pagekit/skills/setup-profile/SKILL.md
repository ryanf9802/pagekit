---
name: setup-profile
description: Set up or change a pagekit profile, for one repo or folder or for the user personally, by asking about brand, footer, and writing rules. Use when the user says "set up pagekit for this repo", "set up a pagekit profile", "set up my personal profile", or wants pages to match a brand. Installing pagekit itself is separate: see docs/agent-setup.md in the clone.
---

# Set up a profile

A profile changes how pages look and read where it applies. Run every command from the folder the
profile is for, because the profile comes from the working directory.

- Ask one question at a time, offer a sensible default, and accept "skip" for anything optional.
- Never guess at branding. Names, logos, and colors come from the person, or from the repo once they confirm them.
- Before each change, say what you will write and where.
- Keep what exists. If a profile already applies here, improve it rather than replacing it.

`docs/profiles.md` in the pagekit clone has the full reference.

## 1. See what applies now

Run `pagekit profile`. Its first lines name the profile, its folder, and any overrides. If that is the profile the
person means, skip to step 4 and change it.

## 2. Choose where it lives

The request usually says which. If not, ask, and default to the first row inside a git repo.

| Scope | Command | Applies to |
| --- | --- | --- |
| Repo, shared | `pagekit init` | Everyone working in this repo, once `.pagekit/profile/` is committed |
| Repo, private | `pagekit init --local` | Only this person in this folder, with nothing added to the repo |
| Personal | `pagekit init --personal` | This person, wherever no other profile applies |

The profile is named after the folder, or `personal`. Use `--name` if the person wants another name.

A repo can offer more than one profile, such as one for internal pages and one for customer documents. Add the others
with `pagekit init --also --name NAME --when "WHEN"`, which puts them in `.pagekit/profiles/NAME`. Every profile in a
repo with more than one needs a `when` in its `profile.toml`, saying in one line which pages it is for, because that is
how agents choose. Agents select one with `--profile NAME`.

A repo profile builds on the built-in profile, so a committed one looks the same for everyone. Add
`--extends personal` only if the person wants it to build on their personal profile, and only on a private one.

## 3. Name the brand

Ask what name to show in the header. Add `--brand "NAME"` to the command only if they give one.

Setting a brand removes the pagekit logo, name, and tab icon, and sets the footer to that name. Without one, the
profile keeps the pagekit look and can still change anything else below.

## 4. Look for branding in the repo

Skip this for a personal profile. Look without asking:

- Logo files: `logo*.svg`, `favicon*`, and folders such as `public/`, `assets/`, `static/`, and `brand/`
- Colors and fonts: CSS custom properties, Tailwind or theme config, and design tokens
- The product name: the README title and the package manifest

Show what you found and ask which to use. Use nothing they have not confirmed.

## 5. Make it theirs

Ask about each of these in turn, in plain language. Everything is optional. Put the results where step 6 says.

| Ask about | What to do with the answer |
| --- | --- |
| Footer text, such as "Internal" or a team name | `footer` in `profile.toml` |
| A copyright notice | `copyright` in `profile.toml`, set to the holder's name |
| A logo | Copy an SVG to `logo.svg`, and any dark-mode version to `logo-dark.svg` |
| A brand color | Set `--pk-accent` in `theme.css`, for light and dark, and check the contrast of each |
| A brand font | Embed static font files as `@font-face` rules in `fonts.css`, and set `--pk-font` in `theme.css` |
| How pages should be written | Add short rules to `INSTRUCTIONS.md`, such as tone and words to avoid |
| Where saved pages should go | `[save]` in `profile.toml`. The default is `~/pages/saved` |
| How to send a page to someone | `[send]` in `profile.toml`, if they have a tool for it |

In `theme.css`, keep dark values under `@media screen and (prefers-color-scheme: dark)` so that printing stays light.
Replace the starter text in `INSTRUCTIONS.md`, or delete the file if they have no rules: `pagekit new` prints it to
every agent.

## 6. Put each setting in the right place

Decide this yourself. Do not ask the person to choose, and say where you put each setting in one line.

For a repo profile, the test is: **would this work, and be wanted, on a teammate's machine?**

| Setting | Goes in | Why |
| --- | --- | --- |
| Brand, theme, fonts, logos, footer, shared writing rules | The profile's folder | It is what the pages are |
| A check script kept in the repo | The profile's folder, as `{profile}/checks/NAME` in `[checks]` | Everyone has it |
| A home folder path, or a tool only this person uses | `~/.pagekit/overrides/PROFILE/` | Only exists for them |
| Steps that use this person's own skills or notes | `~/.pagekit/overrides/PROFILE/` | Same reason |
| Writing rules only this person wants | `~/.pagekit/overrides/PROFILE/INSTRUCTIONS.md` | Others did not ask for them |
| A send tool everyone on the team has | The profile's folder | Ask only here, if you cannot tell whether the team has it |

Settings this person wants for every profile, such as their `[send]` command, go in `~/.pagekit/overrides/all/`. Never
add overrides to a repo or to `.gitignore`: they live outside it so they cannot be committed and still work in
worktrees.

Overrides can only hold `[save]`, `[send]`, `SAVE.md`, and `INSTRUCTIONS.md`. pagekit refuses anything else, so an
override never changes how a shared profile looks or what it must pass. For a private or personal profile, everything
can stay in the profile's own folder.

`pagekit build` warns if a profile in a repo names a path on this machine. Treat that as a mistake and move the setting.

## 7. Prove it works

From the same folder:

```bash
pagekit new pagekit-profile-check --title "Profile check" --summary "A check of this profile"
```

Follow what it prints and the `create-page` skill. Use a callout, a table, and an icon. Run
`pagekit build pagekit-profile-check`, open the page, and look at it yourself, including at phone width and in dark
mode if you can drive a browser. Give the person the link or file and ask if it looks right.

Fix anything they do not like in the profile rather than in the page, then rebuild.

## 8. Finish

Say in a few lines what the profile is, where it lives, and where it applies. Then:

- For a shared repo profile, tell them to commit `.pagekit/`. Commit it only if they ask.
- Otherwise, if the folder is worth keeping, suggest version control or a backup.
- Mention that existing pages keep their old look until rebuilt with `pagekit build SLUG`, and that the check page
  deletes itself after 30 days.
