#!/usr/bin/env python3
"""Decide whether a lightweight Wiki page may be auto-accepted.

A page is auto-accepted (``status: reviewed``) only when all of these hold:

- ``confidence`` is ``high``;
- ``sources`` is not empty;
- the body holds no numeric claim;
- the page records no contradiction.

Every other page stays ``status: draft`` (or moves to ``Wiki/_review/``) and
is recorded in ``log.md``. The gate reads pages and never changes them. It is
a floor: an agent must also send a page to review when it sees a quantity
written in words or a conflict that this script cannot detect.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Sequence

try:
    import yaml
except ImportError as exc:
    print(
        "Missing validation dependency. Run: uv sync --locked --dev, "
        "then use uv run python scripts/ingest_gate.py",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


ROOT = Path(__file__).resolve().parent.parent
WIKI_ROOT = "Wiki"
WIKI_SECTIONS = ("sources", "entities", "concepts", "synthesis", "_review")
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
FENCED_CODE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,}).*?^ {0,3}\1[ \t]*$", re.DOTALL | re.MULTILINE)
IGNORED_SPAN_RES = (
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"`[^`\n]*`"),
    re.compile(r"!?\[\[[^\[\]]*\]\]"),
    re.compile(r"\]\([^)\n]*\)"),
    re.compile(r"https?://\S+"),
    re.compile(r"^\s*(?:>\s*)*\d{1,9}[.)]\s", re.MULTILINE),
    re.compile(r"\[\^[^\]\n]*\]"),
)
# A token that starts with a letter (S3, IPv6, GPT-4, v1.2) is a name, not a
# quantity. A token that starts with a digit (2023, 5GB, 3.5%) is a figure.
TOKEN_RE = re.compile(r"(?<!\w)[^\W_][\w.,/%:-]*")
EMPTY_SECTION_VALUES = {"", "none", "none.", "n/a", "無", "无"}
MAX_EXAMPLES = 3


def split_note(text: str) -> tuple[dict[str, Any] | None, str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, text
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return None, text[match.end() :]
    return (metadata if isinstance(metadata, dict) else None), text[match.end() :]


def numeric_claims(body: str) -> list[str]:
    """Return the figures found in page prose, in reading order."""
    visible = FENCED_CODE_RE.sub("", body)
    for pattern in IGNORED_SPAN_RES:
        visible = pattern.sub(" ", visible)
    return [
        match.group(0).rstrip(".,:/-")
        for match in TOKEN_RE.finditer(visible)
        if match.group(0)[0].isdigit()
    ]


def contradiction_notes(metadata: dict[str, Any], body: str) -> bool:
    """Return whether the page records a contradiction."""
    if metadata.get("contradicts"):
        return True
    in_section = False
    for line in FENCED_CODE_RE.sub("", body).splitlines():
        if re.match(r"^ {0,3}#{1,6}\s", line):
            in_section = bool(
                re.match(r"^ {0,3}#{1,6}\s+(?:Contradictions?|矛盾)\s*$", line, re.IGNORECASE)
            )
            continue
        if in_section:
            content = re.sub(r"^\s*(?:[-*+]|\d+[.)])\s*", "", line).strip()
            if content.casefold() not in EMPTY_SECTION_VALUES:
                return True
    return False


def gate_reasons(metadata: dict[str, Any] | None, body: str) -> list[str]:
    """Return why a page needs owner review; an empty list means accept."""
    if metadata is None:
        return ["frontmatter is missing or invalid"]
    reasons: list[str] = []
    confidence = metadata.get("confidence")
    if confidence != "high":
        reasons.append(f"confidence is {confidence!r}, not 'high'")
    if not metadata.get("sources"):
        reasons.append("no sources")
    figures = numeric_claims(body)
    if figures:
        examples = ", ".join(dict.fromkeys(figures[:MAX_EXAMPLES]))
        reasons.append(f"{len(figures)} numeric claim(s), for example: {examples}")
    if contradiction_notes(metadata, body):
        reasons.append("records a contradiction")
    return reasons


def wiki_pages(root: Path) -> list[Path]:
    pages: list[Path] = []
    for section in WIKI_SECTIONS:
        directory = root / WIKI_ROOT / section
        if directory.is_dir():
            pages.extend(
                path
                for path in directory.rglob("*.md")
                if path.name.lower() != "readme.md"
            )
    return sorted(pages)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Report whether Wiki pages meet the auto-accept rule."
    )
    parser.add_argument("paths", nargs="*", help="vault-relative Wiki page paths")
    parser.add_argument(
        "--all", action="store_true", help="check every lightweight Wiki page"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help=(
            "exit 1 when a page is already reviewed or evergreen, fails the "
            "rule, and is not marked reviewed_by: owner"
        ),
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    if args.all:
        pages = wiki_pages(ROOT)
    else:
        pages = [ROOT / raw for raw in args.paths]
    if not pages:
        print("No Wiki pages selected. Name page paths or use --all.")
        return 0 if args.all else 2

    violations = 0
    for path in pages:
        try:
            name = path.resolve().relative_to(ROOT.resolve()).as_posix()
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError, ValueError):
            print(f"{path}: cannot read a page inside the vault")
            violations += 1
            continue
        metadata, body = split_note(text)
        reasons = gate_reasons(metadata, body)
        if not reasons:
            print(f"{name}: accept -> status: reviewed")
            continue
        print(f"{name}: review -> status: draft; record in log.md")
        for reason in reasons:
            print(f"  - {reason}")
        if (
            metadata is not None
            and metadata.get("status") in {"reviewed", "evergreen"}
            and metadata.get("reviewed_by") != "owner"
        ):
            violations += 1
            print("  - page is already reviewed without reviewed_by: owner")
    return 1 if args.check and violations else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
