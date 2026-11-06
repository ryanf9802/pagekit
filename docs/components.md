# Components

Components keep pages consistent. There are three layers, and each has one job:

- **Core** ships with pagekit: callout, divider, diagram, chart, table, grid, tile row, status, collapsed section,
  figure, before and after, finding card, and decision card. These change only by deliberate choice.
- **Bundled** components also ship with pagekit, for longer documents: contents card, document status, at a
  glance, in short, details layer, rule list, rule table, field map, checklist, and page break. Like the library,
  their styles reach only the pages that use them, so they add nothing to other pages.
- **Your library**, in `~/.pagekit/library/`, holds anything an agent builds that core does not cover. Agents
  add to it as they work, with no user involved, and one library serves every profile.
- **Profiles** set the look and writing rules. A profile restyles components through theme tokens rather than
  defining its own versions of them.

## Commands

```text
pagekit component list [--json]
pagekit component show NAME [NAME...]
pagekit component add NAME --when TEXT --from FOLDER [--update]
```

`show` prints the markup of one or more components to copy into a page, separated by a blank line. Name several to save calls; if any name is unknown, nothing is printed.

## Adding to the library

The folder passed to `--from` holds `component.html` and an optional `component.css`. `--when` is one line on
when to use it, which is what later agents see in the list.

`add` keeps the library consistent by refusing:

- Hard-coded colors, since styles use `--pk-*` tokens
- Inline styles
- Classes that do not start with the component's name
- Core names, and existing names unless `--update` is passed

Saving a component with a bundled name is allowed, and your copy then wins for every page.

`--update` replaces the library's copy for every page on its next build, so use it only for changes that suit
all of them.

A build adds a library component's CSS only to pages that use it. When the library is in a git repository,
`add` commits that folder locally and never pushes.
