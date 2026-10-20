# Contributing

Thank you for improving the Loreloom framework.

## Scope

Good contributions include:

- safer or clearer agent policies;
- note templates and frontmatter schemas;
- lifecycle and organization guidance;
- validator improvements and test fixtures;
- generic examples that contain no personal or restricted material.

Personal notes, copied articles, credentials, proprietary prompts, and provider-specific lock-in are out of scope.

## Before opening a pull request

1. Create an issue for substantial behavioral or schema changes.
2. Use a branch with a focused name such as `docs/source-citations`.
3. Keep examples fictional, public-domain, or short original summaries with attribution.
4. Update documentation and templates together when changing a convention.
5. Run `scripts/check_local.sh`. Add `--portability` when the change touches the portable core. See [Local checks](#local-checks-no-github-actions).
6. Review the diff for names, emails, tokens, local paths, and confidential content.

Python tooling uses uv. Declare validation dependencies in `pyproject.toml`, regenerate with `uv lock`, and commit the updated `uv.lock`. Do not add pip requirements files or hand-edit the lockfile.

## Local checks (no GitHub Actions)

This repository has no GitHub Actions. Nothing runs on a push or a pull request. You run the checks yourself, before you push.

```sh
scripts/check_local.sh                 # every gate
scripts/check_local.sh --portability   # also the Python 3.11 and 3.13 core gates
```

`scripts/check_local.sh` runs these gates and exits 1 if any fails. Every gate blocks, including strict validation.

| Gate | Command |
|---|---|
| Environment | `uv sync --locked --dev` |
| Doctor | `scripts/doctor_vault.py` |
| Daily validation | `scripts/validate_vault.py --mode daily` |
| Strict validation | `scripts/validate_vault.py --mode strict` |
| Wiki lint | `scripts/lint_wiki.py` |
| Tests | `python -m unittest discover -s tests` |

Run `--portability` when your change touches the portable core: `scripts/doctor_vault.py`, `validate_vault.py`, `ingest_gate.py`, `lint_wiki.py`, `migrate_knowledge_to_wiki.py`, `jev_advisory.py`, `schemas/`, `pyproject.toml`, `uv.lock`, or `.python-version`. For Python 3.11 and 3.13 it runs the doctor, both validation modes, and the four portable test modules.

One machine covers only its own operating system. The old CI matrix ran Ubuntu, macOS, and Windows with Python 3.11 and 3.13. The script cannot reproduce the other two systems. Contributors on macOS or Windows (Git Bash or WSL) run `scripts/check_local.sh --portability` on that system.

In the framework repository, `origin` is the public Loreloom framework, and the doctor fails its `remote-privacy` check by design. The script does not change your remotes. It runs the doctor in a temporary copy of your working tree that has no `origin`, and it prints a notice when it does.

To run the checks before every push, install the optional hook:

```sh
scripts/install-hooks.sh           # install a pre-push hook
scripts/install-hooks.sh --force   # replace a pre-push hook that you installed for something else
```

Nothing installs the hook for you. Skip it once with `git push --no-verify`.

Two tests in `tests/test_validate_change.py` can fail on ext4 because of timestamp granularity (`test_directory_entry_created_during_walk_fails_closed` and `test_final_rejects_bytes_changed_after_initial_digest`). If only those fail, run the checks again.

## Compatibility promise

The framework favors standard Markdown and YAML. New features should degrade gracefully when Obsidian community plugins or AI tools are absent.

Schema changes should be additive when possible. A breaking change must include:

- a migration note in `CHANGELOG.md`;
- updated templates and examples;
- validator coverage;
- a rationale in the pull request.

## Agent-generated contributions

AI assistance is welcome, but the contributor remains responsible for accuracy, licensing, and privacy. Disclose material AI-generated changes in the pull request and describe the human review performed. Do not submit unverifiable citations or model output copied from private data.

## Commit and pull request style

Use concise, imperative commit subjects. A pull request should explain:

- the problem;
- the approach;
- user-visible or schema changes;
- validation performed;
- privacy or migration considerations.

By contributing, you agree that your contribution is licensed under this repository's MIT License.
