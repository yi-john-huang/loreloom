#!/usr/bin/env python3
"""Validate managed note frontmatter and Obsidian wikilinks."""

from __future__ import annotations

import re
import sys
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    print(
        "Missing validation dependency. Run: uv sync --locked --dev, "
        "then use uv run python scripts/validate_vault.py",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc


ROOT = Path(__file__).resolve().parent.parent
MANAGED_ROOTS = (
    "Inbox",
    "Sources",
    "Knowledge",
    "Wiki",
    "MOCs",
    "Projects",
    "Areas",
    "Daily",
    "Archive",
)
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
WIKILINK_RE = re.compile(r"(?<!!)\[\[([^\[\]]+?)\]\]")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def relative(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def normalize_yaml_scalars(value: Any) -> Any:
    """Convert PyYAML date objects to the ISO strings stored in Markdown."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: normalize_yaml_scalars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_yaml_scalars(item) for item in value]
    return value


def load_frontmatter(path: Path) -> tuple[dict[str, Any] | None, str | None]:
    text = path.read_text(encoding="utf-8")
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, "missing YAML frontmatter"
    try:
        value = normalize_yaml_scalars(yaml.safe_load(match.group(1)))
    except yaml.YAMLError as exc:
        return None, f"invalid YAML: {exc}"
    if not isinstance(value, dict):
        return None, "frontmatter must be a mapping"
    return value, None


def managed_notes() -> list[Path]:
    notes: list[Path] = []
    for root_name in MANAGED_ROOTS:
        root = ROOT / root_name
        if root.exists():
            notes.extend(
                path
                for path in root.rglob("*.md")
                if path.name.lower() != "readme.md"
            )
    return sorted(notes)


def all_note_paths() -> list[Path]:
    excluded_parts = {".git", ".github", ".agents", "Templates", "docs"}
    return sorted(
        path
        for path in ROOT.rglob("*.md")
        if not excluded_parts.intersection(path.relative_to(ROOT).parts)
    )


def schema_errors(notes: list[Path]) -> list[str]:
    import json

    schema_path = ROOT / "schemas" / "frontmatter.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors: list[str] = []

    for path in notes:
        metadata, parse_error = load_frontmatter(path)
        if parse_error:
            errors.append(f"{relative(path)}: {parse_error}")
            continue
        assert metadata is not None

        for error in sorted(validator.iter_errors(metadata), key=lambda item: list(item.path)):
            field = ".".join(str(part) for part in error.absolute_path) or "frontmatter"
            errors.append(f"{relative(path)}: {field}: {error.message}")

        title = metadata.get("title")
        if isinstance(title, str) and title != path.stem:
            errors.append(
                f"{relative(path)}: title must match filename '{path.stem}' "
                f"(found '{title}')"
            )

        created = metadata.get("created")
        updated = metadata.get("updated")
        if (
            isinstance(created, str)
            and isinstance(updated, str)
            and DATE_RE.fullmatch(created)
            and DATE_RE.fullmatch(updated)
        ):
            try:
                if date.fromisoformat(updated) < date.fromisoformat(created):
                    errors.append(f"{relative(path)}: updated precedes created")
            except ValueError:
                pass

        if metadata.get("type") == "daily" and metadata.get("date") != path.stem:
            errors.append(f"{relative(path)}: daily date must match filename")

        if metadata.get("type") == "concept":
            if metadata.get("status") == "evergreen" and metadata.get("reviewed") is None:
                errors.append(
                    f"{relative(path)}: evergreen concept requires a reviewed date"
                )
            sources = metadata.get("sources", [])
            if any(
                isinstance(source, str) and source.startswith("[[Wiki/")
                for source in sources
            ):
                errors.append(
                    f"{relative(path)}: generated Wiki pages cannot be primary sources"
                )

    return errors


def normalize_target(raw: str) -> str:
    target = raw.split("|", 1)[0].split("#", 1)[0].split("^", 1)[0].strip()
    target = target.replace("\\", "/")
    if target.lower().endswith(".md"):
        target = target[:-3]
    return target.strip("/")


def wikilink_errors(paths: list[Path]) -> list[str]:
    note_paths = all_note_paths()
    by_vault_path: dict[str, Path] = {}
    by_stem: dict[str, list[Path]] = defaultdict(list)
    for path in note_paths:
        without_suffix = relative(path)[:-3]
        by_vault_path[without_suffix.casefold()] = path
        by_stem[path.stem.casefold()].append(path)

    errors: list[str] = []
    for source_path in paths:
        text = source_path.read_text(encoding="utf-8")
        for match in WIKILINK_RE.finditer(text):
            target = normalize_target(match.group(1))
            if not target or target.startswith("#"):
                continue
            if "://" in target:
                continue
            if "/" in target:
                if target.casefold() not in by_vault_path:
                    errors.append(
                        f"{relative(source_path)}: unresolved wikilink [[{match.group(1)}]]"
                    )
            else:
                matches = by_stem.get(target.casefold(), [])
                if not matches:
                    errors.append(
                        f"{relative(source_path)}: unresolved wikilink [[{match.group(1)}]]"
                    )
                elif len(matches) > 1:
                    choices = ", ".join(relative(item) for item in matches)
                    errors.append(
                        f"{relative(source_path)}: ambiguous wikilink [[{match.group(1)}]]; "
                        f"use a vault path ({choices})"
                    )
    return errors


def repository_hygiene_errors() -> list[str]:
    errors: list[str] = []
    forbidden_names = {".env", "workspace.json", "workspace-mobile.json"}
    for path in ROOT.rglob("*"):
        if ".git" in path.relative_to(ROOT).parts or not path.is_file():
            continue
        if path.name in forbidden_names or path.name.endswith(".private.md"):
            errors.append(f"{relative(path)}: private/runtime file must not be committed")
    return errors


def main() -> int:
    notes = managed_notes()
    errors = []
    errors.extend(schema_errors(notes))
    errors.extend(wikilink_errors(all_note_paths()))
    errors.extend(repository_hygiene_errors())

    if errors:
        print(f"Vault validation failed with {len(errors)} error(s):")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1

    print(
        f"Vault validation passed: {len(notes)} managed notes, "
        f"{len(all_note_paths())} Markdown files checked for wikilinks."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
