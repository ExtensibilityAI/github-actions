#!/usr/bin/env python3
"""Unit tests for sync-diy-stack-secrets/sync.py."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import sync  # noqa: E402


def _checkpoint(*, url: str, encryptedkey: str) -> bytes:
    return json.dumps(
        {
            "checkpoint": {
                "latest": {
                    "secrets_providers": {
                        "state": {"url": url, "encryptedkey": encryptedkey}
                    }
                }
            }
        }
    ).encode()


def test_parse_s3_backend_strips_query() -> None:
    bucket, region = sync.parse_s3_backend(
        "s3://acct-pulumi-state?region=us-west-2&awssdk=v2&dynamodb_table=acct-pulumi-locks"
    )
    assert bucket == "acct-pulumi-state"
    assert region == "us-west-2"


def test_parse_s3_backend_no_region() -> None:
    bucket, region = sync.parse_s3_backend("s3://my-bucket")
    assert bucket == "my-bucket"
    assert region is None


def test_skip_when_encryptedkey_present(tmp_path: Path) -> None:
    path = tmp_path / "Pulumi.staging.yaml"
    path.write_text("config: {}\nencryptedkey: already\n", encoding="utf-8")
    calls: list[str] = []

    def boom(*_a: object) -> bytes | None:
        calls.append("called")
        return None

    code = sync.sync_stack_yaml(
        "gs://bucket",
        "proj",
        "staging",
        path,
        fetch_gs=boom,
        fetch_s3=boom,
    )
    assert code == 0
    assert calls == []
    assert path.read_text(encoding="utf-8") == "config: {}\nencryptedkey: already\n"


def test_gcs_path_writes_keys(tmp_path: Path) -> None:
    path = tmp_path / "Pulumi.staging.yaml"
    path.write_text("config:\n  environment: staging\n", encoding="utf-8")
    raw = _checkpoint(url="gcpkms://projects/p/keys/staging", encryptedkey="EK")

    code = sync.sync_stack_yaml(
        "gs://state-bucket",
        "proj",
        "staging",
        path,
        fetch_gs=lambda *_a: raw,
        fetch_s3=lambda *_a: None,
    )
    assert code == 0
    text = path.read_text(encoding="utf-8")
    assert "secretsprovider: gcpkms://projects/p/keys/staging\n" in text
    assert "encryptedkey: EK\n" in text


def test_s3_path_writes_keys(tmp_path: Path) -> None:
    path = tmp_path / "Pulumi.prod.yaml"
    path.write_text("config:\n  environment: prod\n", encoding="utf-8")
    raw = _checkpoint(url="awskms://alias/pulumi-prod?region=us-east-1", encryptedkey="AWSEK")
    seen: list[tuple[str, str, str]] = []

    def fetch_s3(backend: str, project: str, stack: str) -> bytes | None:
        seen.append((backend, project, stack))
        return raw

    backend = (
        "s3://acct-pulumi-state?region=us-east-1&awssdk=v2&dynamodb_table=acct-pulumi-locks"
    )
    code = sync.sync_stack_yaml(
        backend,
        "my-infra",
        "prod",
        path,
        fetch_gs=lambda *_a: None,
        fetch_s3=fetch_s3,
    )
    assert code == 0
    assert seen == [(backend, "my-infra", "prod")]
    text = path.read_text(encoding="utf-8")
    assert "secretsprovider: awskms://alias/pulumi-prod?region=us-east-1\n" in text
    assert "encryptedkey: AWSEK\n" in text


def test_missing_object_noop(tmp_path: Path) -> None:
    path = tmp_path / "Pulumi.staging.yaml"
    original = "config: {}\n"
    path.write_text(original, encoding="utf-8")
    code = sync.sync_stack_yaml(
        "s3://bucket?region=us-east-1",
        "proj",
        "staging",
        path,
        fetch_gs=lambda *_a: None,
        fetch_s3=lambda *_a: None,
    )
    assert code == 0
    assert path.read_text(encoding="utf-8") == original


def test_unknown_backend_noop(tmp_path: Path) -> None:
    path = tmp_path / "Pulumi.staging.yaml"
    path.write_text("config: {}\n", encoding="utf-8")
    code = sync.sync_stack_yaml("file:///tmp/state", "proj", "staging", path)
    assert code == 0
    assert path.read_text(encoding="utf-8") == "config: {}\n"


def test_main_usage() -> None:
    assert sync.main([]) == 2


def test_checkpoint_object_key() -> None:
    assert sync.checkpoint_object_key("proj", "staging") == (
        ".pulumi/stacks/proj/staging.json"
    )


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
