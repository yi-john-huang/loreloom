#!/usr/bin/env python3
"""Validate managed note frontmatter and Obsidian wikilinks."""

from __future__ import annotations

from html import unescape
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

LOW_FIDELITY_CAPTURE_MODES = frozenset(
    {"unknown", "paraphrased", "reference-only"}
)
CAPTURE_METHODS = frozenset(
    {
        "asset",
        "url-reference",
        "web-clipper",
        "manual-entry",
        "file-extraction",
        "ocr",
        "transcription",
        "import",
        "mixed",
    }
)
CAPTURE_MODES = frozenset(
    {
        "preserved-original",
        "verbatim-excerpt",
        "extracted",
        "transcribed",
        "paraphrased",
        "firsthand-observation",
        "reference-only",
        "unknown",
        "mixed",
    }
)
CAPTURE_BOUNDARY_LABELS = (
    "Capture method",
    "Capture mode",
    "Original evidence preserved",
    "Verbatim material",
    "Extracted or transcribed material",
    "Paraphrased material",
    "Unknown or unavailable evidence",
)
CONCRETE_BOUNDARY_LABELS = CAPTURE_BOUNDARY_LABELS[2:]
LOCATOR_RE = re.compile(
    r"(?P<passage>\S(?:.*\S)?)\s+(?:—|–|-)\s*"
    r"(?:page|timestamp|frame|line|section|region)"
    r"(?:\s+|:\s*)(?P<value>\S.*)$",
    re.IGNORECASE,
)
TIMESTAMP_LOCATOR_RE = re.compile(
    r"(?P<passage>\S(?:.*\S)?)\s+(?:—|–|-)\s*timestamp"
    r"(?:\s+|:\s*)(?P<value>\S.*)$",
    re.IGNORECASE,
)
COMMONMARK_RAW_TAG_RE = re.compile(
    r"^<(?P<tag>script|pre|style|textarea)(?=[ \t>]|$)",
    re.IGNORECASE,
)
COMMONMARK_BLOCK_TAG_RE = re.compile(
    r"^</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|"
    r"col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|"
    r"footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|"
    r"link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|"
    r"section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)"
    r"(?=[ \t]|/?>|$)",
    re.IGNORECASE,
)
COMMONMARK_ATTRIBUTE_PATTERN = (
    r"[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:[^ \t\n\"'=<>`]+|'[^']*'|\"[^\"]*\"))?"
)
COMMONMARK_OPEN_TAG_PATTERN = (
    r"<[A-Za-z][A-Za-z0-9-]*"
    rf"(?:[ \t]+{COMMONMARK_ATTRIBUTE_PATTERN})*[ \t]*/?>"
)
COMMONMARK_CLOSE_TAG_PATTERN = r"</[A-Za-z][A-Za-z0-9-]*[ \t]*>"
COMMONMARK_COMPLETE_TAG_RE = re.compile(
    rf"^(?:{COMMONMARK_OPEN_TAG_PATTERN}|{COMMONMARK_CLOSE_TAG_PATTERN})[ \t]*$"
)
INLINE_HTML_TAG_RE = re.compile(
    rf"(?:{COMMONMARK_OPEN_TAG_PATTERN}|{COMMONMARK_CLOSE_TAG_PATTERN})"
)
INLINE_HTML_COMMENT_RE = re.compile(r"<!--.*?(?:-->|$)", re.DOTALL)



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


ATX_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]+|$)")
SETEXT_HEADING_RE = re.compile(r"^ {0,3}(?:=+|-+)[ \t]*$")
THEMATIC_BREAK_RE = re.compile(
    r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$"
)
MARKDOWN_LIST_MARKER_RE = re.compile(
    r"^ {0,3}(?:[-+*]|\d{1,9}[.)])(?:[ \t]+(?P<content>.*)|[ \t]*$)"
)
MARKDOWN_LIST_CONTAINER_RE = re.compile(
    r"^(?P<indent> {0,3})(?P<marker>[-+*]|\d{1,9}[.)])"
    r"(?P<spaces>[ \t]+)(?P<content>.*)$"
)


def markdown_paragraph_open_after(line: str, was_open: bool) -> bool:
    """Return whether CommonMark leaves a paragraph open after this line."""
    if not line.strip() or ATX_HEADING_RE.match(line) or THEMATIC_BREAK_RE.fullmatch(line):
        return False
    if was_open and SETEXT_HEADING_RE.fullmatch(line):
        return False
    if marker := MARKDOWN_LIST_MARKER_RE.match(line):
        return bool(marker.group("content") and marker.group("content").strip())
    if quote := re.match(r"^ {0,3}>\s?(.*)$", line):
        return markdown_paragraph_open_after(quote.group(1), False)
    if not was_open and re.match(r"^(?: {4}|\t)", line):
        return False
    return True


def markdown_container_content(
    line: str, container_indent: int, paragraph_open: bool
) -> tuple[str, int]:
    """Return line content relative to an active CommonMark list container."""
    physical_indent = len(line) - len(line.lstrip(" "))
    if container_indent and physical_indent >= container_indent:
        relative = line[container_indent:]
    else:
        if (
            container_indent
            and physical_indent < container_indent
            and (
                MARKDOWN_LIST_MARKER_RE.match(line)
                or (
                    line.strip()
                    and not (
                        paragraph_open
                        and markdown_paragraph_open_after(line, True)
                    )
                )
            )
        ):
            container_indent = 0
        relative = line

    quote_prefix = False
    while quote := re.match(r"^ {0,3}>\s?(.*)$", relative):
        quote_prefix = True
        relative = quote.group(1)

    if marker := MARKDOWN_LIST_CONTAINER_RE.match(relative):
        spaces = marker.group("spaces")
        content = marker.group("content")
        padding = len(spaces) if len(spaces) <= 4 and content.strip() else 1
        content_offset = (
            len(marker.group("indent")) + len(marker.group("marker")) + padding
        )
        if not quote_prefix:
            container_indent += content_offset
        relative = relative[content_offset:]

    return relative, container_indent




def markdown_without_hidden_blocks(text: str) -> str:
    """Mask fenced code and CommonMark raw HTML while preserving newlines."""
    masked: list[str] = []
    fence_character: str | None = None
    fence_length = 0
    html_end_re: re.Pattern[str] | None = None
    html_until_blank = False
    paragraph_open = False
    container_indent = 0
    fence_opening_re = re.compile(r"^ {0,3}(?P<fence>`{3,}|~{3,})")
    for line in text.splitlines(keepends=True):
        content = line.rstrip("\r\n")
        newline = line[len(content) :]
        structural, container_indent = markdown_container_content(
            content, container_indent, paragraph_open
        )
        if html_end_re is not None:
            masked.append(newline)
            if html_end_re.search(structural):
                html_end_re = None
            continue
        if html_until_blank:
            masked.append(newline)
            if not content.strip():
                html_until_blank = False
            continue
        if fence_character is not None:
            closing_re = re.compile(
                rf"^ {{0,3}}{re.escape(fence_character)}"
                rf"{{{fence_length},}}[ \t]*$"
            )
            if closing_re.fullmatch(structural):
                fence_character = None
                fence_length = 0
            masked.append(newline)
            continue

        indent = len(structural) - len(structural.lstrip(" "))
        stripped = structural[indent:] if indent <= 3 else ""
        raw_tag = COMMONMARK_RAW_TAG_RE.match(stripped)
        if raw_tag:
            html_end_re = re.compile(
                rf"</{re.escape(raw_tag.group('tag'))}\s*>",
                re.IGNORECASE,
            )
        elif stripped.startswith("<!--"):
            html_end_re = re.compile(r"-->")
        elif stripped.startswith("<?"):
            html_end_re = re.compile(r"\?>")
        elif stripped.startswith("<![CDATA["):
            html_end_re = re.compile(r"\]\]>")
        elif (
            len(stripped) > 2
            and stripped.startswith("<!")
            and "A" <= stripped[2] <= "Z"
        ):
            html_end_re = re.compile(r">")
        elif COMMONMARK_BLOCK_TAG_RE.match(stripped):
            html_until_blank = True
        elif (
            COMMONMARK_COMPLETE_TAG_RE.fullmatch(stripped)
            and not paragraph_open
        ):
            html_until_blank = True
        else:
            fence = fence_opening_re.match(structural)
            if fence and not (
                fence.group("fence").startswith("`")
                and "`" in structural[fence.end() :]
            ):
                marker = fence.group("fence")
                fence_character = marker[0]
                paragraph_open = False
                fence_length = len(marker)
                masked.append(newline)
            else:
                masked.append(line)
                paragraph_open = markdown_paragraph_open_after(
                    structural, paragraph_open
                )
            continue

        paragraph_open = False
        masked.append(newline)
        if html_end_re is not None and html_end_re.search(stripped):
            html_end_re = None

    return "".join(masked)

def markdown_section_lines(text: str, heading: str) -> list[str]:
    """Return visible body lines beneath an exact level-two Markdown heading."""
    frontmatter = FRONTMATTER_RE.match(text)
    if frontmatter:
        text = text[frontmatter.end() :]
    visible = markdown_without_hidden_blocks(text)
    lines = visible.splitlines()
    heading_re = re.compile(rf"^ {{0,3}}## {re.escape(heading)}[ \t]*$")
    start: int | None = None
    for index, line in enumerate(lines):
        if heading_re.fullmatch(line):
            start = index + 1
            break
    if start is None:
        return []
    section: list[str] = []
    for line in lines[start:]:
        if re.match(r"^ {0,3}#{1,2}(?:\s|$)", line):
            break
        section.append(line)
    return section


def markdown_list_items(lines: list[str]) -> list[str]:
    """Return CommonMark list items with visible paragraph continuations joined."""
    items: list[str] = []
    current: list[str] = []
    blank_after_item = False
    fence_character: str | None = None
    fence_length = 0

    def flush() -> None:
        if current:
            items.append(" ".join(current).strip())
            current.clear()

    for line in lines:
        stripped = line.lstrip(" \t")
        if fence_character is not None:
            if re.fullmatch(
                rf"{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                stripped,
            ):
                fence_character = None
                fence_length = 0
            continue

        if match := MARKDOWN_LIST_MARKER_RE.match(line):
            flush()
            if content := match.group("content"):
                current.append(content.strip())
            blank_after_item = False
            continue
        if not current:
            continue
        if not line.strip():
            blank_after_item = True
            continue

        indent = len(line) - len(stripped)
        if indent >= 2 and (
            fence := re.match(r"(?P<marker>`{3,}|~{3,})", stripped)
        ):
            marker = fence.group("marker")
            fence_character = marker[0]
            fence_length = len(marker)
            continue
        if indent >= 2:
            if not (blank_after_item and indent >= 6):
                current.append(stripped)
            blank_after_item = False
            continue
        if (
            not blank_after_item
            and not MARKDOWN_LIST_MARKER_RE.match(line)
            and not re.match(r"^ {0,3}>", line)
            and markdown_paragraph_open_after(line, True)
        ):
            current.append(line.strip())
            continue
        flush()
        blank_after_item = False

    flush()
    return items


def markdown_without_inline_comments(value: str) -> str:
    return INLINE_HTML_COMMENT_RE.sub("", value)


def visible_markdown_text(value: str) -> str:
    content = markdown_without_inline_comments(value)
    content = INLINE_HTML_TAG_RE.sub("", content)
    content = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", content)
    content = re.sub(r"!?\[([^\]]*)\]\[[^\]]*\]", r"\1", content)
    content = re.sub(r"[`*_~]", "", unescape(content))
    return content


def placeholder_value(value: str) -> bool:
    stripped = value.strip()
    return bool(
        not stripped
        or stripped.casefold() in {"none", "n/a"}
        or re.fullmatch(r"<!--.*?-->", stripped, re.DOTALL)
        or re.fullmatch(r"\{\{.*?\}\}", stripped, re.DOTALL)
        or re.fullmatch(r"<[^<>]+>", stripped, re.DOTALL)
    )

def concrete_locator(pattern: re.Pattern[str], value: str) -> bool:
    match = pattern.search(markdown_without_inline_comments(value))
    return bool(
        match
        and not placeholder_value(match.group("passage"))
        and any(character.isalnum() for character in match.group("passage"))
        and not placeholder_value(match.group("value"))
    )


def substantive_section_line(line: str) -> bool:
    if re.match(r"^(?: {4}|\t)", line):
        return False
    content = line
    container_re = re.compile(
        r"^\s*(?:>\s?|(?:[-*+]|\d+[.)])(?:\s+|$)|\[[ xX]\](?:\s+|$))"
    )
    while (unwrapped := container_re.sub("", content, count=1)) != content:
        content = unwrapped
    content = content.strip()
    if re.match(r"^#{1,6}(?:\s|$)", content):
        return False
    if re.fullmatch(r"(?:\*\s*){3,}|(?:-\s*){3,}|(?:_\s*){3,}", content):
        return False
    return any(character.isalnum() for character in visible_markdown_text(content))


def capture_boundary_values(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in markdown_list_items(
        markdown_section_lines(text, "Capture boundary")
    ):
        match = re.match(r"^([^:]+):\s*(.*)$", item)
        if match and match.group(1) in CAPTURE_BOUNDARY_LABELS:
            values[match.group(1)] = match.group(2).strip()
    return values


def key_passage_items(text: str) -> list[str]:
    return [
        item
        for item in markdown_list_items(markdown_section_lines(text, "Key passages"))
        if not placeholder_value(item)
    ]


def quoted_item(value: str) -> bool:
    visible = markdown_without_inline_comments(value)
    return bool(
        re.search(r'"[^"\n]+"', visible)
        or re.search(r"“[^”\n]+”", visible)
    )


def source_assets(metadata: dict[str, Any]) -> list[dict[str, Any]]:
    assets = metadata.get("assets")
    if not isinstance(assets, list):
        return []
    return [asset for asset in assets if isinstance(asset, dict)]


def has_audio_video_provenance(metadata: dict[str, Any]) -> bool:
    for asset in source_assets(metadata):
        media_type = asset.get("media_type")
        if isinstance(media_type, str) and media_type.startswith(("audio/", "video/")):
            return True
    return bool(
        valid_source_url(metadata.get("source_url"))
        and metadata.get("source_type") in {"video", "podcast"}
    )


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




def source_capture_fidelity_errors(
    path: Path, metadata: dict[str, Any], text: str
) -> list[str]:
    del path
    errors: list[str] = []
    missing = sorted(
        field
        for field in ("capture_method", "capture_mode")
        if field not in metadata
    )
    if missing:
        errors.append(
            "Source missing required capture classification field(s): "
            f"{', '.join(missing)}; classify manually (no value was inferred)"
        )
        return errors

    method = metadata.get("capture_method")
    mode = metadata.get("capture_mode")
    if method not in CAPTURE_METHODS or mode not in CAPTURE_MODES:
        return errors

    assets = source_assets(metadata)
    has_asset = bool(assets)
    has_primary_asset = any(asset.get("role") == "primary" for asset in assets)
    has_extracted_asset = any(
        asset.get("extraction_status") in {"extracted", "partial"}
        for asset in assets
    )
    boundary = capture_boundary_values(text)
    extracted_boundary = boundary.get("Extracted or transcribed material", "")
    paraphrased_boundary = boundary.get("Paraphrased material", "")
    requires_boundary = (
        method in {"file-extraction", "ocr", "transcription", "mixed"}
        or mode in {"extracted", "transcribed", "paraphrased", "mixed"}
    )
    if requires_boundary and not all(
        label in boundary for label in CAPTURE_BOUNDARY_LABELS
    ):
        errors.append(
            "capture classification requires all exact Capture Boundary labels"
        )
    concrete_boundaries = [
        label
        for label in CONCRETE_BOUNDARY_LABELS
        if label in boundary and not placeholder_value(boundary[label])
    ]
    passages = key_passage_items(text)

    if method == "asset" and not has_asset:
        errors.append("capture_method 'asset' requires a declared Asset")
    if method == "url-reference" and not valid_source_url(metadata.get("source_url")):
        errors.append("capture_method 'url-reference' requires a valid source_url")
    if method in {"file-extraction", "ocr"}:
        if not has_extracted_asset:
            errors.append(
                f"capture_method '{method}' requires an extracted or partial Asset"
            )
        if placeholder_value(extracted_boundary):
            errors.append(
                f"capture_method '{method}' requires a non-empty "
                "Extracted or transcribed material Capture Boundary entry"
            )
    if method == "transcription":
        if not has_audio_video_provenance(metadata):
            errors.append(
                "capture_method 'transcription' requires audio/video provenance"
            )
        if placeholder_value(extracted_boundary):
            errors.append(
                "capture_method 'transcription' requires a non-empty "
                "Extracted or transcribed material Capture Boundary entry"
            )
    if method == "mixed" and len(concrete_boundaries) < 2:
        errors.append(
            "capture_method 'mixed' requires at least two concrete Capture Boundary entries"
        )

    if mode == "preserved-original" and not has_primary_asset:
        errors.append(
            "capture_mode 'preserved-original' requires a primary Asset"
        )
    if mode == "reference-only" and not valid_source_url(metadata.get("source_url")):
        errors.append("capture_mode 'reference-only' requires a valid source_url")
    if mode == "verbatim-excerpt" and not any(
        concrete_locator(LOCATOR_RE, item) for item in passages
    ):
        errors.append(
            "capture_mode 'verbatim-excerpt' requires an exact Key passages locator"
        )
    if mode == "extracted":
        if not has_extracted_asset:
            errors.append(
                "capture_mode 'extracted' requires an extracted or partial Asset"
            )
        if placeholder_value(extracted_boundary):
            errors.append(
                "capture_mode 'extracted' requires a non-empty "
                "Extracted or transcribed material Capture Boundary entry"
            )
    if mode == "transcribed":
        if not has_audio_video_provenance(metadata):
            errors.append("capture_mode 'transcribed' requires audio/video provenance")
        if placeholder_value(extracted_boundary):
            errors.append(
                "capture_mode 'transcribed' requires a non-empty "
                "Extracted or transcribed material Capture Boundary entry"
            )
        if any(
            quoted_item(item)
            and not concrete_locator(TIMESTAMP_LOCATOR_RE, item)
            for item in passages
        ):
            errors.append(
                "quoted transcribed Key passages require a timestamp locator"
            )
    if (
        mode == "firsthand-observation"
        and metadata.get("source_type") != "personal-observation"
    ):
        errors.append(
            "capture_mode 'firsthand-observation' requires "
            "source_type 'personal-observation'"
        )
    if mode == "paraphrased":
        if placeholder_value(paraphrased_boundary):
            errors.append(
                "capture_mode 'paraphrased' requires a non-empty "
                "Paraphrased material Capture Boundary entry"
            )
        if any(quoted_item(item) for item in passages):
            errors.append(
                "capture_mode 'paraphrased' must not use quoted Key passages"
            )
    if mode == "mixed" and len(concrete_boundaries) < 2:
        errors.append(
            "capture_mode 'mixed' requires at least two concrete Capture Boundary entries"
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
            text = path.read_text(encoding="utf-8")
            errors.extend(
                f"{relative(path)}: {error}"
                for error in source_capture_fidelity_errors(path, metadata, text)
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


def concept_capture_fidelity_warnings(notes: list[Path]) -> list[str]:
    warnings: list[str] = []
    for path in notes:
        metadata, parse_error = load_frontmatter(path)
        if (
            parse_error
            or metadata is None
            or metadata.get("type") != "concept"
            or metadata.get("status") not in {"draft", "evergreen"}
        ):
            continue

        evidence = metadata.get("sources")
        if not isinstance(evidence, list):
            continue
        modes: set[str] = set()
        all_sources = bool(evidence)
        all_sources_low = bool(evidence)
        skip_warning = False
        for source in evidence:
            if not isinstance(source, str):
                skip_warning = True
                break
            match = re.fullmatch(r"\[\[([^\[\]]+)\]\]", source)
            if not match:
                skip_warning = True
                break
            target = normalize_target(match.group(1))
            if target.startswith("Daily/"):
                daily_path = ROOT / f"{target}.md"
                if not daily_path.is_file():
                    skip_warning = True
                    break
                all_sources = False
                all_sources_low = False
                continue
            if not target.startswith("Sources/"):
                skip_warning = True
                break
            target_path = ROOT / f"{target}.md"
            if not target_path.is_file():
                skip_warning = True
                break
            source_metadata, source_error = load_frontmatter(target_path)
            if source_error or source_metadata is None:
                skip_warning = True
                break
            capture_mode = source_metadata.get("capture_mode")
            if not isinstance(capture_mode, str):
                skip_warning = True
                break
            if capture_mode in LOW_FIDELITY_CAPTURE_MODES:
                modes.add(capture_mode)
            else:
                all_sources_low = False

        if skip_warning or not modes:
            continue
        limitation_lines = markdown_section_lines(
            path.read_text(encoding="utf-8"), "Evidence limitations"
        )
        if any(substantive_section_line(line) for line in limitation_lines):
            continue
        if (
            metadata.get("status") == "evergreen"
            and all_sources
            and all_sources_low
        ):
            warnings.append(
                f"{relative(path)}: evergreen Concept relies exclusively on unknown, "
                "paraphrased, or reference-only Sources; review and retain an "
                "Evidence limitations section"
            )
        else:
            warnings.append(
                f"{relative(path)}: Concept cites {', '.join(sorted(modes))} Source "
                "evidence; add and review an Evidence limitations section"
            )
    return warnings


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
    warnings = concept_capture_fidelity_warnings(notes)

    if errors:
        print(f"Vault validation failed with {len(errors)} error(s):")
        for error in sorted(set(errors)):
            print(f"- {error}")

    if warnings:
        print("Vault validation warning(s):")
        for warning in sorted(set(warnings)):
            print(f"- {warning}")

    if errors:
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
