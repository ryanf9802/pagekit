"""Reading a version from what git printed, without a repository."""

from __future__ import annotations

import importlib.metadata
import re

import pytest

import pagekit.version as version_module
from pagekit.version import Version, from_metadata, parse_describe


@pytest.mark.parametrize(
    ("described", "shown"),
    [
        ("v0.1.8-0-g0aebe28", "0.1.8"),
        ("v0.1.8-3-g1234abc", "0.1.8+3.g1234abc"),
        ("v0.1.8-3-g1234abc-dirty", "0.1.8+3.g1234abc.dirty"),
        ("v0.1.8-0-g1234abc-dirty", "0.1.8+0.g1234abc.dirty"),
        ("v12.0.100-27-gabcdef0", "12.0.100+27.gabcdef0"),
        ("1234abc", "0.0.0+g1234abc"),
        ("1234abc-dirty", "0.0.0+g1234abc.dirty"),
        ("", "unknown"),
        ("fatal: not a git repository", "unknown"),
    ],
)
def test_describe_output_becomes_a_version(described: str, shown: str) -> None:
    assert str(parse_describe(described)) == shown


def test_the_parts_are_kept_apart() -> None:
    assert parse_describe("v0.1.8-3-g1234abc-dirty") == Version("0.1.8", 3, "1234abc", True)
    assert parse_describe("1234abc") == Version("", 0, "1234abc", False)
    assert parse_describe("nonsense") == Version()


@pytest.mark.parametrize("described", ["v0.1.8-0-g0aebe28", "v0.1.8-3-g1234abc", "v0.1.8-3-g1234abc-dirty", "1234abc"])
def test_a_version_past_a_release_is_a_valid_local_version_so_tools_can_order_it(described: str) -> None:
    assert re.fullmatch(r"\d+(\.\d+)*(\+[0-9a-z]+(\.[0-9a-z]+)*)?", str(parse_describe(described)))


def test_a_plain_install_reads_its_package_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(version_module.importlib.metadata, "version", lambda name: "0.4.2")
    assert str(from_metadata()) == "0.4.2"


def test_an_install_with_no_package_metadata_is_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(name: str) -> str:
        raise importlib.metadata.PackageNotFoundError(name)

    monkeypatch.setattr(version_module.importlib.metadata, "version", missing)
    assert str(from_metadata()) == "unknown"
