# Agent kit

This directory stores model-independent operating instructions for the vault.

- `policies/` defines standing safety and authority rules.
- `prompts/` contains copyable task contracts for Codex.
- `skills/` contains discoverable, reusable task workflows.
- `workflows/` defines repeatable, reviewable transformations.
- `workflows/asset-to-source.md` defines the bounded Assets-to-Source intake before Source-to-Knowledge.

Skills are the preferred reusable interface. Prompts remain useful as transparent examples and one-off task contracts; workflows hold detailed lifecycle procedures. None grant authority beyond `AGENTS.md`. Replace example paths with exact vault paths before use and keep each mutation bounded enough to review as one diff.

Project-scoped read-only custom agent configurations live in `.codex/agents/`. The root workflow is the default; see `docs/MULTI_AGENT.md` for owner-approved advanced delegation.

Runtime logs and caches belong in `.agents/runs/` and `.agents/cache/`; both are ignored by Git.
