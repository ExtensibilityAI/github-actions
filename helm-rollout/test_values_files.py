"""values_files expansion for helm-rollout."""

from __future__ import annotations

from pathlib import Path

import pytest
from values_files import expand


def _touch(root: Path, rel: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("workers: {}\n")


def test_plain_paths_kept_in_order(tmp_path: Path) -> None:
    assert expand(" chart/values.yaml , extra.yaml,", root=tmp_path) == [
        "chart/values.yaml",
        "extra.yaml",
    ]


def test_globs_sorted_after_earlier_entries(tmp_path: Path) -> None:
    _touch(tmp_path, "chart/values.yaml")
    _touch(tmp_path, "workers/etl/deploy/values.yaml")
    _touch(tmp_path, "workers/billing/deploy/values.yaml")
    assert expand("chart/values.yaml,workers/*/deploy/values.yaml", root=tmp_path) == [
        "chart/values.yaml",
        "workers/billing/deploy/values.yaml",
        "workers/etl/deploy/values.yaml",
    ]


def test_empty_glob_dropped(tmp_path: Path) -> None:
    assert expand("chart/values.yaml,workers/*/deploy/values.yaml", root=tmp_path) == [
        "chart/values.yaml"
    ]


def test_glob_must_stay_in_checkout(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        expand("../*/values.yaml", root=tmp_path)
