#!/usr/bin/env python3
"""Build the k8s-migrate Job manifest.

Database settings come from ConfigMap ``CM`` (``envFrom``) plus ``DATABASE_PASSWORD`` from
Secret ``SECRET``/``SECRET_KEY``; either is skipped when its name is empty. Workloads that keep
their settings in Secrets (e.g. Dagster code locations) list them in ``ENV_FROM_SECRETS``
(newline-delimited), each added as ``envFrom: secretRef``. ``RESOURCES_CPU`` /
``RESOURCES_MEMORY`` set requests = limits, which namespaces with a ResourceQuota on limits
require.

Usage (from the action, env set by the step):
  python3 k8s_migrate_job.py /path/out.json
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
from collections.abc import Mapping, Sequence
from typing import Any


def parse_secret_names(text: str) -> list[str]:
    """Newline-delimited Secret names; blanks and ``#`` comments skipped."""
    names = []
    for line in text.splitlines():
        name = line.strip()
        if name and not name.startswith("#"):
            names.append(name)
    return names


def build_manifest(
    *,
    job: str,
    ns: str,
    image: str,
    cmd: str,
    sa: str,
    deploy_env: str,
    cm: str = "",
    cm_data: Mapping[str, str] | None = None,
    secret: str = "",
    secret_key: str = "password",
    env_from_secrets: Sequence[str] = (),
    extra_env: Sequence[Mapping[str, str]] = (),
    resources_cpu: str = "",
    resources_memory: str = "",
) -> dict[str, Any]:
    env_list: list[dict[str, Any]] = [{"name": "CONFIG_ENV", "value": deploy_env}]
    if secret:
        env_list.append(
            {
                "name": "DATABASE_PASSWORD",
                "valueFrom": {"secretKeyRef": {"name": secret, "key": secret_key}},
            }
        )
    # Behind a PgBouncer pooler, app-env's DATABASE_HOST/PORT point at the pooler;
    # migrations connect to the database directly (DATABASE_DIRECT_*).
    cm_data = cm_data or {}
    if cm and cm_data.get("DATABASE_DIRECT_HOST"):
        print("app-env has DATABASE_DIRECT_HOST: migrating against the database directly")
        for name, key in (
            ("DATABASE_HOST", "DATABASE_DIRECT_HOST"),
            ("DATABASE_PORT", "DATABASE_DIRECT_PORT"),
        ):
            if cm_data.get(key):
                env_list.append(
                    {
                        "name": name,
                        "valueFrom": {"configMapKeyRef": {"name": cm, "key": key}},
                    }
                )
    for item in extra_env:
        env_list.append({"name": item["name"], "value": item["value"]})

    env_from: list[dict[str, Any]] = []
    if cm:
        env_from.append({"configMapRef": {"name": cm}})
    env_from.extend({"secretRef": {"name": name}} for name in env_from_secrets)

    container: dict[str, Any] = {
        "name": "migrate",
        "image": image,
        "imagePullPolicy": "Always",
        "command": ["/bin/sh", "-c", cmd],
        "envFrom": env_from,
        "env": env_list,
    }
    resources = {
        key: value
        for key, value in (("cpu", resources_cpu), ("memory", resources_memory))
        if value
    }
    if resources:
        container["resources"] = {"requests": resources, "limits": dict(resources)}

    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": job,
            "namespace": ns,
            "labels": {"app.kubernetes.io/component": "migrate"},
        },
        "spec": {
            "backoffLimit": 0,
            "ttlSecondsAfterFinished": 600,
            "template": {
                "metadata": {
                    "labels": {"app.kubernetes.io/component": "migrate"},
                },
                "spec": {
                    "serviceAccountName": sa,
                    "restartPolicy": "Never",
                    "containers": [container],
                },
            },
        },
    }


def _read_config_map(ns: str, cm: str) -> dict[str, str]:
    out = subprocess.run(
        ["kubectl", "-n", ns, "get", "configmap", cm, "-o", "json"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out).get("data") or {}


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("usage: k8s_migrate_job.py OUT.json", file=sys.stderr)
        return 2
    env = os.environ
    ns = env["NS"]
    cm = env.get("CM", "").strip()
    extra_env: list[dict[str, str]] = []
    extra_file = env.get("EXTRA_ENV_FILE", "")
    if extra_file and pathlib.Path(extra_file).is_file():
        extra_env = json.loads(pathlib.Path(extra_file).read_text(encoding="utf-8"))

    manifest = build_manifest(
        job=env["JOB_NAME"],
        ns=ns,
        image=env["IMAGE"],
        cmd=env["CMD"],
        sa=env["SA"],
        deploy_env=env["DEPLOY_ENV"],
        cm=cm,
        cm_data=_read_config_map(ns, cm) if cm else None,
        secret=env.get("SECRET", "").strip(),
        secret_key=env.get("SECRET_KEY", "password"),
        env_from_secrets=parse_secret_names(env.get("ENV_FROM_SECRETS", "")),
        extra_env=extra_env,
        resources_cpu=env.get("RESOURCES_CPU", "").strip(),
        resources_memory=env.get("RESOURCES_MEMORY", "").strip(),
    )
    pathlib.Path(argv[1]).write_text(json.dumps(manifest), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
