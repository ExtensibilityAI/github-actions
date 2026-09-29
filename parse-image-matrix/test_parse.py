"""Image spec parsing for parse-image-matrix."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from parse import ImageSpecError, load_images, main, normalize


def test_defaults_match_previous_behaviour() -> None:
    [entry] = normalize([{"name": "exampleapp-api", "role": "api", "needs_pypi_auth": True}])
    assert entry == {
        "name": "exampleapp-api",
        "context": ".",
        "dockerfile": "Dockerfile",
        "deployment": "api",
        "container": "api",
        "needs_pypi_auth": "true",
        "build_secret_env": "",
    }


def test_unknown_role_fills_deployment_and_container() -> None:
    [entry] = normalize([{"name": "exampleapp-worker-billing", "role": "worker-billing"}])
    assert entry["deployment"] == "worker-billing"
    assert entry["container"] == "worker-billing"
    assert entry["needs_pypi_auth"] == "false"


def test_no_role_falls_back_to_name() -> None:
    [entry] = normalize([{"name": "website"}])
    assert entry["deployment"] == "website"
    assert entry["container"] == "website"


def test_values_key_passed_through() -> None:
    [entry] = normalize([{"name": "x-worker-billing", "values_key": "workers.billing"}])
    assert entry["values_key"] == "workers.billing"


@pytest.mark.parametrize(
    "key",
    ["workers.billing,services.api.image.tag=evil", "a=b", "a[0]", "a..b", ".a", "a.", "a\\.b"],
)
def test_values_key_rejects_set_syntax(key: str) -> None:
    with pytest.raises(ImageSpecError, match="values_key"):
        normalize([{"name": "x", "values_key": key}])


@pytest.mark.parametrize(
    ("item", "match"),
    [
        ({}, "name is required"),
        ({"name": "a/b"}, "must not contain"),
        ({"name": "a", "role": "Bad_Role"}, "DNS label"),
        ({"name": "a", "context": "../x"}, "'..'"),
        ({"name": "a", "dockerfile": "/abs"}, "relative"),
        ({"name": "a", "build_secret_env": "lower"}, "uppercase"),
    ],
)
def test_invalid_specs(item: dict, match: str) -> None:
    with pytest.raises(ImageSpecError, match=match):
        normalize([item])


def test_empty_array_rejected() -> None:
    with pytest.raises(ImageSpecError, match="non-empty"):
        normalize([])


def test_load_inline() -> None:
    assert load_images('[{"name": "a"}]', "") == [{"name": "a"}]


def test_load_file(tmp_path: Path) -> None:
    (tmp_path / ".github").mkdir()
    (tmp_path / ".github" / "images.json").write_text('[{"name": "a"}]')
    assert load_images("", ".github/images.json", root=tmp_path) == [{"name": "a"}]


def test_load_requires_exactly_one_source(tmp_path: Path) -> None:
    with pytest.raises(ImageSpecError, match="only one"):
        load_images('[{"name": "a"}]', "images.json", root=tmp_path)
    with pytest.raises(ImageSpecError, match="required"):
        load_images("  ", "", root=tmp_path)


def test_load_file_errors(tmp_path: Path) -> None:
    with pytest.raises(ImageSpecError, match="does not exist"):
        load_images("", "missing.json", root=tmp_path)
    with pytest.raises(ImageSpecError, match="'..'"):
        load_images("", "../images.json", root=tmp_path)
    (tmp_path / "bad.json").write_text("{nope")
    with pytest.raises(ImageSpecError, match="not valid JSON"):
        load_images("", "bad.json", root=tmp_path)


def test_main_writes_outputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    out = tmp_path / "out"
    monkeypatch.setenv("GITHUB_OUTPUT", str(out))
    monkeypatch.setenv("IMAGES_JSON", '[{"name": "a-api", "role": "api"}, {"name": "a-web"}]')
    monkeypatch.delenv("IMAGES_FILE", raising=False)
    assert main() == 0
    lines = dict(line.split("=", 1) for line in out.read_text().splitlines())
    assert lines["count"] == "2"
    assert lines["first_name"] == "a-api"
    assert [e["name"] for e in json.loads(lines["matrix"])] == ["a-api", "a-web"]


def test_main_reports_errors(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "out"))
    monkeypatch.setenv("IMAGES_JSON", "[]")
    assert main() == 1
    assert "::error::images must be a non-empty JSON array" in capsys.readouterr().err
