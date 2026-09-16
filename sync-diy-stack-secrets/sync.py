#!/usr/bin/env python3
"""Rehydrate DIY secretsprovider/encryptedkey from a GCS or S3 checkpoint into stack YAML."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Callable
from urllib.parse import parse_qs, urlparse


def checkpoint_object_key(project: str, stack: str) -> str:
    """Return the DIY backend object key for a stack checkpoint."""
    return f".pulumi/stacks/{project}/{stack}.json"


def parse_s3_backend(backend: str) -> tuple[str, str | None]:
    """
    Parse ``s3://bucket?...`` into ``(bucket, region_or_None)``.

    Strips Pulumi DIY query params (``region``, ``awssdk``, ``dynamodb_table``).
    """
    parsed = urlparse(backend)
    bucket = (parsed.netloc or "").strip()
    if not bucket and parsed.path:
        bucket = parsed.path.lstrip("/").split("/", 1)[0]
    if not bucket:
        raise ValueError(f"invalid s3 backend URL: {backend!r}")
    qs = parse_qs(parsed.query)
    region_vals = qs.get("region") or []
    region = region_vals[0].strip() if region_vals else None
    return bucket, region or None


def fetch_gs_checkpoint(backend: str, project: str, stack: str) -> bytes | None:
    """Fetch checkpoint bytes from a ``gs://`` DIY backend, or None on failure."""
    uri = f"{backend.rstrip('/')}/{checkpoint_object_key(project, stack)}"
    try:
        return subprocess.check_output(["gsutil", "cat", uri], stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def fetch_s3_checkpoint(backend: str, project: str, stack: str) -> bytes | None:
    """Fetch checkpoint bytes from an ``s3://`` DIY backend, or None on failure."""
    try:
        bucket, region = parse_s3_backend(backend)
    except ValueError:
        return None
    key = checkpoint_object_key(project, stack)
    uri = f"s3://{bucket}/{key}"
    cmd = ["aws", "s3", "cp", uri, "-"]
    if region:
        cmd.extend(["--region", region])
    try:
        return subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def secrets_from_checkpoint(raw: bytes) -> tuple[str, str] | None:
    """Extract ``(secretsprovider_url, encryptedkey)`` from checkpoint JSON."""
    data = json.loads(raw)
    sp = ((data.get("checkpoint") or {}).get("latest") or {}).get("secrets_providers") or {}
    state = sp.get("state") or {}
    url = (state.get("url") or "").strip()
    key = (state.get("encryptedkey") or "").strip()
    if not url or not key:
        return None
    return url, key


def append_secrets_yaml(text: str, *, secretsprovider: str, encryptedkey: str) -> str:
    """Append missing root secretsprovider/encryptedkey lines to stack YAML text."""
    if not text.endswith("\n"):
        text += "\n"
    if "secretsprovider:" not in text:
        text += f"secretsprovider: {secretsprovider}\n"
    if "encryptedkey:" not in text:
        text += f"encryptedkey: {encryptedkey}\n"
    return text


def sync_stack_yaml(
    backend: str,
    project: str,
    stack: str,
    path: Path,
    *,
    fetch_gs: Callable[[str, str, str], bytes | None] = fetch_gs_checkpoint,
    fetch_s3: Callable[[str, str, str], bytes | None] = fetch_s3_checkpoint,
) -> int:
    """
    If ``path`` lacks ``encryptedkey``, copy secrets metadata from the DIY checkpoint.

    Returns 0 always for operational no-ops / soft failures (CI must not fail open).
    """
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    if "encryptedkey:" in text:
        return 0

    raw: bytes | None = None
    source_uri = ""
    if backend.startswith("gs://"):
        raw = fetch_gs(backend, project, stack)
        source_uri = f"{backend.rstrip('/')}/{checkpoint_object_key(project, stack)}"
    elif backend.startswith("s3://"):
        raw = fetch_s3(backend, project, stack)
        try:
            bucket, _region = parse_s3_backend(backend)
            source_uri = f"s3://{bucket}/{checkpoint_object_key(project, stack)}"
        except ValueError:
            return 0
    else:
        return 0

    if raw is None:
        return 0
    parsed = secrets_from_checkpoint(raw)
    if parsed is None:
        return 0
    url, key = parsed
    path.write_text(
        append_secrets_yaml(text, secretsprovider=url, encryptedkey=key),
        encoding="utf-8",
    )
    print(f"Synced secretsprovider/encryptedkey into {path} from {source_uri}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 4:
        print(
            "usage: sync.py <backend_url> <project> <stack> <stack_yaml>",
            file=sys.stderr,
        )
        return 2
    backend, project, stack, path_s = args
    return sync_stack_yaml(backend, project, stack, Path(path_s))


if __name__ == "__main__":
    raise SystemExit(main())
