# Command reference

Run `pagekit COMMAND --help` for every option. Page commands accept `--profile`.

## Pages

```text
pagekit new SLUG --title T [--summary S] [--mode slots|free]
                          create the page, or reopen it to update in place
pagekit build SLUG        compose index.html, then run the checks
pagekit check SLUG        run the checks only
pagekit pack SLUG         write one self-contained file, with images embedded
pagekit send SLUG         pack, then run the profile's send command
pagekit pdf SLUG [--out FILE]
                          write a bookmarked, tagged PDF
pagekit save SLUG         keep it: copy to the save location, pin the working copy
pagekit ls [--json]       list pages, newest first
pagekit prune [--older-than-days N] [--dry-run]
                          delete unpinned pages past their expiry
```

## Profiles

```text
pagekit profile           print the resolved profile and its instructions
pagekit update [--check]  update pagekit from its clone, or list what an update would bring in
pagekit init [--name NAME] [--brand BRAND] [--when TEXT] [--extends PROFILE] [--personal | --local | --also]
pagekit font add FILE --family NAME [--weight N] [--italic]
                          create a profile
```

## Components and icons

```text
pagekit component list [--json]
pagekit component show NAME
pagekit component add NAME --when TEXT --from FOLDER [--update]
pagekit icons WORD        search icons by name or tag
```

## Server

```text
pagekit serve             run the page index
pagekit install-service [--port PORT] [--public-url URL]
                          install and start a systemd user service
```

## Environment variables

| Variable | Effect | Default |
| --- | --- | --- |
| `PAGEKIT_HOME` | Where pages live | `~/pages` |
| `PAGEKIT_PROFILE` | Use this profile instead of finding one from the working directory | |
| `PAGEKIT_TTL_DAYS` | Days before an unpinned page expires, or `0` to turn off | `30` |
| `PAGEKIT_PORT` | The page index's port | `8766` |
| `PAGEKIT_CHROME` | Path to Chrome or Chromium | Found automatically |
| `PAGEKIT_SESSION` | A label recorded on pages, such as the agent session's name | |
