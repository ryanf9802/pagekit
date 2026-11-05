<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="docs/brand/lockup-dark.svg">
    <img src="docs/brand/lockup.svg" alt="pagekit" height="56">
  </picture>
</p>

# pagekit

**Self-contained HTML pages for coding agents.**

Ask your agent for a page instead of a wall of terminal text. You get one plain file that works offline, prints well,
and reads well on a phone, and you can answer on the page and send your answers straight back to the agent.

## Set up with your agent

The quickest way in. Paste this into your coding agent, and it will install pagekit, connect itself, make a test page,
and offer the optional local server. Prefer to do it yourself? [Set up by hand](#set-up-by-hand).

```text
Set up pagekit for me. Clone https://github.com/ryanf9802/pagekit.git somewhere permanent, then read
docs/agent-setup.md in the clone and follow it step by step. Ask me one question at a time, including
whether I want the local server.
```

Tested on Linux, WSL, and Windows. Any agent that can run commands can follow it. Pages carry the pagekit brand until
you [set up a profile](#set-up-a-profile).

## Ask for a page

**The word "page" is what tells your agent to use pagekit**, so use it when you want one:

- "Make a **page** reviewing this PR, with a checkbox on each finding so I can pick what to fix."
- "Put the three open decisions on a **page**, with your recommendation on each."
- "Write up this incident as a **page** I can send to the team, with a diagram of what happened."
- "Give me a status **page** for this migration, with the numbers at the top."

## What you get

- **Two-way.** Answer forms and comment on items, then one button copies it all back to the agent as your reply.
- **Ready to share.** Light and dark modes, phone layouts, clean printing, and bookmarked PDFs come standard.
- **Rich content.** Components, Lucide icons, Mermaid diagrams, and a table of contents generated from the headings.
- **Yours when you want.** A profile sets your logo, colors, fonts, footer, and writing rules, and the folder you work
  in picks the profile, so each repo can have its own.
- **Checked.** Every build catches missing images, lost answers, and words you have banned before you see the page.
- **Nothing to run.** A built page is one plain file. The Python standard library is the only dependency, the page
  index server is optional, and pages expire after 30 days unless you save them.

## Why pagekit

pagekit started from frustration with Claude artifacts. Showing work as a page is a good idea, but artifacts live on
claude.ai, work only with Claude, and take their branding from your account instead of your project. pagekit keeps the
idea and drops the tie-in: plain files on your machine, any agent that can run commands, and a brand set by the folder
you work in.

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

Once pagekit is set up, ask your agent to set up a pagekit profile, either for the repo you're in or a personal one for
you. A repo profile applies in that repo, and a personal profile applies wherever no other profile does. To do it by
hand, see [Profiles](docs/profiles.md).

## Stay up to date

Ask your agent to "update pagekit", or run `pagekit update`, and you see what changed. An update might bring:

- New core components and generated tags
- Agent instructions that use fewer tokens
- Smaller, cleaner PDFs
- Design and print improvements, and bug fixes

Pages you have already built keep their look until you rebuild them.

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

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE). The bundled Lucide icons, Mermaid, and IBM Plex fonts keep their own licenses, in `src/pagekit/static/`.
