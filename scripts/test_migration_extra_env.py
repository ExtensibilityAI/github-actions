#!/usr/bin/env python3
"""Unit tests for scripts/migration_extra_env.py."""

from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parent / "migration_extra_env.py"
_SPEC = importlib.util.spec_from_file_location("migration_extra_env", _SCRIPT)
assert _SPEC and _SPEC.loader
mod = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod)


class ParseTests(unittest.TestCase):
    def test_single_line(self) -> None:
        entries = mod.parse_migration_extra_env(
            "FOO=bar\nBAZ=qux\n"
        )
        self.assertEqual(entries, [("FOO", "bar"), ("BAZ", "qux")])

    def test_skips_blank_and_comment_before_first_key(self) -> None:
        entries = mod.parse_migration_extra_env(
            "# header\n\nFOO=1\nBAR=2\n"
        )
        self.assertEqual(entries, [("FOO", "1"), ("BAR", "2")])

    def test_blank_lines_inside_value_preserved(self) -> None:
        entries = mod.parse_migration_extra_env("FOO=a\n\nb\nBAR=2\n")
        self.assertEqual(entries, [("FOO", "a\n\nb"), ("BAR", "2")])

    def test_multiline_pem(self) -> None:
        blob = (
            "SCAFFOLDER_GITHUB_ORG=ExtensibilityAI\n"
            "SCAFFOLDER_GITHUB_APP_PRIVATE_KEY_PEM=-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF55L\n"
            "AQAB\n"
            "-----END RSA PRIVATE KEY-----\n"
            "SCAFFOLDER_GITHUB_APP_ID=12345\n"
        )
        entries = mod.parse_migration_extra_env(blob)
        self.assertEqual(len(entries), 3)
        self.assertEqual(entries[0], ("SCAFFOLDER_GITHUB_ORG", "ExtensibilityAI"))
        self.assertEqual(entries[2], ("SCAFFOLDER_GITHUB_APP_ID", "12345"))
        pem = entries[1][1]
        self.assertTrue(pem.startswith("-----BEGIN RSA PRIVATE KEY-----"))
        self.assertIn("MIIEowIBAAKCAQEA0Z3VS5JJcds3xfn/ygWyF55L", pem)
        self.assertTrue(pem.rstrip().endswith("-----END RSA PRIVATE KEY-----"))
        self.assertIn("\n", pem)

    def test_missing_equals(self) -> None:
        with self.assertRaises(mod.MigrationExtraEnvError) as ctx:
            mod.parse_migration_extra_env("NOTAKEY\n")
        self.assertIn("missing '='", str(ctx.exception))

    def test_bad_key(self) -> None:
        with self.assertRaises(mod.MigrationExtraEnvError) as ctx:
            mod.parse_migration_extra_env("bad-key=1\n")
        self.assertIn("missing '='", str(ctx.exception))


class WriteTests(unittest.TestCase):
    def test_github_env_single_and_multiline(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "env"
            path.write_text("", encoding="utf-8")
            mod.write_github_env(
                str(path),
                [
                    ("FOO", "bar"),
                    ("PEM", "-----BEGIN-----\nline2\n-----END-----"),
                ],
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("FOO=bar\n", text)
            self.assertIn("PEM<<EOF_MIGRATE_PEM_", text)
            self.assertIn("-----BEGIN-----\nline2\n-----END-----", text)

    def test_write_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "env.json"
            mod.write_json_file(
                str(path),
                [("FOO", "bar"), ("PEM", "a\nb")],
            )
            data = path.read_text(encoding="utf-8")
            self.assertIn('"name": "FOO"', data)
            self.assertIn('"value": "a\\nb"', data)


if __name__ == "__main__":
    unittest.main()
