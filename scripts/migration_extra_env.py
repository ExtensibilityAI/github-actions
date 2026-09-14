#!/usr/bin/env python3
"""Parse migration_extra_env blobs and apply them for Cloud SQL / RDS migrate.

Supports single-line ``KEY=VALUE`` and multiline values (e.g. PEMs expanded from
GitHub secrets). Multiline values are written to ``GITHUB_ENV`` using heredoc
form ``KEY<<DELIMITER``.

Usage:
  EXTRA_ENV=... python3 migration_extra_env.py apply-github-env
  EXTRA_ENV=... python3 migration_extra_env.py write-json /path/out.json
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
from collections.abc import Sequence

KEY_RE = re.compile(r"^([A-Z][A-Z0-9_]{0,63})=(.*)$")
KEY_ONLY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


class MigrationExtraEnvError(ValueError):
    """Invalid migration_extra_env input."""


def _is_new_assignment(line: str) -> re.Match[str] | None:
    """Return match if line starts a new KEY=VALUE assignment."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    return KEY_RE.match(stripped)


def parse_migration_extra_env(text: str) -> list[tuple[str, str]]:
    """Parse opaque newline-delimited env blob into (key, value) pairs.

    After ``KEY=``, following lines are appended to the value until the next
    line that matches an allowlisted ``KEY=`` assignment (or EOF). Leading blank
    and ``#`` comment lines (before any key) are skipped. Blank lines inside a
    value are preserved.
    """
    entries: list[tuple[str, str]] = []
    current_key: str | None = None
    parts: list[str] = []

    def flush() -> None:
        nonlocal current_key, parts
        if current_key is None:
            return
        entries.append((current_key, "\n".join(parts)))
        current_key = None
        parts = []

    for lineno, raw in enumerate(text.splitlines(), start=1):
        if current_key is None:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            match = KEY_RE.match(line)
            if match is None:
                raise MigrationExtraEnvError(
                    f"Invalid migration_extra_env at line {lineno}: missing '='"
                )
            key, value = match.group(1), match.group(2)
            if not KEY_ONLY_RE.match(key):
                raise MigrationExtraEnvError(
                    f"Invalid migration_extra_env key at line {lineno}"
                )
            current_key = key
            parts = [value]
            continue

        match = _is_new_assignment(raw)
        if match is not None:
            flush()
            key, value = match.group(1), match.group(2)
            if not KEY_ONLY_RE.match(key):
                raise MigrationExtraEnvError(
                    f"Invalid migration_extra_env key at line {lineno}"
                )
            current_key = key
            parts = [value]
            continue

        # Preserve PEM / multiline body (drop CR only).
        parts.append(raw.rstrip("\r"))

    flush()
    return entries


def mask_value(value: str) -> None:
    """Emit ::add-mask:: for each non-empty line (Actions masks are line-oriented)."""
    for line in value.splitlines():
        if line:
            print(f"::add-mask::{line}")


def write_github_env(path: str, entries: Sequence[tuple[str, str]]) -> None:
    """Append entries to a GITHUB_ENV file (heredoc for multiline values)."""
    with open(path, "a", encoding="utf-8") as fh:
        for key, value in entries:
            mask_value(value)
            if "\n" in value or "\r" in value:
                delim = f"EOF_MIGRATE_{key}_{secrets.token_hex(8)}"
                if delim in value:
                    raise MigrationExtraEnvError(
                        f"Refusing to write {key}: value contains heredoc delimiter"
                    )
                fh.write(f"{key}<<{delim}\n")
                fh.write(value)
                if not value.endswith("\n"):
                    fh.write("\n")
                fh.write(f"{delim}\n")
            else:
                fh.write(f"{key}={value}\n")


def write_json_file(path: str, entries: Sequence[tuple[str, str]]) -> None:
    """Write entries as a JSON list of {name, value} for Kubernetes Job env."""
    for _, value in entries:
        mask_value(value)
    payload = [{"name": key, "value": value} for key, value in entries]
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh)


def _read_extra_env() -> str:
    return os.environ.get("EXTRA_ENV", "")


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(
            "usage: migration_extra_env.py apply-github-env | write-json PATH",
            file=sys.stderr,
        )
        return 2

    cmd = argv[1]
    try:
        entries = parse_migration_extra_env(_read_extra_env())
        if cmd == "apply-github-env":
            gh_env = os.environ.get("GITHUB_ENV")
            if not gh_env:
                print("::error::GITHUB_ENV is not set", file=sys.stderr)
                return 1
            if not entries:
                return 0
            write_github_env(gh_env, entries)
            return 0
        if cmd == "write-json":
            if len(argv) < 3:
                print("::error::write-json requires PATH", file=sys.stderr)
                return 2
            write_json_file(argv[2], entries)
            return 0
        print(f"::error::Unknown command {cmd!r}", file=sys.stderr)
        return 2
    except MigrationExtraEnvError as exc:
        print(f"::error::{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
