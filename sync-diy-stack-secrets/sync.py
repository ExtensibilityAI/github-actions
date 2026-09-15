#!/usr/bin/env python3
"""Rehydrate DIY secretsprovider/encryptedkey from a GCS checkpoint into stack YAML."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 5:
        print(
            "usage: sync.py <backend_url> <project> <stack> <stack_yaml>",
            file=sys.stderr,
        )
        return 2
    backend, project, stack, path_s = sys.argv[1:5]
    path = Path(path_s)
    if not path.is_file():
        return 0
    text = path.read_text(encoding="utf-8")
    if "encryptedkey:" in text:
        return 0
    if not backend.startswith("gs://"):
        return 0
    uri = f"{backend.rstrip('/')}/.pulumi/stacks/{project}/{stack}.json"
    try:
        raw = subprocess.check_output(["gsutil", "cat", uri], stderr=subprocess.DEVNULL)
    except (subprocess.CalledProcessError, FileNotFoundError):
        return 0
    data = json.loads(raw)
    sp = ((data.get("checkpoint") or {}).get("latest") or {}).get("secrets_providers") or {}
    state = sp.get("state") or {}
    url = (state.get("url") or "").strip()
    key = (state.get("encryptedkey") or "").strip()
    if not url or not key:
        return 0
    if not text.endswith("\n"):
        text += "\n"
    if "secretsprovider:" not in text:
        text += f"secretsprovider: {url}\n"
    if "encryptedkey:" not in text:
        text += f"encryptedkey: {key}\n"
    path.write_text(text, encoding="utf-8")
    print(f"Synced secretsprovider/encryptedkey into {path} from {uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
