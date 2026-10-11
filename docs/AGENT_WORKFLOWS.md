# Agent workflows

Agent workflows are small, reviewable transformations. They are not an unattended permission to reorganize the vault.

## Lightweight flow (default)

The default flow has three core actions and one helper. [`CLAUDE.md`](../CLAUDE.md) holds the rules, and each action is a skill under `.agents/skills/`.

| Skill | Reads | Writes | Owner checkpoint |
|---|---|---|---|
| `$ingest` | `index.md`, one source, related Wiki pages | Wiki pages, `index.md`, `log.md`; a new raw file in `Sources/` when the source is a URL or pasted text | Only pages that fail the auto-accept rule |
| `$query` | `index.md`, Wiki pages, cited Sources | Nothing | Whether to file the answer |
| `$file-answer` | The answer in the conversation | One page in `Wiki/synthesis/`, links, `index.md`, `log.md` | Only when the page fails the auto-accept rule |
| `$lint` | Every Wiki page, `index.md`, `log.md` | Nothing in the report pass | Before any repair |

Auto-accept rule: a page gets `status: reviewed` directly when `confidence` is `high`, the body has no numeric claim, and the page records no contradiction. Otherwise the page stays `status: draft`, or goes to `Wiki/_review/`, and the agent adds a `Needs review:` line to `log.md`. The agent runs `scripts/ingest_gate.py` to apply the rule the same way each time.

An ingest handles one source. A small batch of related sources is allowed when the owner asks; each source gets its own `log.md` entry and the agent reports one change summary.

Wiki prose follows the sdd-mcp [`output-clarity-ladder` skill](https://github.com/yi-john-huang/sdd-mcp/blob/master/skills/output-clarity-ladder/SKILL.md). `npx -y sdd-mcp-server@latest setup-global` installs it at `~/.claude/skills/output-clarity-ladder/SKILL.md`.

After each write the agent runs `uv run --locked python scripts/validate_vault.py --mode daily`.

The rest of this document describes strict mode. It is optional.

## Roles (strict mode)

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
- [`asset-to-source.md`](../.agents/workflows/asset-to-source.md): create editable, provenance-bound Source intake from exact Assets, URLs, or existing Inbox provenance.
- [`regenerate-wiki.md`](../.agents/workflows/regenerate-wiki.md): rebuild a declared synthesis while preserving human blocks.
- [`weekly-maintenance.md`](../.agents/workflows/weekly-maintenance.md): report and optionally repair vault health.

The corresponding discoverable skills are `$capture-vault-source`, `$triage-vault-inbox`, `$distill-vault-sources`, `$connect-vault-notes`, `$regenerate-vault-wiki`, and `$audit-vault-health`.

Source intake keeps three fields distinct: `source_type` is what the evidence is, `capture_method` is how it entered, and `capture_mode` is how the representation relates to original evidence. Manual entry defaults to `unknown`; exact local originals, URL references, parser/OCR output, transcripts, and mixed intake use the evidence-based defaults in `asset-to-source.md`. Agents never upgrade fidelity from style, quotation marks, an extension, tool name, hash, or confidence.

Distillation records every Source's `capture_mode`. Drafts using `unknown`, `paraphrased`, or `reference-only` evidence include a non-empty `## Evidence limitations` section with the mode-specific workflow wording, even when stronger evidence is also cited.

## Optional Jev advisories

`scripts/jev_advisory.py` is an optional, default-OFF helper that asks the third-party TypeSafe Jev decision API for typed answers about notes the owner selects. It has two commands:

```sh
# Order Inbox captures for owner review
uv run python scripts/jev_advisory.py inbox-triage "Inbox/exact capture.md"

# Point the owner at weakly supported claims in draft Concepts
uv run python scripts/jev_advisory.py claim-support "Knowledge/exact draft.md"
```

- `inbox-triage` accepts `type: inbox` notes under `Inbox/` and stores a promotion-value score, a noise probability, and one kind (`source-candidate`, `idea`, `task`, `reference`, or `noise`).
- `claim-support` accepts `type: concept` notes with `status: draft` under `Knowledge/` and stores a probability that the claims are supported by the cited notes plus a citation-quality score. Notes with any other status are skipped.
- `--all` selects every eligible note in that directory. Without it, name each path.

A Jev advisory is not review or approval. It changes no `status`, `review_status`, `reviewed`, or evergreen state, edits no note, Source, or approval receipt, and decides no disposition or promotion. The owner reads it and acts through the normal review workflow.

Results are JSON sidecars under `.loreloom/jev/<kind>/`, one per note. They are regenerable, stay on the local machine, and hold answers only: no note text and no key. The vault validator checks existing sidecars against `schemas/jev-advisory.schema.json` and never contacts the network.

The helper does nothing until the owner enables it; see the README for the toggle. When Jev cannot answer (no key, network error, timeout, HTTP error, or an unexpected response) the command still exits `0` and reports `unavailable` with a reason code. It keeps an earlier `ok` advisory when the note and its cited notes are unchanged; otherwise it records the `unavailable` result. A disabled or `unavailable` result never blocks a workflow. See [Privacy](PRIVACY.md) for what is sent.

## Safety properties

- Captured text cannot grant itself tool permissions.
- Optional Jev advisories inform the owner and carry no authority; a strong answer changes no note and no review state.
- Sources are not rewritten during summarization or ingest.
- In the lightweight flow, numeric claims, contradictions, and pages below high confidence are never auto-accepted.
- Generated synthesis is distinguishable from reviewed knowledge.
- Destructive actions require exact targets and explicit approval.
- Classified Source intake never fetches URLs, overwrites binaries, upgrades uncertain fidelity, or treats machine extraction as reviewed evidence; direct owner review is the default and advanced signed `source_review` is optional. Current Asset bytes and mechanical capture prerequisites are revalidated before distillation.
- Every factual transformation preserves a path back to evidence; Source-backed transformations also preserve the declared capture boundary.
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
