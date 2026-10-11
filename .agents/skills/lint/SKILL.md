---
name: lint
description: Default lightweight Loreloom health check for the Wiki. Reports orphan pages, broken wikilinks, stale pages, unresolved contradictions, low-confidence pages, pages missing from index.md, and the review backlog. Use for a weekly check or when the owner says lint, check, or health. Read-only until the owner approves a repair.
---

# Lint

Produce one report on the state of the Wiki. Change nothing during the report pass.

## Steps

1. Read `CLAUDE.md`, `index.md`, and `log.md`.
2. Run the validator and keep its output:

   ```sh
   uv run --locked python scripts/validate_vault.py --mode daily
   ```

3. Run the Wiki report and keep its output:

   ```sh
   uv run --locked python scripts/lint_wiki.py
   ```

   Add `--stale-days <N>` when the owner wants a different age limit. The default is 180 days.
4. Read each page that the report lists under contradictions or under reviewed pages that fail the auto-accept rule. Confirm the finding and note the two claims and their sources.
5. Read `log.md` for `Needs review:` lines that have no later `review` entry for the same page. Those items are still open.
6. Write the report in this order. Give exact paths.
   1. Validator errors and warnings.
   2. Broken or ambiguous wikilinks.
   3. Unresolved contradictions, with both claims.
   4. Reviewed pages that fail the auto-accept rule.
   5. Review backlog: draft pages, pages in `Wiki/_review/`, and open `Needs review:` lines.
   6. Low-confidence pages.
   7. Orphan pages and pages missing from `index.md`.
   8. Stale pages.
7. Recommend at most five repairs. Order them by risk to the owner: wrong claims first, then missing links, then tidiness.

## Repairs

- Do not repair anything in the report pass.
- After the owner approves a repair, make only that repair. You may add a missing `index.md` line, fix a link in a Wiki page, or set a page that fails the auto-accept rule back to `status: draft`.
- Never edit `Sources/` or `Assets/`. Never delete or move a page without exact approval. Never resolve a contradiction yourself; the owner decides which claim stands.
- After a repair, append a `## [YYYY-MM-DD] lint | <summary>` entry to `log.md` and run the validator again.

## Output

Give the report, the recommended repairs, and the question of which repairs to apply. State plainly when there are no findings. Follow `docs/output-clarity-ladder.md` in the report text.
