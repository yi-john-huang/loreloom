from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import doctor_vault, validate_vault


class DoctorVaultTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "vault"
        self.repo.mkdir()
        subprocess.run(["git", "init", "-q", "-b", "master"], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "config", "user.name", "Loreloom Tests"], cwd=self.repo, check=True
        )
        subprocess.run(
            ["git", "config", "user.email", "tests@example.invalid"],
            cwd=self.repo,
            check=True,
        )
        self.make_framework_layout()
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(
            ["git", "commit", "-q", "-m", "fixture"], cwd=self.repo, check=True
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def write(self, relative_path: str, content: str) -> Path:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def make_framework_layout(self) -> None:
        for directory in (*validate_vault.MANAGED_ROOTS, "Assets", "Templates", "schemas", "scripts"):
            (self.repo / directory).mkdir(parents=True, exist_ok=True)
        self.write(".python-version", "3.13\n")
        self.write(
            "pyproject.toml",
            '[project]\nrequires-python = ">=3.11"\ndependencies = []\n\n'
            '[dependency-groups]\ndev = ["jsonschema==4.25.1", "pyyaml==6.0.2"]\n',
        )
        self.write("uv.lock", "version = 1\n")
        self.write("schemas/frontmatter.schema.json", "{}\n")
        self.write(".agents/policies/vault-policy.md", "# Policy\n")
        self.write("Templates/Source.md", "# Source\n")
        self.write("Templates/Concept.md", "# Concept\n")
        self.write("Templates/Daily.md", "# Daily\n")
        self.write("scripts/validate_vault.py", "# validator\n")
        self.write(
            ".obsidian/app.json",
            json.dumps({"alwaysUpdateLinks": True, "attachmentFolderPath": "Assets"}),
        )
        self.write(
            ".obsidian/templates.json",
            json.dumps(
                {"folder": "Templates", "dateFormat": "YYYY-MM-DD", "timeFormat": "HH:mm"}
            ),
        )
        self.write(
            ".obsidian/daily-notes.json",
            json.dumps(
                {"folder": "Daily", "format": "YYYY-MM-DD", "template": "Templates/Daily"}
            ),
        )
        self.write(
            ".obsidian/core-plugins.json",
            json.dumps({"properties": True, "daily-notes": True, "templates": True}),
        )


    def run_core(self) -> list[doctor_vault.Check]:
        with mock.patch.object(doctor_vault.shutil, "which", return_value="/usr/bin/tool"), mock.patch.object(
            doctor_vault.importlib.metadata,
            "version",
            side_effect=lambda name: {"jsonschema": "4.25.1", "pyyaml": "6.0.2"}[name.lower()],
        ), mock.patch.object(validate_vault, "main", return_value=0):
            return doctor_vault.core_checks(self.repo)

    @staticmethod
    def by_name(checks: list[doctor_vault.Check]) -> dict[str, doctor_vault.Check]:
        return {check.name: check for check in checks}

    def test_fresh_framework_layout_is_ready_and_read_only(self) -> None:
        before = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }

        checks = self.run_core()

        self.assertFalse([check for check in checks if check.status == "FAIL"], checks)
        after = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file() and ".git" not in path.parts
        }
        self.assertEqual(after, before)

    def test_missing_tool_and_framework_path_fail(self) -> None:
        shutil.rmtree(self.repo / "Knowledge")
        with mock.patch.object(
            doctor_vault.shutil,
            "which",
            side_effect=lambda name: None if name == "uv" else "/usr/bin/tool",
        ), mock.patch.object(validate_vault, "main", return_value=0):
            checks = self.by_name(doctor_vault.core_checks(self.repo))
        self.assertEqual(checks["uv"].status, "FAIL")
        self.assertEqual(checks["framework-layout"].status, "FAIL")

    def test_python_before_311_fails(self) -> None:
        with mock.patch.object(doctor_vault.sys, "version_info", (3, 10)):
            check = doctor_vault._python_check()
        self.assertEqual(check.status, "FAIL")

    def test_missing_git_fails(self) -> None:
        with mock.patch.object(
            doctor_vault.shutil,
            "which",
            side_effect=lambda name: None if name == "git" else "/usr/bin/tool",
        ), mock.patch.object(
            doctor_vault.importlib.metadata,
            "version",
            return_value="4.25.1",
        ), mock.patch.object(validate_vault, "main", return_value=0):
            checks = self.by_name(doctor_vault.core_checks(self.repo))
        self.assertEqual(checks["git"].status, "FAIL")

    def test_missing_dependency_fails(self) -> None:
        with mock.patch.object(doctor_vault.shutil, "which", return_value="/usr/bin/tool"), mock.patch.object(
            doctor_vault.importlib.metadata, "version", side_effect=doctor_vault.importlib.metadata.PackageNotFoundError
        ), mock.patch.object(validate_vault, "main", return_value=0):
            checks = self.by_name(doctor_vault.core_checks(self.repo))
        self.assertEqual(checks["locked-dependencies"].status, "FAIL")

    def test_public_framework_origin_is_rejected_for_all_supported_transports(self) -> None:
        remotes = (
            "https://github.com/yi-john-huang/loreloom.git",
            "git@github.com:yi-john-huang/loreloom.git",
            "ssh://git@github.com/yi-john-huang/loreloom/",
            "ssh://git@ssh.github.com:443/yi-john-huang/loreloom.git",
        )
        for remote in remotes:
            with self.subTest(remote=remote):
                subprocess.run(
                    ["git", "remote", "remove", "origin"],
                    cwd=self.repo,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                subprocess.run(
                    ["git", "remote", "add", "origin", remote], cwd=self.repo, check=True
                )
                checks = self.by_name(self.run_core())
                self.assertEqual(checks["remote-privacy"].status, "FAIL")

    def test_private_or_missing_origin_is_privacy_unverified_warning(self) -> None:
        for remote in ("git@example.com:owner/private.git", None):
            with self.subTest(remote=remote):
                subprocess.run(
                    ["git", "remote", "remove", "origin"],
                    cwd=self.repo,
                    check=False,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                )
                if remote:
                    subprocess.run(
                        ["git", "remote", "add", "origin", remote], cwd=self.repo, check=True
                    )
                checks = self.by_name(self.run_core())
                self.assertEqual(
                    checks["remote-privacy"],
                    doctor_vault.Check(
                        "WARN",
                        "remote-privacy",
                        "repository visibility is not verifiable locally; confirm the remote is private",
                    ),
                )

    def test_malformed_or_unsafe_obsidian_settings_fail(self) -> None:
        self.write(".obsidian/app.json", "not-json")
        checks = self.by_name(self.run_core())
        self.assertEqual(checks["obsidian-settings"].status, "FAIL")

    def test_validator_failure_is_one_stable_check(self) -> None:
        output = io.StringIO()
        with mock.patch.object(doctor_vault.shutil, "which", return_value="/usr/bin/tool"), mock.patch.object(
            doctor_vault.importlib.metadata, "version", return_value="4.25.1"
        ), mock.patch.object(validate_vault, "main", side_effect=lambda: print("private/path.md") or 1), contextlib.redirect_stdout(output):
            checks = self.by_name(doctor_vault.core_checks(self.repo))
        self.assertEqual(checks["vault-validation"].status, "FAIL")
        self.assertEqual(output.getvalue(), "")
        self.assertNotIn("private/path.md", checks["vault-validation"].detail)

    def test_normalize_github_remote(self) -> None:
        self.assertEqual(
            doctor_vault.normalize_github_remote(
                "ssh://git@ssh.github.com:443/YI-JOHN-HUANG/LORELOOM.git/"
            ),
            ("github.com", "yi-john-huang/loreloom"),
        )
        self.assertIsNone(doctor_vault.normalize_github_remote("https://example.com/a/b"))
        self.assertIsNone(doctor_vault.normalize_github_remote("ssh://git@ssh.github.com:22/a/b"))
        self.assertIsNone(
            doctor_vault.normalize_github_remote("ssh://git@github.com:not-a-port/a/b")
        )

    def test_cli_output_and_exit_codes_are_stable(self) -> None:
        passing = [doctor_vault.Check("PASS", "one", "ok"), doctor_vault.Check("WARN", "two", "check")]
        failing = [doctor_vault.Check("FAIL", "one", "broken")]
        for checks, expected_code, readiness in (
            (passing, 0, "READY"),
            (failing, 1, "NOT READY"),
        ):
            with self.subTest(readiness=readiness), mock.patch.object(
                doctor_vault, "core_checks", return_value=checks
            ), contextlib.redirect_stdout(io.StringIO()) as output:
                code = doctor_vault.main([])
            self.assertEqual(code, expected_code)
            self.assertEqual(output.getvalue().splitlines()[-1], f"Core readiness: {readiness}")
        with self.assertRaises(SystemExit) as raised:
            doctor_vault.parse_args(["--unknown"])
        self.assertEqual(raised.exception.code, 2)

    def test_advanced_checks_are_opt_in(self) -> None:
        core = [doctor_vault.Check("PASS", "core", "ready")]
        with mock.patch.object(
            doctor_vault,
            "core_checks",
            return_value=core,
        ), mock.patch.object(
            doctor_vault,
            "advanced_checks",
            side_effect=AssertionError("advanced checks ran without --advanced"),
        ), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(doctor_vault.main([]), 0)

        with mock.patch.object(
            doctor_vault,
            "core_checks",
            return_value=core,
        ), mock.patch.object(
            doctor_vault,
            "advanced_checks",
            return_value=[doctor_vault.Check("FAIL", "advanced", "not ready")],
        ), contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(doctor_vault.main(["--advanced"]), 1)
        self.assertEqual(
            output.getvalue().splitlines()[-1],
            "Advanced readiness: NOT READY",
        )


    @unittest.skipUnless(os.name == "posix" and shutil.which("openssl"), "requires POSIX and OpenSSL")
    def test_advanced_keys_must_parse_and_match_without_leaking_paths(self) -> None:
        key_root = Path(self.temporary.name) / "owner-keys"
        key_root.mkdir()
        private_key = key_root / "owner-private.pem"
        other_key = key_root / "wrong-private.pem"
        public_key = key_root / "owner-public.pem"
        for key in (private_key, other_key):
            subprocess.run(
                ["openssl", "genpkey", "-algorithm", "RSA", "-pkeyopt", "rsa_keygen_bits:2048", "-out", str(key)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            key.chmod(0o600)
        subprocess.run(
            ["openssl", "pkey", "-in", str(private_key), "-pubout", "-out", str(public_key)],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        approval_dir = Path(
            subprocess.run(
                ["git", "rev-parse", "--git-path", "loreloom-approvals"],
                cwd=self.repo,
                check=True,
                text=True,
                stdout=subprocess.PIPE,
            ).stdout.strip()
        )
        if not approval_dir.is_absolute():
            approval_dir = self.repo / approval_dir
        approval_dir.mkdir(parents=True)
        trusted = approval_dir / "approval-public-key.pem"
        digest = approval_dir / "approval-public-key.sha256"
        trusted.write_bytes(public_key.read_bytes())
        digest.write_text(hashlib.sha256(trusted.read_bytes()).hexdigest() + "\n", encoding="utf-8")
        trusted.chmod(0o600)
        digest.chmod(0o600)

        private_key_link = key_root / "owner-private-link.pem"
        private_key_link.symlink_to(private_key)

        cases = (
            (private_key, "PASS"),
            (other_key, "FAIL"),
            (private_key_link, "FAIL"),
        )
        for candidate, expected in cases:
            with self.subTest(candidate=candidate.name), mock.patch.dict(
                os.environ, {"LORELOOM_APPROVAL_PRIVATE_KEY": str(candidate)}, clear=False
            ):
                checks = self.by_name(doctor_vault.advanced_checks(self.repo))
            self.assertEqual(checks["approval-private-key"].status, expected)
            rendered = "\n".join(check.detail for check in checks.values())
            self.assertNotIn(str(candidate), rendered)
            self.assertNotIn(candidate.read_text(encoding="utf-8")[:30], rendered)

        with mock.patch.dict(
            os.environ,
            {"LORELOOM_APPROVAL_PRIVATE_KEY": ""},
            clear=False,
        ):
            checks = self.by_name(doctor_vault.advanced_checks(self.repo))
        self.assertEqual(checks["approval-private-key"].status, "FAIL")

        trusted.chmod(0o644)
        with mock.patch.dict(
            os.environ,
            {"LORELOOM_APPROVAL_PRIVATE_KEY": str(private_key)},
            clear=False,
        ):
            checks = self.by_name(doctor_vault.advanced_checks(self.repo))
        self.assertEqual(checks["approval-public-key"].status, "FAIL")
        trusted.chmod(0o600)

        trusted.unlink()
        with mock.patch.dict(
            os.environ,
            {"LORELOOM_APPROVAL_PRIVATE_KEY": str(private_key)},
            clear=False,
        ):
            checks = self.by_name(doctor_vault.advanced_checks(self.repo))
        self.assertEqual(checks["approval-public-key"].status, "FAIL")
        trusted.write_bytes(public_key.read_bytes())
        trusted.chmod(0o600)

        trusted.unlink()
        trusted.symlink_to(public_key)
        with mock.patch.dict(
            os.environ,
            {"LORELOOM_APPROVAL_PRIVATE_KEY": str(private_key)},
            clear=False,
        ):
            checks = self.by_name(doctor_vault.advanced_checks(self.repo))
        self.assertEqual(checks["approval-public-key"].status, "FAIL")
        trusted.unlink()
        trusted.write_bytes(public_key.read_bytes())
        trusted.chmod(0o600)

        trusted.write_text("malformed public key", encoding="utf-8")
        trusted.chmod(0o600)
        digest.write_text(
            hashlib.sha256(trusted.read_bytes()).hexdigest() + "\n",
            encoding="utf-8",
        )
        with mock.patch.dict(
            os.environ,
            {"LORELOOM_APPROVAL_PRIVATE_KEY": str(private_key)},
            clear=False,
        ):
            checks = self.by_name(doctor_vault.advanced_checks(self.repo))
        self.assertEqual(checks["approval-public-key"].status, "FAIL")

        trusted.write_bytes(public_key.read_bytes())
        trusted.chmod(0o600)
        digest.write_text(
            hashlib.sha256(trusted.read_bytes()).hexdigest() + "\n",
            encoding="utf-8",
        )

        private_key.write_text("malformed", encoding="utf-8")
        private_key.chmod(0o600)
        with mock.patch.dict(
            os.environ, {"LORELOOM_APPROVAL_PRIVATE_KEY": str(private_key)}, clear=False
        ):
            checks = self.by_name(doctor_vault.advanced_checks(self.repo))
        self.assertEqual(checks["approval-private-key"].status, "FAIL")

    def test_advanced_native_windows_requires_wsl(self) -> None:
        with mock.patch.object(doctor_vault.os, "name", "nt"):
            checks = doctor_vault.advanced_checks(self.repo)
        self.assertEqual(
            checks,
            [
                doctor_vault.Check(
                    "FAIL",
                    "advanced-platform",
                    "guarded changes require POSIX descriptor and permission semantics; use Linux, macOS, or WSL",
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
