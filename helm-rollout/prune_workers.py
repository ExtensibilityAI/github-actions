"""Drop removed workers from a release's previous values, for helm-rollout.

    python3 prune_workers.py <previous-values.json> <values file>...

``previous-values.json`` is ``helm get values <release> -o json``. Prints those values as
JSON without each ``workers.<key>`` that none of the values files defines, and logs a
``::notice::`` per removed worker. helm-rollout then upgrades with ``--reset-values``,
passing this output first and the values files after it: the same values as
``--reuse-values``, minus the removed workers. Everything else in the previous values,
such as the image tags of images this deploy did not rebuild, is kept.

A values file whose ``workers`` block cannot be read is an error: pruning would then
guess which workers exist.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

_TOP_KEY = re.compile(r"^(?P<key>[^\s#][^:]*):(?P<rest>.*)$")
_CHILD_KEY = re.compile(r"^(?P<indent> +)(?P<key>[^\s#:'\"-][^:]*|'[^']*'|\"[^\"]*\"):(\s|$)")


class ValuesError(Exception):
    pass


def _workers_keys_yaml(text: str) -> set[str] | None:
    try:
        import yaml
    except ImportError:
        return None
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValuesError("not a mapping")
    workers = data.get("workers")
    if workers is None:
        return set()
    if not isinstance(workers, dict):
        raise ValuesError("`workers` is not a mapping")
    return {str(k) for k in workers}


def _workers_keys_text(text: str) -> set[str]:
    """Keys of the top-level ``workers:`` block, for block-style YAML without PyYAML."""
    lines = text.splitlines()
    keys: set[str] = set()
    start = None
    for i, line in enumerate(lines):
        m = _TOP_KEY.match(line)
        if m and m.group("key").strip().strip("'\"") == "workers":
            rest = m.group("rest").split(" #", 1)[0].strip()
            if rest in ("{}", "~", "null"):
                return set()
            if rest:
                raise ValuesError(f"`workers: {rest}` (flow style) needs PyYAML")
            start = i + 1
            break
    if start is None:
        return set()
    child_indent = None
    for line in lines[start:]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            break
        m = _CHILD_KEY.match(line)
        indent = len(line) - len(line.lstrip(" "))
        if child_indent is None:
            if not m:
                raise ValuesError("unexpected line under `workers:`")
            child_indent = indent
        if indent == child_indent:
            if not m:
                raise ValuesError("unexpected line under `workers:`")
            keys.add(m.group("key").strip("'\""))
    return keys


def workers_keys(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    try:
        keys = _workers_keys_yaml(text)
        return keys if keys is not None else _workers_keys_text(text)
    except ValuesError as exc:
        raise ValuesError(f"{path}: {exc}") from exc
    except Exception as exc:  # yaml.YAMLError, without importing yaml here
        raise ValuesError(f"{path}: {exc}") from exc


def prune(previous: Any, defined: set[str]) -> tuple[dict[str, Any], list[str]]:
    """``previous`` without the ``workers`` keys not in ``defined``, and those keys."""
    if not isinstance(previous, dict):
        return {}, []
    out = dict(previous)
    workers = out.get("workers")
    if not isinstance(workers, dict):
        return out, []
    removed = sorted(k for k in workers if k not in defined)
    out["workers"] = {k: v for k, v in workers.items() if k in defined}
    return out, removed


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print("usage: prune_workers.py <previous-values.json> [values file ...]", file=sys.stderr)
        return 2
    raw = Path(argv[1]).read_text(encoding="utf-8").strip()
    previous = json.loads(raw) if raw else None
    try:
        defined = set().union(*(workers_keys(Path(p)) for p in argv[2:]))
    except ValuesError as exc:
        print(f"::error::helm-rollout: cannot read workers from {exc}", file=sys.stderr)
        return 1
    pruned, removed = prune(previous, defined)
    for key in removed:
        print(
            f"::notice::helm-rollout: worker {key!r} is in the release but in no values "
            "file; removing it from the release values",
            file=sys.stderr,
        )
    print(json.dumps(pruned))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
