"""The light and dark toggle: what a build adds, and the choice switching a real page."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

from pagekit.browser import find_chrome
from pagekit.pages import build_page, new_page, render_index
from pagekit.profiles import builtin_dir, init_profile, load_profile

KEY = 'var KEY = "pagekit:theme"'  # In the toggle script only, not in the event name export.js listens for.
CHROME = find_chrome()  # Found now, since the home fixture hides anything installed under the real home.


def make(profile, body: str = "<p>Hello</p>", slug: str = "demo"):
    page, _ = new_page(profile, slug, "Demo", "One line", "slots")
    page.content.write_text(body, encoding="utf-8")
    build_page(profile, page)
    return page


def repo_profile(home: Path, extra: str = ""):
    repo = home / "repo"
    directory = repo / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    (directory / "profile.toml").write_text(f'name = "acme"\nextends = "builtin"\nfooter = "Acme internal"\n{extra}')
    return load_profile(repo)


def test_a_built_page_has_the_theme_script_after_the_styles(home: Path) -> None:
    document = make(load_profile()).index.read_text(encoding="utf-8")
    assert KEY in document
    assert document.index("</style>") < document.index(KEY) < document.index("</head>")
    # The icons for the button are drawn like any other, not left as markup.
    assert '<i data-icon="sun">' not in document and "pk-i-sun" in document and "pk-i-moon" in document


def test_the_index_has_the_toggle_too(home: Path) -> None:
    assert KEY in render_index(load_profile())


def test_a_profile_can_leave_the_toggle_out(home: Path) -> None:
    document = make(repo_profile(home, "theme_toggle = false\n")).index.read_text(encoding="utf-8")
    assert KEY not in document and "pk-i-moon" not in document


def test_the_toggle_is_styled_like_the_other_header_controls_and_never_prints(home: Path) -> None:
    theme = (builtin_dir() / "theme.css").read_text(encoding="utf-8")
    assert ".pk-theme, .pk-home, .pk-pdf {" in theme
    assert re.search(r"@media print \{.*\.pk-theme,", theme, re.DOTALL)


def test_the_script_is_ascii(home: Path) -> None:
    (Path(__file__).parent.parent / "src" / "pagekit" / "static" / "theme.js").read_text(encoding="ascii")


PICK = """<script>
/* Choose a theme as a reader would, then report what the page looks like. */
document.addEventListener("DOMContentLoaded", function () {
  var out = [];
  function report(label) {
    var root = document.documentElement;
    var source = document.querySelector("source[media]");
    out.push(label + "=" + getComputedStyle(root).getPropertyValue("--pk-bg").trim() + "|" + (root.getAttribute("data-theme") || "-")
      + "|" + (source ? source.getAttribute("media") : "-") + "|" + document.querySelector(".pk-theme").getAttribute("aria-label"));
  }
  report("start");
  var button = document.querySelector(".pk-theme");
  button.click(); report("light");
  button.click(); report("dark");
  button.click(); report("system");
  var pre = document.createElement("pre");
  pre.id = "theme-result";
  pre.textContent = out.join("\\n");
  document.body.appendChild(pre);
});
</script>"""


@pytest.mark.skipif(not CHROME, reason="needs Chrome or Chromium")
def test_the_button_cycles_system_light_dark_in_a_real_page(home: Path, tmp_path: Path) -> None:
    page = make(load_profile(), body=PICK)
    command = [
        str(CHROME), "--headless=new", "--no-sandbox", "--disable-gpu", "--virtual-time-budget=4000",
        f"--user-data-dir={tmp_path / 'chrome'}", "--dump-dom", page.index.as_uri(),
    ]
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                            stdin=subprocess.DEVNULL, timeout=60)
    found = re.search(r'<pre id="theme-result">(.*?)</pre>', result.stdout, re.DOTALL)
    assert found, result.stdout[-600:]
    seen = dict(line.split("=", 1) for line in found.group(1).strip().splitlines())
    light, dark = "#f6f7f9", "#16181c"
    # Headless Chrome prefers light, so the system setting is light here.
    assert seen["start"].startswith(f"{light}|-|") and seen["start"].endswith("Theme: follows system")
    assert seen["light"] == f"{light}|light|not all|Theme: light"
    assert seen["dark"] == f"{dark}|dark|screen|Theme: dark"
    assert seen["system"].startswith(f"{light}|-|") and seen["system"].endswith("Theme: follows system")
