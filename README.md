<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/lockup-dark.svg">
    <img src="docs/brand/lockup.svg" alt="pagekit" height="56">
  </picture>
</p>

# pagekit

**Polished, self-contained HTML pages for coding agents.**

Ask your agent for a report, a review, or a set of questions, and get a real page instead of a wall of terminal
text. The agent writes only the content. pagekit supplies the design, checks the result, and hands you one plain
file that works offline, prints well, and reads well on a phone. You can answer on the page and send your answers
straight back to the agent.

## Why pagekit

pagekit started from frustration with Claude artifacts. Artifacts are a good idea: agents should show their work as
pages, not terminal output. But they are tied to one product. Your pages live on claude.ai, and their branding
follows your account instead of your project, so work pages and personal pages can't reliably look like what they are.

pagekit keeps the idea and drops the tie-in:

| | Claude artifacts | pagekit |
| --- | --- | --- |
| **Where pages live** | Hosted on claude.ai | Plain files on your machine, which work offline |
| **Which agents** | Claude | Any agent that can run commands |
| **How they look** | Up to the model, or a design system you point it at | Your profile, the same on every page |
| **What sets the brand** | Your Claude account | The folder you work in, so each repo can have its own |
| **How you share** | Through claude.ai | Any way you can share a file, or as a bookmarked PDF |

## What to ask for

Once it is set up, just ask your agent in plain language:

- "Make a page reviewing this PR, with a checkbox on each finding so I can pick what to fix."
- "Put the three open decisions on a page, with your recommendation on each."
- "Write up this incident as a page I can send to the team, with a diagram of what happened."
- "Turn these requirements into a document for the customer, and give me a PDF."
- "Give me a status page for this migration, with the numbers at the top."

## What it can do

### Get answers back from a page

This is the part a static report can't do. Readers fill in forms and click any item ID to comment on it. Then one
button copies it all as a block the agent reads as your reply, so a page can be a real step in the conversation:

````text
```pagekit-response
page: pr-1462-review
fields:
  F-01.fix: true
  D-01.choice: option-b
comments:
  S-05: what happened here?
```
````

Answers survive a reload, and a page warns you before you lose ones you haven't copied. For a page going to an
outside reader, a profile can turn all of this off with `interactive = false`.

### Look right everywhere, without trying

- **Light and dark modes**, and phone layouts, on every page
- **An embedded font**, IBM Plex, so pages and PDFs look the same on every machine
- **Clean printing:** header and footer on every sheet, page numbers, collapsed sections opened, and tables that
  wrap instead of being cut off
- **Bookmarked PDFs** from one button on a served page, or `pagekit pdf`, including any answers typed on the page

### Rich content, ready to use

- **Components:** cards, callouts, tables, headline numbers, findings, decisions, before and after images, a
  document status table, a contents card, and more
- **Diagrams:** Mermaid flowcharts that follow your theme, drawn when the page is built
- **A generated table of contents:** `<pk-contents max-level="3"></pk-contents>` builds the list from the page's
  headings, so it can't go out of date
- **Icons:** the full Lucide set, plus your own
- **A library that grows:** when an agent builds something new, it saves it as a component for the next page

### Make it yours

Pages carry the pagekit brand until you replace it. A profile sets your logo, colors, fonts, footer, and writing
rules, and the folder you work in picks the profile, so a client repo can look like the client and everything else
can look like you. Override as little as you like, and the rest stays:

```toml
# .pagekit/profile/profile.toml
name = "acme"
brand = "Acme"
footer = "Prepared by Acme"
interactive = false       # for pages going to outside readers

[[banned]]                # fails the build if a page uses these words
pattern = '\bTBD\b'
why = "state what is true now"
```

`pagekit font add` embeds your own font, and `pagekit profile` shows what each brand file adds to every page.

### Catch mistakes before you see them

Every build runs checks, so an agent finds its own errors first: missing images, form controls whose answers would
be lost, external resources you didn't allow, and banned words, including words inside diagrams. A profile can also
add a check of its own, such as a lint for customer documents.

### Share it, keep it, or let it go

- **Share:** `pagekit pack` writes one self-contained file, and `pagekit send` hands it to whatever you share files
  with
- **Browse:** an optional local server lists your pages with search, and you can add it to a phone's home screen
- **Keep:** pages expire after 30 days so they don't pile up, and `pagekit save` keeps the ones that matter, with a
  hook for filing them wherever you keep notes

Nothing needs to stay running. A built page is one plain file, and the Python standard library is pagekit's only
dependency.

## Set up with your agent

The quickest way in. Paste this into your coding agent, and it will install pagekit, connect itself, and walk you
through the optional local server:

```text
Set up pagekit for me. Clone https://github.com/ryanf9802/pagekit.git somewhere permanent, then read
docs/agent-setup.md in the clone and follow it step by step. Ask me one question at a time, including
whether I want the local server.
```

Tested on Linux, WSL, and Windows. Any agent that can run commands can follow it.

## Set up by hand

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). A local Chrome, Chromium, or Edge is optional, and only
diagrams and generated PDFs use it.

```bash
# Install from a clone, and keep the clone: the command runs from it.
git clone https://github.com/ryanf9802/pagekit.git
cd pagekit
uv tool install --editable .

# Make a page, from anywhere.
pagekit new hello --title "Hello"     # prints the file to write and the house rules
pagekit build hello                   # composes the page and checks it
```

Then give your agent the skills in the clone's `src/pagekit/skills`, and ask it for a page.

## Set up a profile

Once pagekit is set up, ask your agent from the folder you want to brand:

```text
Set up a pagekit profile for this repo.
Set up my personal pagekit profile.
```

A repo profile applies in that repo, and a personal profile applies wherever no other profile does. To do it by
hand, see [Profiles](docs/profiles.md).

## Stay up to date

Ask your agent to "update pagekit", or run `pagekit update`. Either way pulls in new components and features, and you
see what changed.

## Documentation

| Guide | Covers |
| --- | --- |
| [Agent setup guide](docs/agent-setup.md) | The steps your agent follows in the prompt above |
| [Getting started](docs/getting-started.md) | Install, connecting an agent, your first page, and updating |
| [Writing pages](docs/pages.md) | The page workflow, checks, sharing, saving, and expiry |
| [Generated tags](docs/tags.md) | Content the build works out from the page, such as a table of contents |
| [Profiles](docs/profiles.md) | Making pagekit yours: brand, theme, rules, and hooks |
| [Components](docs/components.md) | The core set and your growing library |
| [Icons](docs/icons.md) | Lucide icons, tones, and adding your own |
| [Diagrams](docs/diagrams.md) | Mermaid flowcharts that follow your theme |
| [Answers and comments](docs/answers.md) | Getting input back from readers |
| [Printing and PDFs](docs/printing.md) | Print layout and bookmarked PDFs |
| [Serving pages](docs/serving.md) | The page index, SSH, and your other devices |
| [Command reference](docs/commands.md) | Every command and environment variable |

## Development

```bash
uv run --group dev pytest
```

## License

[MIT](LICENSE). The bundled Lucide icons, Mermaid, and IBM Plex fonts keep their own licenses, in `src/pagekit/static/`.
