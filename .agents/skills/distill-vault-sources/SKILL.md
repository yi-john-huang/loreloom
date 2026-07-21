---
name: distill-vault-sources
description: Transform owner-reviewed Loreloom Source or Daily notes into traceable atomic Knowledge drafts. Use when extracting durable concepts, comparing evidence, detecting duplicate concepts, or preparing human-reviewable notes from exact input paths. Never rewrites Sources, fills gaps from model memory, or promotes drafts to evergreen.
---

# Distill Vault Sources

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `.agents/workflows/source-to-knowledge.md`.
2. Confirm exact Source and Daily inputs and the allowed Knowledge output directory.
3. For every Source input, require `status: captured`, `review_status: reviewed`, and a non-null `reviewed` date. Stop before reading for distillation when the Source is still processing or needs review; Daily inputs are exempt from this Source-specific gate.
4. Run `uv run python scripts/validate_vault.py` before reading or extraction. On any unsafe, missing, unreadable, or hash-drifted bound Asset, report the exact failure and write no Knowledge, even if URL or Inbox provenance also exists.
5. Read each authorized Source and Daily input completely. Record every Source's `capture_mode` before extracting claims, and record unavailable attachments or external material instead of guessing.
6. Search related Knowledge titles, aliases, and likely synonyms, then let the root propose minimal atomic boundaries and reconcile duplicates or contradictions against the original evidence.
7. Use `$orchestrate-vault-work` only after explicit owner opt-in when disjoint Source extraction or consequential architecture review materially benefits from advanced delegation.
8. Present the proposed drafts and citations before writing unless the request already authorizes draft creation.
9. Let the root agent create or update only authorized `status: draft`, `reviewed: null` Concept notes. Preserve Sources unchanged except an explicitly authorized append-only link. Never turn a paraphrase into quotation-like wording or upgrade `unknown` or `paraphrased`.
10. For each affected draft, inspect only the Sources that draft cites. When a cited Source uses `capture_mode: unknown`, `paraphrased`, or `reference-only`, add a non-empty `## Evidence limitations` section and include each applicable statement:
    - `unknown`: `Capture fidelity is unknown; treat this Source as no stronger than a paraphrase. The original evidence was not independently revalidated in the vault.`
    - `paraphrased`: `This claim relies on an owner-reviewed paraphrase. Do not present its wording as a quotation or direct assertion of the original evidence.`
    - `reference-only`: `This Source records an external reference without preserving original bytes in the vault. Recheck the referenced material before relying on exact wording.`
    Retain weaker-source limitations when stronger evidence is also cited by that draft.
11. Run `uv run --locked python scripts/validate_vault.py`. Its capture-fidelity warnings do not block draft creation, but every warning must be resolved or reported. An owner-approved multi-agent mutation additionally uses the immutable-base change-validator protocol and optional independent reviewer; unavailable requested review requires direct owner review and an incomplete-coverage report.

## Output

List revalidated Source paths and capture modes and exact Daily paths; list created, updated, skipped, duplicate, contradictory, and uncertain items; include every draft path and citation, conflicts and Evidence limitations, and the owner-only final claim/citation/limitation review and optional evergreen promotion. Every draft must have valid evidence links and a conservative confidence level.
