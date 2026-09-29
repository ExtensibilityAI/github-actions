"""helm --set values computed by helm-rollout."""

from __future__ import annotations

import json

import pytest
from set_args import extra_set_args, image_set_args

REG = "us-central1-docker.pkg.dev/proj/docker-images"


def _images(*items: dict) -> str:
    return json.dumps(list(items))


def test_api_sets_service_and_top_level_image() -> None:
    args = image_set_args(registry=REG, sha="abc", images_json=_images({"name": "ex-api"}))
    assert args == [
        f"services.api.image.repository={REG}/ex-api",
        "services.api.image.tag=abc",
        f"image.repository={REG}/ex-api",
        "image.tag=abc",
    ]


def test_worker_suffix_sets_worker_image() -> None:
    args = image_set_args(registry=REG, sha="abc", images_json=_images({"name": "ex-worker"}))
    assert args == [f"worker.image.repository={REG}/ex-worker", "worker.image.tag=abc"]


def test_role_is_taken_from_name_not_matrix_role() -> None:
    # parse-image-matrix drops role; a caller such as the website uses role "app"
    # for an image named "website" and relies on services.website.image.*.
    args = image_set_args(registry=REG, sha="abc", images_json=_images({"name": "website"}))
    assert args == [f"services.website.image.repository={REG}/website", "services.website.image.tag=abc"]


def test_values_key_sets_only_that_key() -> None:
    args = image_set_args(
        registry=REG,
        sha="abc",
        images_json=_images(
            {"name": "ex-api"},
            {"name": "ex-worker-billing", "values_key": "workers.billing"},
        ),
    )
    assert args[-2:] == [
        f"workers.billing.image.repository={REG}/ex-worker-billing",
        "workers.billing.image.tag=abc",
    ]
    assert not any(a.startswith(("services.billing", "worker.")) for a in args)


def test_changed_by_name_filters_values_key_images() -> None:
    args = image_set_args(
        registry=REG,
        sha="abc",
        images_json=_images(
            {"name": "ex-api"},
            {"name": "ex-worker-billing", "values_key": "workers.billing"},
        ),
        changed_by_name=json.dumps({"ex-api": "true", "ex-worker-billing": False}),
    )
    assert not any(a.startswith("workers.") for a in args)
    assert f"services.api.image.repository={REG}/ex-api" in args


def test_single_image_fallback() -> None:
    args = image_set_args(registry=REG, sha="abc", images_json="", suffix="ex-api")
    assert args == [
        f"image.repository={REG}/ex-api",
        "image.tag=abc",
        f"services.api.image.repository={REG}/ex-api",
        "services.api.image.tag=abc",
    ]


def test_fallback_requires_suffix() -> None:
    with pytest.raises(SystemExit):
        image_set_args(registry=REG, sha="abc", images_json="[]")


def test_extra_set_args() -> None:
    assert extra_set_args(hostname="", artifacts="", cloud="gcp") == []
    assert extra_set_args(hostname=" h.example ", artifacts="bkt", cloud="aws") == [
        "server.value_options.allowed_hosts=h.example",
        "mlflow.artifactsDestination=s3://bkt",
    ]
