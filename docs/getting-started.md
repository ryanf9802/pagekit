# Getting started

pagekit needs Python 3.11 or newer and has no other dependencies. Local Chrome or Chromium is optional:
only [diagrams](diagrams.md) and [generated PDFs](printing.md#bookmarked-pdfs) use it.

## Install

Clone the repository, then install the command from inside it with [uv](https://docs.astral.sh/uv/):

```bash
git clone https://github.com/ryanf9802/pagekit.git
cd pagekit
uv tool install --editable .
```

Keep the clone where it is: an editable install runs from it, so `git pull` there updates pagekit. After this,
`pagekit` works from any directory.

## Create your profile

A profile is what makes pages yours. Start with a personal one, which applies wherever no other profile does:

```bash
pagekit init --personal --name personal --brand "Your Name"
```

[Profiles](profiles.md) covers adding a logo, colors, and writing rules, and setting up one per project.

## Connect your agent

The `create-page` skill teaches an agent the workflow. From the clone, link it into your agent's skills folder:

```bash
ln -s "$PWD/src/pagekit/skills/create-page" YOUR_AGENT_SKILLS_FOLDER/create-page
```

An agent without skill support can follow the same steps from that file's text.

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

## Where things live

| Path | Holds |
| --- | --- |
| `~/pages/<profile>/<slug>/` | Each page: `content.html`, `assets/`, and the built `index.html` |
| `~/.pagekit/profile/` | Your personal profile |
| `~/.pagekit/profiles/` | Profiles kept outside their projects |
| `~/.pagekit/library/` | Components saved for reuse |

Set `PAGEKIT_HOME` to keep pages somewhere other than `~/pages`. There is no database: the folders are the
whole state.
