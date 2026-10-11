#!/usr/bin/env python3
"""Copy Knowledge/ Concept notes to lightweight Wiki/concepts/ pages.

The default is a dry run that only prints the plan. ``--apply`` writes new
pages. The script never changes, moves, or deletes a Knowledge note and never
overwrites an existing Wiki page, so migration can be gradual.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Sequence

try:
    import yaml
except ImportError as exc:
    print(
        "Missing validation dependency. Run: uv sync --locked --dev, "
        "then use uv run python scripts/migrate_knowledge_to_wiki.py",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_ROOT = "Knowledge"
WIKI_CONCEPTS = "Wiki/concepts"
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
STATUS_MAP = {"draft": "draft", "evergreen": "evergreen"}
CONFIDENCE_VALUES = ("high", "medium", "low")
DEFAULT_CONFIDENCE = "low"
CARRIED_FIELDS = ("created", "tags", "aliases", "reviewed")


@dataclass(frozen=True, slots=True)
class Plan:
    action: str
    source: str
    target: str
    detail: str
    content: str | None = None


def knowledge_notes(root: Path) -> list[Path]:
    directory = root / KNOWLEDGE_ROOT
    if not directory.is_dir():
        return []
    return sorted(
        path for path in directory.rglob("*.md") if path.name.lower() != "readme.md"
    )


def wiki_frontmatter(
    metadata: dict[str, Any], source: str, today: date
) -> tuple[dict[str, Any], list[str]]:
    """Map Concept frontmatter to the lightweight Wiki contract."""
    notes: list[str] = []
    status = STATUS_MAP[metadata["status"]]
    confidence = metadata.get("confidence")
    if confidence not in CONFIDENCE_VALUES:
        notes.append(f"confidence defaulted to {DEFAULT_CONFIDENCE}")
        confidence = DEFAULT_CONFIDENCE
    sources = metadata.get("sources")
    if not isinstance(sources, list):
        sources = []
    sources = [item for item in sources if isinstance(item, str) and item.strip()]
    if not sources and status != "draft":
        notes.append("no sources, so status lowered to draft")
        status = "draft"
    updated = metadata.get("updated")
    if isinstance(updated, str):
        try:
            updated = date.fromisoformat(updated)
        except ValueError:
            pass
    if not isinstance(updated, date):
        notes.append("updated defaulted to today")
        updated = today

    result: dict[str, Any] = {
        "title": metadata.get("title") or Path(source).stem,
        "type": "concept",
        "status": status,
        "confidence": confidence,
        "sources": sources,
        "updated": updated,
    }
    if status == "evergreen":
        result["reviewed_by"] = "owner"
    for field in CARRIED_FIELDS:
        if metadata.get(field) not in (None, [], ""):
            result[field] = metadata[field]
    result["migrated_from"] = source
    return result, notes


def plan_note(root: Path, path: Path, today: date) -> Plan:
    source = path.relative_to(root).as_posix()
    inside = path.relative_to(root / KNOWLEDGE_ROOT).as_posix()
    target = f"{WIKI_CONCEPTS}/{inside}"
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return Plan("skip", source, target, "missing YAML frontmatter")
    try:
        metadata = yaml.safe_load(match.group(1))
    except yaml.YAMLError:
        return Plan("skip", source, target, "invalid YAML frontmatter")
    if not isinstance(metadata, dict):
        return Plan("skip", source, target, "frontmatter is not a mapping")
    if metadata.get("type") != "concept":
        return Plan("skip", source, target, "type is not 'concept'")
    status = metadata.get("status")
    if status not in STATUS_MAP:
        return Plan("skip", source, target, f"status {status!r} has no Wiki mapping")
    if (root / target).exists():
        return Plan("skip", source, target, "target already exists")

    frontmatter, notes = wiki_frontmatter(metadata, source, today)
    dumped = yaml.safe_dump(
        frontmatter, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    detail = f"status {status} -> {frontmatter['status']}"
    if notes:
        detail += "; " + "; ".join(notes)
    return Plan(
        "create", source, target, detail, f"---\n{dumped}---\n{text[match.end():]}"
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Copy Knowledge/ Concept notes to Wiki/concepts/ pages with "
            "lightweight frontmatter. Dry run unless --apply is given."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="vault-relative Knowledge note paths; default is every Knowledge note",
    )
    parser.add_argument(
        "--apply", action="store_true", help="write the planned Wiki pages"
    )
    return parser.parse_args(argv)


def selected_notes(root: Path, raw_paths: Sequence[str]) -> tuple[list[Path], list[str]]:
    if not raw_paths:
        return knowledge_notes(root), []
    notes: list[Path] = []
    problems: list[str] = []
    knowledge = (root / KNOWLEDGE_ROOT).resolve()
    for raw in raw_paths:
        path = root / raw
        try:
            path.resolve().relative_to(knowledge)
        except ValueError:
            problems.append(f"{raw}: not inside {KNOWLEDGE_ROOT}/")
            continue
        if not path.is_file() or path.suffix != ".md":
            problems.append(f"{raw}: not an existing Markdown note")
            continue
        notes.append(path)
    return notes, problems


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    notes, problems = selected_notes(ROOT, args.paths)
    for problem in problems:
        print(f"error: {problem}")
    if problems:
        return 2

    plans = [plan_note(ROOT, path, date.today()) for path in notes]
    created = 0
    for plan in plans:
        if plan.action == "create" and args.apply:
            target = ROOT / plan.target
            target.parent.mkdir(parents=True, exist_ok=True)
            assert plan.content is not None
            with target.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(plan.content)
            created += 1
        verb = {
            ("create", True): "created",
            ("create", False): "would create",
        }.get((plan.action, args.apply), "skipped")
        print(f"{verb}: {plan.source} -> {plan.target} ({plan.detail})")

    planned = sum(plan.action == "create" for plan in plans)
    skipped = len(plans) - planned
    if args.apply:
        print(f"Migration applied: {created} page(s) created, {skipped} skipped.")
        if created:
            print(
                "Next: add the new pages to index.md, record the migration in "
                "log.md, then retire each Knowledge note when you are ready."
            )
    else:
        print(
            f"Dry run: {planned} page(s) would be created, {skipped} skipped. "
            "Re-run with --apply to write them."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
