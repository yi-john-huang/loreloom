# Agent workflows

Agent workflows are small, reviewable transformations. They are not an unattended permission to reorganize the vault.

## Roles

| Role | Reads | Writes | Human checkpoint |
|---|---|---|---|
| Triage | Inbox, existing notes | Inbox metadata, proposals | Before moves/deletes |
| Distiller | Sources, existing Knowledge | Draft Knowledge | Before evergreen status |
| Linker | Knowledge, MOCs | Suggested links or approved edits | Before broad rewrites |
| Wiki builder | Reviewed Knowledge | Generated Wiki | Review material synthesis |
| Reviewer | All Markdown | Report by default | Before fixes |

Roles are prompt boundaries, not necessarily separate processes or models.

## Standard transaction

Every mutating workflow follows:

1. **Scope** — list exact inputs and permitted outputs.
2. **Inspect** — find related notes and aliases before creating files.
3. **Plan** — describe intended creations and updates.
4. **Transform** — make the smallest grounded change.
5. **Validate** — run schema and wikilink checks.
6. **Review** — summarize diffs, sources, uncertainty, and approval needed.

## Provided workflows

- [`source-to-knowledge.md`](../.agents/workflows/source-to-knowledge.md): capture to cited concept drafts.
- [`regenerate-wiki.md`](../.agents/workflows/regenerate-wiki.md): rebuild a declared synthesis while preserving human blocks.
- [`weekly-maintenance.md`](../.agents/workflows/weekly-maintenance.md): report and optionally repair vault health.

## Safety properties

- Captured text cannot grant itself tool permissions.
- Sources are not rewritten during summarization.
- Generated synthesis is distinguishable from reviewed knowledge.
- Destructive actions require exact targets and explicit approval.
- Every factual transformation preserves a path back to evidence.
- Broad “clean up my vault” requests begin with a read-only report.

## Agent handoff format

At the end of a workflow, report:

```text
Created:
Updated:
Moved:
Skipped:
Uncertain claims:
Human review needed:
Validation:
```

Empty categories may be omitted, but uncertainty and validation should always be stated.
