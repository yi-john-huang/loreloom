---
name: orchestrate-vault-work
description: Coordinate complex Loreloom work across project-scoped Codex agents. Use when a vault request has at least two independent read-heavy tracks, spans multiple lifecycle layers, needs architecture plus implementation plus review, or explicitly requests parallel agents. Do not use for a simple single-note edit or one short lookup.
---

# Orchestrate Vault Work

Keep the root agent responsible for scope, decisions, writes, validation, and the final answer. Delegate bounded evidence gathering and specialist review.

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `docs/MULTI_AGENT.md`.
2. State the exact input paths, output paths, and user-authorized mutations.
3. Split work only along independent boundaries. Prefer one source, concern, or review dimension per assignment.
4. Select project agents from `.codex/agents/`:
   - `vault-architect` for ontology and consequential design;
   - `source-reader` for bounded evidence extraction;
   - `knowledge-distiller` for atomic draft proposals;
   - `wiki-synthesizer` for high-level synthesis;
   - `vault-reviewer` for independent QA;
   - `vault-worker` for an implementation-ready proposal on one isolated path set.
5. Verify no live parent permission override broadens child access. Spawn at most three subagents concurrently, require effective read-only access, and do not permit recursive delegation.
6. Give each agent the minimum context needed: exact paths, question, prohibited actions, and return format. Do not include the expected answer.
7. Wait for all assigned agents. Reconcile disagreements against Sources and policy; never resolve a factual conflict by majority vote.
8. Before writing, record the immutable 40-character base commit and run `uv run python -I scripts/validate_change.py --check-clean --base <40-character-commit> --snapshot-file <absolute-temp-path>` with one exact `--allow` per authorized output path. Let only the root agent perform writes.
9. Run `uv run python scripts/validate_vault.py`, then run every final `uv run python -I scripts/validate_change.py --target-root <candidate-vault-root> ...` from a separate clean detached worktree at the immutable base with the same snapshot and every exact changed path. Request an independent `vault-reviewer` pass for material changes.
10. If a gated path needs approval—including an exact processing-to-reviewed `source_review`—stop for an owner- or trusted-UI-created receipt under protected Git metadata. Never create or alter that receipt.
11. Report assignments, accepted and rejected findings, changes, uncertainty, human review, and validation.

## Do not delegate

- user decisions, approval requests, or final truth promotion;
- deletion, archival, bulk rename, commit, push, or publication authority;
- overlapping edits to the same note or generated page;
- a task whose coordination cost exceeds doing it directly.

Never substitute models silently. A disclosed fallback may perform low-risk, read-only analysis while preserving the role's sandbox and instructions. If the configured Sol reviewer or synthesizer is unavailable for a material change, pause for owner direction or require explicit human review and report incomplete coverage.
