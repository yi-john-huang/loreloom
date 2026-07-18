#!/usr/bin/env python3
"""Validate managed note frontmatter and Obsidian wikilinks."""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
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


def is_git_ignored(path: Path) -> bool:
    """Return whether Git excludes a local-only tool artifact from the repository."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "--", relative(path)],
            cwd=ROOT,
            check=False,
            capture_output=True,
        )
    except FileNotFoundError:
        return False
    return result.returncode == 0


def custom_agent_paths() -> list[Path]:
    agent_dir = ROOT / ".codex" / "agents"
    return sorted(
        path for path in agent_dir.glob("*.toml") if not is_git_ignored(path)
    )


def repository_skill_dirs() -> list[Path]:
    skill_root = ROOT / ".agents" / "skills"
    return sorted(
        path
        for path in skill_root.glob("*")
        if path.is_dir() and not is_git_ignored(path)
    )


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
    directory_types = {
        "Inbox": "inbox",
        "Sources": "source",
        "Knowledge": "concept",
        "Wiki": "wiki",
        "MOCs": "moc",
        "Projects": "project",
        "Areas": "area",
        "Daily": "daily",
    }

    for path in notes:
        metadata, parse_error = load_frontmatter(path)
        if parse_error:
            errors.append(f"{relative(path)}: {parse_error}")
            continue
        assert metadata is not None

        root_name = path.relative_to(ROOT).parts[0]
        expected_type = directory_types.get(root_name)
        if expected_type and metadata.get("type") != expected_type:
            errors.append(
                f"{relative(path)}: notes in {root_name}/ must use type '{expected_type}'"
            )

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
            for source in sources:
                if not isinstance(source, str):
                    continue
                match = re.fullmatch(r"\[\[([^\[\]]+)\]\]", source)
                target = normalize_target(match.group(1)) if match else ""
                if not target.startswith(("Sources/", "Daily/")):
                    errors.append(
                        f"{relative(path)}: Concept source must be a Sources/ or "
                        f"Daily/ wikilink (found '{source}')"
                    )

        if metadata.get("type") == "wiki":
            inputs = metadata.get("inputs", [])
            provisional_input = False
            for input_link in inputs:
                if not isinstance(input_link, str):
                    continue
                match = re.fullmatch(r"\[\[([^\[\]]+)\]\]", input_link)
                target = normalize_target(match.group(1)) if match else ""
                if not target.startswith("Knowledge/"):
                    errors.append(
                        f"{relative(path)}: Wiki input must be a Knowledge/ wikilink "
                        f"(found '{input_link}')"
                    )
                    continue
                target_path = ROOT / f"{target}.md"
                if target_path.exists():
                    input_metadata, input_error = load_frontmatter(target_path)
                    if not input_error and input_metadata is not None:
                        provisional_input = (
                            provisional_input
                            or input_metadata.get("status") != "evergreen"
                        )

            if provisional_input and metadata.get("review_status") == "reviewed":
                errors.append(
                    f"{relative(path)}: Wiki pages with draft inputs cannot be reviewed"
                )

            text = path.read_text(encoding="utf-8")
            start_marker = "<!-- human:start -->"
            end_marker = "<!-- human:end -->"
            start_count = text.count(start_marker)
            end_count = text.count(end_marker)
            if start_count != end_count or start_count > 1:
                errors.append(
                    f"{relative(path)}: malformed, multiple, or unpaired human blocks"
                )
            elif start_count == 1 and text.index(start_marker) > text.index(end_marker):
                errors.append(f"{relative(path)}: human block markers are reversed")

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


def codex_agent_errors() -> list[str]:
    errors: list[str] = []
    config_path = ROOT / ".codex" / "config.toml"
    expected_models = {
        "vault-architect": "gpt-5.6-sol",
        "source-reader": "gpt-5.6-luna",
        "knowledge-distiller": "gpt-5.6-terra",
        "wiki-synthesizer": "gpt-5.6-sol",
        "vault-reviewer": "gpt-5.6-sol",
        "vault-worker": "gpt-5.6-terra",
    }
    expected_efforts = {
        name: "high" if name == "source-reader" else "max"
        for name in expected_models
    }

    if config_path.exists():
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{relative(config_path)}: invalid TOML: {exc}")
        else:
            expected_root = {
                "model": "gpt-5.6-sol",
                "model_reasoning_effort": "max",
                "sandbox_mode": "workspace-write",
                "approval_policy": "on-request",
            }
            for field, expected in expected_root.items():
                if config.get(field) != expected:
                    errors.append(
                        f"{relative(config_path)}: {field} must remain {expected!r}"
                    )
            sandbox = config.get("sandbox_workspace_write")
            if not isinstance(sandbox, dict) or sandbox.get("network_access") is not False:
                errors.append(
                    f"{relative(config_path)}: sandbox workspace network_access must remain false"
                )
            agents = config.get("agents")
            if not isinstance(agents, dict):
                errors.append(f"{relative(config_path)}: missing [agents] table")
            else:
                if agents.get("max_depth") != 1:
                    errors.append(
                        f"{relative(config_path)}: agents.max_depth must remain 1"
                    )
                if agents.get("max_threads") != 4:
                    errors.append(
                        f"{relative(config_path)}: agents.max_threads must remain 4"
                    )

    names: set[str] = set()
    for path in custom_agent_paths():
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{relative(path)}: invalid TOML: {exc}")
            continue

        for field in ("name", "description", "developer_instructions"):
            if not isinstance(data.get(field), str) or not data[field].strip():
                errors.append(f"{relative(path)}: missing non-empty {field}")

        name = data.get("name")
        if isinstance(name, str):
            if name != path.stem:
                errors.append(
                    f"{relative(path)}: agent name must match filename '{path.stem}'"
                )
            if name in names:
                errors.append(f"{relative(path)}: duplicate agent name '{name}'")
            names.add(name)

        effort = data.get("model_reasoning_effort")
        expected_effort = expected_efforts.get(path.stem)
        if expected_effort and effort != expected_effort:
            errors.append(
                f"{relative(path)}: reasoning effort must remain {expected_effort!r}"
            )

        expected_model = expected_models.get(path.stem)
        if expected_model and data.get("model") != expected_model:
            errors.append(
                f"{relative(path)}: model must remain {expected_model!r}"
            )

        sandbox = data.get("sandbox_mode")
        if sandbox != "read-only":
            errors.append(f"{relative(path)}: custom vault agents must be read-only")
        approval = data.get("approval_policy")
        if approval != "never":
            errors.append(
                f"{relative(path)}: read-only custom agents must use approval_policy 'never'"
            )

    return errors


def skill_errors() -> list[str]:
    errors: list[str] = []
    for skill_dir in repository_skill_dirs():
        skill_path = skill_dir / "SKILL.md"
        if not skill_path.exists():
            errors.append(f"{relative(skill_dir)}: missing SKILL.md")
            continue

        metadata, parse_error = load_frontmatter(skill_path)
        if parse_error:
            errors.append(f"{relative(skill_path)}: {parse_error}")
            continue
        assert metadata is not None

        name = metadata.get("name")
        description = metadata.get("description")
        if name != skill_dir.name:
            errors.append(
                f"{relative(skill_path)}: skill name must match directory '{skill_dir.name}'"
            )
        if not isinstance(description, str) or len(description.strip()) < 40:
            errors.append(f"{relative(skill_path)}: description is too short")
        if "TODO" in skill_path.read_text(encoding="utf-8"):
            errors.append(f"{relative(skill_path)}: unresolved TODO placeholder")

        ui_path = skill_dir / "agents" / "openai.yaml"
        if not ui_path.exists():
            errors.append(f"{relative(skill_dir)}: missing agents/openai.yaml")
            continue
        try:
            ui_data = yaml.safe_load(ui_path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            errors.append(f"{relative(ui_path)}: invalid YAML: {exc}")
            continue

        interface = ui_data.get("interface") if isinstance(ui_data, dict) else None
        if not isinstance(interface, dict):
            errors.append(f"{relative(ui_path)}: missing interface mapping")
            continue
        default_prompt = interface.get("default_prompt")
        if not isinstance(default_prompt, str) or f"${name}" not in default_prompt:
            errors.append(
                f"{relative(ui_path)}: default_prompt must mention '${name}'"
            )

    return errors


def main() -> int:
    notes = managed_notes()
    errors = []
    errors.extend(schema_errors(notes))
    errors.extend(wikilink_errors(all_note_paths()))
    errors.extend(repository_hygiene_errors())
    errors.extend(codex_agent_errors())
    errors.extend(skill_errors())

    if errors:
        print(f"Vault validation failed with {len(errors)} error(s):")
        for error in sorted(set(errors)):
            print(f"- {error}")
        return 1

    print(
        f"Vault validation passed: {len(notes)} managed notes, "
        f"{len(all_note_paths())} Markdown files checked for wikilinks, "
        f"{len(custom_agent_paths())} custom agents, "
        f"and {len(repository_skill_dirs())} skills."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
