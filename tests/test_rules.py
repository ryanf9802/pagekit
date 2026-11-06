from __future__ import annotations

import pytest

from pagekit.cli import main

RULES_MARKERS = ("components (pagekit component show NAME...):", "--- profile instructions ---")


def _run(capsys: pytest.CaptureFixture[str], *argv: str) -> str:
    assert main(list(argv)) == 0
    return capsys.readouterr().out


def _new(capsys: pytest.CaptureFixture[str], *extra: str) -> str:
    return _run(capsys, "new", "demo", "--title", "Demo", *extra)


def test_first_new_prints_the_rules(home, capsys) -> None:
    out = _new(capsys)
    assert out.startswith("created: ")
    for marker in RULES_MARKERS:
        assert marker in out


def test_reopen_prints_a_short_note_and_no_rules(home, capsys) -> None:
    _new(capsys)
    out = _new(capsys)
    assert out.startswith("exists, updating in place: ")
    for prefix in ("write: ", "assets: ", "then: pagekit build demo", "profile: "):
        assert prefix in out
    assert "rules unchanged (`pagekit rules` shows them)" in out
    assert "`pagekit outline demo`" in out
    assert "not a rewrite" in out
    for marker in RULES_MARKERS:
        assert marker not in out
    assert out.isascii()
    assert len(out) < 1500


def test_rules_prints_what_a_first_new_prints_after_the_paths(home, capsys) -> None:
    first = _new(capsys)
    rules = _run(capsys, "rules")
    assert rules.startswith("components (pagekit component show NAME...):")
    assert first.endswith(rules)


def test_rules_honors_the_profile_flag(home, capsys) -> None:
    first = _new(capsys, "--profile", "builtin")
    rules = _run(capsys, "rules", "--profile", "builtin")
    assert first.endswith(rules)


def test_default_output_leaves_out_the_theme_tokens(home, capsys) -> None:
    assert "theme tokens:" not in _new(capsys)
    assert "theme tokens:" not in _run(capsys, "rules")


def test_rules_tokens_prints_only_the_token_line(home, capsys) -> None:
    out = _run(capsys, "rules", "--tokens")
    assert out.startswith("theme tokens: --pk-")
    assert len(out.splitlines()) == 1


def test_component_descriptions_are_short(home) -> None:
    from pagekit.library import list_components
    from pagekit.profiles import load_profile

    components = [c for c in list_components(load_profile()) if c.source != "library"]
    assert components
    for component in components:
        assert 0 < len(component.when) <= 60, component.name
