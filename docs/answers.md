# Answers and comments

A page can collect input as well as show information. The reader answers on the page, presses **Copy state** in
the footer, and pastes the result to the agent.

## What gets copied

The button copies every named `input`, `select`, `textarea`, `[contenteditable]`, and `details[id]`, plus anything
registered with `pagekit.register(name, getter)`. Password and hidden inputs are never exported.

````text
```pagekit-response
page: pr-1462-review
title: PR 1462 Review
profile: acme
source: /home/you/pages/acme/pr-1462-review/index.html
built: 2026-11-04T18:02:11Z
fields:
  F-01.fix: true
  D-01.choice: option-b
comments:
  S-05: what happened here?
```
````

Empty values mean unanswered, not "no". `source` points at the page, so an agent can read `content.html` beside it
to see what each name refers to.

Give every control a stable name keyed to an item ID. The `decision-card` component shows the pattern.

## Comments

Any item ID marked `<span class="pk-id">` is clickable. It opens a floating comment box, stays marked once
commented, and reopens on another click. Comments are copied under `comments:`, keyed by ID, and the footer shows
a count that steps through them. Comments do not print.

## Answering

- Clicking a selected radio option clears it, as does pressing Space on it.
- Text boxes grow to fit what is typed.
- Closing or reloading a page asks first when it has answers or comments that have not been copied. Browsers do
  not let a page cancel Ctrl+W itself, so this prompt is the guard. Opening a collapsed section does not count as
  a change.

## What survives a rebuild

Answers and comments survive a reload and a style-only rebuild, in `localStorage`. They reset when `content.html`
changes, so collect them before changing a page.
