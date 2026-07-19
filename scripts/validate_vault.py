#!/usr/bin/env python3
"""Validate managed note frontmatter and Obsidian wikilinks."""

from __future__ import annotations

import hashlib
import re
import subprocess
import sys
import tomllib
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse

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
ASSET_EMBED_RE = re.compile(r"!\[\[([^\[\]]+?)\]\]")
MARKDOWN_ASSET_LINK_RE = re.compile(
    r"\]\(\s*(?:<(?P<angle>Assets/[^>\r\n]+)>|(?P<plain>Assets/[^)\s]+))\s*\)"
)
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE_URL_RE = re.compile(
    r"^https?://(?:[^/?#\s@]+@)?(?:\[[^\]\\\s]+\]|[^/?#\s:@]+)"
    r"(?::[0-9]+)?(?:[/?#][^\s]*)?$",
    re.IGNORECASE,
)


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

def markdown_without_fenced_code(text: str) -> str:
    """Mask fenced code while preserving line boundaries for link scanning."""
    masked: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    opening_re = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")

    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        if fence_character is None:
            match = opening_re.match(content)
            if match and not (
                match.group("fence").startswith("`")
                and "`" in content[match.end() :]
            ):
                fence = match.group("fence")
                fence_character = fence[0]
                fence_length = len(fence)
                masked.append(newline)
            else:
                masked.append(line)
            continue

        closing_re = re.compile(
            rf"^ {{0,3}}{re.escape(fence_character)}{{{fence_length},}}[ \t]*$"
        )
        if closing_re.fullmatch(content):
            fence_character = None
            fence_length = 0
        masked.append(newline)

    return "".join(masked)


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
        and (
            path.relative_to(ROOT).parts[0] != "Assets"
            or path.relative_to(ROOT).as_posix() == "Assets/README.md"
        )
    )


def safe_asset_path(raw: str) -> Path | None:
    if not isinstance(raw, str) or not raw:
        return None

    relative_path = Path(raw)
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or relative_path.parts[0] != "Assets"
        or ".." in relative_path.parts
    ):
        return None

    candidate = ROOT.joinpath(*relative_path.parts)
    current = ROOT
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            return None

    try:
        candidate.resolve(strict=False).relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate

def valid_source_url(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    value = value.strip()
    if not value or any(character.isspace() for character in value):
        return False
    if not SOURCE_URL_RE.fullmatch(value):
        return False
    try:
        parsed = urlparse(value)
        return bool(parsed.hostname)
    except ValueError:
        return False


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def inbox_provenance_path(value: Any) -> Path | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\[\[([^\[\]]+)\]\]", value)
    if not match:
        return None
    raw_target = match.group(1).split("|", 1)[0].split("#", 1)[0].split("^", 1)[0]
    if raw_target != raw_target.strip():
        return None
    raw_target = raw_target.replace("\\", "/")
    if raw_target.startswith("/") or raw_target.endswith("/"):
        return None
    target = normalize_target(raw_target)
    target_path = Path(target)
    if (
        len(target_path.parts) < 2
        or target_path.parts[0] != "Inbox"
        or ".." in target_path.parts
    ):
        return None
    relative_path = Path(f"{target}.md")
    candidate = ROOT.joinpath(*relative_path.parts)
    current = ROOT
    for part in relative_path.parts:
        current = current / part
        if current.is_symlink():
            return None
    try:
        candidate.resolve(strict=False).relative_to(ROOT.resolve())
    except ValueError:
        return None
    return candidate if candidate.is_file() else None


def source_provenance_errors(metadata: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    inbox_source = metadata.get("inbox_source")
    inbox_path = inbox_provenance_path(inbox_source)
    if inbox_source is not None and inbox_path is None:
        errors.append("inbox_source must resolve to an existing Inbox wikilink")

    has_provenance = valid_source_url(metadata.get("source_url"))
    assets = metadata.get("assets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            asset_path = safe_asset_path(asset.get("path"))
            expected_hash = asset.get("sha256")
            if (
                asset_path is None
                or asset_path.is_symlink()
                or not asset_path.is_file()
                or not isinstance(expected_hash, str)
            ):
                continue
            try:
                if file_sha256(asset_path) == expected_hash:
                    has_provenance = True
                    break
            except OSError:
                continue
    if inbox_path is not None:
        has_provenance = True
    if not has_provenance:
        errors.append(
            "Source needs a traceable non-empty URL, existing Asset, or Inbox provenance link"
        )
    return errors




def asset_metadata_errors(notes: list[Path]) -> list[str]:
    errors: list[str] = []
    for path in notes:
        metadata, parse_error = load_frontmatter(path)
        if parse_error or metadata is None or metadata.get("type") != "source":
            continue

        assets = metadata.get("assets", [])
        if not isinstance(assets, list):
            continue
        seen_paths: set[str] = set()
        for index, asset_info in enumerate(assets):
            prefix = f"{relative(path)}: assets[{index}]"
            if not isinstance(asset_info, dict):
                continue
            raw_path = asset_info.get("path")
            if isinstance(raw_path, str):
                normalized_path = raw_path.casefold()
                if normalized_path in seen_paths:
                    errors.append(f"{prefix}: duplicate asset path '{raw_path}'")
                    continue
                seen_paths.add(normalized_path)
            asset_path = safe_asset_path(raw_path)
            if asset_path is None:
                errors.append(f"{prefix}: unsafe asset path")
                continue
            if asset_path.is_symlink() or not asset_path.is_file():
                errors.append(f"{prefix}: missing asset '{raw_path}'")
                continue

            expected_hash = asset_info.get("sha256")
            if not isinstance(expected_hash, str):
                errors.append(f"{prefix}: SHA-256 is required for readable asset")
                continue
            try:
                actual_hash = file_sha256(asset_path)
            except OSError:
                errors.append(f"{prefix}: missing asset '{raw_path}'")
                continue
            if expected_hash != actual_hash:
                errors.append(f"{prefix}: asset SHA-256 mismatch")
    return errors


def embedded_asset_errors(paths: list[Path]) -> list[str]:
    errors: list[str] = []
    for source_path in paths:
        text = markdown_without_fenced_code(
            source_path.read_text(encoding="utf-8")
        )
        raw_targets = list(ASSET_EMBED_RE.findall(text))
        raw_targets.extend(WIKILINK_RE.findall(text))
        raw_targets.extend(markdown_asset_targets(text))
        targets = list(dict.fromkeys(normalize_asset_target(raw) for raw in raw_targets))

        metadata, parse_error = load_frontmatter(source_path)
        is_source = not parse_error and metadata is not None and metadata.get("type") == "source"
        declared_assets: set[str] = set()
        if is_source:
            assets = metadata.get("assets", [])
            if isinstance(assets, list):
                declared_assets = {
                    normalize_asset_target(asset.get("path"))
                    for asset in assets
                    if isinstance(asset, dict) and isinstance(asset.get("path"), str)
                }

        for target in targets:
            if not target.startswith("Assets/") or asset_readme_target(target):
                continue
            asset_path = safe_asset_path(target)
            if asset_path is None:
                errors.append(f"{relative(source_path)}: unsafe asset path '{target}'")
            elif asset_path.is_symlink() or not asset_path.is_file():
                errors.append(f"{relative(source_path)}: missing asset '{target}'")
            elif is_source and target not in declared_assets:
                errors.append(
                    f"{relative(source_path)}: Source Asset reference '{target}' "
                    "is not declared in assets"
                )
    return errors


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
        if metadata.get("type") == "source":
            status = metadata.get("status")
            review_status = metadata.get("review_status")
            reviewed = metadata.get("reviewed")
            state_error = False
            if status == "processing" and (
                review_status != "needs-review" or reviewed is not None
            ):
                state_error = True
            if status == "captured" and (
                review_status != "reviewed" or reviewed is None
            ):
                state_error = True
            if review_status == "needs-review" and reviewed is not None:
                state_error = True
            if review_status == "reviewed" and reviewed is None:
                state_error = True
            if state_error:
                errors.append(
                    f"{relative(path)}: Source review state is inconsistent"
                )
            source_url = metadata.get("source_url")
            if source_url != "" and not valid_source_url(source_url):
                errors.append(
                    f"{relative(path)}: source_url: must be an absolute HTTP(S) "
                    "URL with a hostname"
                )
            if "processed" in metadata:
                errors.append(
                    f"{relative(path)}: Source uses removed 'processed' field"
                )
            errors.extend(
                f"{relative(path)}: {error}"
                for error in source_provenance_errors(metadata)
            )


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
                    continue
                if target.startswith("Sources/"):
                    target_path = ROOT / f"{target}.md"
                    if (
                        target_path.is_file()
                        and target_path.resolve().is_relative_to(
                            (ROOT / "Sources").resolve()
                        )
                    ):
                        source_metadata, source_error = load_frontmatter(target_path)
                        if (
                            not source_error
                            and source_metadata is not None
                            and (
                                source_metadata.get("status") != "captured"
                                or source_metadata.get("review_status") != "reviewed"
                                or source_metadata.get("reviewed") is None
                            )
                        ):
                            errors.append(
                                f"{relative(path)}: Concept source must be "
                                f"owner-reviewed before use (found '{source}')"
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


def normalize_asset_target(raw: str) -> str:
    target = raw.strip()
    if target.startswith("<") and target.endswith(">"):
        target = target[1:-1]
    target = target.split("|", 1)[0].split("#", 1)[0].split("^", 1)[0]
    target = unquote(target).replace("\\", "/")
    return target.strip().strip("/")


def markdown_asset_targets(text: str) -> list[str]:
    return [
        match.group("angle") or match.group("plain")
        for match in MARKDOWN_ASSET_LINK_RE.finditer(text)
    ]


def asset_readme_target(target: str) -> bool:
    return target.casefold() in {"assets/readme", "assets/readme.md"}


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
        text = markdown_without_fenced_code(
            source_path.read_text(encoding="utf-8")
        )
        for match in WIKILINK_RE.finditer(text):
            raw_target = match.group(1)
            asset_target = normalize_asset_target(raw_target)
            if (
                asset_target.startswith("Assets/")
                and not asset_readme_target(asset_target)
            ):
                continue
            target = normalize_target(raw_target)
            if not target or target.startswith("#"):
                continue
            if "://" in target:
                continue
            if "/" in target:
                if target.casefold() not in by_vault_path:
                    errors.append(
                        f"{relative(source_path)}: unresolved wikilink [[{raw_target}]]"
                    )
            else:
                matches = by_stem.get(target.casefold(), [])
                if not matches:
                    errors.append(
                        f"{relative(source_path)}: unresolved wikilink [[{raw_target}]]"
                    )
                elif len(matches) > 1:
                    choices = ", ".join(relative(item) for item in matches)
                    errors.append(
                        f"{relative(source_path)}: ambiguous wikilink [[{raw_target}]]; "
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

    if not config_path.exists():
        errors.append(f"{relative(config_path)}: missing .codex/config.toml")
    else:
        try:
            config = tomllib.loads(config_path.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as exc:
            errors.append(f"{relative(config_path)}: invalid TOML: {exc}")
        else:
            expected_root = {
                "sandbox_mode": "workspace-write",
                "approval_policy": "on-request",
            }
            for field, expected in expected_root.items():
                if config.get(field) != expected:
                    errors.append(
                        f"{relative(config_path)}: {field} must remain {expected!r}"
                    )
            for field in ("model", "model_reasoning_effort"):
                value = config.get(field)
                if field in config and (
                    not isinstance(value, str) or not value.strip()
                ):
                    errors.append(
                        f"{relative(config_path)}: {field} must be a non-empty string when set"
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

        for field in ("model", "model_reasoning_effort"):
            value = data.get(field)
            if field in data and (
                not isinstance(value, str) or not value.strip()
            ):
                errors.append(
                    f"{relative(path)}: {field} must be a non-empty string when set"
                )

        sandbox = data.get("sandbox_mode")
        if sandbox != "read-only":
            errors.append(f"{relative(path)}: custom vault agents must be read-only")
        approval = data.get("approval_policy")
        if approval != "never":
            errors.append(
                f"{relative(path)}: approval_policy must remain 'never' for read-only custom agents"
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
    all_paths = all_note_paths()
    errors = []
    errors.extend(schema_errors(notes))
    errors.extend(asset_metadata_errors(notes))
    errors.extend(embedded_asset_errors(all_paths))
    errors.extend(wikilink_errors(all_paths))
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
