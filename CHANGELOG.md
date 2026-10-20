# Changelog

All notable framework changes will be documented here.

The format is based on Keep a Changelog, and the project follows semantic versioning once the first release is tagged.

## [Unreleased]

### Added

- Lifecycle-based vault structure for a multi-topic knowledge base.
- Human/agent authority model and prompt-injection boundaries.
- Note templates and machine-readable frontmatter schema.
- Starter Codex prompts and repeatable agent workflows.
- Example notes demonstrating cross-topic links.
- Local and GitHub Actions validation.
- Project-scoped Sol, Terra, and Luna specialist agents with bounded orchestration.
- Repository skills for capture triage, source distillation, cross-topic linking, Wiki regeneration, vault auditing, and multi-agent routing.
- Multi-agent model, safety, and single-writer guidance.
- Diff-aware, snapshot-bound mutation guardrails, protected human-approval receipts, and adversarial validator tests.
- Optional, default-OFF Jev advisory helper (`scripts/jev_advisory.py`) for Inbox triage and draft Concept claim support, with local schema-validated sidecars under the gitignored `.loreloom/jev/`. Advisories never change notes, review state, or approvals.

- Lightweight agent-first flow as the default: root `CLAUDE.md`, `index.md`, `log.md`, and `Wiki/sources`, `entities`, `concepts`, `synthesis`, and `_review` sections with six-field page frontmatter (`schemas/wiki-page.schema.json`, `Templates/Wiki page.md`).
- `ingest`, `query`, `file-answer`, and `lint` skills, plus the read-only helpers `scripts/ingest_gate.py` (auto-accept rule) and `scripts/lint_wiki.py` (Wiki health report).
- `scripts/migrate_knowledge_to_wiki.py` (dry run by default, `--apply` to write) and `docs/migration-lightweight.md` for gradual migration of `Knowledge/` notes.
- A pointer to the sdd-mcp [`output-clarity-ladder` skill](https://github.com/yi-john-huang/sdd-mcp/blob/master/skills/output-clarity-ladder/SKILL.md) (installed with `npx -y sdd-mcp-server@latest setup-global`) as the writing style for Wiki prose, with its `references/zh-TW.md` for Traditional Chinese. The repository keeps no copy of the skill. Also a "Scope of use" section in `README.md` and `CLAUDE.md`.
- `scripts/check_local.sh` runs every check of the removed CI before a push: `uv sync --locked --dev`, the doctor, daily and strict validation, the Wiki lint report, and the full test suite. Strict validation is a gate. `--portability` repeats the doctor, both validation modes, and the four portable test modules on Python 3.11 and 3.13. In the framework repository the doctor runs in a temporary copy of the working tree without `origin`; the script never changes Git remotes.
- Optional `scripts/install-hooks.sh` installs a pre-push hook that runs `scripts/check_local.sh`. Nothing installs it automatically; `--force` replaces a hook that it did not write.

### Changed

- `scripts/validate_vault.py` now has `--mode daily` (default: basic frontmatter, required fields, broken wikilinks) and `--mode strict` (every earlier check). Set the default with `[tool.loreloom] validation_mode` or `LORELOOM_VALIDATION_MODE`. Run `--mode strict` to get the earlier behavior.
- `scripts/doctor_vault.py` reports the configured validation mode with a recommendation, runs the validator in that mode, and warns when the lightweight layout is missing.
- The existing `*-vault-*` skills, `Knowledge/`, and generated `type: wiki` pages are now the optional strict mode. `AGENTS.md` points to `CLAUDE.md` for the default flow.
- CI validates the vault in both modes and added `pytest` to the locked dev dependencies.
- Replaced pip requirements with a locked uv project for local validation and CI.
- Renamed the default branch from `main` to `master`.
- Routed bounded source extraction and classification to Luna High while retaining Terra Max for knowledge distillation.

### Removed

- The GitHub Actions workflow `.github/workflows/validate.yml`. The repository has no hosted CI. Run `scripts/check_local.sh` before a push, and `scripts/check_local.sh --portability` when a change touches the portable core. The macOS and Windows legs of the old matrix cannot be reproduced on one machine; contributors on those systems run `--portability` there.

[Unreleased]: https://github.com/yi-john-huang/loreloom/compare/v0.1.0...HEAD
