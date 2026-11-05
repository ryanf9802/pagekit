<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/lockup-dark.svg">
    <img src="docs/brand/lockup.svg" alt="pagekit" height="56">
  </picture>
</p>

# pagekit

**Polished, self-contained HTML pages for coding agents.**

Ask an agent for a report, a review, or a set of questions, and get a page instead of a wall of
terminal text. Every page looks like it came from the same designer, works offline, prints well, and
reads well on a phone.

- **Yours when you want.** Pages carry the pagekit brand until a profile sets your theme, logo, footer,
  and writing rules. The working directory picks the profile, so each repo can have its own.
- **Two-way.** Readers answer forms and comment on items, then one button copies it all back to the agent.
- **Ready to share.** Light and dark modes, phone layouts, clean printing, and bookmarked PDFs come standard.
- **Rich content.** Components, Lucide icons, and Mermaid diagrams are built in, and agents grow a shared
  library as they work.
- **Nothing to run.** A built page is one plain file. The Python standard library is the only dependency,
  and the page index server is optional.
- **Tidy.** Pages expire after 30 days unless you save them.

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

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

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

## Make it yours

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

[MIT](LICENSE). The bundled Lucide icons and Mermaid keep their own licenses, in `src/pagekit/static/`.
