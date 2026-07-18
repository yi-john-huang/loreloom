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

### Changed

- Replaced pip requirements with a locked uv project for local validation and CI.
- Renamed the default branch from `main` to `master`.
- Routed bounded source extraction and classification to Luna High while retaining Terra Max for knowledge distillation.

[Unreleased]: https://github.com/yi-john-huang/loreloom/compare/v0.1.0...HEAD
