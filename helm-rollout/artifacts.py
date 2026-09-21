"""Resolve MLflow artifactsDestination from ARTIFACTS_BUCKET + cloud."""

from __future__ import annotations


def artifacts_destination(artifacts: str, cloud: str) -> str | None:
    """Return a gs:// or s3:// URI, or None when unset."""
    value = artifacts.strip()
    if not value:
        return None
    if value.startswith("gs://") or value.startswith("s3://"):
        return value
    scheme = "s3" if cloud.strip().lower() == "aws" else "gs"
    return f"{scheme}://{value}"
