"""Image sizes, added at build time so a page keeps its layout while lazy images load.

Without a width and height a browser gives an image no space until it arrives, so the page jumps as a
reader scrolls. The theme's max-width and height: auto still scale the image to fit.
"""

from __future__ import annotations

import re
import struct
from pathlib import Path
from urllib.parse import unquote

_IMG_RE = re.compile(r"<img\b[^>]*>", re.IGNORECASE)
_ASSET_RE = re.compile(r"""\ssrc\s*=\s*["'](assets/[^"'?#]+)["']""", re.IGNORECASE)
_SIZED_RE = re.compile(r"\s(?:width|height)\s*=", re.IGNORECASE)
# Start-of-frame markers, the only JPEG segments that hold a size.
_JPEG_FRAMES = {0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF}
_HEADER_BYTES = 64


def _jpeg_size(path: Path) -> tuple[int, int] | None:
    with path.open("rb") as stream:
        stream.seek(2)
        while True:
            marker = stream.read(2)
            if len(marker) < 2 or marker[0] != 0xFF:
                return None
            if marker[1] == 0xFF:
                # Padding: the next byte may be the real marker.
                stream.seek(-1, 1)
                continue
            length = stream.read(2)
            if len(length) < 2:
                return None
            if marker[1] in _JPEG_FRAMES:
                frame = stream.read(5)
                if len(frame) < 5:
                    return None
                height, width = struct.unpack(">HH", frame[1:])
                return width, height
            stream.seek(struct.unpack(">H", length)[0] - 2, 1)


def _webp_size(head: bytes) -> tuple[int, int] | None:
    kind = head[12:16]
    if kind == b"VP8 " and len(head) >= 30:
        width, height = struct.unpack("<HH", head[26:30])
        return width & 0x3FFF, height & 0x3FFF
    if kind == b"VP8L" and len(head) >= 25:
        bits = int.from_bytes(head[21:25], "little")
        return (bits & 0x3FFF) + 1, ((bits >> 14) & 0x3FFF) + 1
    if kind == b"VP8X" and len(head) >= 30:
        return int.from_bytes(head[24:27], "little") + 1, int.from_bytes(head[27:30], "little") + 1
    return None


def image_size(path: Path) -> tuple[int, int] | None:
    """Width and height from a PNG, JPEG, GIF, or WebP header, or None for anything else."""
    try:
        with path.open("rb") as stream:
            head = stream.read(_HEADER_BYTES)
        if head[:8] == b"\x89PNG\r\n\x1a\n" and len(head) >= 24:
            size = struct.unpack(">II", head[16:24])
        elif head[:6] in (b"GIF87a", b"GIF89a") and len(head) >= 10:
            size = struct.unpack("<HH", head[6:10])
        elif head[:2] == b"\xff\xd8":
            size = _jpeg_size(path)
        elif head[:4] == b"RIFF" and head[8:12] == b"WEBP":
            size = _webp_size(head)
        else:
            return None
    except (OSError, struct.error):
        return None
    return size if size and all(size) else None


def add_image_sizes(source: str, page_dir: Path) -> str:
    """Add a width and height to each <img> that points at a page asset and has neither."""
    assets = (page_dir / "assets").resolve()

    def sized(match: re.Match) -> str:
        tag = match.group(0)
        found = _ASSET_RE.search(tag)
        if not found or _SIZED_RE.search(tag):
            return tag
        path = (page_dir / unquote(found.group(1))).resolve()
        size = image_size(path) if path.is_relative_to(assets) else None
        if not size:
            return tag
        return f'<img width="{size[0]}" height="{size[1]}"{tag[len("<img") :]}'

    return _IMG_RE.sub(sized, source)
