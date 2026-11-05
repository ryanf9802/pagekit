from __future__ import annotations

import struct
from pathlib import Path

import pytest

from pagekit.images import add_image_sizes, image_size
from pagekit.pages import PageError, build_page, new_page, send_page
from pagekit.profiles import init_profile, load_profile

PNG = b"\x89PNG\r\n\x1a\n" + struct.pack(">I", 13) + b"IHDR" + struct.pack(">II", 640, 480)
GIF = b"GIF89a" + struct.pack("<HH", 32, 16)
# A comment segment comes first, so the size has to be found by walking the segments.
JPEG = (
    b"\xff\xd8\xff\xfe"
    + struct.pack(">H", 6)
    + b"note"
    + b"\xff\xc0"
    + struct.pack(">H", 17)
    + b"\x08"
    + struct.pack(">HH", 200, 300)
)
WEBP_LOSSY = b"RIFF\0\0\0\0WEBPVP8 " + b"\0" * 10 + struct.pack("<HH", 100, 50)
WEBP_LOSSLESS = b"RIFF\0\0\0\0WEBPVP8L" + b"\0" * 5 + ((99) | (49 << 14)).to_bytes(4, "little")
WEBP_EXTENDED = (
    b"RIFF\0\0\0\0WEBPVP8X" + b"\0" * 8 + (99).to_bytes(3, "little") + (49).to_bytes(3, "little")
)


def asset(folder: Path, name: str, data: bytes) -> None:
    (folder / "assets").mkdir(exist_ok=True)
    (folder / "assets" / name).write_bytes(data)


@pytest.mark.parametrize(
    ("data", "size"),
    [
        (PNG, (640, 480)),
        (GIF, (32, 16)),
        (JPEG, (300, 200)),
        (WEBP_LOSSY, (100, 50)),
        (WEBP_LOSSLESS, (100, 50)),
        (WEBP_EXTENDED, (100, 50)),
    ],
)
def test_reads_each_format(tmp_path: Path, data: bytes, size: tuple[int, int]) -> None:
    path = tmp_path / "image"
    path.write_bytes(data)
    assert image_size(path) == size


@pytest.mark.parametrize("data", [b"", b"<svg></svg>", b"\x89PNG\r\n\x1a\n", b"\xff\xd8\xff"])
def test_unknown_or_cut_off_files_have_no_size(tmp_path: Path, data: bytes) -> None:
    path = tmp_path / "image"
    path.write_bytes(data)
    assert image_size(path) is None


def test_adds_a_size_and_keeps_the_rest_of_the_tag(tmp_path: Path) -> None:
    asset(tmp_path, "a b.png", PNG)
    result = add_image_sizes('<img src="assets/a%20b.png" alt="x" loading="lazy">', tmp_path)
    assert result == '<img width="640" height="480" src="assets/a%20b.png" alt="x" loading="lazy">'


@pytest.mark.parametrize(
    "tag",
    [
        '<img src="assets/a.png" width="10">',
        '<img src="assets/a.png" height="10">',
        '<img src="assets/missing.png">',
        '<img src="https://example.com/a.png">',
        '<img src="assets/../secret.png">',
    ],
)
def test_leaves_other_images_alone(tmp_path: Path, tag: str) -> None:
    asset(tmp_path, "a.png", PNG)
    (tmp_path / "secret.png").write_bytes(PNG)
    assert add_image_sizes(tag, tmp_path) == tag


def test_build_sizes_images_and_leaves_the_source_alone(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    asset(page.dir, "a.png", PNG)
    source = '<img src="assets/a.png" alt="x">'
    page.content.write_text(source)
    build_page(profile, page)
    assert '<img width="640" height="480" src="assets/a.png"' in page.index.read_text()
    assert page.content.read_text() == source


def profile_that_sends(home: Path, command: str):
    directory = home / "repo" / ".pagekit" / "profile"
    init_profile(directory, "acme", "builtin", "Acme")
    with (directory / "profile.toml").open("a") as stream:
        stream.write(f"\n[send]\ncommand = {command}\n")
    return load_profile(home / "repo")


@pytest.mark.posix
def test_send_runs_the_profile_command_on_a_named_copy(home: Path) -> None:
    script = home / "share"
    script.write_text('#!/bin/sh\ntest -f "$1" && echo "sent $(basename "$1") as $2"\n')
    script.chmod(0o755)
    profile = profile_that_sends(home, f'["{script}", "{{file}}", "{{title}} ({{slug}})"]')
    page, _ = new_page(profile, "demo", "Demo Page", None, "slots")
    build_page(profile, page)
    assert send_page(profile, page) == "sent demo.html as Demo Page (demo)"
    assert not (page.dir / "demo.html").exists()


def test_send_needs_a_command(home: Path) -> None:
    profile = load_profile()
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    build_page(profile, page)
    with pytest.raises(PageError, match=r"no \[send\] command"):
        send_page(profile, page)


@pytest.mark.parametrize(
    ("command", "message"),
    [('["/no/such/tool"]', "could not run"), ('["python3", "-c", "raise SystemExit(1)"]', "failed")],
)
def test_send_reports_a_command_that_fails(home: Path, command: str, message: str) -> None:
    profile = profile_that_sends(home, command)
    page, _ = new_page(profile, "demo", "Demo", None, "slots")
    build_page(profile, page)
    with pytest.raises(PageError, match=message):
        send_page(profile, page)
    assert not (page.dir / "demo.html").exists()
