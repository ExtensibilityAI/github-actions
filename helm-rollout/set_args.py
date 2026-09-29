"""Compute helm ``--set`` values for image repositories and tags.

Each image in ``images_json`` (the parse-image-matrix output) sets:

* ``<values_key>.image.{repository,tag}`` when it has a ``values_key``;
* otherwise, by a role taken from ``role`` or the image name's last ``-`` segment:
  ``worker.image.*`` for ``worker``, else ``services.<role>.image.*`` (plus top-level
  ``image.*`` for ``api`` / ``app``).

parse-image-matrix does not pass ``role`` through, so in practice the role comes
from the image name. That is kept as is: some callers set a ``role`` that differs
from their name suffix (e.g. ``website`` with ``role: app``).
"""

from __future__ import annotations

import json
import os
import sys

from artifacts import artifacts_destination


def image_set_args(
    *,
    registry: str,
    sha: str,
    images_json: str,
    changed_by_name: str = "",
    suffix: str = "",
) -> list[str]:
    """Return ``key=value`` strings for the images' repositories and tags."""
    args: list[str] = []
    changed = None
    if changed_by_name.strip():
        try:
            changed = json.loads(changed_by_name)
        except json.JSONDecodeError:
            changed = None

    def want(name: str) -> bool:
        if changed is None:
            return True
        return bool(changed.get(name, True))

    images_raw = images_json.strip()
    if images_raw and images_raw != "[]":
        for obj in json.loads(images_raw):
            name = str(obj.get("name") or "").strip()
            if not name or not want(name):
                continue
            image_repo = f"{registry}/{name}"
            values_key = str(obj.get("values_key") or "").strip()
            if values_key:
                args.append(f"{values_key}.image.repository={image_repo}")
                args.append(f"{values_key}.image.tag={sha}")
                continue
            role = str(obj.get("role") or "").strip() or name.rsplit("-", 1)[-1]
            if role == "worker":
                args.append(f"worker.image.repository={image_repo}")
                args.append(f"worker.image.tag={sha}")
            else:
                args.append(f"services.{role}.image.repository={image_repo}")
                args.append(f"services.{role}.image.tag={sha}")
                # OSS charts often use top-level image.*
                if role in ("api", "app"):
                    args.append(f"image.repository={image_repo}")
                    args.append(f"image.tag={sha}")
    else:
        if not suffix.strip():
            raise SystemExit("helm_image_repository_suffix or images_json required")
        image_repo = f"{registry}/{suffix.strip()}"
        args.append(f"image.repository={image_repo}")
        args.append(f"image.tag={sha}")
        args.append(f"services.api.image.repository={image_repo}")
        args.append(f"services.api.image.tag={sha}")
    return args


def extra_set_args(*, hostname: str, artifacts: str, cloud: str) -> list[str]:
    """Return ``key=value`` strings for the gateway hostname and artifacts bucket."""
    args: list[str] = []
    if hostname.strip():
        args.append(f"server.value_options.allowed_hosts={hostname.strip()}")
    dest = artifacts_destination(artifacts, cloud) if artifacts.strip() else None
    if dest:
        args.append(f"mlflow.artifactsDestination={dest}")
    return args


def main() -> int:
    env = os.environ
    args = image_set_args(
        registry=env["REGISTRY"],
        sha=env["SHA"],
        images_json=env.get("IMAGES_JSON", ""),
        changed_by_name=env.get("CHANGED_BY_NAME", ""),
        suffix=env.get("IMAGE_SUFFIX", ""),
    )
    args += extra_set_args(
        hostname=env.get("GATEWAY_HOSTNAME", ""),
        artifacts=env.get("ARTIFACTS_BUCKET", ""),
        cloud=env.get("CLOUD", "gcp"),
    )
    for a in args:
        print(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
