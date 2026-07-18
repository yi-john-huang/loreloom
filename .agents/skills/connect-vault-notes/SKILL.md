---
name: connect-vault-notes
description: Find and add meaningful relationships among a bounded set of Loreloom Knowledge notes and MOCs. Use for orphan review, near-duplicate detection, cross-topic navigation, reciprocal context, or approved backlink improvements. Starts read-only and does not mass-link keywords, create placeholders, merge, rename, or delete notes.
---

# Connect Vault Notes

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `docs/CONVENTIONS.md`.
2. Confirm exact Knowledge and MOC scope plus whether edits are already authorized.
3. Search titles, aliases, likely synonyms, existing links, and relevant MOC entry points.
4. For disjoint topic slices, assign read-only relationship discovery to `source-reader`. Use `vault-architect` for ambiguous note boundaries or cross-topic structure.
5. Rank candidate links by navigation value, evidence, and confidence. Explain the relationship in both directions rather than matching keywords alone.
6. Report near-duplicates separately; do not merge or rename during link discovery.
7. Before writing, record the immutable base commit and run the change-validator clean preflight with an external snapshot file and every exact output path.
8. Apply only expressly authorized link additions through the root agent. Preserve human prose and Wiki human blocks.
9. Run the vault validator and the final change validator against the same base and snapshot with every exact changed path. Report ambiguous titles or rejected suggestions.

## Output

List proposed or added links with source path, target path, relationship phrase, confidence, and rationale. Include duplicate candidates, MOC gaps, skipped low-value links, and validation.
