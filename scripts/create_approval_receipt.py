#!/usr/bin/env python3
"""Create a short-lived human approval receipt in protected Git metadata."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import validate_change as guard


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Review and approve exact gated Loreloom changes. Run this manually "
            "outside the agent sandbox, or through a trusted approval UI."
        )
    )
    parser.add_argument("--approval-id", required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--snapshot-file", required=True)
    parser.add_argument("--allow", action="append", default=[], metavar="PATH")
    parser.add_argument("--allow-destructive", action="append", default=[])
    parser.add_argument("--allow-promotion", action="append", default=[])
    parser.add_argument("--allow-reviewed-change", action="append", default=[])
    parser.add_argument("--allow-archive", action="append", default=[])
    parser.add_argument("--allow-human-block", action="append", default=[])
    parser.add_argument("--allow-source-create", action="append", default=[])
    parser.add_argument("--allow-source-amendment", action="append", default=[])
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
    base = guard.immutable_base(args.base)
    if base is None:
        return fail("--base must be an existing immutable 40-character commit")
    if not args.allow or len(args.allow) != len(set(args.allow)):
        return fail("provide each exact --allow path once")
    if args.expires_minutes < 1 or args.expires_minutes > 60:
        return fail("--expires-minutes must be between 1 and 60")

    snapshot_path = Path(args.snapshot_file).expanduser().resolve()
    loaded = guard.load_snapshot(snapshot_path)
    if loaded is None:
        return fail("missing, invalid, or modified preflight snapshot")
    snapshot_base, snapshot_sha256, snapshot_allowed, before_files = loaded
    if snapshot_base != base or sorted(snapshot_allowed) != sorted(args.allow):
        return fail("base or exact allowed paths do not match the preflight snapshot")

    operations = {
        "destructive": sorted(args.allow_destructive),
        "promotion": sorted(args.allow_promotion),
        "reviewed_change": sorted(args.allow_reviewed_change),
        "archive": sorted(args.allow_archive),
        "human_block": sorted(args.allow_human_block),
        "source_create": sorted(args.allow_source_create),
        "source_amendment": sorted(args.allow_source_amendment),
        "framework_change": sorted(args.framework_change),
    }
    gated_paths = [path for paths in operations.values() for path in paths]
    if not gated_paths:
        return fail("an approval receipt requires at least one gated operation")
    if any(path not in args.allow for path in gated_paths):
        return fail("every gated operation path must also appear in --allow")

    after_files = guard.filesystem_manifest()
    changes = guard.manifest_changes(before_files, after_files)
    digest = guard.change_digest(base, changes, before_files, after_files)
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
