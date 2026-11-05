# Icons

All [Lucide](https://lucide.dev) icons ship with pagekit, and a page embeds only the ones it uses.

```text
pagekit icons WORD                                        search by name or tag
<i data-icon="NAME" tone="blue" aria-label="..."></i>     tone and label are optional
```

- **Tones** are blue, purple, green, teal, orange, success, warning, danger, accent, and muted. Each follows
  light and dark.
- **Labels:** add `aria-label` when an icon stands alone with no text. Otherwise it is hidden from screen readers.
- **Size** is 1em with no margin, so use a space or component CSS for the gap.
- **Errors:** an unknown name or tone fails the build.
- **Styling:** the build turns the tag into `<svg class="pk-icon">`, so component CSS targets `.pk-icon`, not
  `i[data-icon]`.

## Your own icons

A profile adds icons in its `icons/` folder. They are used the same way and take priority over Lucide.

| File | Purpose |
| --- | --- |
| `icons/NAME.svg` | The icon. It can be multicolor, with gradients and simple `.class` styles, which are namespaced so they cannot collide. Scripts are refused. |
| `icons/NAME-dark.svg` | Optional dark-mode version. Print always uses a light version. |
| `icons/NAME-print.png` | Optional image for print, about 128 px. |

## Size in PDFs

A page stores each icon once and points to it, so hundreds of marks stay small: a plain Lucide icon costs about
110 bytes per use. Chromium redraws a complex vector on every use, though, about 1 KB each for a gradient logo.
Give a complex icon used many times a `NAME-print.png`, because an image is stored once.

## Updating Lucide

Run `scripts/update_lucide.py` to refresh the icon set. Lucide's ISC license is in
`src/pagekit/static/lucide-LICENSE`.
