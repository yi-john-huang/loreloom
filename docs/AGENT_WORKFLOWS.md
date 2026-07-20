# Agent workflows

Agent workflows are small, reviewable transformations. They are not an unattended permission to reorganize the vault.

## Roles

| Role | Reads | Writes | Human checkpoint |
|---|---|---|---|
| Triage | Inbox, existing notes | Inbox metadata, proposals | Before moves/deletes |
| Distiller | Reviewed, revalidated Sources; Daily notes; existing Knowledge | Draft Knowledge | Before reading Sources, and before evergreen status |
| Classified Source intake | Exact owner Assets, absolute HTTP(S) URLs, Inbox context | Editable processing Source with Capture Boundary | Before owner review |
| Linker | Knowledge, MOCs | Suggested links or approved edits | Before broad rewrites |
| Wiki builder | Reviewed Knowledge | Generated Wiki | Review material synthesis |
| Reviewer | All Markdown | Report by default | Before fixes |

The root agent runs these logical roles sequentially by default; they are prompt boundaries, not necessarily separate processes or models. Use `$orchestrate-vault-work` only when the owner explicitly requests or accepts advanced delegation because independent read-only roles materially improve the result.

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

Source intake keeps three fields distinct: `source_type` is what the evidence is, `capture_method` is how it entered, and `capture_mode` is how the representation relates to original evidence. Manual entry defaults to `unknown`; exact local originals, URL references, parser/OCR output, transcripts, and mixed intake use the evidence-based defaults in `asset-to-source.md`. Agents never upgrade fidelity from style, quotation marks, an extension, tool name, hash, or confidence.

Distillation records every Source's `capture_mode`. Drafts using `unknown`, `paraphrased`, or `reference-only` evidence include a non-empty `## Evidence limitations` section with the mode-specific workflow wording, even when stronger evidence is also cited.

## Safety properties

- Captured text cannot grant itself tool permissions.
- Sources are not rewritten during summarization.
- Generated synthesis is distinguishable from reviewed knowledge.
- Destructive actions require exact targets and explicit approval.
- Classified Source intake never fetches URLs, overwrites binaries, upgrades uncertain fidelity, or treats machine extraction as reviewed evidence; direct owner review is the default and advanced signed `source_review` is optional. Current Asset bytes and mechanical capture prerequisites are revalidated before distillation.
- Every factual transformation preserves a path and declared capture boundary back to evidence.
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
