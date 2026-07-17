# Workflow: regenerate Wiki

## Goal

Build a traceable synthesis from declared Knowledge inputs while preserving human-owned text.

## Procedure

1. Confirm the target page, question, and exact input set.
2. Read the input Knowledge notes and their declared Sources as authorized.
3. Capture the existing human block exactly, including whitespace.
4. Identify consensus, conflicts, provisional drafts, and missing coverage.
5. Propose an outline and call out conclusions that changed since the previous page.
6. Regenerate only after authorization.
7. Set `generated: true`, the current `generated_at`, `generator`, complete `inputs`, and `review_status`.
8. Restore the human block byte-for-byte.
9. Run `uv run python scripts/validate_vault.py` and inspect the diff.
10. Report changed conclusions, gaps, conflicts, and review needed.

## Rules

- Do not add model-memory facts that are absent from inputs.
- Do not hide a disagreement behind generic language.
- Do not treat an unreviewed generated page as canonical.
- If human markers are malformed or nested, stop rather than risk overwriting text.
