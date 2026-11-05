# Agent setup guide

You are a coding agent setting up pagekit for the person you are working with. Lead them through it as a short
conversation. These steps are written for you; the person never needs to read them.

Pages carry the pagekit brand until a profile replaces it, so this guide does not ask about branding, with one
exception in [step 6](#6-offer-a-repo-profile). Profiles are set up per folder, later, with the `setup-profile` skill.

## How to run this

- Ask one question at a time, offer a sensible default, and accept "skip" for anything optional.
- Before each change outside the clone, say what you will write and where.
- Keep what already exists. If pagekit is already set up, improve it rather than replacing it.
- If a step fails, say so plainly and offer a way forward. Do not claim a step worked until you have run it.
- Read [Serving pages](serving.md) when you need more detail than this guide gives.

## 1. Check the machine

Find these yourself, without asking:

- The operating system, and whether you are inside WSL
- Python 3.11 or newer, and [uv](https://docs.astral.sh/uv/)
- Chrome, Chromium, or Edge, which diagrams and generated PDFs need
- Whether `pagekit` is already installed: run `pagekit profile`
- The directory you were started in, which step 6 needs

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

## 3. Connect the agent

Make two skills available to the agent you are running as, and to any others they name. They live in the clone at
`src/pagekit/skills/create-page` and `src/pagekit/skills/setup-profile`.

- If the agent has a skills folder, link both there so they stay current. On Linux, macOS, and WSL use `ln -s`.
  On Windows use `mklink /J` from Command Prompt, which needs no special rights.
- If the agent has no skills, add a short note to its instructions file saying that when asked for a "page", it
  should read `create-page/SKILL.md` and follow it, and when asked to set up a pagekit profile, it should do the same
  with `setup-profile/SKILL.md`. Ask before editing that file.

Tell the person that from now on they can ask any connected agent for a page.

## 4. Offer the page index

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

## 5. Prove it works

Build a real page:

```bash
pagekit new pagekit-setup-check --title "pagekit is ready" --summary "A check that setup worked"
```

Follow what it prints and the `create-page` skill. Use a callout, a table, an icon, and one decision card asking
whether the page looks right. Run `pagekit build pagekit-setup-check`, open the page, and look at it yourself, including
at phone width and in dark mode if you can drive a browser. Then give the person the link or file, and ask them to press
**Copy state** and paste the result back. That one round trip proves the whole loop.

## 6. Offer a repo profile

Skip this step without mentioning it unless all of these are true of the directory you were started in:

- It is inside a git repository, and that repository is not the pagekit clone.
- `pagekit profile`, run there, does not show a profile belonging to that repository.
- The repository has branding, such as a logo file, brand colors in its CSS or theme config, or a brand font.

If so, say what you found and offer to make pages created there match, in a single question. For example: "This repo
has a logo and brand colors. Should pages made here use them?" If they accept, follow the `setup-profile` skill from
that directory. If not, move on.

Do not ask about a personal profile.

## 7. Finish

Summarize in a few lines what you set up and whether the server is running. Mention that the check page deletes itself
after 30 days, and that `git pull` in the clone updates pagekit.

Tell them pages use the pagekit brand until a profile replaces it, and that they can ask you at any time to "set up a
pagekit profile for this repo" or to "set up my personal pagekit profile". Then suggest a first real page, based on what
you know about their work.
