"""Artifact URI scheme defaults for helm-rollout."""

from __future__ import annotations

from artifacts import artifacts_destination


def test_artifacts_destination_passthrough() -> None:
    assert artifacts_destination("s3://bucket", "gcp") == "s3://bucket"
    assert artifacts_destination("gs://bucket", "aws") == "gs://bucket"


def test_artifacts_destination_prefixes_by_cloud() -> None:
    assert artifacts_destination("my-bucket", "aws") == "s3://my-bucket"
    assert artifacts_destination("my-bucket", "gcp") == "gs://my-bucket"
    assert artifacts_destination("my-bucket", "") == "gs://my-bucket"


def test_artifacts_destination_empty() -> None:
    assert artifacts_destination("", "aws") is None
    assert artifacts_destination("  ", "gcp") is None
