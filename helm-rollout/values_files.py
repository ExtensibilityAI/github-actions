"""Expand helm-rollout's ``values_files`` input into one path per line.

Entries are comma-separated, in order. A glob entry (``*``, ``?`` or ``[``) expands to
its sorted matches and is dropped when nothing matches, so
``chart/values.yaml,workers/*/deploy/values.yaml`` works for a project with no workers.
A plain path is kept as given; helm reports it if it is missing.
"""

from __future__ import annotations

import sys
from pathlib import Path

GLOB_CHARS = "*?["


def expand(values_files: str, *, root: Path = Path(".")) -> list[str]:
    out: list[str] = []
    for entry in (e.strip() for e in values_files.split(",")):
        if not entry:
            continue
        if not any(c in entry for c in GLOB_CHARS):
            out.append(entry)
            continue
        if entry.startswith("/") or ".." in entry.split("/"):
            raise SystemExit(f"::error::values_files glob {entry!r} must be relative, without '..'")
        out.extend(
            sorted(p.relative_to(root).as_posix() for p in root.glob(entry) if p.is_file())
        )
    return out


def main(argv: list[str]) -> int:
    for path in expand(argv[1] if len(argv) > 1 else ""):
        print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
