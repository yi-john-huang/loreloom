#!/usr/bin/env python3
"""Validate a proposed vault diff against Loreloom authority boundaries."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parent.parent
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
HUMAN_BLOCK_RE = re.compile(
    r"<!-- human:start -->(.*?)<!-- human:end -->", re.DOTALL
)
PROTECTED_PREFIXES = (
    ".agents/",
    ".codex/",
    ".github/",
    "Templates/",
    "docs/",
    "schemas/",
    "scripts/",
    "tests/",
)
PROTECTED_FILES = {
    "AGENTS.md",
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "CODE_OF_CONDUCT.md",
    "CHANGELOG.md",
    "pyproject.toml",
    "uv.lock",
}
SNAPSHOT_EXCLUDED_NAMES = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
    ".trash",
}


@dataclass(frozen=True)
class Change:
    status: str
    old_path: str | None
    new_path: str | None

    @property
    def paths(self) -> tuple[str, ...]:
        return tuple(path for path in (self.old_path, self.new_path) if path)


def git_bytes(*args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return result.stdout


def changed_files(base: str) -> list[Change]:
    fields = git_bytes("diff", "--name-status", "-z", "--find-renames", base, "--").split(
        b"\0"
    )
    changes: list[Change] = []
    index = 0
    while index < len(fields) and fields[index]:
        status = fields[index].decode("utf-8", errors="replace")
        index += 1
        if status.startswith(("R", "C")):
            old_path = fields[index].decode("utf-8")
            new_path = fields[index + 1].decode("utf-8")
            index += 2
        else:
            path = fields[index].decode("utf-8")
            index += 1
            old_path = None if status == "A" else path
            new_path = None if status == "D" else path
        changes.append(Change(status=status, old_path=old_path, new_path=new_path))

    tracked_paths = {path for change in changes for path in change.paths}
    untracked = git_bytes("ls-files", "--others", "--exclude-standard", "-z").split(b"\0")
    for raw_path in untracked:
        if not raw_path:
            continue
        path = raw_path.decode("utf-8")
        if path not in tracked_paths:
            changes.append(Change(status="A", old_path=None, new_path=path))
    return changes


def parse_frontmatter(text: str) -> dict[str, Any] | None:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None
    value = yaml.safe_load(match.group(1))
    return value if isinstance(value, dict) else None


def base_text(base: str, path: str) -> str | None:
    result = subprocess.run(
        ["git", "show", f"{base}:{path}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.stdout if result.returncode == 0 else None


def current_text(path: str) -> str | None:
    candidate = ROOT / path
    if candidate.is_symlink():
        return None
    if not candidate.is_file():
        return None
    return candidate.read_text(encoding="utf-8")


def is_runtime_only_path(path: Path) -> bool:
    if any(part in SNAPSHOT_EXCLUDED_NAMES for part in path.parts):
        return True
    posix = path.as_posix()
    if posix in {
        ".obsidian/workspace.json",
        ".obsidian/workspace-mobile.json",
        ".DS_Store",
        "Thumbs.db",
    }:
        return True
    if posix.startswith(".obsidian/cache/"):
        return True
    if posix.startswith(".agents/runs/") or posix.startswith(".agents/cache/"):
        return True
    if (
        len(path.parts) >= 4
        and path.parts[0] == ".obsidian"
        and path.parts[1] == "plugins"
        and path.name == "data.json"
    ):
        return True
    return path.suffix in {".pyc", ".pyo", ".swp", ".swo"}


def filesystem_manifest() -> dict[str, dict[str, str]]:
    manifest: dict[str, dict[str, str]] = {}
    for candidate in sorted(ROOT.rglob("*")):
        relative_path = candidate.relative_to(ROOT)
        if is_runtime_only_path(relative_path):
            continue
        if candidate.is_symlink():
            content = candidate.readlink().as_posix().encode()
            kind = "symlink"
        elif candidate.is_file():
            content = candidate.read_bytes()
            kind = "file"
        else:
            continue
        manifest[relative_path.as_posix()] = {
            "kind": kind,
            "mode": oct(candidate.lstat().st_mode & 0o777),
            "sha256": hashlib.sha256(content).hexdigest(),
        }
    return manifest


def manifest_changes(
    before: dict[str, dict[str, str]], after: dict[str, dict[str, str]]
) -> list[Change]:
    changes: list[Change] = []
    for path in sorted(set(before) | set(after)):
        if before.get(path) == after.get(path):
            continue
        if path not in before:
            changes.append(Change(status="A", old_path=None, new_path=path))
        elif path not in after:
            changes.append(Change(status="D", old_path=path, new_path=None))
        else:
            changes.append(Change(status="M", old_path=path, new_path=path))
    return changes


def snapshot_hash(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def load_snapshot(
    path: Path,
) -> tuple[str, str, list[str], dict[str, dict[str, str]]] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    supplied_hash = data.pop("snapshot_sha256", None)
    if supplied_hash != snapshot_hash(data):
        return None
    if (
        data.get("version") != 1
        or not isinstance(data.get("allowed_paths"), list)
        or not all(isinstance(item, str) for item in data["allowed_paths"])
        or not isinstance(data.get("files"), dict)
    ):
        return None
    base = data.get("base_commit")
    if not isinstance(base, str):
        return None
    return base, supplied_hash, data["allowed_paths"], data["files"]


def write_snapshot(
    path: Path,
    base: str,
    allowed_paths: list[str],
    files: dict[str, dict[str, str]],
) -> None:
    payload = {
        "version": 1,
        "base_commit": base,
        "allowed_paths": sorted(allowed_paths),
        "files": files,
    }
    payload["snapshot_sha256"] = snapshot_hash(payload)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(payload, stream, indent=2, sort_keys=True)
        stream.write("\n")


def change_digest(
    base: str,
    changes: list[Change],
    before: dict[str, dict[str, str]],
    after: dict[str, dict[str, str]],
) -> str:
    records: list[dict[str, str | None]] = []
    for change in sorted(changes, key=lambda item: item.paths):
        old_hash: str | None = None
        new_hash: str | None = None
        old_mode: str | None = None
        new_mode: str | None = None
        if change.old_path:
            old_entry = before.get(change.old_path)
            if old_entry:
                old_hash = old_entry.get("sha256")
                old_mode = old_entry.get("mode")
            else:
                old_bytes = git_bytes("show", f"{base}:{change.old_path}", check=False)
                old_hash = hashlib.sha256(old_bytes).hexdigest()
        if change.new_path:
            new_entry = after.get(change.new_path)
            if new_entry:
                new_hash = new_entry.get("sha256")
                new_mode = new_entry.get("mode")
        records.append(
            {
                "status": change.status,
                "old_path": change.old_path,
                "new_path": change.new_path,
                "old_sha256": old_hash,
                "new_sha256": new_hash,
                "old_mode": old_mode,
                "new_mode": new_mode,
            }
        )
    payload = json.dumps(records, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def is_allowed(path: str, allowed: list[str]) -> bool:
    return path in allowed


def is_safe_repository_path(path: str) -> bool:
    candidate = Path(path)
    return not candidate.is_absolute() and ".." not in candidate.parts


def is_protected(path: str) -> bool:
    return path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES)


def approval_receipt_path(receipt_id: str) -> Path | None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", receipt_id):
        return None
    result = subprocess.run(
        ["git", "rev-parse", "--git-path", f"loreloom-approvals/{receipt_id}.json"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0:
        return None
    path = Path(result.stdout.strip())
    return path if path.is_absolute() else ROOT / path


def load_approval_receipt(receipt_id: str) -> dict[str, Any] | None:
    path = approval_receipt_path(receipt_id)
    if path is None or not path.is_file() or path.is_symlink():
        return None
    if path.stat().st_mode & 0o777 != 0o600:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def receipt_expired(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return True
    if parsed.tzinfo is None:
        return True
    return parsed.astimezone(timezone.utc) <= datetime.now(timezone.utc)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reject vault diffs that cross agent authority boundaries."
    )
    parser.add_argument(
        "--base",
        required=True,
        help="Immutable 40-character pre-task Git commit",
    )
    parser.add_argument(
        "--allow",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact output path; repeat once for every authorized path",
    )
    parser.add_argument(
        "--check-clean",
        action="store_true",
        help="Preflight: require every declared output path to match the base commit",
    )
    parser.add_argument(
        "--snapshot-file",
        required=True,
        help="Absolute snapshot path outside the repository; reuse it for final validation",
    )
    parser.add_argument(
        "--allow-destructive",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact human-approved deletion or rename path; repeat as needed",
    )
    parser.add_argument(
        "--allow-promotion",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact human-approved evergreen/reviewed path; repeat as needed",
    )
    parser.add_argument(
        "--allow-reviewed-change",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact approved reviewed-content edit path; repeat as needed",
    )
    parser.add_argument(
        "--allow-archive",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact approved archive path; repeat as needed",
    )
    parser.add_argument(
        "--allow-human-block",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact approved Wiki human-block path; repeat as needed",
    )
    parser.add_argument(
        "--allow-source-create",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact approved new Source path; repeat as needed",
    )
    parser.add_argument(
        "--allow-source-amendment",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact approved append-only Source amendment path; repeat as needed",
    )
    parser.add_argument(
        "--framework-change",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact approved protected framework path; repeat as needed",
    )
    parser.add_argument(
        "--approval-receipt",
        metavar="ID",
        help="Receipt ID under protected Git metadata, required for gated paths",
    )
    parser.add_argument(
        "--print-diff-sha256",
        action="store_true",
        help="Print the final path-and-content digest for owner review",
    )
    return parser.parse_args()


def immutable_base(base: str) -> str | None:
    if not re.fullmatch(r"[0-9a-fA-F]{40}", base):
        return None
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{base}^{{commit}}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0:
        return None
    resolved = result.stdout.strip().lower()
    return resolved if resolved == base.lower() else None


def main() -> int:
    args = parse_args()
    base = immutable_base(args.base)
    if base is None:
        print(
            "--base must be an existing immutable 40-character commit captured before the task",
            file=sys.stderr,
        )
        return 2
    try:
        git_changes = changed_files(base)
    except subprocess.CalledProcessError as exc:
        print(f"Unable to compare against {base}: {exc}", file=sys.stderr)
        return 2

    snapshot_path = Path(args.snapshot_file).expanduser().resolve()
    try:
        snapshot_path.relative_to(ROOT.resolve())
    except ValueError:
        pass
    else:
        print("--snapshot-file must be outside the repository", file=sys.stderr)
        return 2

    errors: list[str] = []
    if not args.allow:
        errors.append("no output paths declared; repeat --allow for every exact path")

    if args.check_clean:
        if any(
            (
                args.allow_destructive,
                args.allow_promotion,
                args.allow_reviewed_change,
                args.allow_archive,
                args.allow_human_block,
                args.allow_source_create,
                args.allow_source_amendment,
                args.framework_change,
            )
        ):
            errors.append("preflight does not accept gated override paths")
        dirty_paths = sorted(
            {
                path
                for change in git_changes
                for path in change.paths
                if is_allowed(path, args.allow)
            }
        )
        if dirty_paths:
            print("Preflight failed; declared output paths already differ from the base:")
            for path in dirty_paths:
                print(f"- {path}")
            return 1
        if errors:
            print(f"Preflight failed with {len(errors)} error(s):")
            for error in errors:
                print(f"- {error}")
            return 1
        try:
            write_snapshot(snapshot_path, base, args.allow, filesystem_manifest())
        except FileExistsError:
            print(
                "preflight snapshot already exists; choose a new protected path",
                file=sys.stderr,
            )
            return 2
        print(
            f"Preflight passed: {len(args.allow)} exact output path(s) are clean "
            f"against {base}; snapshot written to {snapshot_path}."
        )
        return 0

    loaded_snapshot = load_snapshot(snapshot_path)
    if loaded_snapshot is None:
        print("missing or invalid --snapshot-file from the preflight", file=sys.stderr)
        return 2
    snapshot_base, snapshot_sha256, snapshot_allowed, before_files = loaded_snapshot
    if snapshot_base != base:
        print("snapshot base does not match --base", file=sys.stderr)
        return 2
    if sorted(args.allow) != sorted(snapshot_allowed):
        print(
            "final --allow paths must exactly match the preflight snapshot",
            file=sys.stderr,
        )
        return 2
    after_files = filesystem_manifest()
    changes = manifest_changes(before_files, after_files)
    digest = change_digest(base, changes, before_files, after_files)
    if args.print_diff_sha256:
        print(f"Diff SHA-256: {digest}")

    gated_path_sets = (
        args.allow_destructive,
        args.allow_promotion,
        args.allow_reviewed_change,
        args.allow_archive,
        args.allow_human_block,
        args.allow_source_create,
        args.allow_source_amendment,
        args.framework_change,
    )
    approval_reference: str | None = None
    if any(gated_path_sets):
        receipt = (
            load_approval_receipt(args.approval_receipt)
            if args.approval_receipt
            else None
        )
        expected_operations = {
            "destructive": sorted(args.allow_destructive),
            "promotion": sorted(args.allow_promotion),
            "reviewed_change": sorted(args.allow_reviewed_change),
            "archive": sorted(args.allow_archive),
            "human_block": sorted(args.allow_human_block),
            "source_create": sorted(args.allow_source_create),
            "source_amendment": sorted(args.allow_source_amendment),
            "framework_change": sorted(args.framework_change),
        }
        if receipt is None:
            errors.append(
                "gated paths require a protected mode-0600 --approval-receipt"
            )
        else:
            receipt_approval_id = receipt.get("approval_id")
            approval_reference = (
                receipt_approval_id if isinstance(receipt_approval_id, str) else None
            )
            expected_receipt = {
                "version": 1,
                "approval_id": args.approval_receipt,
                "base_commit": base,
                "snapshot_sha256": snapshot_sha256,
                "allowed_paths": sorted(args.allow),
                "operations": expected_operations,
                "approved_diff_sha256": digest,
            }
            for field, expected in expected_receipt.items():
                if receipt.get(field) != expected:
                    errors.append(f"approval receipt {field} does not match final change")
            if receipt_expired(receipt.get("expires_at")):
                errors.append("approval receipt is expired or has an invalid expiry")

    for change in changes:
        for path in change.paths:
            if not is_safe_repository_path(path):
                errors.append(f"{path}: unsafe repository path")
            if not is_allowed(path, args.allow):
                errors.append(f"{path}: outside the declared output scope")
            candidate = ROOT / path
            if candidate.is_symlink():
                errors.append(f"{path}: symlink changes are not accepted")
            if path == "Sources" or path.startswith("Sources/"):
                source_creation = change.status == "A" and is_allowed(
                    path, args.allow_source_create
                )
                source_amendment = (
                    change.status == "M"
                    and is_allowed(path, args.allow_source_amendment)
                )
                if not source_creation and not source_amendment:
                    errors.append(f"{path}: Sources are immutable in agent change sets")
            if is_protected(path) and not is_allowed(path, args.framework_change):
                errors.append(f"{path}: protected framework path")
            if path == "Archive" or path.startswith("Archive/"):
                if not is_allowed(path, args.allow_archive):
                    errors.append(f"{path}: archive changes need exact approval")

        if change.status.startswith(("D", "R")) and not all(
            is_allowed(path, args.allow_destructive) for path in change.paths
        ):
            errors.append(
                f"{change.status} {' -> '.join(change.paths)}: destructive change needs approval"
            )

        new_path = change.new_path
        if not new_path or not new_path.endswith(".md"):
            continue
        old_path = change.old_path
        old_text = base_text(base, old_path) if old_path else None
        new_text = current_text(new_path)
        if new_text is None:
            continue

        if (
            new_path.startswith("Sources/")
            and is_allowed(new_path, args.allow_source_amendment)
            and old_text is not None
            and not new_text.startswith(old_text)
        ):
            errors.append(
                f"{new_path}: approved Source amendments must append without rewriting"
            )

        old_meta = parse_frontmatter(old_text) if old_text is not None else None
        new_meta = parse_frontmatter(new_text)

        if old_meta and not is_allowed(new_path, args.allow_reviewed_change):
            reviewed_concept = old_meta.get("type") == "concept" and (
                old_meta.get("status") == "evergreen"
                or old_meta.get("reviewed") is not None
            )
            reviewed_wiki = (
                old_meta.get("type") == "wiki"
                and old_meta.get("review_status") == "reviewed"
            )
            if reviewed_concept:
                errors.append(
                    f"{new_path}: changing reviewed or evergreen Concept content needs approval"
                )
            if reviewed_wiki:
                errors.append(
                    f"{new_path}: changing reviewed Wiki content needs approval"
                )

        if new_meta and not is_allowed(new_path, args.allow_promotion):
            if new_meta.get("type") == "concept":
                if (
                    (old_meta is None or old_meta.get("status") != "evergreen")
                    and new_meta.get("status") == "evergreen"
                ):
                    errors.append(f"{new_path}: Concept evergreen promotion needs approval")
                if (
                    (old_meta is None or old_meta.get("reviewed") is None)
                    and new_meta.get("reviewed") is not None
                ):
                    errors.append(
                        f"{new_path}: Concept reviewed transition needs approval"
                    )
            if new_meta.get("type") == "wiki":
                if (
                    (old_meta is None or old_meta.get("review_status") != "reviewed")
                    and new_meta.get("review_status") == "reviewed"
                ):
                    errors.append(f"{new_path}: Wiki reviewed transition needs approval")

        if new_meta and not is_allowed(new_path, args.allow_archive):
            old_status = old_meta.get("status") if old_meta else None
            if old_status != "archived" and new_meta.get("status") == "archived":
                errors.append(f"{new_path}: archive transition needs exact approval")

        is_wiki = new_path.startswith("Wiki/") or (
            old_meta is not None and old_meta.get("type") == "wiki"
        ) or (new_meta is not None and new_meta.get("type") == "wiki")
        if is_wiki:
            old_blocks = (
                HUMAN_BLOCK_RE.findall(old_text) if old_text is not None else []
            )
            new_blocks = HUMAN_BLOCK_RE.findall(new_text)
            if old_blocks != new_blocks and not is_allowed(
                new_path, args.allow_human_block
            ):
                errors.append(f"{new_path}: human-owned Wiki block changed")

    if errors:
        print(f"Change validation failed with {len(set(errors))} error(s):")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1

    print(
        f"Change validation passed: {len(changes)} changed path record(s) "
        f"against {base}; diff SHA-256 {digest}."
    )
    if approval_reference:
        print(f"Approval reference: {approval_reference}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
