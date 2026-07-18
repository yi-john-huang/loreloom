from __future__ import annotations

import re
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timedelta, timezone


VALIDATOR = Path(__file__).resolve().parents[1] / "scripts" / "validate_change.py"


class ChangeValidatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "vault"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(VALIDATOR, self.repo / "scripts" / "validate_change.py")
        self.write(".gitignore", "Private/\n")
        self.write("seed.txt", "seed\n")
        self.git("init", "-b", "master")
        self.git("config", "user.name", "Loreloom Tests")
        self.git("config", "user.email", "tests@example.invalid")
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.snapshot = self.root / "snapshot.json"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", *args],
            cwd=self.repo,
            check=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    def write(self, path: str, text: str) -> None:
        destination = self.repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")

    def run_validator(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "scripts/validate_change.py", *args],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def preflight(self, *paths: str) -> subprocess.CompletedProcess[str]:
        arguments = [
            "--check-clean",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
        ]
        for path in paths:
            arguments.extend(("--allow", path))
        return self.run_validator(*arguments)

    def final(
        self, *paths: str, extra: tuple[str, ...] = ()
    ) -> subprocess.CompletedProcess[str]:
        arguments = [
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
        ]
        for path in paths:
            arguments.extend(("--allow", path))
        arguments.extend(extra)
        return self.run_validator(*arguments)

    def approved_digest(
        self, path: str, gate: str
    ) -> tuple[str, subprocess.CompletedProcess[str]]:
        result = self.final(
            path,
            extra=("--print-diff-sha256", gate, path),
        )
        match = re.search(r"Diff SHA-256: ([0-9a-f]{64})", result.stdout)
        self.assertIsNotNone(match, result.stdout)
        return match.group(1), result  # type: ignore[union-attr]

    def create_receipt(
        self,
        path: str,
        operation: str,
        digest: str,
        receipt_id: str = "test",
    ) -> None:
        snapshot = json.loads(self.snapshot.read_text(encoding="utf-8"))
        operations = {
            "destructive": [],
            "promotion": [],
            "reviewed_change": [],
            "archive": [],
            "human_block": [],
            "source_create": [],
            "source_amendment": [],
            "framework_change": [],
        }
        operations[operation] = [path]
        receipt = {
            "version": 1,
            "approval_id": receipt_id,
            "base_commit": self.base,
            "snapshot_sha256": snapshot["snapshot_sha256"],
            "allowed_paths": [path],
            "operations": operations,
            "approved_diff_sha256": digest,
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(minutes=10)
            ).isoformat(),
        }
        receipt_path = self.repo / ".git" / "loreloom-approvals" / f"{receipt_id}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        receipt_path.chmod(0o600)

    def test_preflight_requires_exact_allow_path(self) -> None:
        result = self.run_validator(
            "--check-clean",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no output paths declared", result.stdout)

    def test_symbolic_and_unknown_bases_are_rejected(self) -> None:
        for base in ("HEAD", "0" * 40):
            result = self.run_validator(
                "--check-clean",
                "--base",
                base,
                "--snapshot-file",
                str(self.snapshot),
                "--allow",
                "Knowledge/new.md",
            )
            self.assertEqual(result.returncode, 2, result.stdout)

    def test_dirty_declared_path_fails_preflight(self) -> None:
        self.write("Knowledge/existing.md", "before\n")
        self.git("add", ".")
        self.git("commit", "-m", "knowledge")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.write("Knowledge/existing.md", "after\n")
        result = self.preflight("Knowledge/existing.md")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("already differ", result.stdout)

    def test_new_evergreen_concept_is_gated(self) -> None:
        path = "Knowledge/evergreen.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            "---\ntype: concept\nstatus: evergreen\nreviewed: null\n---\n\n# Claim\n",
        )
        result = self.final(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evergreen promotion", result.stdout)

    def test_new_reviewed_wiki_is_gated(self) -> None:
        path = "Wiki/reviewed.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            "---\ntype: wiki\nreview_status: reviewed\n---\n\n# Synthesis\n",
        )
        result = self.final(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Wiki reviewed transition", result.stdout)

    def test_existing_evergreen_rewrite_is_gated(self) -> None:
        path = "Knowledge/reviewed.md"
        self.write(
            path,
            "---\ntype: concept\nstatus: evergreen\nreviewed: 2026-01-01\n---\n\nOld\n",
        )
        self.git("add", ".")
        self.git("commit", "-m", "reviewed concept")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            "---\ntype: concept\nstatus: evergreen\nreviewed: 2026-01-01\n---\n\nNew\n",
        )
        result = self.final(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("evergreen Concept content", result.stdout)

    def test_archive_transition_is_gated(self) -> None:
        path = "Knowledge/draft.md"
        self.write(path, "---\ntype: concept\nstatus: draft\n---\n\nDraft\n")
        self.git("add", ".")
        self.git("commit", "-m", "draft")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: concept\nstatus: archived\n---\n\nDraft\n")
        result = self.final(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("archive transition", result.stdout)

    def test_source_append_only_can_be_digest_approved(self) -> None:
        path = "Sources/source.md"
        self.write(path, "---\ntype: source\n---\n\nOriginal\n")
        self.git("add", ".")
        self.git("commit", "-m", "source")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: source\n---\n\nOriginal\n\n## Amendment\nNew\n")
        digest, first = self.approved_digest(path, "--allow-source-amendment")
        self.assertNotEqual(first.returncode, 0)
        self.create_receipt(path, "source_amendment", digest)
        result = self.final(
            path,
            extra=(
                "--allow-source-amendment",
                path,
                "--approval-receipt",
                "test",
            ),
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_source_rewrite_fails_even_with_digest_approval(self) -> None:
        path = "Sources/source.md"
        self.write(path, "---\ntype: source\n---\n\nOriginal\n")
        self.git("add", ".")
        self.git("commit", "-m", "source")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: source\n---\n\nRewritten\n")
        digest, _ = self.approved_digest(path, "--allow-source-amendment")
        self.create_receipt(path, "source_amendment", digest)
        result = self.final(
            path,
            extra=(
                "--allow-source-amendment",
                path,
                "--approval-receipt",
                "test",
            ),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must append without rewriting", result.stdout)

    def test_digest_mismatch_rejects_exact_override(self) -> None:
        path = "Sources/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: source\n---\n\nCaptured\n")
        self.create_receipt(path, "source_create", "0" * 64)
        result = self.final(
            path,
            extra=(
                "--allow-source-create",
                path,
                "--approval-receipt",
                "test",
            ),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("approved_diff_sha256 does not match", result.stdout)

    def test_non_wiki_marker_literals_do_not_trigger_human_block_gate(self) -> None:
        path = "Knowledge/markers.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            "---\ntype: concept\nstatus: draft\nreviewed: null\n---\n\n"
            "The literals <!-- human:start --> and <!-- human:end --> are documented.\n",
        )
        result = self.final(path)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_symlink_change_is_rejected(self) -> None:
        path = "Knowledge/link.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        (self.repo / "Knowledge").mkdir(parents=True, exist_ok=True)
        (self.repo / path).symlink_to(self.repo / "seed.txt")
        result = self.final(path)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("symlink changes are not accepted", result.stdout)

    def test_ignored_path_write_is_visible_to_snapshot_scope(self) -> None:
        allowed = "Knowledge/allowed.md"
        self.assertEqual(self.preflight(allowed).returncode, 0)
        self.write(allowed, "---\ntype: concept\nstatus: draft\n---\n")
        self.write("Private/secret.md", "unexpected\n")
        result = self.final(allowed)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Private/secret.md: outside the declared output scope", result.stdout)

    def test_final_allow_set_must_match_snapshot(self) -> None:
        path = "Knowledge/one.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        result = self.final(path, "Knowledge/two.md")
        self.assertEqual(result.returncode, 2)
        self.assertIn("exactly match", result.stdout)


if __name__ == "__main__":
    unittest.main()
