#!/usr/bin/env python3
"""Create a short-lived human approval receipt in protected Git metadata."""

from __future__ import annotations

import sys


if __name__ == "__main__" and not sys.flags.isolated:
    print(
        "run this approval tool with an isolated interpreter: "
        "python -I scripts/create_approval_receipt.py",
        file=sys.stderr,
    )
    raise SystemExit(2)

# Dynamic guard loading must not dirty the trusted detached tool worktree.
sys.dont_write_bytecode = True


import argparse
import importlib.util
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path


def load_change_guard():
    validator_path = Path(__file__).with_name("validate_change.py")
    spec = importlib.util.spec_from_file_location(
        "_loreloom_approval_guard", validator_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("approval validator is unavailable")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except BaseException:
        sys.modules.pop(spec.name, None)
        raise
    return module


guard = load_change_guard()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review and approve exact gated Loreloom changes. Run this manually "
            "outside the agent sandbox, or through a trusted approval UI."
        )
    )
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument(
        "--target-root",
        metavar="PATH",
        help="Vault Git worktree to approve from an immutable base tool worktree",
    )
    parser.add_argument("--snapshot-file", required=True)
    parser.add_argument("--allow", action="append", default=[], metavar="PATH")
    parser.add_argument("--allow-destructive", action="append", default=[])
    parser.add_argument("--allow-promotion", action="append", default=[])
    parser.add_argument("--allow-reviewed-change", action="append", default=[])
    parser.add_argument("--allow-archive", action="append", default=[])
    parser.add_argument("--allow-human-block", action="append", default=[])
    parser.add_argument("--allow-source-create", action="append", default=[])
    parser.add_argument("--allow-source-amendment", action="append", default=[])
    parser.add_argument("--allow-source-review", action="append", default=[])
    parser.add_argument("--framework-change", action="append", default=[])
    parser.add_argument("--expires-minutes", type=int, default=15)
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip terminal confirmation; trusted approval UIs only",
    )
    return parser.parse_args()


def fail(message: str) -> int:
    print(message, file=sys.stderr)
    return 2


def main() -> int:
    args = parse_args()
    if target_error := guard.configure_target_root(args.target_root):
        return fail(target_error)
    base = guard.immutable_base(args.base)
    if base is None:
        return fail("--base must be an existing immutable 40-character commit")
    if guard.current_head() != base:
        return fail(
            "--base must equal the current HEAD; restart preflight after any commit"
        )
    if not args.allow or len(args.allow) != len(set(args.allow)):
        return fail("provide each exact --allow path once")
    if args.expires_minutes < 1 or args.expires_minutes > 60:
        return fail("--expires-minutes must be between 1 and 60")

    operations = {
        "destructive": sorted(args.allow_destructive),
        "promotion": sorted(args.allow_promotion),
        "reviewed_change": sorted(args.allow_reviewed_change),
        "archive": sorted(args.allow_archive),
        "human_block": sorted(args.allow_human_block),
        "source_create": sorted(args.allow_source_create),
        "source_amendment": sorted(args.allow_source_amendment),
        "source_review": sorted(args.allow_source_review),
        "framework_change": sorted(args.framework_change),
    }
    gated_paths = [path for paths in operations.values() for path in paths]
    if not gated_paths:
        return fail("an approval receipt requires at least one gated operation")
    if any(path not in args.allow for path in gated_paths):
        return fail("every gated operation path must also appear in --allow")
    if path_errors := guard.declared_path_errors([*args.allow, *gated_paths]):
        return fail("; ".join(path_errors))
    if trust_error := guard.trusted_approval_tool_error(base):
        return fail(trust_error)

    snapshot_path = Path(args.snapshot_file).expanduser().resolve()
    loaded = guard.load_snapshot(snapshot_path)
    if loaded is None:
        return fail("missing, invalid, or modified preflight snapshot")
    snapshot_base, snapshot_sha256, snapshot_allowed, before_files = loaded
    if snapshot_base != base or sorted(snapshot_allowed) != sorted(args.allow):
        return fail("base or exact allowed paths do not match the preflight snapshot")

    try:
        after_files = guard.filesystem_manifest(args.allow)
        changes = guard.manifest_changes(before_files, after_files)
        digest = guard.change_digest(base, changes, before_files, after_files)
    except guard.ManifestError as exc:
        return fail(str(exc))
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=args.expires_minutes)
    receipt = {
        "version": 1,
        "approval_id": args.approval_id,
        "base_commit": base,
        "snapshot_sha256": snapshot_sha256,
        "allowed_paths": sorted(args.allow),
        "operations": operations,
        "approved_diff_sha256": digest,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }
    private_key = os.environ.get(guard.APPROVAL_PRIVATE_KEY_ENV)
    if not private_key:
        return fail(
            f"{guard.APPROVAL_PRIVATE_KEY_ENV} must name an owner-held private key"
        )
    _, trust_error = guard.trusted_approval_public_key()
    if trust_error:
        return fail(trust_error)
    try:
        receipt["signature"] = guard.sign_receipt(receipt, private_key)
    except RuntimeError as exc:
        return fail(str(exc))

    print(f"Approval ID: {args.approval_id}")
    print(f"Base commit: {base}")
    print(f"Snapshot SHA-256: {snapshot_sha256}")
    print(f"Final diff SHA-256: {digest}")
    print("Gated operations:")
    for operation, paths in operations.items():
        for path in paths:
            print(f"- {operation}: {path}")

    if not args.yes:
        if not sys.stdin.isatty():
            return fail("interactive terminal required unless a trusted UI supplies --yes")
        confirmation = input(f'Type approval ID "{args.approval_id}" to confirm: ')
        if confirmation != args.approval_id:
            return fail("approval cancelled")

    receipt_path = guard.approval_receipt_path(args.approval_id)
    if receipt_path is None:
        return fail("approval ID may contain only letters, digits, dot, underscore, or dash")
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        descriptor = os.open(
            receipt_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
        )
    except FileExistsError:
        return fail("approval receipt already exists; use a new approval ID")
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(receipt, stream, indent=2, sort_keys=True)
        stream.write("\n")
    print(f"Receipt written to protected Git metadata: {receipt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
