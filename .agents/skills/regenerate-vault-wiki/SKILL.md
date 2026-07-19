---
name: regenerate-vault-wiki
description: Build or regenerate a Loreloom generated Wiki page from declared Knowledge inputs. Use for overview pages, comparisons, guides, conflict synthesis, changed-input refreshes, or stale Wiki review. Preserves human-owned blocks exactly and never adds facts absent from authorized inputs.
---

# Regenerate Vault Wiki

## Workflow

1. Read `AGENTS.md`, `.agents/policies/vault-policy.md`, and `.agents/workflows/regenerate-wiki.md`.
2. Confirm one target Wiki path, the question it answers, and exact Knowledge inputs.
3. Capture any `<!-- human:start -->` block through `<!-- human:end -->` byte-for-byte. Stop if markers are malformed or nested.
4. Let the root agent inspect all authorized inputs and propose the outline, synthesis, conflicts, draft-input warnings, and coverage gaps.
5. Use `$orchestrate-vault-work` only after explicit owner opt-in when independent coverage or synthesis review materially benefits from advanced delegation.
6. Compare the proposal with the current page and surface changed conclusions before writing.
7. Let the root agent regenerate only authorized content, restore the human block exactly, and update `generated_at`, `generator`, `inputs`, and `review_status`.
8. Run `uv run --locked python scripts/validate_vault.py`. An owner-approved multi-agent mutation additionally uses the immutable-base change-validator protocol and optional independent reviewer. Material synthesis always requires owner review; report incomplete specialist coverage when a requested reviewer is unavailable.

## Output

Report the input set, changed conclusions, preserved human content, conflicts, gaps, review status, and validation. Generated Wiki pages remain synthesis, never primary evidence.
