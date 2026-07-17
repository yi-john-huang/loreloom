# Contributing

Thank you for improving the Sourceweave framework.

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
5. Run `python3 scripts/validate_vault.py`.
6. Review the diff for names, emails, tokens, local paths, and confidential content.

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
