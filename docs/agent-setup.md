# Agent setup guide

You are a coding agent setting up pagekit for the person you are working with. Lead them through it as a short
conversation. These steps are written for you; the person never needs to read them.

## How to run this

- Ask one question at a time, offer a sensible default, and accept "skip" for anything optional.
- Never guess at branding. Names, logos, and colors come from the person.
- Before each change outside the clone, say what you will write and where.
- Keep what already exists. If pagekit or a profile is already set up, improve it rather than replacing it.
- If a step fails, say so plainly and offer a way forward. Do not claim a step worked until you have run it.
- Read [Profiles](profiles.md) and [Serving pages](serving.md) when you need more detail than this guide gives.

## 1. Check the machine

Find these yourself, without asking:

- The operating system, and whether you are inside WSL
- Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/)
- Chrome, Chromium, or Edge, which diagrams and generated PDFs need
- Whether `pagekit` is already installed: run `pagekit profile`

Tell the person what you found. If uv is missing, offer to install it from its official instructions. If no browser
is found, say that pages still work, but diagrams and generated PDFs will not until one is installed. If a browser
is installed somewhere pagekit cannot find it, set `PAGEKIT_CHROME` to its path.

## 2. Install

Ask where the clone should live, because it has to stay there. Suggest a folder where they keep code. If you were
already started inside a clone, use that one.

```bash
git clone https://github.com/ryanf9802/pagekit.git
cd pagekit
uv tool install --editable .
```

Confirm with `pagekit --help`, from a different directory. If the command is not found, run `uv tool update-shell`,
then have the person open a new terminal.

## 3. Create the personal profile

This is the look and rules used wherever no project profile applies. Ask for the name to show in the page header,
which can be a person or an organization, then:

```bash
pagekit init --personal --name personal --brand "NAME"
```

## 4. Make it theirs

Ask about each of these in turn, in plain language. Everything is optional, and pages use the pagekit brand until a profile replaces it. Put
the results in the profile folder that `pagekit profile` lists, which is `~/.pagekit/profile/` for the personal one.

| Ask about | What to do with the answer |
| --- | --- |
| Footer text, such as "Internal" or a team name | `footer` in `profile.toml` |
| A copyright notice | `copyright` in `profile.toml`, set to the holder's name |
| A logo | Copy an SVG to `logo.svg`, and any dark-mode version to `logo-dark.svg` |
| A brand color | Set `--pk-accent` in `theme.css`, for light and dark, and check the contrast of each |
| A brand font | Embed static font files as `@font-face` rules in `fonts.css`, and set `--pk-font` in `theme.css` |
| How pages should be written | Add short rules to `INSTRUCTIONS.md`, such as tone and words to avoid |
| Where saved pages should go | [`[save]`](profiles.md#saving) in `profile.toml`. The default is `~/pages/saved` |
| How to send a page to someone | [`[send]`](profiles.md#send) in `profile.toml`, if they have a tool for it |

In `theme.css`, keep dark values under `@media screen and (prefers-color-scheme: dark)` so that printing stays light.

## 5. Add project profiles

Ask whether any project should look different from the personal profile, such as work for a client. For each one,
from that project's folder:

```bash
pagekit init --name NAME --brand "BRAND"           # in the project: commit it to share with a team
pagekit init --name NAME --brand "BRAND" --local   # kept in ~/.pagekit/profiles, nothing added to the project
```

Then repeat step 4 for what differs. Offer the `--local` form when the person does not want files in that repository.

## 6. Connect the agent

Make the `create-page` skill available to the agent you are running as, and to any others they name. It lives in the
clone at `src/pagekit/skills/create-page`.

- If the agent has a skills folder, link the skill there so it stays current. On Linux, macOS, and WSL use `ln -s`.
  On Windows use `mklink /J` from Command Prompt, which needs no special rights.
- If the agent has no skills, add a short note to its instructions file saying that when asked for a "page", it
  should read that skill's `SKILL.md` and follow it. Ask before editing that file.

Tell the person that from now on they can ask any connected agent for a page.

## 7. Offer the page index

Explain the choice in one or two sentences: pages are plain files and work without a server, while the server adds an
index of all their pages, shareable links on their own machines, and a **Download PDF** button. Then ask which they
want:

| Choice | What to do |
| --- | --- |
| No server | Nothing. Agents hand over files instead of links. |
| Only when wanted | Show them `pagekit serve`, which runs until the terminal closes. |
| Always on | Linux or WSL with systemd: `pagekit install-service`. Otherwise see [Serving pages](serving.md#starting-at-login). |

Run the server where the agent and pagekit run. From WSL, a Windows browser reaches `localhost` too, so the link
works there. If they chose a server, open `http://localhost:8766` to confirm it works. Then ask whether they use it in either of
these ways, and skip what does not apply:

- **Over SSH:** add the [port forward](serving.md#over-ssh) on the machine they connect from.
- **From a phone or another device:** set up a [private address](serving.md#from-your-other-devices). Never expose
  the server to the public internet.

## 8. Prove it works

Build a real page with what you just set up, from a directory that uses the profile:

```bash
pagekit new pagekit-setup-check --title "pagekit is ready" --summary "A check that setup worked"
```

Follow what it prints and the `create-page` skill. Use the profile's brand, a callout, a table, an icon, and one
decision card asking whether the page looks right. Run `pagekit build pagekit-setup-check`, open the page, and look at
it yourself, including at phone width and in dark mode if you can drive a browser. Then give the person the link or
file, and ask them to press **Copy state** and paste the result back. That one round trip proves the whole loop.

Fix anything they do not like in the profile rather than in the page, then rebuild.

## 9. Finish

Summarize in a few lines what you set up, where the profile lives, and whether the server is running. Mention that
the check page deletes itself after 30 days, and that `git pull` in the clone updates pagekit.

If their profile folder is worth keeping, suggest putting it under version control or a backup, since it holds their
brand and rules. Then suggest a first real page, based on what you know about their work.
