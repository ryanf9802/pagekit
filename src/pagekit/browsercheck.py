"""Look at a built page in headless Chrome at phone width: overflow and console errors, in light and dark.

Chrome prints the DOM after the page runs (--dump-dom), so a small script injected into a copy of the page writes its
measurements into the DOM and we read them back. That needs no debugging protocol and no dependency.
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from .browser import find_chrome
from .pages import PHONE_WIDTH_PX, Page, PageError

_TIMEOUT_SECONDS = 120
MAX_OFFENDERS = 5
_SCREENSHOT_MAX_HEIGHT = 16000
_RESULT_ID = "pagekit-browser-check"
SCHEMES = ("light", "dark")

# First in the head, so it sees errors from every later script and resource.
_COLLECTOR = """<script>
window.__pkErrors = [];
window.addEventListener("error", function (e) {
  var t = e.target;
  if (t && t !== window && (t.src || t.href)) { window.__pkErrors.push("failed to load " + (t.src || t.href)); }
  else { window.__pkErrors.push(String(e.message || e)); }
}, true);
window.addEventListener("unhandledrejection", function (e) { window.__pkErrors.push("unhandled rejection: " + e.reason); });
var __pkConsoleError = console.error;
console.error = function () {
  window.__pkErrors.push(Array.prototype.map.call(arguments, String).join(" "));
  return __pkConsoleError.apply(console, arguments);
};
</script>"""

# Last in the body; it reports to the harness page that frames this one. Elements inside a clipping or scrolling container (tables, code, wide diagrams) are meant to be
# wider than the screen, so they are not offenders.
_MEASURE = """<script>
window.addEventListener("load", function () {
  setTimeout(function () {
    var width = window.innerWidth, root = document.documentElement, offenders = [];
    function clipped(el) {
      for (var p = el.parentElement; p && p !== root && p !== document.body; p = p.parentElement) {
        if (p.classList.contains("pk-table-wrap")) { return true; }
        if (getComputedStyle(p).overflowX !== "visible") { return true; }
      }
      return false;
    }
    var all = document.body.getElementsByTagName("*"), flagged = [];
    for (var i = 0; i < all.length; i++) {
      var el = all[i], r = el.getBoundingClientRect();
      if (!r.width || !r.height || el.tagName === "SCRIPT" || el.tagName === "STYLE") { continue; }
      // Its box, or content spilling out of its box, reaches past the screen.
      var scrolls = el.classList.contains("pk-table-wrap") || getComputedStyle(el).overflowX !== "visible";
      var reach = scrolls ? r.right : Math.max(r.right, r.left + el.scrollWidth);
      if (reach > width + 0.5 && !clipped(el)) { flagged.push({el: el, reach: reach}); }
    }
    // The innermost elements are the cause; their ancestors only inherit the overflow.
    for (var j = 0; j < flagged.length && offenders.length < __MAX__; j++) {
      var inner = flagged.some(function (o) { return o.el !== flagged[j].el && flagged[j].el.contains(o.el); });
      if (!inner) {
        var f = flagged[j].el;
        offenders.push({tag: f.tagName.toLowerCase(), cls: f.getAttribute("class") || "", id: f.id || "",
                        right: Math.round(flagged[j].reach)});
      }
    }
    var out = JSON.stringify({scrollWidth: root.scrollWidth, width: width, height: root.scrollHeight,
                              offenders: offenders, dark: matchMedia("(prefers-color-scheme: dark)").matches, errors: window.__pkErrors}).replace(/</g, "\\u003c");
    parent.postMessage(out, "*");
  }, 300);
});
</script>"""


@dataclass
class SchemeResult:
    scheme: str
    scroll_width: int
    width: int
    height: int = 0
    offenders: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    dark: bool = False

    @property
    def overflow(self) -> int:
        return max(0, self.scroll_width - self.width)

    @property
    def ok(self) -> bool:
        return not self.overflow and not self.offenders and not self.errors


def parse_result(scheme: str, dom: str) -> SchemeResult:
    match = re.search(rf'<script type="application/json" id="{_RESULT_ID}">(.*?)</script>', dom, re.DOTALL)
    if not match:
        raise PageError(f"browser check: the page gave no measurements in {scheme} mode")
    data = json.loads(match.group(1))
    return SchemeResult(
        scheme,
        int(data["scrollWidth"]),
        int(data["width"]),
        int(data.get("height", 0)),
        list(data.get("offenders", [])),
        [str(e) for e in data.get("errors", [])],
        bool(data.get("dark")),
    )


def format_results(results: list[SchemeResult]) -> list[str]:
    lines = []
    for r in results:
        state = "ok" if not r.overflow else f"overflows by {r.overflow}px"
        lines.append(f"{r.scheme}: scrollWidth {r.scroll_width} vs window {r.width}: {state}")
        for o in r.offenders:
            name = o["tag"] + (f"#{o['id']}" if o.get("id") else "")
            name += f".{o['cls'].replace(' ', '.')}" if o.get("cls") else ""
            lines.append(f"  {name} reaches {o['right']}px")
        for e in r.errors:
            lines.append(f"  console error: {e}")
    lines.append("browser check: ok" if exit_code(results) == 0 else "browser check: failed")
    return lines


def exit_code(results: list[SchemeResult]) -> int:
    return 0 if all(r.ok for r in results) else 1


def _inject(document: str) -> str:
    measure = _MEASURE.replace("__MAX__", str(MAX_OFFENDERS))
    head = re.search(r"<head[^>]*>", document, re.IGNORECASE)
    if head:
        document = document[: head.end()] + _COLLECTOR + document[head.end() :]
    else:
        document = _COLLECTOR + document
    end = document.lower().rfind("</body>")
    return document[:end] + measure + document[end:] if end >= 0 else document + measure


def _harness(target: Path, height: int) -> str:
    """A page that frames the target at phone width, because a headless window will not go narrower than 500px."""
    return (
        '<!doctype html><meta charset="utf-8"><body style="margin:0;background:#808080">'
        f'<iframe src="{target.name}" style="display:block;border:0;width:{PHONE_WIDTH_PX}px;height:{height}px"></iframe>'
        "<script>addEventListener('message', function (e) {"
        f"if (document.getElementById('{_RESULT_ID}') || typeof e.data !== 'string') {{ return; }}"
        "var s = document.createElement('script'); s.type = 'application/json';"
        f"s.id = '{_RESULT_ID}'; s.textContent = e.data; document.body.appendChild(s); }});</script>"
    )


def _run(chrome: str, args: list[str], url: str) -> subprocess.CompletedProcess:
    with tempfile.TemporaryDirectory(prefix="pagekit-chrome-") as profile:
        command = [
            chrome,
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--allow-file-access-from-files",
            "--hide-scrollbars",
            "--virtual-time-budget=8000",
            f"--user-data-dir={profile}",
            *args,
            url,
        ]
        try:
            return subprocess.run(
                command, capture_output=True, text=True, encoding="utf-8", errors="replace", stdin=subprocess.DEVNULL, timeout=_TIMEOUT_SECONDS
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PageError(f"browser check failed: {exc}") from exc


def check_in_browser(page: Page, screenshot: Path | None = None) -> list[SchemeResult]:
    """Load the built page at phone width in light and dark. The built page itself is never changed."""
    chrome = find_chrome()
    if not chrome:
        raise PageError("no Chrome or Chromium found: set PAGEKIT_CHROME to its path")
    if not page.index.is_file():
        raise PageError(f"not built: run pagekit build {page.slug}")
    # Beside the original, so its relative asset links still resolve.
    token = uuid.uuid4().hex
    copy = page.dir / f".browsercheck-{token}.html"
    harness = page.dir / f".browsercheck-{token}-frame.html"
    results = []
    try:
        copy.write_text(_inject(page.index.read_text(encoding="utf-8")), encoding="utf-8")
        for scheme in SCHEMES:
            harness.write_text(_harness(copy, 900), encoding="utf-8")
            # Chrome's setting is 0 for dark and 1 for light; if a version swaps them, the page says so and we retry.
            for value in ((0, 1) if scheme == "dark" else (1, 0)):
                args = ["--window-size=500,900", f"--blink-settings=preferredColorScheme={value}", "--dump-dom"]
                run = _run(chrome, args, harness.as_uri())
                if run.returncode != 0 and not run.stdout.strip():
                    raise PageError(f"browser check failed: {run.stderr.strip()[-300:] or 'no output'}")
                result = parse_result(scheme, run.stdout)
                if result.dark == (scheme == "dark"):
                    break
            else:
                raise PageError(f"browser check: Chrome would not switch to {scheme} mode")
            results.append(result)
        if screenshot is not None:
            height = min(max(results[0].height, 900), _SCREENSHOT_MAX_HEIGHT)
            harness.write_text(_harness(page.index, height), encoding="utf-8")
            screenshot.parent.mkdir(parents=True, exist_ok=True)
            run = _run(chrome, [f"--window-size=500,{height}", f"--screenshot={screenshot}"], harness.as_uri())
            if not screenshot.is_file() or screenshot.stat().st_size == 0:
                raise PageError(f"screenshot failed: {run.stderr.strip()[-300:] or 'no output'}")
    finally:
        copy.unlink(missing_ok=True)
        harness.unlink(missing_ok=True)
    return results
