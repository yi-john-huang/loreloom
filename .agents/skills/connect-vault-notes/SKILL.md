---
name: connect-vault-notes
description: Find and add meaningful relationships among a bounded set of Loreloom Knowledge notes and MOCs. Use for orphan review, near-duplicate detection, cross-topic navigation, reciprocal context, or approved backlink improvements. Starts read-only and does not mass-link keywords, create placeholders, merge, rename, or delete notes.
---

# Connect Vault Notes

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `docs/CONVENTIONS.md`.
2. Confirm exact Knowledge and MOC scope plus whether edits are already authorized.
3. Search titles, aliases, likely synonyms, existing links, and relevant MOC entry points.
4. Discover and rank candidate relationships sequentially in the root agent. Use `$orchestrate-vault-work` only after explicit owner opt-in for disjoint topic slices or consequential architecture review.
5. Rank candidate links by navigation value, evidence, and confidence. Explain the relationship in both directions rather than matching keywords alone.
6. Report near-duplicates separately; do not merge or rename during link discovery.
7. Apply only expressly authorized link additions through the root agent. Preserve human prose and Wiki human blocks.
8. Run `uv run --locked python scripts/validate_vault.py`. An owner-approved multi-agent mutation additionally uses the immutable-base change-validator protocol. Report ambiguous titles or rejected suggestions.

## Output

List proposed or added links with source path, target path, relationship phrase, confidence, and rationale. Include duplicate candidates, MOC gaps, skipped low-value links, and validation.
