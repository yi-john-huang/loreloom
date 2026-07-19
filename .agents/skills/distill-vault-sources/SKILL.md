---
name: distill-vault-sources
description: Transform owner-reviewed Loreloom Source or Daily notes into traceable atomic Knowledge drafts. Use when extracting durable concepts, comparing evidence, detecting duplicate concepts, or preparing human-reviewable notes from exact Source paths. Never rewrites Sources, fills gaps from model memory, or promotes drafts to evergreen.
---

# Distill Vault Sources

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `.agents/workflows/source-to-knowledge.md`.
2. Confirm exact Source inputs and the allowed Knowledge output directory.
3. For every Source input, require `status: captured`, `review_status: reviewed`, and a non-null `reviewed` date. Stop before reading for distillation when the Source is still processing or needs review; Daily inputs are exempt from this Source-specific gate.
4. Run `uv run python scripts/validate_vault.py` before reading or extraction. On any unsafe, missing, unreadable, or hash-drifted bound Asset, report the exact failure and write no Knowledge, even if URL or Inbox provenance also exists.
5. Read each Source completely. Record unavailable attachments or external material instead of guessing.
6. When inputs are independent, assign disjoint Sources to `source-reader` agents for claim and provenance extraction.
7. Ask `knowledge-distiller` to propose minimal atomic boundaries after related Knowledge titles, aliases, and synonyms have been searched.
8. Reconcile duplicate or contradictory proposals against the original evidence. Use `vault-architect` only for ambiguous boundaries with cross-vault consequences.
9. Present the proposed drafts and citations before writing unless the request already authorizes draft creation.
10. Before writing, record the immutable base commit and run the change-validator clean preflight with an external snapshot file and every exact output path.
11. Let the root agent create or update `status: draft`, `reviewed: null` Concept notes. Preserve Sources unchanged except an explicitly authorized append-only link.
12. Run the vault validator and the final change validator against the same base and snapshot with every exact changed path. Request `vault-reviewer` for consequential claims.

## Output

List revalidated Source paths, created, updated, skipped, duplicate, contradictory, and uncertain items; include every draft path and citation, conflicts and limitations, and the owner-only final claim/citation review and optional evergreen promotion. Every draft must have valid evidence links and a conservative confidence level.
