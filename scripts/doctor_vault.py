#!/usr/bin/env python3
"""Report whether a Loreloom template copy is ready without changing it."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import importlib
import importlib.metadata
import io
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
PUBLIC_FRAMEWORK = ("github.com", "yi-john-huang/loreloom")
APPROVAL_PRIVATE_KEY_ENV = "LORELOOM_APPROVAL_PRIVATE_KEY"
APPROVAL_PUBLIC_KEY_NAME = "approval-public-key.pem"
APPROVAL_PUBLIC_KEY_DIGEST_NAME = "approval-public-key.sha256"
REQUIRED_CORE_PLUGINS = {"properties", "daily-notes", "templates"}


@dataclass(frozen=True, slots=True)
class Check:
    status: str
    name: str
    detail: str


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check Loreloom core readiness without modifying the vault."
    )
    parser.add_argument(
        "--advanced",
        action="store_true",
        help="also check POSIX multi-agent and signed-approval prerequisites",
    )
    return parser.parse_args(argv)


def normalize_github_remote(value: str) -> tuple[str, str] | None:
    """Return a canonical GitHub host/repository pair for supported Git transports."""
    raw = value.strip().rstrip("/")
    host: str
    repository: str

    scp_match = re.fullmatch(r"git@([^:/\s]+):([^/\s]+/[^/\s]+)", raw)
    if scp_match:
        host, repository = scp_match.groups()
    elif raw.startswith("https://"):
        try:
            parsed = urlparse(raw)
            port = parsed.port
        except ValueError:
            return None
        if (
            parsed.scheme != "https"
            or parsed.username is not None
            or parsed.password is not None
            or port is not None
            or parsed.query
            or parsed.fragment
        ):
            return None
        host = parsed.hostname or ""
        repository = parsed.path.lstrip("/")
    elif raw.startswith("ssh://"):
        try:
            parsed = urlparse(raw)
            port = parsed.port
        except ValueError:
            return None
        if (
            parsed.scheme != "ssh"
            or parsed.username != "git"
            or parsed.password
            or parsed.query
            or parsed.fragment
        ):
            return None
        host = parsed.hostname or ""
        repository = parsed.path.lstrip("/")
        if port is not None:
            if host.casefold() == "ssh.github.com" and port == 443:
                host = "github.com"
            else:
                return None
    else:
        return None

    host = host.casefold()
    if host != "github.com":
        return None
    if repository.casefold().endswith(".git"):
        repository = repository[:-4]
    repository = repository.strip("/").casefold()
    if not re.fullmatch(r"[^/\s]+/[^/\s]+", repository):
        return None
    return host, repository


def _run(root: Path, args: Sequence[str], *, input_bytes: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(
            list(args),
            cwd=root,
            input=input_bytes,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError:
        return subprocess.CompletedProcess(list(args), 127, b"", b"")


def _load_validator():
    module_name = f"{__package__}.validate_vault" if __package__ else "validate_vault"
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        try:
            return importlib.import_module(module_name)
        except (ImportError, SystemExit):
            return None


def _python_check() -> Check:
    current = sys.version_info[:2]
    if current >= (3, 11):
        return Check("PASS", "python", f"Python {current[0]}.{current[1]} satisfies >=3.11")
    return Check("FAIL", "python", "Python >=3.11 is required")


def _tool_check(name: str) -> Check:
    if shutil.which(name):
        return Check("PASS", name, "available")
    return Check("FAIL", name, "not found on PATH")


def _git_root_check(root: Path) -> Check:
    result = _run(root, ("git", "rev-parse", "--show-toplevel"))
    if result.returncode != 0:
        return Check("FAIL", "git-worktree", "repository root is not a Git worktree")
    try:
        reported = Path(result.stdout.decode().strip()).resolve()
    except (OSError, UnicodeError):
        return Check("FAIL", "git-worktree", "Git returned an unreadable worktree root")
    if reported != root.resolve():
        return Check("FAIL", "git-worktree", "run the doctor from the exact vault worktree root")
    return Check("PASS", "git-worktree", "vault root matches the Git worktree root")


def _dependency_check(root: Path) -> Check:
    path = root / "pyproject.toml"
    try:
        project = tomllib.loads(path.read_text(encoding="utf-8"))
        requirements = project["dependency-groups"]["dev"]
    except (OSError, UnicodeError, tomllib.TOMLDecodeError, KeyError, TypeError):
        return Check("FAIL", "locked-dependencies", "cannot read locked dev requirements")
    failures: list[str] = []
    for requirement in requirements:
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s]+)", requirement)
        if not match:
            failures.append("an unpinned or malformed dev requirement")
            continue
        distribution, expected = match.groups()
        try:
            actual = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"{distribution} is not installed")
            continue
        if actual != expected:
            failures.append(f"{distribution} {expected} is required")
    if failures:
        return Check("FAIL", "locked-dependencies", "; ".join(failures))
    return Check("PASS", "locked-dependencies", "locked dev requirements are installed")


def _framework_check(root: Path, validator) -> Check:
    required = [
        ".python-version",
        "pyproject.toml",
        "uv.lock",
        "schemas/frontmatter.schema.json",
        ".agents/policies/vault-policy.md",
        "Templates/Source.md",
        "Templates/Concept.md",
        "Templates/Daily.md",
        "Assets",
    ]
    if validator is None:
        return Check("FAIL", "framework-layout", "validator dependencies are unavailable")
    required.extend(validator.MANAGED_ROOTS)
    missing = [item for item in required if not (root / item).exists()]
    if missing:
        return Check("FAIL", "framework-layout", "missing required framework paths: " + ", ".join(missing))
    return Check("PASS", "framework-layout", "required framework paths exist")


def _origin_check(root: Path) -> Check:
    result = _run(root, ("git", "remote", "get-url", "origin"))
    if result.returncode != 0:
        return Check(
            "WARN",
            "remote-privacy",
            "repository visibility is not verifiable locally; confirm the remote is private",
        )
    try:
        remote = result.stdout.decode().strip()
    except UnicodeError:
        remote = ""
    if normalize_github_remote(remote) == PUBLIC_FRAMEWORK:
        return Check(
            "FAIL",
            "remote-privacy",
            "origin still points to the public Loreloom framework; create a private template copy",
        )
    return Check(
        "WARN",
        "remote-privacy",
        "repository visibility is not verifiable locally; confirm the remote is private",
    )


def _json_object(path: Path) -> dict[str, object] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _obsidian_check(root: Path) -> Check:
    app = _json_object(root / ".obsidian/app.json")
    templates = _json_object(root / ".obsidian/templates.json")
    daily = _json_object(root / ".obsidian/daily-notes.json")
    plugins_path = root / ".obsidian/core-plugins.json"
    try:
        plugins_value = json.loads(plugins_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        plugins_value = None
    if isinstance(plugins_value, dict):
        enabled = {key for key, value in plugins_value.items() if value is True}
    elif isinstance(plugins_value, list) and all(isinstance(item, str) for item in plugins_value):
        enabled = set(plugins_value)
    else:
        enabled = set()
    valid = (
        app is not None
        and app.get("alwaysUpdateLinks") is True
        and app.get("attachmentFolderPath") == "Assets"
        and templates is not None
        and templates.get("folder") == "Templates"
        and templates.get("dateFormat") == "YYYY-MM-DD"
        and templates.get("timeFormat") == "HH:mm"
        and daily is not None
        and daily.get("folder") == "Daily"
        and daily.get("format") == "YYYY-MM-DD"
        and daily.get("template") == "Templates/Daily"
        and REQUIRED_CORE_PLUGINS <= enabled
    )
    if not valid:
        return Check("FAIL", "obsidian-settings", "portable app, template, daily-note, or required core-plugin settings are missing or invalid")
    return Check("PASS", "obsidian-settings", "portable Obsidian defaults are ready")


def _validation_check(root: Path, validator) -> Check:
    if validator is None:
        return Check("FAIL", "vault-validation", "validation dependencies are unavailable")
    original_root = validator.ROOT
    captured = io.StringIO()
    try:
        validator.ROOT = root
        with contextlib.redirect_stdout(captured):
            result = validator.main()
    except (OSError, SystemExit):
        result = 1
    finally:
        validator.ROOT = original_root
    lines = [line.strip() for line in captured.getvalue().splitlines() if line.strip()]
    if result == 0:
        detail = lines[-1] if lines else "vault validation passed"
        return Check("PASS", "vault-validation", detail)
    return Check("FAIL", "vault-validation", "failed; run 'uv run --locked python scripts/validate_vault.py' for full path-specific errors")


def core_checks(root: Path) -> list[Check]:
    """Run ordered, read-only checks required by every supported platform."""
    root = root.resolve()
    validator = _load_validator()
    return [
        _python_check(),
        _tool_check("uv"),
        _tool_check("git"),
        _git_root_check(root),
        _framework_check(root, validator),
        _dependency_check(root),
        _origin_check(root),
        _obsidian_check(root),
        _validation_check(root, validator),
    ]


def _protected_file(path: Path) -> bool:
    try:
        return path.is_file() and not path.is_symlink() and stat.S_IMODE(path.stat().st_mode) == 0o600
    except OSError:
        return False


def _approval_path(root: Path, name: str) -> Path | None:
    result = _run(root, ("git", "rev-parse", "--git-path", f"loreloom-approvals/{name}"))
    if result.returncode != 0:
        return None
    try:
        path = Path(result.stdout.decode().strip())
    except UnicodeError:
        return None
    return path if path.is_absolute() else root / path


def _openssl_der(root: Path, path: Path, *, public: bool) -> bytes | None:
    args = ["openssl", "pkey"]
    if public:
        args.append("-pubin")
    args.extend(("-in", str(path), "-pubout", "-outform", "DER"))
    result = _run(root, args)
    return result.stdout if result.returncode == 0 and result.stdout else None


def _advanced_platform_check() -> Check:
    required = ("O_NOFOLLOW", "O_CREAT", "O_EXCL")
    if os.name != "posix" or any(not hasattr(os, name) for name in required):
        return Check("FAIL", "advanced-platform", "POSIX file-descriptor and permission protections are unavailable")
    return Check("PASS", "advanced-platform", "POSIX guarded-change protections are available")


def _head_check(root: Path) -> Check:
    result = _run(root, ("git", "rev-parse", "--verify", "HEAD^{commit}"))
    value = result.stdout.decode(errors="ignore").strip()
    if result.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{40}", value):
        return Check("PASS", "committed-head", "a full committed HEAD is available")
    return Check("FAIL", "committed-head", "a full committed HEAD is required")


def _clean_check(root: Path) -> Check:
    result = _run(root, ("git", "status", "--porcelain"))
    if result.returncode == 0 and not result.stdout.strip():
        return Check("PASS", "clean-worktree", "worktree is clean")
    return Check("FAIL", "clean-worktree", "guarded changes require a clean worktree")


def _approval_checks(root: Path) -> list[Check]:
    public_path = _approval_path(root, APPROVAL_PUBLIC_KEY_NAME)
    digest_path = _approval_path(root, APPROVAL_PUBLIC_KEY_DIGEST_NAME)
    public_file_ok = public_path is not None and _protected_file(public_path)
    digest_ok = digest_path is not None and _protected_file(digest_path)
    public_der = (
        _openssl_der(root, public_path, public=True)
        if public_file_ok and public_path is not None
        else None
    )
    public_ok = public_file_ok and public_der is not None
    public_check = Check(
        "PASS" if public_ok else "FAIL",
        "approval-public-key",
        "trusted public key is protected and parseable"
        if public_ok
        else "trusted public key must be a regular non-symlink mode-0600 file parseable by OpenSSL",
    )
    fingerprint_ok = False
    if public_file_ok and digest_ok and public_path is not None and digest_path is not None:
        try:
            expected = digest_path.read_text(encoding="ascii").strip().casefold()
            actual = hashlib.sha256(public_path.read_bytes()).hexdigest()
            fingerprint_ok = re.fullmatch(r"[0-9a-f]{64}", expected) is not None and expected == actual
        except (OSError, UnicodeError):
            fingerprint_ok = False
    fingerprint_check = Check(
        "PASS" if fingerprint_ok else "FAIL",
        "approval-fingerprint",
        "trusted public-key fingerprint matches" if fingerprint_ok else "protected public-key fingerprint is missing or does not match",
    )

    private_value = os.environ.get(APPROVAL_PRIVATE_KEY_ENV)
    private_path: Path | None = None
    private_file_ok = False
    if private_value:
        try:
            private_path = Path(private_value).expanduser().absolute()
            resolved_private_path = private_path.resolve(strict=False)
            resolved_private_path.relative_to(root.resolve())
        except ValueError:
            private_file_ok = _protected_file(private_path)
        except OSError:
            private_file_ok = False
    private_der = _openssl_der(root, private_path, public=False) if private_file_ok and private_path else None
    private_ok = bool(public_der and private_der and public_der == private_der)
    private_check = Check(
        "PASS" if private_ok else "FAIL",
        "approval-private-key",
        "owner private key is an external, regular non-symlink mode-0600 file that parses and matches the trusted public key"
        if private_ok
        else "owner private key must be an external, regular non-symlink mode-0600 file that parses and matches the trusted public key",
    )
    return [public_check, fingerprint_check, private_check]


def advanced_checks(root: Path) -> list[Check]:
    """Run read-only prerequisites for the POSIX guarded-change workflow."""
    if os.name == "nt":
        return [
            Check(
                "FAIL",
                "advanced-platform",
                "guarded changes require POSIX descriptor and permission semantics; use Linux, macOS, or WSL",
            )
        ]
    root = root.resolve()
    checks = [_advanced_platform_check(), _tool_check("openssl"), _head_check(root), _clean_check(root)]
    checks.extend(_approval_checks(root))
    return checks


def _print_checks(checks: Sequence[Check]) -> None:
    for check in checks:
        print(f"[{check.status}] {check.name}: {check.detail}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    core = core_checks(ROOT)
    _print_checks(core)
    core_ready = not any(check.status == "FAIL" for check in core)
    print(f"Core readiness: {'READY' if core_ready else 'NOT READY'}")
    if not args.advanced:
        return 0 if core_ready else 1

    advanced = advanced_checks(ROOT)
    _print_checks(advanced)
    advanced_ready = not any(check.status == "FAIL" for check in advanced)
    print(f"Advanced readiness: {'READY' if advanced_ready else 'NOT READY'}")
    return 0 if core_ready and advanced_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
