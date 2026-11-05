"""Mermaid flowcharts as themed inline SVG, drawn once at build time so pages stay offline.

An author writes assets/NAME.mmd and <pk-diagram src="assets/NAME.mmd"></pk-diagram>. Mermaid runs in
local Chromium, measuring text with the profile's font. All of its colors and styles are then removed
in favor of classes, so a diagram follows the theme in light mode, dark mode, and print.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import tempfile
from importlib import resources
from pathlib import Path

from .browser import find_chrome

_TAG_RE = re.compile(r"""<pk-diagram\s+src\s*=\s*["']assets/([a-z0-9][a-z0-9-]*\.mmd)["']\s*>(.*?)</pk-diagram>""", re.DOTALL)
_FRONT_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_ELEMENT_RE = re.compile(r"<(\w+)\b[^>]*?>")
_OUTPUT_RE = re.compile(r'<textarea id="out">(.*?)</textarea>', re.DOTALL)
_FONT_RE = re.compile(r"--pk-font:\s*([^;]+);")
_KEEP = {
    "node", "edgeLabel", "label", "flowchart-link", "edge-thickness-thick",
    "edge-pattern-dashed", "edge-pattern-dotted", "marker", "cross",
}  # fmt: skip
TONES = {"strong", "neutral", "accent", "danger", "muted"}
_TIMEOUT_SECONDS = 90
# Changing this redraws every diagram.
_PIPELINE_VERSION = "1"
_CACHE_DIR = ".diagram-cache"
# Sizes and spacing only. Colors come from the theme, through the classes added below.
_MERMAID_CONFIG = {
    "startOnLoad": False,
    "securityLevel": "loose",
    "theme": "base",
    "themeVariables": {"fontSize": "15px"},
    "flowchart": {
        "htmlLabels": False,
        "curve": "linear",
        "padding": 8,
        "nodeSpacing": 30,
        "rankSpacing": 44,
        "useMaxWidth": True,
        "wrappingWidth": 420,
    },
}


class DiagramError(Exception):
    pass


def parse_source(name: str, text: str) -> tuple[str, str, str]:
    """Split a .mmd file into title, description, and Mermaid source, and hold it to the rules."""
    match = _FRONT_RE.match(text)
    fields: dict[str, str] = {}
    if match:
        for line in match.group(1).splitlines():
            key, _, value = line.partition(":")
            fields[key.strip()] = value.strip()
        text = text[match.end() :]
    title, desc = fields.get("title", ""), fields.get("desc", "")
    if not title or not desc:
        raise DiagramError(f"{name}: start with --- title: ... desc: ... --- so readers and screen readers get both")
    if not re.match(r"\s*(flowchart|graph)\b", text):
        raise DiagramError(f"{name}: only flowchart diagrams are supported")
    for line in text.splitlines():
        statement = line.strip()
        if re.match(r"(classDef|style|linkStyle)\b", statement):
            raise DiagramError(f"{name}: no {statement.split()[0]}, since colors come from the theme: use class NODE TONE")
        if statement.startswith("class "):
            tone = statement.split()[-1].rstrip(";")
            if tone not in TONES:
                raise DiagramError(f"{name}: unknown tone {tone!r}: use {', '.join(sorted(TONES))}")
    for tone in re.findall(r":::([\w-]+)", text):
        if tone not in TONES:
            raise DiagramError(f"{name}: unknown tone {tone!r}: use {', '.join(sorted(TONES))}")
    return title, desc, text


def _render_page(source: str, svg_id: str, fonts_css: str, font_family: str) -> str:
    config = {**_MERMAID_CONFIG, "fontFamily": font_family}
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts_css}
body {{ font-family: {font_family}; }}</style>
<script src="{resources.files("pagekit").joinpath("static/mermaid.min.js").as_uri()}"></script></head>
<body><span style="font-weight:400">a</span><b>a</b><textarea id="out"></textarea><script>
(async function () {{
  var out = document.getElementById("out");
  try {{
    await document.fonts.ready;
    mermaid.initialize({json.dumps(config)});
    var result = await mermaid.render({json.dumps(svg_id)}, {json.dumps(source)});
    out.textContent = result.svg;
  }} catch (err) {{
    out.textContent = "ERROR: " + err.message;
  }}
}})();
</script></body></html>"""


def _draw(source: str, svg_id: str, fonts_css: str, font_family: str) -> str:
    chrome = find_chrome()
    if not chrome:
        raise DiagramError("drawing a diagram needs Chrome or Chromium: set PAGEKIT_CHROME to its path")
    with tempfile.TemporaryDirectory(prefix="pagekit-diagram-") as folder:
        page = Path(folder) / "draw.html"
        page.write_text(_render_page(source, svg_id, fonts_css, font_family))
        command = [
            chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--allow-file-access-from-files",
            "--virtual-time-budget=20000", f"--user-data-dir={folder}/profile", "--dump-dom", page.as_uri(),
        ]  # fmt: skip
        try:
            result = subprocess.run(
                command, capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=_TIMEOUT_SECONDS
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise DiagramError(f"drawing failed: {exc}") from exc
    match = _OUTPUT_RE.search(result.stdout)
    output = html.unescape(match.group(1)).strip() if match else ""
    if output.startswith("ERROR: "):
        raise DiagramError(f"Mermaid could not draw it: {output[7:]}")
    if not output.startswith("<svg"):
        raise DiagramError(f"drawing failed: {result.stderr.strip()[-300:] or 'no output'}")
    return output


def themed_svg(raw: str, svg_id: str, title: str, desc: str) -> str:
    """Remove Mermaid's own styling, keeping only the classes the theme styles."""
    svg = re.sub(r"<style>.*?</style>", "", raw, flags=re.DOTALL)
    svg = re.sub(r"<(linear|radial)Gradient.*?</\1Gradient>", "", svg, flags=re.DOTALL)
    width = re.search(r"max-width:\s*([\d.]+)px", svg[: svg.index(">")])

    def element(match: re.Match) -> str:
        tag = match.group(0)
        found = re.search(r'\sclass="([^"]*)"', tag)
        names = found.group(1).split() if found else []
        kept = [f"pk-diagram-{name}" for name in names if name in _KEEP]
        kept += [f"pk-diagram-tone-{name}" for name in names if name in TONES]
        tag = re.sub(r'\sstyle="[^"]*"', "", tag)
        tag = re.sub(r'\s(?:fill|stroke)="#[^"]*"', "", tag)
        tag = re.sub(r'\sclass="[^"]*"', "", tag)
        if kept:
            tag = re.sub(r"^(<\w+)", lambda m: f'{m.group(1)} class="{" ".join(kept)}"', tag, count=1)
        return tag

    svg = _ELEMENT_RE.sub(element, svg)
    natural = f' style="--pk-diagram-w:{round(float(width.group(1)))}px"' if width else ""
    labels = f'role="img" aria-labelledby="{svg_id}-t {svg_id}-d"{natural}'
    svg = re.sub(r'\saria-roledescription="[^"]*"', "", svg, count=1)
    svg = re.sub(r'\srole="[^"]*"', "", svg, count=1)
    alt = f'<title id="{svg_id}-t">{html.escape(title)}</title><desc id="{svg_id}-d">{html.escape(desc)}</desc>'
    return re.sub(r"^<svg\b([^>]*)>", lambda m: f"<svg{m.group(1)} {labels}>{alt}", svg, count=1)


def _font_family(theme: str) -> str:
    # The last definition is the profile's own.
    found = _FONT_RE.findall(theme)
    return found[-1].strip() if found else "sans-serif"


def _cached_svg(page_dir: Path, source_text: str, svg_id: str, fonts_css: str, theme: str) -> str:
    name = f"{svg_id}.mmd"
    title, desc, source = parse_source(name, source_text)
    family = _font_family(theme)
    engine = resources.files("pagekit").joinpath("static/mermaid.min.js").read_bytes()
    key = hashlib.sha256(
        "\0".join([_PIPELINE_VERSION, source_text, svg_id, family, fonts_css, hashlib.sha256(engine).hexdigest()]).encode()
    ).hexdigest()[:24]
    cache = page_dir / _CACHE_DIR
    path = cache / f"{svg_id}-{key}.svg"
    if path.is_file():
        return path.read_text()
    svg = themed_svg(_draw(source, svg_id, fonts_css, family), svg_id, title, desc)
    cache.mkdir(exist_ok=True)
    for old in cache.glob(f"{svg_id}-*.svg"):
        old.unlink()
    path.write_text(svg)
    return svg


def expand_diagrams(document: str, page_dir: Path, fonts_css: str, theme: str) -> str:
    """Replace each <pk-diagram> with its figure. Anything inside the tag becomes a note below it."""

    def figure(match: re.Match) -> str:
        filename, note = match.group(1), match.group(2).strip()
        source = page_dir / "assets" / filename
        if not source.is_file():
            raise DiagramError(f"missing diagram source: assets/{filename}")
        text = source.read_text()
        svg_id = filename[: -len(".mmd")]
        title = parse_source(filename, text)[0]
        svg = _cached_svg(page_dir, text, svg_id, fonts_css, theme)
        label = html.escape(f"Diagram: {title}", quote=True)
        return (
            f'<figure class="pk-diagram" id="diagram-{svg_id}"><figcaption>{html.escape(title)}</figcaption>'
            f"<!-- Mermaid source: assets/{filename} -->"
            f'<div class="pk-diagram-scroll" tabindex="0" role="region" aria-label="{label}">{svg}</div>'
            f"{note}</figure>"
        )

    return _TAG_RE.sub(figure, document)
