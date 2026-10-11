---
name: file-answer
description: Save a good answer from the current conversation as a Loreloom synthesis page in Wiki/synthesis/, link it from related pages, and update index.md and log.md. Use after the query skill when the owner says file it, save this answer, or keep this. Applies the same auto-accept rule as ingest.
---

# File answer

Turn the answer that the owner wants to keep into one synthesis page.

## Steps

1. Read `CLAUDE.md` and `index.md`. Read the sdd-mcp `output-clarity-ladder` skill (`~/.claude/skills/output-clarity-ladder/SKILL.md`; source: https://github.com/yi-john-huang/sdd-mcp/blob/master/skills/output-clarity-ladder/SKILL.md) before you write prose. For Traditional Chinese prose, also read its `references/zh-TW.md`.
2. Identify the answer to file. Use the most recent answer unless the owner names another one. Keep its claims and citations. Do not add new claims.
3. Check `index.md` and `Wiki/synthesis/` for a page that answers the same question. Update that page when one exists and it does not have `status: evergreen` or `reviewed_by: owner`. Otherwise create a new page.
4. Write `Wiki/synthesis/<Title>.md`. Use a short title that names the question or topic. Use this shape:

   ```markdown
   ---
   title: <Title>
   type: synthesis
   status: draft
   confidence: high|medium|low
   sources:
     - "[[Wiki/concepts/<page used>]]"
     - "[[Sources/<source used>]]"
   updated: YYYY-MM-DD
   agent: <your agent name>
   ---

   # <Title>

   ## Question

   ## Answer

   ## Limits

   ## Sources
   ```

   - `sources` lists every Wiki page and Source that the answer cites. A synthesis page with no sources stays a draft.
   - `confidence` is no higher than the lowest confidence among the pages that the answer relies on.
   - Rewrite the answer so that it follows the `output-clarity-ladder` skill. Keep every number, condition, and uncertainty.
   - Remove any statement that was marked "not from the vault", or keep it under `## Limits` with that label.
5. Run the gate and set the status from the result:

   ```sh
   uv run --locked python scripts/ingest_gate.py "Wiki/synthesis/<Title>.md"
   ```

   - `accept`: set `status: reviewed` and `reviewed_by: agent`.
   - `review`: keep `status: draft` and add a `Needs review:` line to the `log.md` entry.
   - Never set `status: evergreen` or `reviewed_by: owner`.
6. Link the new page. Add one line under a `## Related` section on up to three of the most related Wiki pages. Skip a page that has `status: evergreen` or `reviewed_by: owner`, and report the skipped link to the owner.
7. Add one line for the page under `## Synthesis` in `index.md`.
8. Append one entry to the end of `log.md`:

   ```markdown
   ## [YYYY-MM-DD] query | <Title>

   - Filed: [[Wiki/synthesis/<Title>]] with status reviewed.
   - Linked from: [[Wiki/concepts/<page>]]
   ```

9. Run `uv run --locked python scripts/validate_vault.py --mode daily`. Fix every error. Report every warning.

## Output

Report the page path, its status, the pages that now link to it, each `Needs review:` item, and the validator result. Do not commit or push unless the owner asks.
