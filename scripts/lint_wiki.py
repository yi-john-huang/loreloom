#!/usr/bin/env python3
"""Report the health of the lightweight Wiki without changing any file."""

from __future__ import annotations

import argparse
import importlib
import sys
from datetime import date
from pathlib import Path
from typing import Sequence


def _load(name: str):
    return importlib.import_module(f"{__package__}.{name}" if __package__ else name)


validate_vault = _load("validate_vault")
ingest_gate = _load("ingest_gate")

DEFAULT_STALE_DAYS = 180
SECTIONS = (
    ("broken", "Broken or ambiguous wikilinks"),
    ("orphan", "Orphan pages (no inbound link except index.md and log.md)"),
    ("unindexed", "Pages missing from index.md"),
    ("contradiction", "Unresolved contradictions"),
    ("gate", "Reviewed pages that fail the auto-accept rule without reviewed_by: owner"),
    ("low", "Low-confidence pages"),
    ("queue", "Pages that wait for owner review"),
    ("stale", "Stale pages"),
)


def lint_findings(today: date, stale_days: int) -> dict[str, list[str]]:
    """Return findings by category for every lightweight Wiki page."""
    root = validate_vault.ROOT
    pages = validate_vault.wiki_pages()
    findings: dict[str, list[str]] = {key: [] for key, _ in SECTIONS}
    findings["broken"] = validate_vault.wikilink_errors(pages)

    navigation = {root / validate_vault.WIKI_INDEX_NAME, root / validate_vault.WIKI_LOG_NAME}
    inbound: set[str] = set()
    for path in validate_vault.all_note_paths():
        if path in navigation:
            continue
        own = {validate_vault.relative(path)[:-3].casefold(), path.stem.casefold()}
        inbound |= validate_vault.linked_targets(path) - own
    indexed = validate_vault.linked_targets(root / validate_vault.WIKI_INDEX_NAME)

    for path in pages:
        name = validate_vault.relative(path)
        keys = {name[:-3].casefold(), path.stem.casefold()}
        queued = path.relative_to(root).parts[1] == validate_vault.WIKI_REVIEW_SECTION
        metadata, body = ingest_gate.split_note(path.read_text(encoding="utf-8"))
        if metadata is None:
            continue
        if not queued and not keys & inbound:
            findings["orphan"].append(name)
        if not queued and not keys & indexed:
            findings["unindexed"].append(name)
        if ingest_gate.contradiction_notes(metadata, body):
            findings["contradiction"].append(name)
        status = metadata.get("status")
        reasons = ingest_gate.gate_reasons(metadata, body)
        if (
            reasons
            and status in {"reviewed", "evergreen"}
            and metadata.get("reviewed_by") != "owner"
        ):
            findings["gate"].append(f"{name}: {'; '.join(reasons)}")
        if metadata.get("confidence") == "low":
            findings["low"].append(name)
        if queued or status == "draft":
            findings["queue"].append(f"{name}: {'; '.join(reasons) or 'draft'}")
        updated = metadata.get("updated")
        if isinstance(updated, date) and status != "evergreen":
            age = (today - updated).days
            if age > stale_days:
                findings["stale"].append(f"{name}: updated {age} days ago")
    return findings


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Print a read-only health report for the lightweight Wiki."
    )
    parser.add_argument(
        "--stale-days",
        type=int,
        default=DEFAULT_STALE_DAYS,
        help=f"report non-evergreen pages not updated for this many days (default {DEFAULT_STALE_DAYS})",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    findings = lint_findings(date.today(), args.stale_days)
    total = sum(len(items) for items in findings.values())
    print(
        f"Wiki lint: {len(validate_vault.wiki_pages())} page(s), {total} finding(s)."
    )
    for key, heading in SECTIONS:
        if key == "stale":
            heading = f"{heading} (not updated for more than {args.stale_days} days)"
        print(f"\n{heading}: {len(findings[key])}")
        for item in sorted(findings[key]):
            print(f"- {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
