# Contributing

`pagekit update` pulls `main`, so every merge reaches users straight away. Everything here exists to keep `main` safe to
ship.

## Set up

You need [uv](https://docs.astral.sh/uv/). uv installs Python and the development tools for you.

```bash
git clone https://github.com/ryanf9802/pagekit.git
cd pagekit
uv run --group dev pytest
```

To try your changes as the `pagekit` command, run `uv run pagekit`, or `uv tool install --editable .` from your clone.

## Make a change

1. **Start with an issue.** Anything beyond a typo or a small docs fix starts as a
   [GitHub issue](https://github.com/ryanf9802/pagekit/issues/new/choose), so the scope is agreed before the work begins.
2. **Work on a branch** named after the issue, such as `42-rebuild-all`. Fork the repo first if you cannot push to it.
3. **Check your work** before pushing:

   ```bash
   uv run --group dev pytest
   uv run --group dev ruff check
   ```

   For anything that changes how a page looks or behaves, build a page and look at it, including at phone width, in dark
   mode, and in print.
4. **Open a pull request** to `main`, and link the issue with `Fixes #42`.
5. **Merge** once CI passes. Pull requests are squash merged, and the branch is deleted automatically.

Direct pushes to `main` are refused, for everyone.

## Name your pull request well

The title becomes the commit subject, and `pagekit update` shows those subjects to users. Write it for them, as a scope and
an imperative:

```text
index: use the same header as other pages
profiles: add overrides for settings on one machine
```

Keep a pull request to one change. If you find something else to fix, open another issue.

## Project rules

CI or the tests enforce some of these. The rest rely on you and your reviewer.

- **No runtime dependencies.** pagekit runs on the Python standard library alone. Development tools go in the `dev`
  group.
- **Python 3.11 and newer**, on Linux, WSL, and Windows. CI runs the oldest and the latest supported Python on both
  Ubuntu and Windows.
- **UTF-8 everywhere.** Every text read, write, and subprocess names its encoding, because Windows otherwise uses a legacy
  code page.
- **Pages work offline.** A built page is one self-contained file. Nothing in core may need the network or a server.
- **Keep one source for the chrome.** The header, footer, and theme come from the shared code and the profile. Do not add a
  second copy for one page.
- **Components use only `--pk-*` tokens**, so every profile can restyle them. Their classes start with the component's
  name.
- **Nothing specific to one company, person, or machine** goes in core: no names, home paths, or hostnames. Those belong
  in a [profile or an override](docs/profiles.md).
- **Update the docs in the same pull request** when behavior changes. Docs and skills use plain ASCII.

## Report a security problem

See [SECURITY.md](SECURITY.md). Do not open a public issue.
