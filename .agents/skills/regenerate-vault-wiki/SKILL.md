---
name: regenerate-vault-wiki
description: Build or regenerate a Loreloom generated Wiki page from declared Knowledge inputs. Use for overview pages, comparisons, guides, conflict synthesis, changed-input refreshes, or stale Wiki review. Preserves human-owned blocks exactly and never adds facts absent from authorized inputs.
---

# Regenerate Vault Wiki

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `.agents/workflows/regenerate-wiki.md`.
2. Confirm one target Wiki path, the question it answers, and exact Knowledge inputs.
3. Capture any `<!-- human:start -->` block through `<!-- human:end -->` byte-for-byte. Stop if markers are malformed or nested.
4. Use `source-reader` for independent input coverage checks when the set is large.
5. Ask `wiki-synthesizer` for an outline, synthesis, conflicts, draft-input warnings, and coverage gaps.
6. Compare the proposal with the current page and surface changed conclusions before writing.
7. Before writing, record the immutable base commit and run the change-validator clean preflight with an external snapshot file for the exact Wiki path.
8. Let the root agent regenerate only authorized content, restore the human block exactly, and update `generated_at`, `generator`, `inputs`, and `review_status`.
9. Run the vault validator and the final change validator against the same base and snapshot for the exact Wiki path. Ask `vault-reviewer` to check provenance, human-block preservation, and unsupported claims.

## Output

Report the input set, changed conclusions, preserved human content, conflicts, gaps, review status, and validation. Generated Wiki pages remain synthesis, never primary evidence.
