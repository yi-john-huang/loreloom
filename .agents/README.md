# Agent kit

This directory stores model-independent operating instructions for the vault.

- `policies/` defines standing safety and authority rules.
- `prompts/` contains copyable task contracts for Codex.
- `workflows/` defines repeatable, reviewable transformations.

Prompts do not grant authority beyond `AGENTS.md`. Replace example paths with exact vault paths before use. Prefer one bounded workflow per agent session so its diff is easy to review.

Runtime logs and caches belong in `.agents/runs/` and `.agents/cache/`; both are ignored by Git.
