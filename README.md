# pagekit

**Polished, self-contained HTML pages for coding agents.**

Ask an agent for a report, a review, or a set of questions, and get a page instead of a wall of
terminal text. You bring the brand once, as a profile. Every page after that looks like it came from
the same designer, works offline, prints well, and reads well on a phone.

- **On brand by default.** A profile sets the theme, logo, footer, and writing rules, and the working
  directory picks the profile.
- **Two-way.** Readers answer forms and comment on items, then one button copies it all back to the agent.
- **Ready to share.** Light and dark modes, phone layouts, clean printing, and bookmarked PDFs come standard.
- **Rich content.** Components, Lucide icons, and Mermaid diagrams are built in, and agents grow a shared
  library as they work.
- **Nothing to run.** A built page is one plain file. The Python standard library is the only dependency,
  and the page index server is optional.
- **Tidy.** Pages expire after 30 days unless you save them.

## Quick start

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv tool install --editable .
pagekit init --personal --name personal --brand "Your Name"

pagekit new hello --title "Hello"     # prints the file to write and the house rules
pagekit build hello                   # composes the page and checks it
```

Then give your agent the skill in `src/pagekit/skills/create-page`, and ask it for a page.

## Documentation

| Guide | Covers |
| --- | --- |
| [Getting started](docs/getting-started.md) | Install, your first profile, and connecting an agent |
| [Writing pages](docs/pages.md) | The page workflow, checks, sharing, saving, and expiry |
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
