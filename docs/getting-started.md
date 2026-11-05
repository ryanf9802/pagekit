# Getting started

To have your coding agent do all of this for you, use the prompt in the [README](../README.md#set-up-with-your-agent).

pagekit needs Python 3.11 or newer and has no other dependencies. A local Chrome, Chromium, or Edge is optional:
only [diagrams](diagrams.md) and [generated PDFs](printing.md#bookmarked-pdfs) use it.

| Platform | Support |
| --- | --- |
| Linux and WSL | Everything |
| Windows | Everything except `pagekit install-service`, which needs systemd. [Start the server at login](serving.md#starting-at-login) instead. |
| macOS | Expected to match Windows, but not yet tested. |

## Install

Clone the repository, then install the command from inside it with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/ryanf9802/pagekit.git
cd pagekit
uv tool install --editable .
```

Keep the clone where it is: an editable install runs from it. After this, `pagekit` works from any directory.

## Connect your agent

The `create-page` skill teaches an agent to make pages, `setup-profile` to set up a profile, and `update-pagekit` to
update pagekit. From the clone, link them into your agent's skills folder:

```bash
ln -s "$PWD/src/pagekit/skills/create-page" YOUR_AGENT_SKILLS_FOLDER/create-page
ln -s "$PWD/src/pagekit/skills/setup-profile" YOUR_AGENT_SKILLS_FOLDER/setup-profile
ln -s "$PWD/src/pagekit/skills/update-pagekit" YOUR_AGENT_SKILLS_FOLDER/update-pagekit
```

On Windows, use `mklink /J YOUR_AGENT_SKILLS_FOLDER\create-page src\pagekit\skills\create-page` from Command
Prompt, and the same for the other two. An agent without skill support can follow the same steps from each
`SKILL.md`.

## Make a page

```bash
pagekit new hello --title "Hello" --summary "My first page"
```

This prints the file to write, the components available, and the profile's rules. Write the page body to
the printed `content.html`, then build:

```bash
pagekit build hello
```

The build prints the page's location and any check that failed. Open the file in a browser, or run the
[page index](serving.md) to browse all your pages.

## Make it yours

Pages carry the pagekit brand until a profile replaces it. From the folder you want to brand, ask your agent to "set
up a pagekit profile for this repo" or to "set up my personal pagekit profile". [Profiles](profiles.md) covers doing
it by hand.

## Keep it up to date

Ask your agent to "update pagekit", and it will pull in the newest release and tell you what changed. To do it yourself:

```bash
pagekit update --check    # list what an update would bring in
pagekit update            # move to the newest release, reinstall if needed, and restart the server
pagekit update --main     # follow the main branch instead, to try changes before they are released
```

`pagekit update` runs from the clone, and stops without changing anything if the clone has uncommitted changes or is on
another branch. It never moves a clone backwards, so a clone ahead of the newest release (after `--main`) stays put. It
names any new skill to link. Pages already built keep their old look until you run `pagekit build SLUG`.

To make one machine follow `main` every time, such as the machine you develop pagekit on, put this in
`~/.pagekit/update.toml`:

```toml
follow = "main"
```

Then plain `pagekit update` follows `main` there, and says so. `--releases` follows the newest release for one run, and
`--main` follows `main` for one run on a machine that follows releases. A flag always beats the file. A value other than
`"releases"` or `"main"` is an error that names the file.

### Which version is this

```bash
pagekit --version
```

At a release it prints that release, such as `pagekit 0.1.8`. A machine that follows `main` is usually past the last
release, so it prints the release, the commits since it, and the commit: `pagekit 0.1.8+3.g1234abc` is three commits
after 0.1.8, at commit `1234abc`. A `.dirty` on the end means the clone has uncommitted changes. If git cannot tell
(a shallow clone with no tags), it counts from `0.0.0`.

The version is read from the clone's git history each time, never stored, so it is right straight after an update. It
counts from the release tags the clone has, and `pagekit update` or `pagekit update --check` fetches new ones. So a
commit that CI has just released still reads as `0.1.8+1.g...` until the next fetch turns it into `0.1.9`. The number of
the next release is not known until CI tags it, which is why a machine on `main` shows how far past the last one it is.

`pagekit update` and `pagekit update --check` name both versions, in either mode:

```text
updated pagekit 0.1.8 -> 0.1.9 with 3 change(s):
updated pagekit 0.1.9+1.g0aebe28 -> 0.1.9+4.g1234abc with 3 change(s):
2 update(s) available (0.1.8 -> 0.1.9): run pagekit update
pagekit 0.1.9 is up to date
```

## Where things live

| Path | Holds |
| --- | --- |
| `~/pages/<profile>/<slug>/` | Each page: `content.html`, `assets/`, and the built `index.html` |
| `~/.pagekit/profile/` | Your personal profile, if you make one |
| `~/.pagekit/profiles/` | Profiles kept outside their projects |
| `~/.pagekit/overrides/` | [Settings for this machine](profiles.md#overrides), layered on top of any profile |
| `~/.pagekit/library/` | Components saved for reuse |

Set `PAGEKIT_HOME` to keep pages somewhere other than `~/pages`. There is no database: the folders are the
whole state.
