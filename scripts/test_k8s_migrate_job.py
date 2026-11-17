#!/usr/bin/env python3
"""Unit tests for scripts/k8s_migrate_job.py."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "k8s_migrate_job.py"
_SPEC = importlib.util.spec_from_file_location("k8s_migrate_job", _SCRIPT)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)

_BASE = {
    "job": "migrate-abcd1234",
    "ns": "app",
    "image": "reg/app:sha",
    "cmd": "alembic upgrade head",
    "sa": "api",
    "deploy_env": "staging",
}


def _container(manifest: dict) -> dict:
    return manifest["spec"]["template"]["spec"]["containers"][0]


class AppDefaultsTests(unittest.TestCase):
    """The defaults (ConfigMap app-env + Secret db) keep the pre-v2.11 Job unchanged."""

    def test_default_manifest(self) -> None:
        manifest = mod.build_manifest(
            **_BASE, cm="app-env", cm_data={"DATABASE_HOST": "h"}, secret="db"
        )
        self.assertEqual(
            manifest,
            {
                "apiVersion": "batch/v1",
                "kind": "Job",
                "metadata": {
                    "name": "migrate-abcd1234",
                    "namespace": "app",
                    "labels": {"app.kubernetes.io/component": "migrate"},
                },
                "spec": {
                    "backoffLimit": 0,
                    "ttlSecondsAfterFinished": 600,
                    "template": {
                        "metadata": {"labels": {"app.kubernetes.io/component": "migrate"}},
                        "spec": {
                            "serviceAccountName": "api",
                            "restartPolicy": "Never",
                            "containers": [
                                {
                                    "name": "migrate",
                                    "image": "reg/app:sha",
                                    "imagePullPolicy": "Always",
                                    "command": ["/bin/sh", "-c", "alembic upgrade head"],
                                    "envFrom": [{"configMapRef": {"name": "app-env"}}],
                                    "env": [
                                        {"name": "CONFIG_ENV", "value": "staging"},
                                        {
                                            "name": "DATABASE_PASSWORD",
                                            "valueFrom": {
                                                "secretKeyRef": {
                                                    "name": "db",
                                                    "key": "password",
                                                }
                                            },
                                        },
                                    ],
                                }
                            ],
                        },
                    },
                },
            },
        )

    def test_direct_host_overrides(self) -> None:
        manifest = mod.build_manifest(
            **_BASE,
            cm="app-env",
            cm_data={"DATABASE_DIRECT_HOST": "10.0.0.5", "DATABASE_DIRECT_PORT": "5432"},
            secret="db",
        )
        names = [e["name"] for e in _container(manifest)["env"]]
        self.assertEqual(names, ["CONFIG_ENV", "DATABASE_PASSWORD", "DATABASE_HOST", "DATABASE_PORT"])

    def test_extra_env_appended(self) -> None:
        manifest = mod.build_manifest(
            **_BASE, cm="app-env", secret="db", extra_env=[{"name": "FOO", "value": "1"}]
        )
        self.assertEqual(_container(manifest)["env"][-1], {"name": "FOO", "value": "1"})


class SecretEnvTests(unittest.TestCase):
    def test_secrets_only_with_resources(self) -> None:
        manifest = mod.build_manifest(
            **_BASE,
            env_from_secrets=["reference-data-runtime-env"],
            resources_cpu="500m",
            resources_memory="1Gi",
        )
        container = _container(manifest)
        self.assertEqual(
            container["envFrom"], [{"secretRef": {"name": "reference-data-runtime-env"}}]
        )
        self.assertEqual(container["env"], [{"name": "CONFIG_ENV", "value": "staging"}])
        self.assertEqual(
            container["resources"],
            {
                "requests": {"cpu": "500m", "memory": "1Gi"},
                "limits": {"cpu": "500m", "memory": "1Gi"},
            },
        )

    def test_no_resources_key_by_default(self) -> None:
        manifest = mod.build_manifest(**_BASE, cm="app-env", secret="db")
        self.assertNotIn("resources", _container(manifest))

    def test_parse_secret_names(self) -> None:
        self.assertEqual(
            mod.parse_secret_names("a\n\n# comment\n  b  \n"),
            ["a", "b"],
        )


if __name__ == "__main__":
    unittest.main()
