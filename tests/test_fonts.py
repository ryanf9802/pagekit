from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pagekit.fonts import FontError, add_font, is_variable_font
from pagekit.profiles import init_profile, load_profile


def sfnt(*tags: bytes) -> bytes:
    header = b"\x00\x01\x00\x00" + struct.pack(">H", len(tags)) + b"\x00" * 6
    return header + b"".join(tag + b"\x00" * 12 for tag in tags)


def woff2(*indexes: int) -> bytes:
    """A table directory with one-byte lengths. glyf and loca get version 3, which has no second length."""
    entries = b""
    for index in indexes:
        entries += bytes([index | (3 << 6 if index in (10, 11) else 0), 1])
    return b"wOF2" + b"\x00" * 8 + struct.pack(">H", len(indexes)) + b"\x00" * 34 + entries


def test_detects_variable_fonts() -> None:
    assert is_variable_font(sfnt(b"head", b"fvar"))
    assert not is_variable_font(sfnt(b"head", b"glyf"))
    assert is_variable_font(woff2(1, 10, 47))
    assert is_variable_font(woff2(1, 10, 48))
    assert not is_variable_font(woff2(1, 10, 11, 5))


@pytest.fixture
def profile(home: Path):
    repo = home / "repo"
    init_profile(repo / ".pagekit" / "profile", "acme", "builtin", "Acme")
    return load_profile(repo)


def test_adds_a_static_font_to_the_nearest_profile(profile, tmp_path: Path) -> None:
    font = tmp_path / "acme.ttf"
    font.write_bytes(sfnt(b"head", b"glyf"))
    target = add_font(profile, font, "Acme Sans", 600)
    assert target == profile.nearest / "fonts.css"
    css = target.read_text()
    assert 'font-family: "Acme Sans";' in css and "font-weight: 600;" in css and 'format("truetype")' in css
    assert "Acme Sans" in profile.fonts()


def test_keeps_weights_side_by_side_and_refuses_a_repeat(profile, tmp_path: Path) -> None:
    font = tmp_path / "acme.ttf"
    font.write_bytes(sfnt(b"head"))
    add_font(profile, font, "Acme Sans", 400)
    add_font(profile, font, "Acme Sans", 700)
    add_font(profile, font, "Acme Sans", 400, italic=True)
    assert (profile.nearest / "fonts.css").read_text().count("@font-face") == 3
    with pytest.raises(FontError, match="already in"):
        add_font(profile, font, "Acme Sans", 400)


def test_refuses_variable_fonts(profile, tmp_path: Path) -> None:
    font = tmp_path / "acme.ttf"
    font.write_bytes(sfnt(b"fvar"))
    with pytest.raises(FontError, match="variable font"):
        add_font(profile, font, "Acme Sans", 400)


def test_refuses_other_files_and_bad_names(profile, tmp_path: Path) -> None:
    other = tmp_path / "notes.txt"
    other.write_text("hi")
    with pytest.raises(FontError, match="use a .woff2"):
        add_font(profile, other, "Acme", 400)
    font = tmp_path / "acme.ttf"
    font.write_bytes(sfnt(b"head"))
    with pytest.raises(FontError, match="invalid family"):
        add_font(profile, font, 'Acme"; }', 400)


def test_refuses_to_change_the_builtin_profile(home: Path, tmp_path: Path) -> None:
    font = tmp_path / "acme.ttf"
    font.write_bytes(sfnt(b"head"))
    with pytest.raises(FontError, match="pagekit's own profile"):
        add_font(load_profile(override="builtin"), font, "Acme", 400)
