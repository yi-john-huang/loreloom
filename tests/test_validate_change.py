from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

from scripts import validate_change


CREATE_RECEIPT = (
    Path(__file__).resolve().parents[1] / "scripts" / "create_approval_receipt.py"
)
VALIDATOR = Path(__file__).resolve().parents[1] / "scripts" / "validate_change.py"


class ChangeValidatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        super().setUpClass()
        cls.key_temporary = tempfile.TemporaryDirectory()
        key_root = Path(cls.key_temporary.name)
        cls.private_key = key_root / "approval-private.pem"
        cls.public_key = key_root / "approval-public.pem"
        subprocess.run(
            [
                "openssl",
                "genpkey",
                "-algorithm",
                "RSA",
                "-pkeyopt",
                "rsa_keygen_bits:2048",
                "-out",
                str(cls.private_key),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        subprocess.run(
            [
                "openssl",
                "pkey",
                "-in",
                str(cls.private_key),
                "-pubout",
                "-out",
                str(cls.public_key),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls.key_temporary.cleanup()
        super().tearDownClass()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.repo = self.root / "vault"
        (self.repo / "scripts").mkdir(parents=True)
        shutil.copy2(VALIDATOR, self.repo / "scripts" / "validate_change.py")
        shutil.copy2(
            CREATE_RECEIPT, self.repo / "scripts" / "create_approval_receipt.py"
        )
        (self.repo / "schemas").mkdir(parents=True)
        shutil.copy2(
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "frontmatter.schema.json",
            self.repo / "schemas" / "frontmatter.schema.json",
        )
        self.write(".gitignore", "Private/\nvenv/\n")
        self.write("seed.txt", "seed\n")
        self.git("init", "-b", "master")
        approval_dir = Path(
            self.git("rev-parse", "--git-path", "loreloom-approvals").stdout.strip()
        )
        if not approval_dir.is_absolute():
            approval_dir = self.repo / approval_dir
        self.approval_dir = approval_dir
        approval_dir.mkdir(parents=True, exist_ok=True)
        self.approval_public_key_path = approval_dir / "approval-public-key.pem"
        self.approval_digest_path = approval_dir / "approval-public-key.sha256"
        self.approval_public_key_path.write_bytes(self.public_key.read_bytes())
        self.approval_digest_path.write_text(
            hashlib.sha256(self.public_key.read_bytes()).hexdigest() + "\n",
            encoding="utf-8",
        )
        self.approval_public_key_path.chmod(0o600)
        self.approval_digest_path.chmod(0o600)
        self.git("config", "user.name", "Loreloom Tests")
        self.git("config", "user.email", "tests@example.invalid")
        global_excludes = self.root / "empty-global-excludes"
        global_excludes.write_text("", encoding="utf-8")
        self.git("config", "core.excludesFile", str(global_excludes))
        self.git("add", ".")
        self.git("commit", "-m", "fixture")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.snapshot = self.root / "snapshot.json"
        self.trusted = self.root / "trusted"
        self.trusted_base: str | None = None

    def tearDown(self) -> None:
        if self.trusted_base is not None:
            self.git("worktree", "remove", "--force", str(self.trusted))
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
    def write_bytes(self, path: str, content: bytes) -> None:
        destination = self.repo / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(content)

    def valid_source(
        self,
        title: str,
        *,
        reviewed: bool = False,
        source_url: str = "https://example.com/report",
        assets: str = "[]",
        capture_method: str = "url-reference",
        capture_mode: str = "reference-only",
        inbox_source: str = "null",
        body: str = "",
    ) -> str:
        status = "captured" if reviewed else "processing"
        review_status = "reviewed" if reviewed else "needs-review"
        reviewed_date = "2026-07-19" if reviewed else "null"
        return f"""---
type: source
title: {title}
status: {status}
created: 2026-07-18
updated: 2026-07-19
tags: []
aliases: []
source_type: other
capture_method: {capture_method}
capture_mode: {capture_mode}
source_url: "{source_url}"
inbox_source: {inbox_source}
author: ""
published: null
captured: 2026-07-18
review_status: {review_status}
reviewed: {reviewed_date}
assets: {assets}
---

# {title}

{body}"""


    def trusted_tool_root(self) -> Path:
        current_head = self.git("rev-parse", "HEAD").stdout.strip()
        if self.trusted_base == current_head:
            return self.trusted
        if self.trusted_base is not None:
            self.git("worktree", "remove", "--force", str(self.trusted))
        self.git("worktree", "add", "--detach", str(self.trusted), current_head)
        self.trusted_base = current_head
        return self.trusted

    def run_validator(self, *args: str) -> subprocess.CompletedProcess[str]:
        trusted_root = self.trusted_tool_root()
        return subprocess.run(
            [
                sys.executable,
                "-I",
                str(trusted_root / "scripts" / "validate_change.py"),
                "--target-root",
                str(self.repo),
                *args,
            ],
            cwd=trusted_root,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def run_local_validator(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-I", "scripts/validate_change.py", *args],
            cwd=self.repo,
            check=False,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def run_receipt_helper(
        self, *args: str
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["LORELOOM_APPROVAL_PRIVATE_KEY"] = str(self.private_key)
        trusted_root = self.trusted_tool_root()
        return subprocess.run(
            [
                sys.executable,
                "-I",
                str(trusted_root / "scripts" / "create_approval_receipt.py"),
                "--target-root",
                str(self.repo),
                *args,
            ],
            cwd=trusted_root,
            check=False,
            text=True,
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

    def run_local_receipt_helper(
        self, *args: str
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        environment["LORELOOM_APPROVAL_PRIVATE_KEY"] = str(self.private_key)
        return subprocess.run(
            [sys.executable, "-I", "scripts/create_approval_receipt.py", *args],
            cwd=self.repo,
            check=False,
            text=True,
            env=environment,
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
            "source_review": [],
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
        signing_fields = (
            "version",
            "approval_id",
            "base_commit",
            "snapshot_sha256",
            "allowed_paths",
            "operations",
            "approved_diff_sha256",
            "expires_at",
        )
        signing_bytes = json.dumps(
            {field: receipt[field] for field in signing_fields},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        signature = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-sign",
                str(self.private_key),
            ],
            input=signing_bytes,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
        receipt["signature"] = base64.b64encode(signature).decode("ascii")
        receipt_path = self.approval_dir / f"{receipt_id}.json"
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        receipt_path.chmod(0o600)

    def test_absent_declared_output_passes_preflight(self) -> None:
        result = self.preflight("Knowledge/new.md")

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_duplicate_allow_is_rejected(self) -> None:
        result = self.run_validator(
            "--check-clean",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            "Knowledge/new.md",
            "--allow",
            "Knowledge/new.md",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("each exact --allow path once", result.stdout)

    def test_ignored_file_symlink_fails_preflight(self) -> None:
        external = self.root / "outside"
        external.write_text("outside\n", encoding="utf-8")
        private = self.repo / "Private"
        private.mkdir()
        (private / "link").symlink_to(external)

        result = self.preflight("Knowledge/new.md")

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn(
            "Private/link: repository symlinks are not allowed",
            result.stdout,
        )
        self.assertFalse(self.snapshot.exists())

    def test_directory_replacement_cannot_redirect_manifest_walk(self) -> None:
        guarded = self.repo / "guarded"
        guarded.mkdir()
        (guarded / "inside").write_text("inside\n", encoding="utf-8")
        moved = self.repo / "guarded-original"
        external = self.root / "outside-directory"
        external.mkdir()
        (external / "outside").write_text("outside\n", encoding="utf-8")
        real_scandir = os.scandir
        swapped = False

        def root_scan(value: object) -> bool:
            if value == self.repo:
                return True
            if isinstance(value, int):
                try:
                    opened = os.fstat(value)
                    root_metadata = self.repo.stat()
                    return (opened.st_dev, opened.st_ino) == (
                        root_metadata.st_dev,
                        root_metadata.st_ino,
                    )
                except OSError:
                    return False

        class EntryProxy:
            def __init__(self, entry: os.DirEntry[str]) -> None:
                self.entry = entry
                self.name = entry.name

            def stat(self, *, follow_symlinks: bool = True) -> os.stat_result:
                nonlocal swapped
                metadata = self.entry.stat(follow_symlinks=follow_symlinks)
                if self.name == "guarded" and not swapped:
                    guarded.rename(moved)
                    guarded.symlink_to(external, target_is_directory=True)
                    swapped = True
                return metadata

        class ScandirProxy:
            def __init__(self, value: object) -> None:
                self.scan = real_scandir(value)  # type: ignore[arg-type]

            def __enter__(self):
                entries = self.scan.__enter__()
                return iter(EntryProxy(entry) for entry in entries)

            def __exit__(self, *args: object) -> None:
                self.scan.__exit__(*args)

        def swapping_scandir(value: object):
            return ScandirProxy(value) if root_scan(value) else real_scandir(value)  # type: ignore[arg-type]

        with (
            mock.patch.object(validate_change, "ROOT", self.repo),
            mock.patch.object(os, "scandir", side_effect=swapping_scandir),
        ):
            with self.assertRaisesRegex(
                validate_change.ManifestError,
                "guarded: repository symlinks are not allowed",
            ):
                validate_change.filesystem_manifest()

    def test_directory_entry_created_during_walk_fails_closed(self) -> None:
        guarded = self.repo / "guarded"
        guarded.mkdir()
        (guarded / "inside").write_text("inside\n", encoding="utf-8")
        real_scandir = os.scandir
        mutated = False

        def guarded_scan(value: object) -> bool:
            if isinstance(value, int):
                try:
                    opened = os.fstat(value)
                    guarded_metadata = guarded.stat()
                    return (opened.st_dev, opened.st_ino) == (
                        guarded_metadata.st_dev,
                        guarded_metadata.st_ino,
                    )
                except OSError:
                    return False
            return value == guarded

        class MutatingIterator:
            def __init__(self, entries: object) -> None:
                self.entries = iter(entries)  # type: ignore[arg-type]

            def __iter__(self):
                return self

            def __next__(self):
                nonlocal mutated
                try:
                    return next(self.entries)
                except StopIteration:
                    if not mutated:
                        (guarded / "late").write_text("late\n", encoding="utf-8")
                        mutated = True
                    raise

        class ScandirProxy:
            def __init__(self, value: object) -> None:
                self.scan = real_scandir(value)  # type: ignore[arg-type]

            def __enter__(self):
                return MutatingIterator(self.scan.__enter__())

            def __exit__(self, *args: object) -> None:
                self.scan.__exit__(*args)

        def mutating_scandir(value: object):
            return ScandirProxy(value) if guarded_scan(value) else real_scandir(value)  # type: ignore[arg-type]

        with (
            mock.patch.object(validate_change, "ROOT", self.repo),
            mock.patch.object(os, "scandir", side_effect=mutating_scandir),
        ):
            with self.assertRaisesRegex(
                validate_change.ManifestError,
                "guarded: repository directory changed while traversing",
            ):
                validate_change.filesystem_manifest()



    def test_manifest_bound_text_rejects_swap_and_restore(self) -> None:
        path = "Knowledge/concept.md"
        original = "---\ntype: concept\nstatus: evergreen\n---\n\n# Invalid final bytes\n"
        transient = "---\ntype: concept\nstatus: draft\n---\n\n# Valid transient bytes\n"
        self.write(path, original)

        with mock.patch.object(validate_change, "ROOT", self.repo):
            before = validate_change.filesystem_manifest()
            self.write(path, transient)
            with self.assertRaisesRegex(
                validate_change.ManifestError,
                "bytes do not match the captured manifest",
            ):
                validate_change.manifest_bound_text(path, before[path])
            self.write(path, original)
            after = validate_change.filesystem_manifest()

        self.assertEqual(after, before)

    def test_semantic_evidence_capture_rejects_unrelated_addition(self) -> None:
        evidence_path = "Assets/venv/report.pdf"
        self.write_bytes(evidence_path, b"evidence")
        self.git("add", "-f", evidence_path)
        self.git("commit", "-m", "owner evidence")
        base = self.git("rev-parse", "HEAD").stdout.strip()

        with mock.patch.object(validate_change, "ROOT", self.repo):
            before = validate_change.filesystem_manifest()
            self.write("unrelated.txt", "undeclared\n")
            with self.assertRaisesRegex(
                validate_change.ManifestError,
                "repository changed during semantic evidence capture",
            ):
                validate_change.capture_semantic_evidence(
                    before,
                    {evidence_path},
                    (),
                    base,
                )

    def test_semantic_evidence_cannot_hide_normal_path_restoration(self) -> None:
        evidence_path = "Assets/report.pdf"
        self.write_bytes(evidence_path, b"evidence")
        self.git("add", evidence_path)
        self.git("commit", "-m", "owner evidence")
        base = self.git("rev-parse", "HEAD").stdout.strip()

        with mock.patch.object(validate_change, "ROOT", self.repo):
            transient_after = validate_change.filesystem_manifest()
            transient_after.pop(evidence_path)
            with self.assertRaisesRegex(
                validate_change.ManifestError,
                "repository changed during semantic evidence capture",
            ):
                validate_change.capture_semantic_evidence(
                    transient_after,
                    {evidence_path},
                    (),
                    base,
                )

    def test_unreadable_regular_file_fails_closed(self) -> None:
        candidate = self.repo / "Private" / "unreadable"
        candidate.parent.mkdir()
        candidate.write_text("secret\n", encoding="utf-8")
        candidate.chmod(0)
        try:
            try:
                candidate.open("rb").close()
            except PermissionError:
                pass
            else:
                self.skipTest("platform permissions do not make files unreadable")
            with mock.patch.object(validate_change, "ROOT", self.repo):
                with self.assertRaisesRegex(
                    validate_change.ManifestError,
                    "Private/unreadable: repository file is unreadable",
                ):
                    validate_change.filesystem_manifest()
        finally:
            candidate.chmod(0o600)

    def test_unreadable_repository_directory_fails_closed(self) -> None:
        directory = self.repo / "Private" / "closed"
        directory.mkdir(parents=True)
        (directory / "ignored").write_text("ignored\n", encoding="utf-8")
        directory.chmod(0)
        try:
            try:
                with os.scandir(directory):
                    pass
            except PermissionError:
                pass
            else:
                self.skipTest("platform permissions do not make directories unreadable")
            with mock.patch.object(validate_change, "ROOT", self.repo):
                with self.assertRaisesRegex(
                    validate_change.ManifestError,
                    "Private/closed: repository directory is unreadable",
                ):
                    validate_change.filesystem_manifest()
        finally:
            directory.chmod(0o700)

    def test_manifest_symlink_blocks_receipt_and_final_digest(self) -> None:
        path = "Knowledge/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: concept\nstatus: draft\n---\n")
        external = self.root / "outside"
        external.write_text("outside\n", encoding="utf-8")
        private = self.repo / "Private"
        private.mkdir()
        (private / "link").symlink_to(external)

        final = self.final(path)
        self.assertEqual(final.returncode, 1, final.stdout)
        self.assertNotIn("Diff SHA-256:", final.stdout)

        helper = self.run_receipt_helper(
            "--approval-id",
            "manifest-failure",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            path,
            "--framework-change",
            path,
            "--yes",
        )
        self.assertEqual(helper.returncode, 2, helper.stdout)
        self.assertFalse((self.approval_dir / "manifest-failure.json").exists())

    def test_unstable_regular_file_digest_fails_closed(self) -> None:
        candidate = self.root / "unstable.bin"
        candidate.write_bytes(b"stable bytes")
        initial = candidate.lstat()
        fields = list(initial)
        fields[6] += 1
        changed = os.stat_result(fields)

        with mock.patch.object(Path, "lstat", side_effect=(initial, changed)):
            with self.assertRaisesRegex(
                validate_change.ManifestError,
                "repository file changed while hashing",
            ):
                validate_change.regular_file_digest(candidate)

    def test_canonical_modes_preserve_leading_zero_and_special_bits(self) -> None:
        self.assertEqual(validate_change.canonical_mode(0o100044), "0o0044")
        self.assertEqual(validate_change.canonical_mode(0o104755), "0o4755")

    def test_malformed_snapshot_shapes_are_rejected(self) -> None:
        valid_file = {
            "kind": "file",
            "mode": "0o0644",
            "sha256": "a" * 64,
        }
        invalid_payloads = (
            {
                "version": 1,
                "base_commit": "a" * 40,
                "allowed_paths": ["Knowledge/a.md"],
                "files": {},
                "extra": True,
            },
            {
                "version": 1,
                "base_commit": "a" * 40,
                "allowed_paths": ["Knowledge/b.md", "Knowledge/a.md"],
                "files": {},
            },
            {
                "version": 1,
                "base_commit": "a" * 40,
                "allowed_paths": ["Knowledge/a.md", "Knowledge/a.md"],
                "files": {},
            },
            {
                "version": 1,
                "base_commit": "a" * 40,
                "allowed_paths": ["../outside"],
                "files": {},
            },
            {
                "version": 1,
                "base_commit": "a" * 40,
                "allowed_paths": ["Knowledge/a.md"],
                "files": {"../outside": valid_file},
            },
            {
                "version": 1,
                "base_commit": "a" * 40,
                "allowed_paths": ["Knowledge/a.md"],
                "files": {
                    "seed.txt": {
                        **valid_file,
                        "extra": True,
                    }
                },
            },
            {
                "version": 1,
                "base_commit": "a" * 40,
                "allowed_paths": ["Knowledge/a.md"],
                "files": {
                    "seed.txt": {
                        **valid_file,
                        "mode": "0o644",
                    }
                },
            },
        )
        for index, payload in enumerate(invalid_payloads):
            with self.subTest(index=index):
                path = self.root / f"invalid-{index}.json"
                serialized = dict(payload)
                serialized["snapshot_sha256"] = validate_change.snapshot_hash(payload)
                path.write_text(json.dumps(serialized), encoding="utf-8")
                self.assertIsNone(validate_change.load_snapshot(path))

    def test_ungated_final_rejects_candidate_tool_root(self) -> None:
        path = "Knowledge/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: concept\nstatus: draft\n---\n")

        result = self.run_local_validator(
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            path,
        )

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("separate clean detached Git worktree", result.stdout)

    def test_complete_processing_source_passes_exact_admission(self) -> None:
        path = "Sources/report.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, self.valid_source("report"))

        result = self.final(path)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_source_contract_rejects_malformed_authorities(self) -> None:
        for url in ("https://example.com:", "https://user@@example.com"):
            with self.subTest(url=url):
                metadata, parse_error = validate_change.parse_frontmatter(
                    self.valid_source("report", source_url=url)
                )
                self.assertIsNone(parse_error)
                assert metadata is not None

                errors = validate_change.source_contract_errors(
                    "Sources/report.md",
                    metadata,
                    self.valid_source("report", source_url=url),
                )

                self.assertFalse(validate_change.valid_source_url(url))
                self.assertTrue(any("source_url" in error for error in errors), errors)
                self.assertTrue(
                    any("traceable non-empty URL" in error for error in errors),
                    errors,
                )

    def test_source_contract_allows_high_numeric_port(self) -> None:
        url = "https://example.com:99999/report"
        metadata, parse_error = validate_change.parse_frontmatter(
            self.valid_source("report", source_url=url)
        )
        self.assertIsNone(parse_error)
        assert metadata is not None

        errors = validate_change.source_contract_errors(
            "Sources/report.md",
            metadata,
            self.valid_source("report", source_url=url),
        )

        self.assertTrue(validate_change.valid_source_url(url))
        self.assertEqual(errors, [])

    def test_non_markdown_source_is_rejected(self) -> None:
        path = "Sources/report.txt"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, self.valid_source("report"))

        result = self.final(path)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Source intake must use a Markdown file", result.stdout)

    def test_incomplete_processing_source_is_rejected(self) -> None:
        path = "Sources/report.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            self.valid_source("report")
            .replace("capture_method: url-reference\n", "")
            .replace("capture_mode: reference-only\n", ""),
        )

        result = self.final(path)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("capture_method, capture_mode", result.stdout)
        self.assertIn("no value was inferred", result.stdout)

    def test_invalid_processing_source_state_is_rejected(self) -> None:
        path = "Sources/report.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            self.valid_source("report").replace(
                "review_status: needs-review\nreviewed: null",
                "review_status: reviewed\nreviewed: null",
            ),
        )

        result = self.final(path)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Source review state is inconsistent", result.stdout)

    def test_reviewed_source_creation_requires_source_create(self) -> None:
        path = "Sources/report.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, self.valid_source("report", reviewed=True))

        result = self.final(path)

        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("Source creation needs exact approval", result.stdout)

    def test_processing_source_review_requires_matching_signed_operation(self) -> None:
        path = "Sources/report.md"
        self.write(path, self.valid_source("report", body="Initial draft\n"))
        self.git("add", ".")
        self.git("commit", "-m", "processing source")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            self.valid_source(
                "report",
                reviewed=True,
                body="Owner-verified summary\n",
            ),
        )

        without_gate = self.final(path)
        self.assertEqual(without_gate.returncode, 1, without_gate.stdout)

        helper = self.run_receipt_helper(
            "--approval-id",
            "source-review",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            path,
            "--allow-source-review",
            path,
            "--yes",
        )
        self.assertEqual(helper.returncode, 0, helper.stdout)
        result = self.final(
            path,
            extra=(
                "--allow-source-review",
                path,
                "--approval-receipt",
                "source-review",
            ),
        )

        self.assertEqual(result.returncode, 0, result.stdout)
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

    def test_filesystem_manifest_rejects_unsafe_extra_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsafe repository output path"):
            validate_change.filesystem_manifest(["../outside"])

    def test_filesystem_entry_hashes_without_reading_entire_file(self) -> None:
        path = self.root / "large.bin"
        content = b"content" * 200_000
        path.write_bytes(content)

        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError):
            entry = validate_change.filesystem_entry(path)

        self.assertEqual(entry["sha256"], hashlib.sha256(content).hexdigest())

    def test_approval_key_cannot_reside_in_tool_repository(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "outside the repository"):
            validate_change._external_key_path(VALIDATOR)

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

    def test_non_head_base_is_rejected(self) -> None:
        old_base = self.base
        self.write("seed.txt", "new commit\n")
        self.git("add", "seed.txt")
        self.git("commit", "-m", "advance head")
        result = self.run_validator(
            "--check-clean",
            "--base",
            old_base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            "Knowledge/new.md",
        )
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("base must equal the current HEAD", result.stdout)

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
        source = self.valid_source("source", body="Original\n")
        self.write(path, source)
        self.git("add", ".")
        self.git("commit", "-m", "source")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, source + "\n## Amendment\nNew\n")
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

    def test_receipt_helper_creates_signed_receipt(self) -> None:
        path = "Sources/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, self.valid_source("new", body="Captured\n"))
        helper = self.run_receipt_helper(
            "--approval-id",
            "helper-test",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            path,
            "--allow-source-create",
            path,
            "--yes",
        )
        self.assertEqual(helper.returncode, 0, helper.stdout)
        result = self.final(
            path,
            extra=(
                "--allow-source-create",
                path,
                "--approval-receipt",
                "helper-test",
            ),
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_receipt_helper_keeps_trusted_worktree_clean(self) -> None:
        path = "Sources/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, self.valid_source("new", body="Captured\n"))

        helper = self.run_receipt_helper(
            "--approval-id",
            "clean-helper-test",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            path,
            "--allow-source-create",
            path,
            "--yes",
        )

        self.assertEqual(helper.returncode, 0, helper.stdout)
        status = self.git(
            "-C",
            str(self.trusted_tool_root()),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        )
        self.assertEqual(status.stdout, "")

    def test_receipt_helper_hashes_explicit_runtime_output(self) -> None:
        source_path = "Sources/new.md"
        runtime_path = ".DS_Store"
        self.assertEqual(self.preflight(source_path, runtime_path).returncode, 0)
        self.write(source_path, self.valid_source("new", body="Captured\n"))
        self.write_bytes(runtime_path, b"runtime")

        helper = self.run_receipt_helper(
            "--approval-id",
            "runtime-test",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            source_path,
            "--allow",
            runtime_path,
            "--allow-source-create",
            source_path,
            "--yes",
        )

        self.assertEqual(helper.returncode, 0, helper.stdout)
        result = self.final(
            source_path,
            runtime_path,
            extra=(
                "--allow-source-create",
                source_path,
                "--approval-receipt",
                "runtime-test",
            ),
        )
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_receipt_helper_rejects_candidate_tool_root(self) -> None:
        path = "Sources/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            "---\n"
            "type: source\n"
            "status: processing\n"
            "source_url: https://example.invalid/new\n"
            "review_status: needs-review\n"
            "reviewed: null\n"
            "---\n\n"
            "Captured\n",
        )

        result = self.run_local_receipt_helper(
            "--approval-id",
            "untrusted-test",
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            path,
            "--allow-source-create",
            path,
            "--yes",
        )

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("separate clean detached Git worktree", result.stdout)
        self.assertFalse((self.approval_dir / "untrusted-test.json").exists())

    def test_gated_validation_rejects_candidate_tool_root(self) -> None:
        path = "Sources/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            "---\n"
            "type: source\n"
            "status: processing\n"
            "source_url: https://example.invalid/new\n"
            "review_status: needs-review\n"
            "reviewed: null\n"
            "---\n\n"
            "Captured\n",
        )

        result = self.run_local_validator(
            "--base",
            self.base,
            "--snapshot-file",
            str(self.snapshot),
            "--allow",
            path,
            "--allow-source-create",
            path,
        )

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("separate clean detached Git worktree", result.stdout)

    def test_gated_validation_rejects_untracked_tool_module(self) -> None:
        path = "Sources/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            "---\n"
            "type: source\n"
            "status: processing\n"
            "source_url: https://example.invalid/new\n"
            "review_status: needs-review\n"
            "reviewed: null\n"
            "---\n\n"
            "Captured\n",
        )
        malicious_module = self.trusted_tool_root() / "scripts" / "yaml.py"
        malicious_module.write_text('raise RuntimeError("untrusted module loaded")\n')

        result = self.final(
            path,
            extra=("--allow-source-create", path),
        )

        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("separate clean detached Git worktree", result.stdout)

    def test_approval_tools_require_isolation_before_shadowed_imports(self) -> None:
        trusted_root = self.trusted_tool_root()
        (trusted_root / "scripts" / "json.py").write_text(
            'raise RuntimeError("shadowed module loaded")\n',
            encoding="utf-8",
        )

        for tool_name in ("validate_change.py", "create_approval_receipt.py"):
            with self.subTest(tool_name=tool_name):
                result = subprocess.run(
                    [sys.executable, str(trusted_root / "scripts" / tool_name)],
                    cwd=trusted_root,
                    check=False,
                    text=True,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )

                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("isolated interpreter", result.stdout)
                self.assertNotIn("shadowed module loaded", result.stdout)

    def test_receipt_signature_tampering_is_rejected(self) -> None:
        path = "Sources/source.md"
        self.write(path, "---\ntype: source\n---\n\nOriginal\n")
        self.git("add", ".")
        self.git("commit", "-m", "source")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: source\n---\n\nOriginal\n\n## Amendment\nNew\n")
        digest, _ = self.approved_digest(path, "--allow-source-amendment")
        self.create_receipt(path, "source_amendment", digest)
        receipt_path = self.approval_dir / "test.json"
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["signature"] = base64.b64encode(b"tampered").decode("ascii")
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        receipt_path.chmod(0o600)
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
        self.assertIn("approval receipt signature is invalid", result.stdout)

    def test_receipt_trust_fingerprint_is_checked(self) -> None:
        path = "Sources/source.md"
        self.write(path, "---\ntype: source\n---\n\nOriginal\n")
        self.git("add", ".")
        self.git("commit", "-m", "source")
        self.approval_digest_path.write_text("0" * 64 + "\n", encoding="utf-8")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: source\n---\n\nOriginal\n\n## Amendment\nNew\n")
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
        self.assertIn(
            "approval public key does not match its trusted fingerprint",
            result.stdout,
        )

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
        self.assertIn("unsafe repository output path", result.stdout)

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


    def test_preflight_rejects_preexisting_ignored_output(self) -> None:
        path = "Private/existing.pdf"
        self.write_bytes(path, b"existing")

        result = self.preflight(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("declared output already exists", result.stdout)

    def test_preflight_rejects_git_output_path_case_insensitively(self) -> None:
        for path in (".git/config", ".GIT/config"):
            with self.subTest(path=path):
                result = self.preflight(path)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn("unsafe repository output path", result.stdout)

    def test_preflight_rejects_symlinked_parent(self) -> None:
        external = self.root / "external"
        external.mkdir()
        (self.repo / "Assets").symlink_to(external, target_is_directory=True)

        result = self.preflight("Assets/new.pdf")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsafe repository output path", result.stdout)

    def test_new_unreviewed_source_is_allowed(self) -> None:
        path = "Sources/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, self.valid_source("new"))

        result = self.final(path)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_new_processing_source_requires_traceable_provenance(self) -> None:
        path = "Sources/unprovenanced.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(
            path,
            self.valid_source(
                "unprovenanced",
                source_url="",
                capture_method="manual-entry",
                capture_mode="unknown",
            ),
        )

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("traceable non-empty URL, existing Asset, or Inbox", result.stdout)

    def test_verified_local_asset_allows_new_processing_source(self) -> None:
        asset_path = "Assets/report.pdf"
        source_path = "Sources/report.md"
        content = b"%PDF-1.7\nreport\n"
        self.write_bytes(asset_path, content)
        self.git("add", asset_path)
        self.git("commit", "-m", "owner asset")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(source_path).returncode, 0)
        self.write(
            source_path,
            self.valid_source(
                "report",
                source_url="",
                capture_method="asset",
                capture_mode="preserved-original",
                assets=(
                    "\n  - path: Assets/report.pdf\n"
                    "    media_type: application/pdf\n"
                    "    role: primary\n"
                    f"    sha256: {hashlib.sha256(content).hexdigest()}\n"
                    "    extraction_status: extracted"
                ),
            ),
        )

        result = self.final(source_path)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_excluded_existing_asset_allows_new_processing_source(self) -> None:
        asset_path = "Assets/venv/report.pdf"
        source_path = "Sources/report.md"
        content = b"%PDF-1.7\nruntime-named path\n"
        self.write_bytes(asset_path, content)
        self.git("add", "-f", asset_path)
        self.git("commit", "-m", "owner asset in excluded directory")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(source_path).returncode, 0)
        self.write(
            source_path,
            self.valid_source(
                "report",
                source_url="",
                capture_method="asset",
                capture_mode="preserved-original",
                assets=(
                    "\n  - path: Assets/venv/report.pdf\n"
                    "    media_type: application/pdf\n"
                    "    role: primary\n"
                    f"    sha256: {hashlib.sha256(content).hexdigest()}\n"
                    "    extraction_status: extracted"
                ),
            ),
        )

        result = self.final(source_path)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_mismatched_asset_hash_does_not_satisfy_new_source_provenance(self) -> None:
        asset_path = "Assets/report.pdf"
        source_path = "Sources/report.md"
        self.write_bytes(asset_path, b"%PDF-1.7\nreport\n")
        self.git("add", asset_path)
        self.git("commit", "-m", "owner asset")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(source_path).returncode, 0)
        self.write(
            source_path,
            self.valid_source(
                "report",
                source_url="",
                capture_method="asset",
                capture_mode="preserved-original",
                assets=(
                    "\n  - path: Assets/report.pdf\n"
                    "    media_type: application/pdf\n"
                    "    role: primary\n"
                    "    sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
                    "    extraction_status: extracted"
                ),
            ),
        )

        result = self.final(source_path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("traceable non-empty URL, existing Asset, or Inbox", result.stdout)

    def test_ignored_excluded_asset_cannot_satisfy_new_source(self) -> None:
        asset_path = "Assets/venv/new.pdf"
        source_path = "Sources/report.md"
        content = b"%PDF-1.7\nagent-created ignored asset\n"
        self.assertEqual(self.preflight(source_path).returncode, 0)
        self.write_bytes(asset_path, content)
        self.write(
            source_path,
            self.valid_source(
                "report",
                source_url="",
                capture_method="asset",
                capture_mode="preserved-original",
                assets=(
                    "\n  - path: Assets/venv/new.pdf\n"
                    "    media_type: application/pdf\n"
                    "    role: primary\n"
                    f"    sha256: {hashlib.sha256(content).hexdigest()}\n"
                    "    extraction_status: extracted"
                ),
            ),
        )

        result = self.final(source_path)

        self.assertNotEqual(result.returncode, 0, result.stdout)
        self.assertIn("evidence path is absent from the immutable base", result.stdout)

    def test_existing_inbox_link_allows_new_processing_source(self) -> None:
        inbox_path = "Inbox/capture.md"
        source_path = "Sources/capture.md"
        self.write(inbox_path, "# Capture\n")
        self.git("add", inbox_path)
        self.git("commit", "-m", "owner inbox capture")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(source_path).returncode, 0)
        self.write(
            source_path,
            self.valid_source(
                "capture",
                source_url="",
                inbox_source='"[[Inbox/capture]]"',
                capture_method="manual-entry",
                capture_mode="unknown",
            ),
        )

        result = self.final(source_path)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_malformed_source_frontmatter_is_reported(self) -> None:
        path = "Sources/malformed.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: [\n---\n\n# Malformed\n")

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid YAML frontmatter", result.stdout)

    def test_source_without_frontmatter_is_reported(self) -> None:
        path = "Sources/no-frontmatter.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "# Missing frontmatter\n")

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Source requires YAML frontmatter", result.stdout)

    def test_source_path_requires_source_type(self) -> None:
        path = "Sources/wrong-type.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: concept\n---\n\n# Wrong type\n")

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Sources/ notes must use type 'source'", result.stdout)

    def test_reviewed_source_still_requires_gate(self) -> None:
        path = "Sources/reviewed.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, self.valid_source("reviewed", reviewed=True))

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Source creation needs exact approval", result.stdout)

    def test_new_asset_addition_is_rejected(self) -> None:
        path = "Assets/unpaired.pdf"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write_bytes(path, b"%PDF-1.7\n")

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent Asset additions are not allowed", result.stdout)

    def test_new_asset_and_processing_source_are_rejected_together(self) -> None:
        asset_path = "Assets/paired.pdf"
        source_path = "Sources/paired.md"
        self.assertEqual(self.preflight(asset_path, source_path).returncode, 0)
        self.write_bytes(asset_path, b"%PDF-1.7\n")
        digest = hashlib.sha256(b"%PDF-1.7\n").hexdigest()
        self.write(
            source_path,
            self.valid_source(
                "paired",
                source_url="",
                assets=(
                    "\n  - path: Assets/paired.pdf\n"
                    "    media_type: application/pdf\n"
                    "    role: primary\n"
                    f"    sha256: {digest}\n"
                    "    extraction_status: not-requested"
                ),
            ),
        )

        result = self.final(asset_path, source_path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent Asset additions are not allowed", result.stdout)

    def test_preflight_rejects_existing_excluded_asset(self) -> None:
        path = "Assets/venv/report.pdf"
        self.write_bytes(path, b"existing")

        result = self.preflight(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("declared output already exists", result.stdout)

    def test_final_detects_new_excluded_asset(self) -> None:
        path = "Assets/venv/report.pdf"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write_bytes(path, b"new")

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent Asset additions are not allowed", result.stdout)

    def test_final_rejects_bytes_changed_after_initial_digest(self) -> None:
        path = "Knowledge/new.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "---\ntype: concept\nstatus: draft\n---\n\n# Before\n")
        trusted_root = self.trusted_tool_root()
        process = subprocess.Popen(
            [
                sys.executable,
                "-u",
                "-I",
                str(trusted_root / "scripts" / "validate_change.py"),
                "--target-root",
                str(self.repo),
                "--base",
                self.base,
                "--snapshot-file",
                str(self.snapshot),
                "--allow",
                path,
                "--print-diff-sha256",
            ],
            cwd=trusted_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )
        assert process.stdout is not None
        output: list[str] = []
        changed = False
        for line in process.stdout:
            output.append(line)
            if line.startswith("Diff SHA-256:"):
                self.write(
                    path,
                    "---\ntype: concept\nstatus: draft\n---\n\n# After\n",
                )
                changed = True
        process.stdout.close()
        returncode = process.wait(timeout=30)
        rendered = "".join(output)

        self.assertTrue(changed, rendered)
        self.assertEqual(returncode, 1, rendered)
        self.assertIn("repository changed during final validation", rendered)

    def test_preflight_rejects_undeclared_symlink_directory(self) -> None:
        external = self.root / "external-assets"
        external.mkdir()
        (self.repo / "Assets").symlink_to(external, target_is_directory=True)

        result = self.preflight("Knowledge/new.md")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("repository symlinks are not allowed", result.stdout)

    def test_assets_readme_is_documentation_exception(self) -> None:
        path = "Assets/README.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "# Assets\n")

        result = self.final(path)

        self.assertEqual(result.returncode, 0, result.stdout)

    def test_markdown_asset_addition_is_rejected(self) -> None:
        path = "Assets/evidence.md"
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "# evidence\n")

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("agent Asset additions are not allowed", result.stdout)

    def test_markdown_asset_modification_is_rejected(self) -> None:
        path = "Assets/evidence.md"
        self.write(path, "before\n")
        self.git("add", ".")
        self.git("commit", "-m", "markdown asset")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write(path, "after\n")

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existing Assets are immutable in agent change sets", result.stdout)
    def test_existing_asset_modification_is_rejected(self) -> None:
        path = "Assets/existing.pdf"
        self.write_bytes(path, b"before")
        self.git("add", ".")
        self.git("commit", "-m", "asset")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        self.assertEqual(self.preflight(path).returncode, 0)
        self.write_bytes(path, b"after")

        result = self.final(path)

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("existing Assets are immutable in agent change sets", result.stdout)


class CaptureFidelityContractTests(unittest.TestCase):
    def metadata(self, method: str, mode: str, **overrides: object) -> dict[str, object]:
        metadata: dict[str, object] = {
            "type": "source",
            "title": "report",
            "status": "processing",
            "created": "2026-07-18",
            "updated": "2026-07-18",
            "tags": [],
            "aliases": [],
            "source_type": "other",
            "capture_method": method,
            "capture_mode": mode,
            "source_url": "https://example.com/report",
            "author": "",
            "published": None,
            "captured": "2026-07-18",
            "review_status": "needs-review",
            "reviewed": None,
            "assets": [],
        }
        metadata.update(overrides)
        return metadata

    def boundary(self, **values: str) -> str:
        defaults = {
            "Capture method": "Recorded route.",
            "Capture mode": "Recorded representation.",
            "Original evidence preserved": "None",
            "Verbatim material": "None",
            "Extracted or transcribed material": "None",
            "Paraphrased material": "None",
            "Unknown or unavailable evidence": "None",
        }
        defaults.update(values)
        return "## Capture boundary\n\n" + "\n".join(
            f"- {label}: {defaults[label]}"
            for label in validate_change.CAPTURE_BOUNDARY_LABELS
        )

    def errors(
        self, metadata: dict[str, object], body: str = ""
    ) -> list[str]:
        return validate_change.source_capture_fidelity_errors(
            "Sources/report.md", metadata, body
        )

    def test_valid_method_and_mode_prerequisites(self) -> None:
        primary = {
            "path": "Assets/report.pdf",
            "media_type": "application/pdf",
            "role": "primary",
            "sha256": "a" * 64,
            "extraction_status": "partial",
        }
        audio = {**primary, "media_type": "audio/wav"}
        extracted = self.boundary(
            **{"Extracted or transcribed material": "Tool output from primary Asset."}
        )
        cases = (
            (self.metadata("asset", "preserved-original", assets=[primary]), ""),
            (self.metadata("url-reference", "reference-only"), ""),
            (
                self.metadata("web-clipper", "unknown"),
                "",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "Owner-declared summary."}
                ),
            ),
            (
                self.metadata("file-extraction", "extracted", assets=[primary]),
                extracted,
            ),
            (
                self.metadata("ocr", "extracted", assets=[primary]),
                extracted,
            ),
            (
                self.metadata("transcription", "transcribed", assets=[audio]),
                extracted
                + '\n\n## Key passages\n\n- “Transcript.” — timestamp 00:01:00',
            ),
            (self.metadata("import", "unknown"), ""),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                '## Key passages\n\n- "Exact." — section Abstract',
            ),
            (
                self.metadata(
                    "manual-entry",
                    "firsthand-observation",
                    source_type="personal-observation",
                ),
                "",
            ),
            (
                self.metadata("mixed", "mixed"),
                self.boundary(
                    **{
                        "Original evidence preserved": "Primary representation.",
                        "Unknown or unavailable evidence": "Missing appendix.",
                    }
                ),
            ),
        )
        for metadata, body in cases:
            with self.subTest(
                method=metadata["capture_method"], mode=metadata["capture_mode"]
            ):
                self.assertEqual(self.errors(metadata, body), [])

    def test_invalid_prerequisites_locators_and_boundaries(self) -> None:
        unavailable = {
            "path": "Assets/report.pdf",
            "media_type": "application/pdf",
            "role": "supporting",
            "sha256": "a" * 64,
            "extraction_status": "unavailable",
        }
        cases = (
            (self.metadata("asset", "unknown"), "", "declared Asset"),
            (
                self.metadata("url-reference", "unknown", source_url=""),
                "",
                "valid source_url",
            ),
            (
                self.metadata(
                    "asset",
                    "preserved-original",
                    assets=[unavailable],
                ),
                "",
                "primary Asset",
            ),
            (
                self.metadata("file-extraction", "extracted", assets=[]),
                self.boundary(
                    **{
                        "Extracted or transcribed material": "Parser output was declared."
                    }
                ),
                "extracted or partial Asset",
            ),
            (
                self.metadata("file-extraction", "unknown", assets=[unavailable]),
                "",
                "extracted or partial Asset",
            ),
            (
                self.metadata("ocr", "extracted", assets=[unavailable]),
                self.boundary(
                    **{"Extracted or transcribed material": "OCR output."}
                ),
                "extracted or partial Asset",
            ),
            (
                self.metadata("transcription", "transcribed"),
                self.boundary(
                    **{"Extracted or transcribed material": "Transcript."}
                ),
                "audio/video provenance",
            ),
            (
                self.metadata("manual-entry", "preserved-original"),
                "",
                "primary Asset",
            ),
            (
                self.metadata("manual-entry", "reference-only", source_url=""),
                "",
                "valid source_url",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "```\n## Key passages\n- “Fake.” — line 1\n```",
                "exact Key passages locator",
            ),
            (
                self.metadata(
                    "transcription",
                    "transcribed",
                    source_type="video",
                ),
                self.boundary(
                    **{"Extracted or transcribed material": "Transcript."}
                )
                + '\n\n## Key passages\n\n- “Quoted.” — frame 9',
                "timestamp locator",
            ),
            (
                self.metadata("manual-entry", "firsthand-observation"),
                "",
                "personal-observation",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "Summary."}
                )
                + '\n\n## Key passages\n\n- “Not permitted.” — page 2',
                "must not use quoted Key passages",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "## Capture boundary\n\n"
                "- Paraphrased material: Owner-declared summary.",
                "requires all exact Capture Boundary labels",
            ),
            (
                self.metadata("mixed", "mixed"),
                self.boundary(
                    **{"Verbatim material": "One concrete entry."}
                ),
                "at least two concrete Capture Boundary entries",
            ),
        )
        for metadata, body, expected in cases:
            with self.subTest(
                method=metadata["capture_method"], mode=metadata["capture_mode"]
            ):
                errors = self.errors(metadata, body)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_hidden_sections_and_placeholder_locators_fail_closed(self) -> None:
        cases = (
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "---\nnotes: |\n  ## Key passages\n  - “Fake.” — page 1\n---\n",
                "exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "    ## Key passages\n\n    - “Fake.” — page 1",
                "exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n    - “Fake.” — page 1",
                "exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<!--\n## Key passages\n- “Fake.” — page 1\n-->",
                "exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n- “Fake.” fake-page 1",
                "exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n- “Fake.” — page <page>",
                "exact Key passages locator",
            ),
            (
                self.metadata(
                    "transcription",
                    "transcribed",
                    source_type="video",
                ),
                self.boundary(
                    **{"Extracted or transcribed material": "Typed transcript."}
                )
                + "\n\n## Key passages\n\n"
                '- “Fake.” — timestamp {{timestamp}}',
                "timestamp locator",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary().replace(
                    "- Paraphrased material: None",
                    "- Paraphrased material: <!--\n"
                    "  add a substantive explanation\n"
                    "  -->",
                ),
                "non-empty Paraphrased material",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "Owner-declared summary."}
                ).replace("\n-", "\n    -"),
                "requires all exact Capture Boundary labels",
            ),
        )
        for metadata, body, expected in cases:
            with self.subTest(body=body):
                errors = self.errors(metadata, body)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_missing_fields_and_invalid_enums_fail_contract(self) -> None:
        metadata = self.metadata("manual-entry", "unknown")
        del metadata["capture_method"]
        del metadata["capture_mode"]
        errors = validate_change.source_contract_errors(
            "Sources/report.md", metadata, "# report\n"
        )
        self.assertTrue(any("capture_method, capture_mode" in error for error in errors))
        self.assertTrue(any("no value was inferred" in error for error in errors))

        for field, value in (
            ("capture_method", "invented"),
            ("capture_mode", "synthetic"),
        ):
            invalid = self.metadata("manual-entry", "unknown")
            invalid[field] = value
            errors = validate_change.source_contract_errors(
                "Sources/report.md", invalid, "# report\n"
            )
            self.assertTrue(any(field in error for error in errors), errors)


if __name__ == "__main__":
    unittest.main()
