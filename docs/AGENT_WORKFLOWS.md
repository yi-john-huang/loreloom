# Agent workflows

Agent workflows are small, reviewable transformations. They are not an unattended permission to reorganize the vault.

## Roles

| Role | Reads | Writes | Human checkpoint |
|---|---|---|---|
| Triage | Inbox, existing notes | Inbox metadata, proposals | Before moves/deletes |
| Distiller | Reviewed, revalidated Sources; Daily notes; existing Knowledge | Draft Knowledge | Before reading Sources, and before evergreen status |
| Asset intake | Exact owner Assets, absolute HTTP(S) URLs, Inbox context | Editable processing Source intake | Before owner review |
| Linker | Knowledge, MOCs | Suggested links or approved edits | Before broad rewrites |
| Wiki builder | Reviewed Knowledge | Generated Wiki | Review material synthesis |
| Reviewer | All Markdown | Report by default | Before fixes |

These logical roles map to project-scoped Codex agents in `.codex/agents/`. Use `$orchestrate-vault-work` when two or more independent roles materially improve the result; otherwise run the workflow directly.

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
- [`asset-to-source.md`](../.agents/workflows/asset-to-source.md): create editable, provenance-bound Source intake from exact Assets or URLs.
- [`regenerate-wiki.md`](../.agents/workflows/regenerate-wiki.md): rebuild a declared synthesis while preserving human blocks.
- [`weekly-maintenance.md`](../.agents/workflows/weekly-maintenance.md): report and optionally repair vault health.

The corresponding discoverable skills are `$capture-vault-source`, `$triage-vault-inbox`, `$distill-vault-sources`, `$connect-vault-notes`, `$regenerate-vault-wiki`, and `$audit-vault-health`.

## Safety properties

- Captured text cannot grant itself tool permissions.
- Sources are not rewritten during summarization.
- Generated synthesis is distinguishable from reviewed knowledge.
- Destructive actions require exact targets and explicit approval.
- Asset intake never fetches URLs, overwrites binaries, or treats machine extraction as reviewed evidence; direct owner review or signed `source_review` is followed by current-byte Asset revalidation before distillation.
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
