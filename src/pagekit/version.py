"""Which pagekit this is: the release tag a clone is at, or how far past it, so the version is never written by hand.

CI makes a tag like v0.1.8 for every merge that passes, and an install runs from a clone, so the clone's git history is
the truth. The git calls live in update.py; this reads what git printed. A machine that follows main is usually past
the last release, so it reads as that release plus the commits since, such as 0.1.8+3.g1234abc.
"""

from __future__ import annotations

import importlib.metadata
import re
from dataclasses import dataclass

# What `git describe --long` prints when a release tag is behind the commit, and when no tag is.
_TAGGED = re.compile(r"^v?(?P<release>[0-9].*?)-(?P<ahead>[0-9]+)-g(?P<commit>[0-9a-f]+)(?P<dirty>-dirty)?$")
_UNTAGGED = re.compile(r"^(?P<commit>[0-9a-f]+)(?P<dirty>-dirty)?$")
# Shown when there is no release to count from. It sorts before every real release.
_NO_RELEASE = "0.0.0"


@dataclass(frozen=True)
class Version:
    # The newest release at or before this commit, such as "0.1.8", or "" when there is none.
    release: str = ""
    # Commits after that release.
    ahead: int = 0
    # The abbreviated commit, or "" when it is not known.
    commit: str = ""
    # The clone has uncommitted changes.
    dirty: bool = False

    def __str__(self) -> str:
        if not self.release and not self.commit:
            return "unknown"
        if self.release and not self.ahead and not self.dirty:
            return self.release
        # A local version label (after the +) is dot separated, so tools can still order the result.
        parts = [str(self.ahead)] if self.release else []
        parts += [f"g{self.commit}"] if self.commit else []
        parts += ["dirty"] if self.dirty else []
        return f"{self.release or _NO_RELEASE}+{'.'.join(parts)}"


def parse_describe(text: str) -> Version:
    """Reads `git describe --tags --long --always` output. Anything else is an unknown version."""
    text = text.strip()
    tagged = _TAGGED.match(text)
    if tagged:
        return Version(tagged["release"], int(tagged["ahead"]), tagged["commit"], bool(tagged["dirty"]))
    untagged = _UNTAGGED.match(text)
    if untagged:
        return Version("", 0, untagged["commit"], bool(untagged["dirty"]))
    return Version()


def from_metadata() -> Version:
    """The version a plain install carries, for an install with no clone to ask."""
    try:
        return Version(importlib.metadata.version("pagekit"))
    except importlib.metadata.PackageNotFoundError:
        return Version()
