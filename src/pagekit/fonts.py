"""Embed a font in a profile. Static fonts only: variable fonts make PDFs much larger."""

from __future__ import annotations

import base64
import re
import struct
from pathlib import Path

from .profiles import Profile, builtin_dir


class FontError(Exception):
    pass


_FORMATS = {".woff2": ("woff2", "font/woff2"), ".woff": ("woff", "font/woff"), ".ttf": ("truetype", "font/ttf"), ".otf": ("opentype", "font/otf")}
_FAMILY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9 _-]*$")
_VARIABLE_TAGS = {b"fvar", b"gvar", b"CFF2"}
# The tables a WOFF2 file refers to by index, from the WOFF2 specification. Index 63 means a tag follows.
_WOFF2_INDEX_FVAR, _WOFF2_INDEX_GVAR, _WOFF2_INDEX_GLYF, _WOFF2_INDEX_LOCA = 47, 48, 10, 11


def _base128(data: bytes, at: int) -> int:
    for _ in range(5):
        if not data[at] & 0x80:
            return at + 1
        at += 1
    raise FontError("not a valid WOFF2 font file")


def _woff2_is_variable(data: bytes) -> bool:
    count = struct.unpack(">H", data[12:14])[0]
    at = 48
    for _ in range(count):
        flags = data[at]
        at += 1
        index, version = flags & 0x3F, flags >> 6
        tag = None
        if index == 63:
            tag = data[at : at + 4]
            at += 4
        if index in (_WOFF2_INDEX_FVAR, _WOFF2_INDEX_GVAR) or tag in _VARIABLE_TAGS:
            return True
        at = _base128(data, at)
        # glyf and loca carry a transformed length unless their version is 3. Other tables are the reverse.
        transformed = version != 3 if index in (_WOFF2_INDEX_GLYF, _WOFF2_INDEX_LOCA) else version != 0
        if transformed:
            at = _base128(data, at)
    return False


def is_variable_font(data: bytes) -> bool:
    try:
        signature = data[:4]
        if signature == b"wOF2":
            return _woff2_is_variable(data)
        if signature == b"wOFF":
            count, start, size = struct.unpack(">H", data[12:14])[0], 44, 20
        else:
            count, start, size = struct.unpack(">H", data[4:6])[0], 12, 16
        return any(data[start + i * size : start + i * size + 4] in _VARIABLE_TAGS for i in range(count))
    except (IndexError, struct.error) as exc:
        raise FontError("not a valid font file") from exc


def add_font(profile: Profile, source: Path, family: str, weight: int, italic: bool = False) -> Path:
    """Add one @font-face to the nearest profile's fonts.css, and return that file."""
    if profile.nearest.resolve() == builtin_dir().resolve():
        raise FontError("this would change pagekit's own profile: run it where your profile applies, or pass --profile")
    if not source.is_file():
        raise FontError(f"no font file at {source}")
    kind = _FORMATS.get(source.suffix.lower())
    if not kind:
        raise FontError(f"{source.name}: use a .woff2, .woff, .ttf, or .otf file")
    if not _FAMILY_RE.match(family):
        raise FontError(f"invalid family name {family!r}: use letters, digits, spaces, hyphens, and underscores")
    if not 1 <= weight <= 1000:
        raise FontError(f"invalid weight {weight}: use a number such as 400")
    data = source.read_bytes()
    if is_variable_font(data):
        raise FontError(f"{source.name} is a variable font, which makes PDFs much larger: use a static file for each weight")
    style = "italic" if italic else "normal"
    target = profile.nearest / "fonts.css"
    existing = target.read_text(encoding="utf-8") if target.is_file() else ""
    faces = re.findall(r"@font-face\s*\{[^}]*\}", existing)
    for face in faces:
        if f'font-family: "{family}"' in face and f"font-weight: {weight};" in face and f"font-style: {style};" in face:
            raise FontError(f"{family} {weight} {style} is already in {target}: remove it first to replace it")
    encoded = base64.b64encode(data).decode()
    face = (
        "@font-face {\n"
        f'  font-family: "{family}";\n'
        f'  src: url("data:{kind[1]};base64,{encoded}") format("{kind[0]}");\n'
        f"  font-style: {style};\n"
        f"  font-weight: {weight};\n"
        "  font-display: swap;\n"
        "}\n"
    )
    target.write_text(f"{existing.rstrip()}\n{face}".lstrip(), encoding="utf-8")
    return target
