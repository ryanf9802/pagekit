from __future__ import annotations

import stat
from pathlib import Path

import pytest

from pagekit import cli
from pagekit.browsercheck import SchemeResult, check_in_browser, exit_code, format_results, parse_result
from pagekit.pages import PageError, build_page, new_page
from pagekit.profiles import load_profile

# Answers --dump-dom with $RESULT, and keeps the injected copy of the page it was asked to load.
FAKE_CHROME = """#!/bin/sh
for arg in "$@"; do
  case "$arg" in
    file://*) src="${arg#file://}" ;;
  esac
done
framed=$(sed -n 's/.*iframe src="\\([^"]*\\)".*/\\1/p' "$src")
cp "$(dirname "$src")/$framed" "$CHROME_LOG.copy"
echo '<html><body><script type="application/json" id="pagekit-browser-check">'"$RESULT"'</script></body></html>'
"""


def dom(scroll: int = 390, offenders: str = "[]", errors: str = "[]", dark: str = "false") -> str:
    return (
        '<script type="application/json" id="pagekit-browser-check">'
        f'{{"scrollWidth":{scroll},"width":390,"height":2000,"offenders":{offenders},"errors":{errors},"dark":{dark}}}</script>'
    )


def test_clean_result_is_ok_and_exits_zero() -> None:
    results = [parse_result("light", dom()), parse_result("dark", dom())]
    assert exit_code(results) == 0
    assert format_results(results) == [
        "light: scrollWidth 390 vs window 390: ok",
        "dark: scrollWidth 390 vs window 390: ok",
        "browser check: ok",
    ]


def test_overflow_names_the_elements_and_exits_nonzero() -> None:
    offenders = '[{"tag":"p","cls":"a b","id":"long","right":900}]'
    results = [parse_result("light", dom()), parse_result("dark", dom(scroll=900, offenders=offenders))]
    assert exit_code(results) == 1
    lines = format_results(results)
    assert "dark: scrollWidth 900 vs window 390: overflows by 510px" in lines
    assert "  p#long.a.b reaches 900px" in lines
    assert lines[-1] == "browser check: failed"


def test_a_console_error_alone_fails() -> None:
    result = parse_result("light", dom(errors='["boom"]'))
    assert exit_code([result]) == 1
    assert "  console error: boom" in format_results([result])


def test_missing_measurements_are_an_error() -> None:
    with pytest.raises(PageError):
        parse_result("light", "<html></html>")


def test_exit_code_with_a_fake_result() -> None:
    assert exit_code([SchemeResult("light", 390, 390)]) == 0
    assert exit_code([SchemeResult("light", 391, 390)]) == 1
    assert exit_code([SchemeResult("light", 390, 390, offenders=[{"tag": "p"}])]) == 1


def built(home: Path):
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    page.content.write_text("<h2>Section</h2>")
    build_page(profile, page)
    return page


@pytest.mark.posix
def test_runs_chrome_on_a_copy_and_leaves_the_page_alone(home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    script = tmp_path / "fake-chrome"
    script.write_text(FAKE_CHROME)
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PAGEKIT_CHROME", str(script))
    monkeypatch.setenv("CHROME_LOG", str(tmp_path / "chrome"))
    monkeypatch.setenv("RESULT", '{"scrollWidth":390,"width":390,"height":900,"offenders":[],"errors":[],"dark":true}')
    page = built(home)
    before = page.index.read_bytes()
    # The fake always says dark, so the light run cannot be satisfied and the check reports it.
    with pytest.raises(PageError, match="would not switch to light"):
        check_in_browser(page)
    copy = (tmp_path / "chrome.copy").read_text()
    assert "__pkErrors" in copy and "postMessage" in copy
    assert page.index.read_bytes() == before
    assert not list(page.dir.glob(".browsercheck-*"))


def test_screenshot_needs_browser(home: Path) -> None:
    page = built(home)
    with pytest.raises(PageError, match="needs --browser"):
        cli.cmd_check(cli.build_parser().parse_args(["check", page.slug, "--screenshot", "x.png"]))


def test_no_chrome_is_a_clear_error(home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pagekit.browsercheck.find_chrome", lambda: None)
    with pytest.raises(PageError, match="no Chrome"):
        check_in_browser(built(home))
