"""Validate and normalize the image specs for deploy-gke-app / deploy-eks-app.

Reads ``IMAGES_JSON`` (inline JSON) or ``IMAGES_FILE`` (comma-separated paths and
globs of JSON files in the checkout); exactly one must be set. Writes ``matrix``,
``count`` and ``first_name`` to ``$GITHUB_OUTPUT``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any

ROLE_DEFAULTS = {
    "api": ("api", "api"),
    "frontend": ("frontend", "frontend"),
    "app": ("app", "app"),
}
KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
DNS_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
# Dotted Helm path; no characters with meaning to --set (',', '=', '[', '\\', ...).
VALUES_KEY_RE = re.compile(r"^[A-Za-z0-9_-]+(\.[A-Za-z0-9_-]+)*$")
GLOB_CHARS = "*?["


class ImageSpecError(ValueError):
    """An image spec is invalid; the message is shown as a workflow error."""


def _check_path(field: str, value: Any) -> None:
    if not isinstance(value, str) or not value:
        raise ImageSpecError(f"{field} must be a non-empty string")
    if ".." in value.split("/"):
        raise ImageSpecError(f"{field} must not contain '..' segments")
    if value.startswith("/"):
        raise ImageSpecError(f"{field} must be a relative path")


def _parse_json(raw: str, source: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ImageSpecError(f"{source} is not valid JSON: {e}") from None


def _image_files(images_file: str, root: Path) -> list[str]:
    """Expand the comma-separated paths and globs, in list order.

    A plain path must exist. A glob may match nothing (a project may have no workers);
    its matches are sorted.
    """
    files: list[str] = []
    for entry in (e.strip() for e in images_file.split(",")):
        if not entry:
            continue
        _check_path("images_file", entry)
        if not any(c in entry for c in GLOB_CHARS):
            if not (root / entry).is_file():
                raise ImageSpecError(f"images_file {entry!r} does not exist")
            files.append(entry)
            continue
        for match in sorted(p.relative_to(root).as_posix() for p in root.glob(entry)):
            _check_path("images_file", match)
            if (root / match).is_file():
                files.append(match)
    return files


def load_images(images_json: str, images_file: str, *, root: Path = Path(".")) -> Any:
    """Return the parsed images array from exactly one of the two sources.

    ``images_file`` may list several paths and globs; their arrays are concatenated.
    """
    images_json = images_json.strip()
    images_file = images_file.strip()
    if images_json and images_file:
        raise ImageSpecError("set only one of images and images_file")
    if images_json:
        return _parse_json(images_json, "images")
    if not images_file:
        raise ImageSpecError("one of images or images_file is required")
    images: list[Any] = []
    for path in _image_files(images_file, root):
        source = f"images_file {path!r}"
        data = _parse_json((root / path).read_text(encoding="utf-8"), source)
        if not isinstance(data, list):
            raise ImageSpecError(f"{source} must hold a JSON array")
        images.extend(data)
    return images


def normalize(images: Any) -> list[dict[str, str]]:
    """Validate the specs and apply defaults; return the matrix entries."""
    if not isinstance(images, list) or not images:
        raise ImageSpecError("images must be a non-empty JSON array")
    out = []
    seen: set[str] = set()
    for i, item in enumerate(images):
        if not isinstance(item, dict):
            raise ImageSpecError(f"images[{i}] must be an object")
        name = item.get("name")
        if not name or not isinstance(name, str):
            raise ImageSpecError(f"images[{i}].name is required")
        if "/" in name or ".." in name:
            raise ImageSpecError(f"images[{i}].name must not contain '/' or '..'")
        if name in seen:
            raise ImageSpecError(f"images[{i}].name {name!r} is used by more than one image")
        seen.add(name)
        role = item.get("role") or ""
        if role and not DNS_LABEL_RE.fullmatch(role):
            raise ImageSpecError(
                f"images[{i}].role must be a Kubernetes DNS label "
                "(lowercase alphanumeric and hyphens) or empty"
            )
        context = item.get("context") or "."
        dockerfile = item.get("dockerfile") or "Dockerfile"
        _check_path(f"images[{i}].context", context)
        _check_path(f"images[{i}].dockerfile", dockerfile)
        build_secret_env = item.get("build_secret_env") or ""
        if build_secret_env and not KEY_RE.match(build_secret_env):
            raise ImageSpecError(f"images[{i}].build_secret_env must be an uppercase env var name")
        values_key = item.get("values_key") or ""
        if values_key and (
            not isinstance(values_key, str) or not VALUES_KEY_RE.fullmatch(values_key)
        ):
            raise ImageSpecError(
                f"images[{i}].values_key must be a dotted Helm values path "
                "(letters, digits, '-' and '_' separated by '.')"
            )
        dep, cont = ROLE_DEFAULTS.get(role, (role or None, role or None))
        entry = {
            "name": name,
            "context": context,
            "dockerfile": dockerfile,
            "deployment": item.get("deployment") or dep or name,
            "container": item.get("container") or cont or name,
            # Stringy booleans for composite action inputs.
            "needs_pypi_auth": "true" if item.get("needs_pypi_auth", False) else "false",
            "build_secret_env": build_secret_env,
        }
        if values_key:
            entry["values_key"] = values_key
        out.append(entry)
    return out


def main() -> int:
    try:
        images = load_images(
            os.environ.get("IMAGES_JSON", ""), os.environ.get("IMAGES_FILE", "")
        )
        out = normalize(images)
    except ImageSpecError as e:
        print(f"::error::{e}", file=sys.stderr)
        return 1
    matrix = json.dumps(out, separators=(",", ":"))
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as fh:
        fh.write(f"matrix={matrix}\n")
        fh.write(f"count={len(out)}\n")
        fh.write(f"first_name={out[0]['name']}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
