#!/usr/bin/env python3
"""Validate a proposed vault diff against Loreloom authority boundaries."""

from __future__ import annotations

import sys


if __name__ == "__main__" and not sys.flags.isolated:
    print(
        "run this approval tool with an isolated interpreter: "
        "python -I scripts/validate_change.py",
        file=sys.stderr,
    )
    raise SystemExit(2)


import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlparse

try:
    import yaml
    from jsonschema import Draft202012Validator, FormatChecker
except ImportError as exc:
    print(
        "Missing validation dependency. Run: uv sync --locked --dev, "
        "then use uv run python -I scripts/validate_change.py",
        file=sys.stderr,
    )
    raise SystemExit(2) from exc
SOURCE_URL_RE = re.compile(
    r"^https?://(?:[^/?#\s@]+@)?(?:\[[^\]\\\s]+\]|[^/?#\s:@]+)"
    r"(?::[0-9]+)?(?:[/?#][^\s]*)?$",
    re.IGNORECASE,
)




TOOL_ROOT = Path(__file__).resolve().parent.parent
ROOT = TOOL_ROOT
FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*(?:\n|\Z)", re.DOTALL)
APPROVAL_PRIVATE_KEY_ENV = "LORELOOM_APPROVAL_PRIVATE_KEY"
APPROVAL_PUBLIC_KEY_NAME = "approval-public-key.pem"
APPROVAL_PUBLIC_KEY_DIGEST_NAME = "approval-public-key.sha256"
RECEIPT_SIGNING_FIELDS = (
    "version",
    "approval_id",
    "base_commit",
    "snapshot_sha256",
    "allowed_paths",
    "operations",
    "approved_diff_sha256",
    "expires_at",
)
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


class ManifestError(RuntimeError):
    def __init__(self, path: str, reason: str) -> None:
        self.path = path
        self.reason = reason
        super().__init__(f"{path}: {reason}")


def manifest_relative(candidate: Path) -> str:
    try:
        return candidate.relative_to(ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()


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

def configure_target_root(value: str | None) -> str | None:
    """Point validation at a Git worktree while retaining this script's tool root."""
    global ROOT

    candidate = TOOL_ROOT if value is None else Path(value).expanduser()
    try:
        resolved = candidate.resolve(strict=True)
    except OSError:
        return "target root is unavailable"
    if not resolved.is_dir():
        return "target root must be a directory"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=resolved,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return "target root is not a Git worktree"
    if result.returncode != 0:
        return "target root is not a Git worktree"
    try:
        worktree_root = Path(result.stdout.strip()).resolve(strict=True)
    except OSError:
        return "target root is unavailable"
    if worktree_root != resolved:
        return "--target-root must name the Git worktree root"
    ROOT = resolved
    return None


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


def normalize_yaml_scalars(value: Any) -> Any:
    """Convert PyYAML date objects to the ISO strings stored in Markdown."""
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: normalize_yaml_scalars(item) for key, item in value.items()}
    if isinstance(value, list):
        return [normalize_yaml_scalars(item) for item in value]
    return value


def parse_frontmatter(text: str) -> tuple[dict[str, Any] | None, str | None]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        return None, None
    try:
        value = normalize_yaml_scalars(yaml.safe_load(match.group(1)))
    except yaml.YAMLError:
        return None, "invalid YAML frontmatter"
    if not isinstance(value, dict):
        return None, "frontmatter must be a mapping"
    return value, None


def is_unreviewed_source(
    path: str,
    text: str | None,
    manifest_files: dict[str, dict[str, str]],
) -> bool:
    metadata, parse_error = (
        parse_frontmatter(text) if text is not None else (None, None)
    )
    return bool(
        not parse_error
        and metadata
        and metadata.get("type") == "source"
        and metadata.get("status") == "processing"
        and metadata.get("review_status") == "needs-review"
        and metadata.get("reviewed") is None
        and not source_contract_errors(path, metadata, manifest_files)
    )






def base_text(base: str, path: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", "show", f"{base}:{path}"],
            cwd=ROOT,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except OSError:
        return None
    return result.stdout if result.returncode == 0 else None




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


def canonical_mode(st_mode: int) -> str:
    return f"0o{stat.S_IMODE(st_mode):04o}"


def _regular_file_digest(
    candidate: str | Path,
    path: str,
    *,
    directory_fd: int | None = None,
    initial: os.stat_result | None = None,
) -> tuple[os.stat_result, str]:
    def target_lstat() -> os.stat_result:
        if directory_fd is None:
            return Path(candidate).lstat()
        return os.stat(candidate, dir_fd=directory_fd, follow_symlinks=False)

    if initial is None:
        try:
            initial = target_lstat()
        except FileNotFoundError:
            raise
        except OSError as exc:
            raise ManifestError(path, "repository file is unreadable") from exc
    if stat.S_ISLNK(initial.st_mode):
        raise ManifestError(path, "repository symlinks are not allowed")
    if not stat.S_ISREG(initial.st_mode):
        raise ManifestError(path, "unsupported repository file type")

    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        if directory_fd is None:
            descriptor = os.open(candidate, flags)
        else:
            descriptor = os.open(candidate, flags, dir_fd=directory_fd)
    except OSError as exc:
        try:
            replaced = target_lstat()
        except OSError:
            replaced = None
        if replaced is not None and stat.S_ISLNK(replaced.st_mode):
            raise ManifestError(path, "repository symlinks are not allowed") from exc
        raise ManifestError(path, "repository file is unreadable") from exc

    def stability_tuple(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )

    try:
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or (opened.st_dev, opened.st_ino) != (initial.st_dev, initial.st_ino)
            ):
                raise ManifestError(path, "repository file changed while hashing")
            recorded = stability_tuple(opened)
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            final_descriptor = os.fstat(stream.fileno())
    except ManifestError:
        raise
    except OSError as exc:
        raise ManifestError(path, "repository file is unreadable") from exc

    try:
        final_path = target_lstat()
    except OSError as exc:
        raise ManifestError(path, "repository file changed while hashing") from exc
    if (
        stability_tuple(initial) != recorded
        or stability_tuple(final_descriptor) != recorded
        or stability_tuple(final_path) != recorded
    ):
        raise ManifestError(path, "repository file changed while hashing")
    return opened, digest


def regular_file_digest(candidate: Path) -> tuple[os.stat_result, str]:
    return _regular_file_digest(candidate, manifest_relative(candidate))


def file_sha256(candidate: Path) -> str:
    return regular_file_digest(candidate)[1]


def filesystem_entry(candidate: Path) -> dict[str, str] | None:
    path = manifest_relative(candidate)
    try:
        metadata = candidate.lstat()
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ManifestError(path, "repository file is unreadable") from exc
    if stat.S_ISDIR(metadata.st_mode):
        return None
    if stat.S_ISLNK(metadata.st_mode):
        raise ManifestError(path, "repository symlinks are not allowed")
    if not stat.S_ISREG(metadata.st_mode):
        raise ManifestError(path, "unsupported repository file type")
    stable_metadata, digest = _regular_file_digest(
        candidate,
        path,
        initial=metadata,
    )
    return {
        "kind": "file",
        "mode": canonical_mode(stable_metadata.st_mode),
        "sha256": digest,
    }


def filesystem_manifest(
    extra_paths: Iterable[str] = (),
) -> dict[str, dict[str, str]]:
    extra_paths = tuple(extra_paths)
    for raw_path in extra_paths:
        if error := repository_output_error(raw_path):
            raise ValueError(f"{raw_path}: {error}")

    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
    )
    try:
        root_fd = os.open(ROOT, directory_flags)
    except OSError as exc:
        raise ManifestError(".", "repository directory is unreadable") from exc

    manifest: dict[str, dict[str, str]] = {}

    def directory_stability_tuple(
        metadata: os.stat_result,
    ) -> tuple[int, int, int, int, int, int]:
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )


    def child_metadata(
        directory_fd: int,
        name: str,
        path: str,
        unreadable: str,
    ) -> os.stat_result | None:
        try:
            return os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            return None
        except OSError as exc:
            raise ManifestError(path, unreadable) from exc

    def open_child_directory(
        directory_fd: int,
        name: str,
        relative_path: Path,
        initial: os.stat_result,
    ) -> int:
        label = relative_path.as_posix()
        try:
            child_fd = os.open(name, directory_flags, dir_fd=directory_fd)
        except OSError as exc:
            replaced = child_metadata(
                directory_fd,
                name,
                label,
                "repository directory is unreadable",
            )
            if replaced is not None and stat.S_ISLNK(replaced.st_mode):
                raise ManifestError(label, "repository symlinks are not allowed") from exc
            raise ManifestError(label, "repository directory is unreadable") from exc
        opened = os.fstat(child_fd)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or directory_stability_tuple(opened)
            != directory_stability_tuple(initial)
        ):
            os.close(child_fd)
            raise ManifestError(label, "repository directory changed while traversing")
        return child_fd

    def walk(directory_fd: int, relative_directory: Path) -> None:
        initial_directory = os.fstat(directory_fd)
        if not stat.S_ISDIR(initial_directory.st_mode):
            raise ManifestError(
                relative_directory.as_posix() or ".",
                "repository directory changed while traversing",
            )
        try:
            with os.scandir(directory_fd) as entries:
                ordered = sorted(entries, key=lambda entry: entry.name)
                for directory_entry in ordered:
                    relative_path = relative_directory / directory_entry.name
                    try:
                        metadata = directory_entry.stat(follow_symlinks=False)
                    except OSError as exc:
                        raise ManifestError(
                            relative_directory.as_posix() or ".",
                            "repository directory is unreadable",
                        ) from exc
                    if stat.S_ISLNK(metadata.st_mode):
                        raise ManifestError(
                            relative_path.as_posix(),
                            "repository symlinks are not allowed",
                        )
                    if is_runtime_only_path(relative_path):
                        continue
                    if stat.S_ISDIR(metadata.st_mode):
                        child_fd = open_child_directory(
                            directory_fd,
                            directory_entry.name,
                            relative_path,
                            metadata,
                        )
                        try:
                            walk(child_fd, relative_path)
                        finally:
                            os.close(child_fd)
                        final = child_metadata(
                            directory_fd,
                            directory_entry.name,
                            relative_path.as_posix(),
                            "repository directory is unreadable",
                        )
                        if final is not None and stat.S_ISLNK(final.st_mode):
                            raise ManifestError(
                                relative_path.as_posix(),
                                "repository symlinks are not allowed",
                            )
                        if (
                            final is None
                            or not stat.S_ISDIR(final.st_mode)
                            or directory_stability_tuple(final)
                            != directory_stability_tuple(metadata)
                        ):
                            raise ManifestError(
                                relative_path.as_posix(),
                                "repository directory changed while traversing",
                            )
                        continue
                    if not stat.S_ISREG(metadata.st_mode):
                        raise ManifestError(
                            relative_path.as_posix(),
                            "unsupported repository file type",
                        )
                    stable_metadata, digest = _regular_file_digest(
                        directory_entry.name,
                        relative_path.as_posix(),
                        directory_fd=directory_fd,
                        initial=metadata,
                    )
                    manifest[relative_path.as_posix()] = {
                        "kind": "file",
                        "mode": canonical_mode(stable_metadata.st_mode),
                        "sha256": digest,
                    }
                final_directory = os.fstat(directory_fd)
                if (
                    directory_stability_tuple(final_directory)
                    != directory_stability_tuple(initial_directory)
                ):
                    raise ManifestError(
                        relative_directory.as_posix() or ".",
                        "repository directory changed while traversing",
                    )
        except ManifestError:
            raise
        except OSError as exc:
            label = relative_directory.as_posix() or "."
            raise ManifestError(label, "repository directory is unreadable") from exc

    def descriptor_entry(relative_path: Path) -> dict[str, str] | None:
        current_fd = root_fd
        owned_fds: list[int] = []
        try:
            for index, part in enumerate(relative_path.parts[:-1]):
                traversed = Path(*relative_path.parts[: index + 1])
                metadata = child_metadata(
                    current_fd,
                    part,
                    traversed.as_posix(),
                    "repository directory is unreadable",
                )
                if metadata is None:
                    return None
                if stat.S_ISLNK(metadata.st_mode):
                    raise ManifestError(
                        traversed.as_posix(),
                        "repository symlinks are not allowed",
                    )
                if not stat.S_ISDIR(metadata.st_mode):
                    raise ManifestError(
                        traversed.as_posix(),
                        "unsupported repository file type",
                    )
                child_fd = open_child_directory(current_fd, part, traversed, metadata)
                owned_fds.append(child_fd)
                current_fd = child_fd

            name = relative_path.name
            metadata = child_metadata(
                current_fd,
                name,
                relative_path.as_posix(),
                "repository file is unreadable",
            )
            if metadata is None:
                return None
            if stat.S_ISDIR(metadata.st_mode):
                return None
            if stat.S_ISLNK(metadata.st_mode):
                raise ManifestError(
                    relative_path.as_posix(),
                    "repository symlinks are not allowed",
                )
            if not stat.S_ISREG(metadata.st_mode):
                raise ManifestError(
                    relative_path.as_posix(),
                    "unsupported repository file type",
                )
            stable_metadata, digest = _regular_file_digest(
                name,
                relative_path.as_posix(),
                directory_fd=current_fd,
                initial=metadata,
            )
            return {
                "kind": "file",
                "mode": canonical_mode(stable_metadata.st_mode),
                "sha256": digest,
            }
        finally:
            for descriptor in reversed(owned_fds):
                os.close(descriptor)

    try:
        walk(root_fd, Path())
        for raw_path in extra_paths:
            relative_path = Path(raw_path)
            entry = descriptor_entry(relative_path)
            if entry is not None:
                manifest[relative_path.as_posix()] = entry
    finally:
        os.close(root_fd)
    return dict(sorted(manifest.items()))


def manifest_bound_text(path: str, expected: dict[str, str]) -> str:
    if error := repository_output_error(path):
        raise ManifestError(path, error)
    relative_path = Path(path)
    directory_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_DIRECTORY", 0)
    )
    file_flags = (
        os.O_RDONLY
        | getattr(os, "O_CLOEXEC", 0)
        | getattr(os, "O_NOFOLLOW", 0)
    )

    try:
        root_fd = os.open(ROOT, directory_flags)
    except OSError as exc:
        raise ManifestError(".", "repository directory is unreadable") from exc

    current_fd = root_fd
    owned_fds: list[int] = []

    def target_metadata(name: str) -> os.stat_result:
        try:
            return os.stat(name, dir_fd=current_fd, follow_symlinks=False)
        except OSError as exc:
            raise ManifestError(path, "changed file is missing or unreadable") from exc

    def stability_tuple(
        metadata: os.stat_result,
    ) -> tuple[int, int, int, int, int, int]:
        return (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_mode,
            metadata.st_size,
            metadata.st_mtime_ns,
            metadata.st_ctime_ns,
        )

    try:
        for part in relative_path.parts[:-1]:
            metadata = target_metadata(part)
            if stat.S_ISLNK(metadata.st_mode):
                raise ManifestError(path, "repository symlinks are not allowed")
            if not stat.S_ISDIR(metadata.st_mode):
                raise ManifestError(path, "changed file parent is not a directory")
            try:
                child_fd = os.open(part, directory_flags, dir_fd=current_fd)
            except OSError as exc:
                raise ManifestError(
                    path,
                    "changed file parent is missing or unreadable",
                ) from exc
            opened = os.fstat(child_fd)
            if (
                not stat.S_ISDIR(opened.st_mode)
                or (opened.st_dev, opened.st_ino)
                != (metadata.st_dev, metadata.st_ino)
            ):
                os.close(child_fd)
                raise ManifestError(path, "changed file parent changed while reading")
            owned_fds.append(child_fd)
            current_fd = child_fd

        name = relative_path.name
        initial = target_metadata(name)
        if stat.S_ISLNK(initial.st_mode):
            raise ManifestError(path, "repository symlinks are not allowed")
        if not stat.S_ISREG(initial.st_mode):
            raise ManifestError(path, "changed path is not a regular file")
        try:
            descriptor = os.open(name, file_flags, dir_fd=current_fd)
        except OSError as exc:
            raise ManifestError(path, "changed file is missing or unreadable") from exc

        try:
            with os.fdopen(descriptor, "rb") as stream:
                opened = os.fstat(stream.fileno())
                if (
                    not stat.S_ISREG(opened.st_mode)
                    or (opened.st_dev, opened.st_ino)
                    != (initial.st_dev, initial.st_ino)
                ):
                    raise ManifestError(path, "changed file changed while reading")
                payload = stream.read()
                final_descriptor = os.fstat(stream.fileno())
        except ManifestError:
            raise
        except OSError as exc:
            raise ManifestError(path, "changed file is unreadable") from exc

        final_path = target_metadata(name)
        if (
            stability_tuple(initial) != stability_tuple(opened)
            or stability_tuple(final_descriptor) != stability_tuple(opened)
            or stability_tuple(final_path) != stability_tuple(opened)
        ):
            raise ManifestError(path, "changed file changed while reading")

        digest = hashlib.sha256(payload).hexdigest()
        if (
            expected.get("kind") != "file"
            or expected.get("mode") != canonical_mode(opened.st_mode)
            or expected.get("sha256") != digest
        ):
            raise ManifestError(path, "bytes do not match the captured manifest")
        try:
            return payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ManifestError(path, "changed Markdown file is not UTF-8") from exc
    finally:
        for descriptor in reversed(owned_fds):
            os.close(descriptor)
        os.close(root_fd)


def capture_semantic_evidence(
    after_files: dict[str, dict[str, str]],
    evidence_paths: set[str],
    allowed_paths: Iterable[str],
    base: str,
) -> tuple[dict[str, dict[str, str]], set[str], list[str]]:
    capture_paths = sorted(set(allowed_paths) | evidence_paths)
    semantic_only_paths = {
        path
        for path in evidence_paths
        if path not in after_files and is_runtime_only_path(Path(path))
    }
    semantic_files = filesystem_manifest(capture_paths)
    for path in sorted(semantic_only_paths):
        base_entry = base_file_entry(base, path)
        if base_entry is None:
            raise ManifestError(path, "evidence path is absent from the immutable base")
        if semantic_files.get(path) != base_entry:
            raise ManifestError(path, "evidence path differs from the immutable base")
    captured_change_files = {
        path: entry
        for path, entry in semantic_files.items()
        if path not in semantic_only_paths
    }
    if captured_change_files != after_files:
        raise ManifestError(".", "repository changed during semantic evidence capture")
    return semantic_files, semantic_only_paths, capture_paths


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
        serialized = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(serialized, dict) or set(serialized) != {
        "version",
        "base_commit",
        "allowed_paths",
        "files",
        "snapshot_sha256",
    }:
        return None
    data = dict(serialized)
    supplied_hash = data.pop("snapshot_sha256")
    if (
        not isinstance(supplied_hash, str)
        or not re.fullmatch(r"[0-9a-f]{64}", supplied_hash)
        or supplied_hash != snapshot_hash(data)
        or data.get("version") != 1
    ):
        return None

    base = data.get("base_commit")
    allowed_paths = data.get("allowed_paths")
    files = data.get("files")
    if (
        not isinstance(base, str)
        or not re.fullmatch(r"[0-9a-f]{40}", base)
        or not isinstance(allowed_paths, list)
        or not all(isinstance(item, str) for item in allowed_paths)
        or allowed_paths != sorted(allowed_paths)
        or len(allowed_paths) != len(set(allowed_paths))
        or any(repository_output_error(item) for item in allowed_paths)
        or not isinstance(files, dict)
    ):
        return None
    for file_path, entry in files.items():
        if (
            not isinstance(file_path, str)
            or repository_output_error(file_path)
            or not isinstance(entry, dict)
            or set(entry) != {"kind", "mode", "sha256"}
            or entry.get("kind") != "file"
            or not isinstance(entry.get("mode"), str)
            or not re.fullmatch(r"0o[0-7]{4}", entry["mode"])
            or not isinstance(entry.get("sha256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"])
        ):
            return None
    return base, supplied_hash, allowed_paths, files


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

def repository_output_error(path: str) -> str | None:
    candidate = Path(path)
    if (
        not candidate.parts
        or candidate.is_absolute()
        or ".." in candidate.parts
        or any(part.casefold() == ".git" for part in candidate.parts)
    ):
        return "unsafe repository output path"

    current = ROOT
    for part in candidate.parts:
        current = current / part
        if current.is_symlink():
            return "unsafe repository output path"

    try:
        (ROOT / candidate).resolve(strict=False).relative_to(ROOT.resolve())
    except ValueError:
        return "unsafe repository output path"
    return None


def declared_path_errors(paths: Iterable[str]) -> list[str]:
    return sorted(
        {
            f"{path}: {error}"
            for path in paths
            if (error := repository_output_error(path))
        }
    )


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


def inbox_provenance_path(
    value: Any,
    manifest_files: dict[str, dict[str, str]] | None = None,
) -> Path | None:
    if not isinstance(value, str):
        return None
    match = re.fullmatch(r"\[\[([^\[\]]+)\]\]", value)
    if not match:
        return None
    target = match.group(1).split("|", 1)[0].split("#", 1)[0].split("^", 1)[0]
    if target != target.strip():
        return None
    target = target.replace("\\", "/")
    if target.startswith("/") or target.endswith("/"):
        return None
    if target.lower().endswith(".md"):
        target = target[:-3]
    target_path = Path(target)
    if len(target_path.parts) < 2 or target_path.parts[0] != "Inbox":
        return None
    relative_path = Path(f"{target_path.as_posix()}.md")
    if repository_output_error(relative_path.as_posix()):
        return None
    candidate = ROOT / relative_path
    if manifest_files is not None:
        return candidate if relative_path.as_posix() in manifest_files else None
    return candidate if not candidate.is_symlink() and candidate.is_file() else None


def safe_source_asset_path(value: Any) -> Path | None:
    if not isinstance(value, str) or not value:
        return None
    relative_path = Path(value)
    if (
        relative_path.is_absolute()
        or not relative_path.parts
        or relative_path.parts[0] != "Assets"
        or ".." in relative_path.parts
        or repository_output_error(value)
    ):
        return None
    return ROOT / relative_path


def source_provenance_error(
    metadata: dict[str, Any],
    manifest_files: dict[str, dict[str, str]] | None = None,
) -> str | None:
    if valid_source_url(metadata.get("source_url")):
        return None
    assets = metadata.get("assets")
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            raw_path = asset.get("path")
            candidate = safe_source_asset_path(raw_path)
            expected_hash = asset.get("sha256")
            if candidate is None or not isinstance(expected_hash, str):
                continue
            if manifest_files is not None:
                entry = manifest_files.get(raw_path)
                if entry is not None and entry.get("sha256") == expected_hash:
                    return None
                continue
            try:
                if file_sha256(candidate) == expected_hash:
                    return None
            except (FileNotFoundError, ManifestError):
                continue
    if inbox_provenance_path(metadata.get("inbox_source"), manifest_files) is not None:
        return None
    return "Source needs a traceable non-empty URL, existing Asset, or Inbox provenance link"


def source_schema_validator() -> Draft202012Validator:
    schema_path = TOOL_ROOT / "schemas" / "frontmatter.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    source_branch = next(
        branch
        for branch in schema["allOf"][0]["oneOf"]
        if branch.get("properties", {}).get("type", {}).get("const") == "source"
    )
    properties = {**schema["properties"], **source_branch["properties"]}
    contract = {
        "$schema": schema["$schema"],
        "type": "object",
        "properties": properties,
        "required": sorted(set(schema["required"]) | set(source_branch["required"])),
        "not": source_branch["not"],
        "additionalProperties": schema.get("additionalProperties", True),
    }
    return Draft202012Validator(contract, format_checker=FormatChecker())


def source_contract_errors(
    path: str,
    metadata: dict[str, Any],
    manifest_files: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    errors: list[str] = []
    if Path(path).suffix != ".md":
        errors.append(f"{path}: Source intake must use a Markdown file")

    try:
        validator = source_schema_validator()
    except (OSError, json.JSONDecodeError, KeyError, StopIteration, ValueError) as exc:
        return [f"{path}: Source schema is unavailable or invalid: {exc}"]
    for error in sorted(validator.iter_errors(metadata), key=lambda item: list(item.path)):
        field = ".".join(str(part) for part in error.absolute_path) or "frontmatter"
        errors.append(f"{path}: {field}: {error.message}")

    title = metadata.get("title")
    if isinstance(title, str) and title != Path(path).stem:
        errors.append(
            f"{path}: title must match filename '{Path(path).stem}' (found '{title}')"
        )
    created = metadata.get("created")
    updated = metadata.get("updated")
    if isinstance(created, str) and isinstance(updated, str):
        try:
            if date.fromisoformat(updated) < date.fromisoformat(created):
                errors.append(f"{path}: updated precedes created")
        except ValueError:
            pass

    status = metadata.get("status")
    review_status = metadata.get("review_status")
    reviewed = metadata.get("reviewed")
    valid_processing = (
        status == "processing"
        and review_status == "needs-review"
        and reviewed is None
    )
    valid_captured = (
        status == "captured"
        and review_status == "reviewed"
        and reviewed is not None
    )
    if not (valid_processing or valid_captured):
        errors.append(f"{path}: Source review state is inconsistent")
    if "processed" in metadata:
        errors.append(f"{path}: Source uses removed 'processed' field")

    assets = metadata.get("assets")
    seen_paths: set[str] = set()
    if isinstance(assets, list):
        for index, asset in enumerate(assets):
            if not isinstance(asset, dict):
                continue
            raw_path = asset.get("path")
            if isinstance(raw_path, str):
                folded = raw_path.replace("\\", "/").casefold()
                if folded in seen_paths:
                    errors.append(f"{path}: assets[{index}]: duplicate asset path")
                    continue
                seen_paths.add(folded)
            candidate = safe_source_asset_path(raw_path)
            if candidate is None:
                errors.append(f"{path}: assets[{index}]: unsafe asset path")
                continue
            expected_hash = asset.get("sha256")
            if manifest_files is not None:
                entry = manifest_files.get(raw_path) if isinstance(raw_path, str) else None
                actual_hash = entry.get("sha256") if entry is not None else None
            else:
                try:
                    actual_hash = file_sha256(candidate)
                except (FileNotFoundError, ManifestError):
                    errors.append(f"{path}: assets[{index}]: missing or unreadable asset")
                    continue
            if not isinstance(expected_hash, str) or actual_hash != expected_hash:
                errors.append(f"{path}: assets[{index}]: asset SHA-256 mismatch")

    if provenance_error := source_provenance_error(metadata, manifest_files):
        errors.append(f"{path}: {provenance_error}")
    return errors


def current_source_contract_errors(
    path: str,
    text: str | None,
    manifest_files: dict[str, dict[str, str]],
) -> list[str]:
    if text is None:
        return [f"{path}: Source file is missing or unreadable"]
    metadata, parse_error = parse_frontmatter(text)
    if parse_error:
        return [f"{path}: {parse_error}"]
    if metadata is None:
        return [f"{path}: Source requires YAML frontmatter"]
    if metadata.get("type") != "source":
        return [f"{path}: Sources/ notes must use type 'source'"]
    return source_contract_errors(path, metadata, manifest_files)


def is_source_review_transition(
    base: str,
    path: str,
    new_text: str | None,
    manifest_files: dict[str, dict[str, str]],
) -> bool:
    old_text = base_text(base, path)
    if old_text is None or new_text is None:
        return False
    old_metadata, old_error = parse_frontmatter(old_text)
    new_metadata, new_error = parse_frontmatter(new_text)
    return bool(
        not old_error
        and not new_error
        and old_metadata
        and new_metadata
        and old_metadata.get("type") == "source"
        and old_metadata.get("status") == "processing"
        and old_metadata.get("review_status") == "needs-review"
        and old_metadata.get("reviewed") is None
        and new_metadata.get("status") == "captured"
        and new_metadata.get("review_status") == "reviewed"
        and new_metadata.get("reviewed") is not None
        and not source_contract_errors(path, new_metadata, manifest_files)
    )


def base_file_entry(base: str, path: str) -> dict[str, str] | None:
    result = subprocess.run(
        ["git", "ls-tree", base, "--", path],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    if result.returncode != 0 or not result.stdout:
        return None
    fields = result.stdout.split(None, 2)
    if len(fields) < 2 or fields[1] != b"blob":
        return None
    content = git_bytes("show", f"{base}:{path}", check=False)
    return {
        "kind": "file",
        "mode": canonical_mode(int(fields[0], 8)),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def declared_output_error(
    base: str, path: str, manifest: dict[str, dict[str, str]]
) -> str | None:
    path_error = repository_output_error(path)
    if path_error:
        return path_error

    current_entry = filesystem_entry(ROOT / Path(path))
    if current_entry is None:
        current_entry = manifest.get(path)
    base_entry = base_file_entry(base, path)
    if base_entry is None:
        return "declared output already exists" if current_entry is not None else None
    if current_entry != base_entry:
        return "declared output already differs from the base"
    return None



def is_safe_repository_path(path: str) -> bool:
    return repository_output_error(path) is None


def is_protected(path: str) -> bool:
    return path in PROTECTED_FILES or path.startswith(PROTECTED_PREFIXES)


def approval_metadata_path(name: str) -> Path | None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", name):
        return None
    result = subprocess.run(
        ["git", "rev-parse", "--git-path", f"loreloom-approvals/{name}"],
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


def approval_receipt_path(receipt_id: str) -> Path | None:
    if not re.fullmatch(r"[A-Za-z0-9._-]+", receipt_id):
        return None
    return approval_metadata_path(f"{receipt_id}.json")


def load_approval_receipt(receipt_id: str) -> dict[str, Any] | None:
    path = approval_receipt_path(receipt_id)
    if path is None or not path.is_file() or path.is_symlink():
        return None
    if stat.S_IMODE(path.stat().st_mode) != 0o600:
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


def receipt_signing_bytes(receipt: dict[str, Any]) -> bytes:
    payload = {field: receipt[field] for field in RECEIPT_SIGNING_FIELDS}
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _external_key_path(value: str | Path | None) -> Path:
    if value is None:
        raise RuntimeError("approval key configuration is missing")
    path = Path(value).expanduser()
    try:
        resolved = path.resolve(strict=False)
    except OSError as exc:
        raise RuntimeError("approval private key is unavailable") from exc
    for repository_root in (ROOT, TOOL_ROOT):
        try:
            resolved.relative_to(repository_root.resolve())
        except ValueError:
            continue
        raise RuntimeError("approval keys must be outside the repository")
    return path


def sign_receipt(receipt: dict[str, Any], private_key: str | Path) -> str:
    key_path = _external_key_path(private_key)
    if key_path.is_symlink() or not key_path.is_file():
        raise RuntimeError("approval private key is unavailable")
    try:
        if stat.S_IMODE(key_path.stat().st_mode) != 0o600:
            raise RuntimeError("approval private key must have mode 0600")
    except OSError as exc:
        raise RuntimeError("approval private key is unavailable") from exc
    try:
        result = subprocess.run(
            ["openssl", "dgst", "-sha256", "-sign", str(key_path)],
            input=receipt_signing_bytes(receipt),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise RuntimeError("approval signing tool is unavailable") from exc
    if result.returncode != 0:
        raise RuntimeError("approval receipt signing failed")
    return base64.b64encode(result.stdout).decode("ascii")


def trusted_approval_public_key() -> tuple[bytes | None, str | None]:
    public_key_path = approval_metadata_path(APPROVAL_PUBLIC_KEY_NAME)
    digest_path = approval_metadata_path(APPROVAL_PUBLIC_KEY_DIGEST_NAME)
    if public_key_path is None or digest_path is None:
        return None, "approval key metadata path is unavailable"
    if (
        public_key_path.parent.is_symlink()
        or digest_path.parent.is_symlink()
        or public_key_path.is_symlink()
        or digest_path.is_symlink()
    ):
        return None, "approval key metadata must not use symlinks"
    try:
        if (
            stat.S_IMODE(public_key_path.stat().st_mode) != 0o600
            or stat.S_IMODE(digest_path.stat().st_mode) != 0o600
        ):
            return None, "approval key metadata must have mode 0600"
        public_key = public_key_path.read_bytes()
        fingerprint = digest_path.read_text(encoding="ascii").strip().lower()
    except (OSError, UnicodeDecodeError):
        return None, "approval public key metadata is unavailable"
    if not public_key:
        return None, "approval public key metadata is empty"
    if not re.fullmatch(r"[0-9a-f]{64}", fingerprint):
        return None, "approval public key fingerprint is unavailable or invalid"
    if hashlib.sha256(public_key).hexdigest() != fingerprint:
        return None, "approval public key does not match its trusted fingerprint"
    return public_key, None


def verify_receipt_signature(receipt: dict[str, Any]) -> str | None:
    public_key, trust_error = trusted_approval_public_key()
    if trust_error:
        return trust_error
    if public_key is None:
        return "approval public key metadata is unavailable"

    signature_value = receipt.get("signature")
    if not isinstance(signature_value, str):
        return "approval receipt signature is missing"
    try:
        signature = base64.b64decode(signature_value, validate=True)
    except (ValueError, binascii.Error):
        return "approval receipt signature is invalid"

    public_key_path: Path | None = None
    signature_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix="loreloom-approval-key-", delete=False
        ) as stream:
            stream.write(public_key)
            public_key_path = Path(stream.name)
        with tempfile.NamedTemporaryFile(
            prefix="loreloom-receipt-", delete=False
        ) as stream:
            stream.write(signature)
            signature_path = Path(stream.name)
        result = subprocess.run(
            [
                "openssl",
                "dgst",
                "-sha256",
                "-verify",
                str(public_key_path),
                "-signature",
                str(signature_path),
            ],
            input=receipt_signing_bytes(receipt),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except (OSError, KeyError):
        return "approval signature verification is unavailable"
    finally:
        if public_key_path is not None:
            public_key_path.unlink(missing_ok=True)
        if signature_path is not None:
            signature_path.unlink(missing_ok=True)
    if result.returncode != 0:
        return "approval receipt signature is invalid"
    return None



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
        "--target-root",
        metavar="PATH",
        help=(
            "Git worktree to validate when this trusted tool runs from a separate "
            "immutable base worktree"
        ),
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
        "--allow-source-review",
        action="append",
        default=[],
        metavar="PATH",
        help="Exact owner-approved processing-to-reviewed Source path; repeat as needed",
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


def current_head() -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"],
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0:
        return None
    resolved = result.stdout.strip().lower()
    return resolved if re.fullmatch(r"[0-9a-f]{40}", resolved) else None

def trusted_approval_tool_error(base: str) -> str | None:
    requirement = (
        "final validation must run from a separate clean detached Git worktree "
        "checked out at --base"
    )
    try:
        tool_root = TOOL_ROOT.resolve(strict=True)
    except OSError:
        return requirement
    if tool_root == ROOT.resolve():
        return requirement
    try:
        root_result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=tool_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        head_result = subprocess.run(
            ["git", "rev-parse", "--verify", "HEAD^{commit}"],
            cwd=tool_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        detached_result = subprocess.run(
            ["git", "symbolic-ref", "--quiet", "HEAD"],
            cwd=tool_root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        clean_result = subprocess.run(
            ["git", "diff", "--quiet", "HEAD", "--"],
            cwd=tool_root,
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        status_result = subprocess.run(
            ["git", "status", "--porcelain=v1", "--untracked-files=all"],
            cwd=tool_root,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return requirement
    if (
        root_result.returncode != 0
        or head_result.returncode != 0
        or detached_result.returncode != 1
        or clean_result.returncode != 0
        or status_result.returncode != 0
        or status_result.stdout
    ):
        return requirement
    try:
        worktree_root = Path(root_result.stdout.strip()).resolve(strict=True)
    except OSError:
        return requirement
    if worktree_root != tool_root or head_result.stdout.strip().lower() != base:
        return requirement
    return None




def main() -> int:
    args = parse_args()
    target_error = configure_target_root(args.target_root)
    if target_error:
        print(target_error, file=sys.stderr)
        return 2

    gated_path_sets = (
        args.allow_destructive,
        args.allow_promotion,
        args.allow_reviewed_change,
        args.allow_archive,
        args.allow_human_block,
        args.allow_source_create,
        args.allow_source_amendment,
        args.allow_source_review,
        args.framework_change,
    )
    if len(args.allow) != len(set(args.allow)):
        print("provide each exact --allow path once", file=sys.stderr)
        return 2
    path_errors = declared_path_errors(
        [
            *args.allow,
            *(path for paths in gated_path_sets for path in paths),
        ]
    )
    undeclared_gated_paths = sorted(
        {
            path
            for paths in gated_path_sets
            for path in paths
            if path not in args.allow
        }
    )
    if undeclared_gated_paths:
        print("every gated operation path must also appear in --allow", file=sys.stderr)
        return 2
    if path_errors:
        print(f"Change validation failed with {len(path_errors)} error(s):")
        for error in path_errors:
            print(f"- {error}")
        return 2

    base = immutable_base(args.base)
    if base is None:
        print(
            "--base must be an existing immutable 40-character commit captured before the task",
            file=sys.stderr,
        )
        return 2
    head = current_head()
    if head is None or base != head:
        print(
            "--base must equal the current HEAD; restart preflight after any commit",
            file=sys.stderr,
        )
        return 2
    if not args.check_clean:
        if trust_error := trusted_approval_tool_error(base):
            print(trust_error, file=sys.stderr)
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
        if any(gated_path_sets):
            errors.append("preflight does not accept gated override paths")
        try:
            current_manifest = filesystem_manifest(args.allow)
            declared_errors = [
                (path, error)
                for path in args.allow
                if (error := declared_output_error(base, path, current_manifest))
            ]
        except ManifestError as exc:
            errors.append(str(exc))
            current_manifest = {}
            declared_errors = []
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
        if declared_errors:
            print("Preflight failed; declared output paths are not clean:")
            for path, error in declared_errors:
                print(f"- {path}: {error}")
            return 1
        if errors:
            print(f"Preflight failed with {len(errors)} error(s):")
            for error in errors:
                print(f"- {error}")
            return 1
        try:
            write_snapshot(snapshot_path, base, args.allow, current_manifest)
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
    if sorted(args.allow) != snapshot_allowed:
        print(
            "final --allow paths must exactly match the preflight snapshot",
            file=sys.stderr,
        )
        return 2
    try:
        after_files = filesystem_manifest(args.allow)
        changes = manifest_changes(before_files, after_files)
        digest = change_digest(base, changes, before_files, after_files)
    except ManifestError as exc:
        print("Change validation failed with 1 error(s):")
        print(f"- {exc}")
        return 1
    current_texts: dict[str, str] = {}
    for change in changes:
        new_path = change.new_path
        if (
            not new_path
            or change.status not in {"A", "M", "R"}
            or not (new_path.endswith(".md") or new_path.startswith("Sources/"))
        ):
            continue
        expected_entry = after_files.get(new_path)
        if expected_entry is None:
            errors.append(f"{new_path}: changed file is absent from the captured manifest")
            continue
        try:
            current_texts[new_path] = manifest_bound_text(new_path, expected_entry)
        except ManifestError as exc:
            errors.append(str(exc))

    evidence_paths: set[str] = set()
    for source_path, text in current_texts.items():
        if not source_path.startswith("Sources/"):
            continue
        metadata, parse_error = parse_frontmatter(text)
        if parse_error or metadata is None:
            continue
        assets = metadata.get("assets")
        if isinstance(assets, list):
            for asset in assets:
                if not isinstance(asset, dict):
                    continue
                raw_path = asset.get("path")
                if safe_source_asset_path(raw_path) is not None:
                    evidence_paths.add(raw_path)
        inbox_path = inbox_provenance_path(metadata.get("inbox_source"))
        if inbox_path is not None:
            evidence_paths.add(manifest_relative(inbox_path))

    capture_paths = sorted(set(args.allow) | evidence_paths)
    semantic_only_paths = {
        path
        for path in evidence_paths
        if path not in after_files and is_runtime_only_path(Path(path))
    }
    semantic_files = after_files
    try:
        semantic_files, semantic_only_paths, capture_paths = (
            capture_semantic_evidence(
                after_files,
                evidence_paths,
                args.allow,
                base,
            )
        )
    except ManifestError as exc:
        errors.append(str(exc))

    if args.print_diff_sha256:
        print(f"Diff SHA-256: {digest}")

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
            "source_review": sorted(args.allow_source_review),
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
            signature_error = verify_receipt_signature(receipt)
            if signature_error:
                errors.append(signature_error)


    for change in changes:
        for path in change.paths:
            path_error = repository_output_error(path)
            if path_error:
                errors.append(f"{path}: {path_error}")
            if not is_allowed(path, args.allow):
                errors.append(f"{path}: outside the declared output scope")
            if (
                change.new_path
                and change.new_path.startswith("Sources/")
                and change.status in {"A", "M"}
            ):
                errors.extend(
                    current_source_contract_errors(
                        change.new_path,
                        current_texts.get(change.new_path),
                        semantic_files,
                    )
                )
            if path == "Sources" or path.startswith("Sources/"):
                source_creation = change.status == "A" and (
                    is_allowed(path, args.allow_source_create)
                    or is_unreviewed_source(
                        path,
                        current_texts.get(path),
                        semantic_files,
                    )
                )
                source_amendment = (
                    change.status == "M"
                    and is_allowed(path, args.allow_source_amendment)
                )
                source_review = (
                    change.status == "M"
                    and is_allowed(path, args.allow_source_review)
                    and is_source_review_transition(
                        base,
                        path,
                        current_texts.get(path),
                        semantic_files,
                    )
                )
                if not source_creation and not source_amendment and not source_review:
                    if change.status == "A":
                        errors.append(f"{path}: Source creation needs exact approval")
                    elif is_allowed(path, args.allow_source_review):
                        errors.append(
                            f"{path}: Source review must be a complete processing-to-reviewed transition"
                        )
                    else:
                        errors.append(f"{path}: Sources are immutable in agent change sets")
            if path.startswith("Assets/") and path != "Assets/README.md":
                if change.status == "A":
                    errors.append(
                        f"{path}: agent Asset additions are not allowed; "
                        "owner must place files under Assets"
                    )
                elif change.status == "M":
                    errors.append(
                        f"{path}: existing Assets are immutable in agent change sets"
                    )
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
        new_text = current_texts.get(new_path)
        if new_text is None:
            errors.append(f"{new_path}: changed Markdown file is unreadable")
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

        old_meta, _ = (
            parse_frontmatter(old_text) if old_text is not None else (None, None)
        )
        new_meta, new_metadata_error = parse_frontmatter(new_text)
        if new_metadata_error:
            errors.append(f"{new_path}: {new_metadata_error}")

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

    if not errors:
        try:
            verified_semantic_files = filesystem_manifest(capture_paths)
            verified_after_files = {
                path: entry
                for path, entry in verified_semantic_files.items()
                if path not in semantic_only_paths
            }
            verified_changes = manifest_changes(before_files, verified_after_files)
            verified_digest = change_digest(
                base,
                verified_changes,
                before_files,
                verified_after_files,
            )
        except ManifestError as exc:
            errors.append(str(exc))
        else:
            if (
                verified_semantic_files != semantic_files
                or verified_after_files != after_files
                or verified_changes != changes
                or verified_digest != digest
            ):
                errors.append("repository changed during final validation")

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
