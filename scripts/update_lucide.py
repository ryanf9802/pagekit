#!/usr/bin/env python3
"""Refresh the vendored Lucide icons from an unpacked lucide-static package.

    npm pack lucide-static && tar xzf lucide-static-*.tgz
    python3 scripts/update_lucide.py package
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

STATIC = Path(__file__).resolve().parent.parent / "src" / "pagekit" / "static"


def main(package: Path) -> None:
    version = json.loads((package / "package.json").read_text(encoding="utf-8"))["version"]
    tags = json.loads((package / "tags.json").read_text(encoding="utf-8"))
    icons = {}
    for path in sorted((package / "icons").glob("*.svg")):
        body = re.search(r"<svg[^>]*>(.*)</svg>", path.read_text(encoding="utf-8"), re.DOTALL)
        icons[path.stem] = {"body": re.sub(r"\s*\n\s*", "", body.group(1)).strip(), "tags": tags.get(path.stem, [])}
    data = json.dumps({"version": version, "icons": icons}, separators=(",", ":"), sort_keys=True, ensure_ascii=True)
    (STATIC / "lucide-icons.json").write_text(data, encoding="utf-8")
    shutil.copyfile(package / "LICENSE", STATIC / "lucide-LICENSE")
    print(f"lucide {version}: {len(icons)} icons, {len(data)} bytes")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
