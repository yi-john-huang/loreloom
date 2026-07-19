---
name: orchestrate-vault-work
description: Coordinate advanced Loreloom work across project-scoped Codex agents only after the owner explicitly requests parallel/custom agents or accepts a stated delegation benefit. Keeps every child read-only and the root as sole writer.
---

# Orchestrate Vault Work

Keep the root agent responsible for scope, decisions, writes, validation, and the final answer. Delegate bounded evidence gathering and specialist review.

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `docs/MULTI_AGENT.md`.
2. Confirm the owner's explicit request or acceptance of advanced delegation.
3. State the exact input paths, output paths, user-authorized mutations, and concrete delegation benefit.
4. Split work only along independent boundaries and select the narrowest available read-only roles from `.codex/agents/`.
5. Verify no live parent permission override broadens child access. Spawn at most three subagents concurrently and prohibit recursive delegation.
6. Give each role minimum context: exact paths, question, prohibited actions, and return format. Do not include the expected answer.
7. If a role is unavailable, do not substitute silently. Low-risk extraction or proposal work may return to the root with reduced coverage disclosed; material synthesis or review requires direct owner review and an incomplete-specialist-coverage report.
8. Reconcile disagreements against Sources and policy, never majority vote.
9. Before writing, record the immutable 40-character base commit and run `uv run python -I scripts/validate_change.py --check-clean --base <40-character-commit> --snapshot-file <absolute-temp-path>` with one exact `--allow` per authorized output path. Let only the root write.
10. Run `uv run --locked python scripts/validate_vault.py`, then run every final `uv run python -I scripts/validate_change.py --target-root <candidate-vault-root> ...` from a separate clean detached worktree at the immutable base with the same snapshot and every exact changed path. Request independent read-only review for material changes when available.
11. If a gated path needs approval, stop for an owner- or trusted-UI-created receipt under protected Git metadata. Never create or alter that receipt.
12. Report assignments, accepted and rejected findings, changes, uncertainty, human review, specialist coverage, and validation.

## Do not delegate

- user decisions, approval requests, or final truth promotion;
- deletion, archival, bulk rename, commit, push, or publication authority;
- overlapping edits to the same note or generated page;
- a task whose coordination cost exceeds doing it directly.

Never substitute a model or role silently. Disclose reduced coverage and follow the owner-review rules above.
