---
name: audit-vault-health
description: Perform a read-only Loreloom health audit covering schema errors, broken or ambiguous links, provenance gaps, stale generated pages, privacy risks, orphan notes, and workflow drift. Use for weekly reviews, pre-publication checks, unexplained vault degradation, or broad cleanup requests before any repair work.
---

# Audit Vault Health

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `.agents/workflows/weekly-maintenance.md`.
2. Run `uv run python scripts/validate_vault.py` and preserve its objective failures separately from editorial judgment.
3. Define the requested date window or vault slice.
4. Audit every requested dimension sequentially in the root agent and consolidate exact-path findings.
5. Use `$orchestrate-vault-work` only after explicit owner opt-in when a broad audit materially benefits from disjoint read-only provenance, architecture, or privacy review.
6. Remove duplicate findings and rank by severity, confidence, repair value, and risk.
7. For asset-first vaults, inspect `Assets/` excluding `Assets/README.md` and report unreferenced files, duplicate hashes, hash drift, unavailable extraction, missing Source bindings, and reviewed Sources whose declared Assets are missing. Do not move, delete, or rewrite assets during the report pass.
8. Recommend at most five actions. Do not implement repairs during the audit pass.
9. Require exact approval for a second repair pass, especially promotion, archive, move, rename, deletion, commit, or push.

## Output

Separate validator failures, high-confidence risks, editorial suggestions, and questions for the owner. State explicitly when no actionable issue is found.
Separate asset findings into missing bindings, duplicate-risk, hash drift, unavailable extraction, privacy/rights concerns, and validator failures. Never infer that an unreferenced file is safe to delete.
