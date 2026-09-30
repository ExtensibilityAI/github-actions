"""Pruning removed workers from the previous release values (helm-rollout)."""

from __future__ import annotations

import json
from pathlib import Path

import prune_workers
import pytest
from prune_workers import ValuesError, main, prune, workers_keys

PREVIOUS = {
    "global": {"env": "staging"},
    "services": {"api": {"image": {"repository": "r/ex-api", "tag": "old-sha"}}},
    "workers": {
        "etl": {"kind": "deployment", "image": {"repository": "r/ex-worker-etl", "tag": "etl-sha"}},
        "audit": {"kind": "deployment", "image": {"repository": "r/ex-worker-audit", "tag": "a"}},
    },
}


def _write(root: Path, rel: str, text: str) -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def _files(root: Path, *workers: str) -> list[Path]:
    files = [_write(root, "chart/values.yaml", "global: {}\nworkers: {}\n")]
    for name in workers:
        files.append(
            _write(
                root,
                f"workers/{name}/deploy/values.yaml",
                f"# {name}\nworkers:\n  # the worker\n  {name}:\n    kind: deployment\n"
                f"    env:\n      - {{name: A, value: b}}\n",
            )
        )
    return files


def _run(tmp_path: Path, previous, files: list[Path], capsys) -> dict:
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(previous) if previous is not None else "null")
    assert main(["prune_workers.py", str(prev), *map(str, files)]) == 0
    return json.loads(capsys.readouterr().out)


def test_removed_worker_is_dropped(tmp_path: Path, capsys) -> None:
    out = _run(tmp_path, PREVIOUS, _files(tmp_path, "etl"), capsys)
    assert list(out["workers"]) == ["etl"]


def test_kept_worker_and_image_tags_carried_over(tmp_path: Path, capsys) -> None:
    out = _run(tmp_path, PREVIOUS, _files(tmp_path, "etl", "audit"), capsys)
    assert out == PREVIOUS
    assert out["workers"]["etl"]["image"]["tag"] == "etl-sha"
    assert out["services"]["api"]["image"]["tag"] == "old-sha"


def test_added_worker_needs_nothing_from_previous(tmp_path: Path, capsys) -> None:
    out = _run(tmp_path, PREVIOUS, _files(tmp_path, "etl", "audit", "reports"), capsys)
    assert set(out["workers"]) == {"etl", "audit"}


def test_no_previous_values(tmp_path: Path, capsys) -> None:
    assert _run(tmp_path, None, _files(tmp_path, "etl"), capsys) == {}


def test_notice_names_removed_worker(tmp_path: Path, capsys) -> None:
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(PREVIOUS))
    main(["prune_workers.py", str(prev), *map(str, _files(tmp_path, "etl"))])
    assert "worker 'audit'" in capsys.readouterr().err


def test_prune_without_workers_key() -> None:
    assert prune({"a": 1}, set()) == ({"a": 1}, [])


@pytest.mark.parametrize("use_yaml", [True, False])
@pytest.mark.parametrize(
    ("text", "keys"),
    [
        ("workers: {}\n", set()),
        ("a: 1\n", set()),
        ("workers:\n  etl:\n    kind: x\n  # c\n  billing: {kind: y}\nother: 1\n", {"etl", "billing"}),
        ("workers:\n\n    'q-w':\n      a: [1]\n", {"q-w"}),
    ],
)
def test_workers_keys(tmp_path: Path, monkeypatch, use_yaml: bool, text: str, keys: set) -> None:
    if not use_yaml:
        monkeypatch.setattr(prune_workers, "_workers_keys_yaml", lambda _t: None)
    assert workers_keys(_write(tmp_path, "v.yaml", text)) == keys


def test_text_parser_refuses_flow_style(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(prune_workers, "_workers_keys_yaml", lambda _t: None)
    with pytest.raises(ValuesError, match="flow style"):
        workers_keys(_write(tmp_path, "v.yaml", "workers: {etl: {}}\n"))


def test_unreadable_values_file_fails(tmp_path: Path, capsys) -> None:
    prev = tmp_path / "prev.json"
    prev.write_text(json.dumps(PREVIOUS))
    bad = _write(tmp_path, "v.yaml", "workers: [a]\n")
    assert main(["prune_workers.py", str(prev), str(bad)]) == 1
    assert "::error::" in capsys.readouterr().err
