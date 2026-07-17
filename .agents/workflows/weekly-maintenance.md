# Workflow: weekly maintenance

## Pass 1: read-only health report

1. Run `uv run python scripts/validate_vault.py`.
2. Inspect the requested date window using `created` and `updated`.
3. Find unprocessed captures, stale drafts, unresolved uncertainty, generated pages with changed inputs, missing MOC entry points, Projects without next actions, and Areas due for review.
4. Separate validator failures from editorial suggestions.
5. Rank at most five maintenance actions by value and risk.

Do not mutate the vault during Pass 1.

## Pass 2: approved repairs

After the owner approves exact actions:

1. apply the smallest relevant changes;
2. avoid bulk renaming or retagging;
3. preserve source records and human blocks;
4. run validation again;
5. report created, updated, moved, skipped, and uncertain items.

Promotion to evergreen, archive moves, deletions, commits, and pushes each require explicit authority.
