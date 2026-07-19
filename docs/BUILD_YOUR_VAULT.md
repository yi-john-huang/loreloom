# Build your personal vault

This guide turns a clean Loreloom template into a private, working Obsidian vault. You do not need to design the complete knowledge system before you begin. Start with a few real notes, keep the lifecycle folders stable, and let the structure grow from use.

## 1. Keep the framework and your vault separate

Use two repositories:

1. the public Loreloom framework, containing generic documentation, templates, examples, and automation;
2. your private personal vault, containing your notes, sources, projects, daily records, and attachments.

On GitHub, choose **Use this template -> Create a new repository** and select **Private**. A template-created repository has independent history. Do not use a public fork for personal notes, and do not add private notes directly to the public framework checkout.

Clone your new private repository:

```sh
git clone git@github.com:YOUR-NAME/YOUR-PRIVATE-VAULT.git my-vault
cd my-vault
uv sync --locked --dev
uv run python scripts/validate_vault.py
```

If you are starting locally, copy the framework into a new folder and configure a private remote before adding personal material.

## 2. Open the repository in Obsidian

In Obsidian, select **Open folder as vault** and choose the repository root—the folder containing `AGENTS.md`, `Inbox/`, `Knowledge/`, and the other lifecycle directories.

Recommended core settings:

- enable **Automatically update internal links**;
- set the attachment folder to `Assets/`;
- enable **Properties view** for YAML frontmatter;
- enable **Templates** and set its folder to `Templates/`;
- enable **Daily notes**, set its folder to `Daily/`, and use `YYYY-MM-DD` as the date format.

Community plugins are optional. Add them only after the plain-Markdown workflow works, and remember that a plugin can read the entire vault.

## 3. Understand where notes belong

Choose a location by the note's role, not its subject:

| You have | Put it in | Example |
|---|---|---|
| Something captured but not processed | `Inbox/` | A quick conference idea |
| A chronological observation | `Daily/` | What you learned today |
| A local PDF, image, HTML, audio, video, or other binary | `Assets/` | An owner-supplied report or photo |
| Original or faithfully recorded evidence | `Sources/` | An article, meeting record, or book note |
| One durable, cited idea | `Knowledge/` | “IAM roles use temporary credentials” |
| A generated overview from Knowledge | `Wiki/` | “AWS identity fundamentals” |
| A navigation page | `MOCs/` | “Technology” or “Japan” |
| A time-bound outcome | `Projects/` | “Prepare for AWS Summit” |
| An ongoing responsibility | `Areas/` | “Career development” |
| Inactive material worth retaining | `Archive/` | A completed project |

Do not create top-level folders such as `Tech/`, `Food/`, or `Travel/`. Keep those subjects connected through MOCs, links, aliases, and tags so one note can participate in several topics.

## 4. Personalize the empty vault

Start with a small amount of structure:

1. Edit `MOCs/Home.md` with three to five subjects you expect to revisit.
2. Add only current, outcome-oriented Projects.
3. Add Areas for responsibilities you intend to maintain.
4. Review `AGENTS.md` and adjust owner-specific rules without weakening provenance, privacy, or human-review gates.
5. Keep the examples during onboarding. When ready, replace every link under `Example topics` and `Action` in `MOCs/Home.md`, remove the `Examples/` subdirectories, and run `uv run python scripts/validate_vault.py` to catch any link you missed.

Avoid building a large taxonomy in advance. A useful MOC can begin with two links and a sentence explaining why they belong together.

## 5. Complete one knowledge cycle

Use one real item to learn the system end to end.

### Capture

Create an Inbox note from `Templates/Inbox.md`. Write enough context for your future self to understand why it matters.

### Collect evidence

Choose either an owner-controlled local Asset, an absolute HTTP(S) URL, or both. For a local PDF, image, HTML file, recording, video, or other binary, place it under `Assets/`, keep the filename stable, and record rights or sharing constraints. Use the streaming SHA-256 command and space-safe link forms in [[Assets/README|Assets]]. Do not execute active content.

### Create and review the Source

For manual intake, create a note from `Templates/Source.md`; bind each exact Asset path and current SHA-256, or record an absolute HTTP(S) URL without fetching it. URL-only intake does not promise reachability, freshness, or extraction. For semi-automatic intake, use `$capture-vault-source` on exact existing Assets or URLs. Both routes create only editable `status: processing`, `review_status: needs-review`, `reviewed: null` Sources.

The owner verifies provenance, current hashes, rights, fidelity, and machine-assisted limitations, then reviews directly or initiates an exact signed `source_review`. Immediately run `uv run python scripts/validate_vault.py`; stop before distillation on any bound-Asset error.

### Preserve the evidence

Keep every original Asset unchanged. A Source binds it through structured `assets` frontmatter and may use the space-safe references documented in [[Assets/README|Assets]]. Reviewed Sources are append-only; record authorized corrections as dated Amendments and put interpretation in Knowledge.

### Distill one concept

Only after Source review and current-byte revalidation, create a note from `Templates/Concept.md` for one durable claim. Keep it at `status: draft`, set conservative confidence, add an actual `[[Sources/...]]` or `[[Daily/...]]` evidence link, and have the owner review every claim and citation before promotion.

### Connect it

Link the concept from one relevant MOC and add only relationships that help navigation or understanding. Do not mass-link matching keywords.

### Synthesize when useful

Create a Wiki page only when several Knowledge notes answer a broader question. Declare its Knowledge inputs and keep the page generated and reviewable. Wiki pages summarize canonical Knowledge; they are not evidence themselves.

## 6. Introduce Codex safely

Open Codex at the vault root. Begin with a read-only onboarding request:

```text
Read AGENTS.md, .agents/policies/vault-policy.md, and
docs/BUILD_YOUR_VAULT.md. Audit this vault without changing files. Propose a
minimal personalization plan, identify the examples I can remove later, and
do not infer personal facts.
```

```text
Use $capture-vault-source on Assets/My report.pdf or https://example.com/report.
Start read-only, propose the exact Source path and metadata, record URLs without
fetching them, overwrite nothing, create no Knowledge, and label machine-assisted extraction.
```

Then use the narrowest repository skill for the task:

```text
Use $triage-vault-inbox on Inbox/My capture.md. Start read-only and show the
recommended disposition before changing anything.
```

```text
Use $distill-vault-sources on Sources/My source.md. Propose the fewest atomic
Knowledge drafts, cite exact evidence, and do not promote anything to
evergreen.
```

```text
Use $connect-vault-notes on these exact Knowledge and MOC paths. Suggest only
meaningful relationships and do not merge, rename, or delete notes.
```

Use `$regenerate-vault-wiki` for a declared Wiki synthesis, `$audit-vault-health` for a read-only review, and `$orchestrate-vault-work` only when a task genuinely has multiple independent workstreams.

Agents may draft Knowledge. You remain responsible for checking evidence and approving evergreen status, reviewed Wiki conclusions, archival, deletion, publication, commits, and pushes.

## 7. Establish a simple rhythm

A sustainable routine is more valuable than aggressive automation.

### Daily

- capture quickly in Inbox or Daily;
- add context and provenance while it is fresh;
- avoid reorganizing the whole vault during capture.

### Weekly

- triage a bounded set of Inbox notes;
- promote useful observations into cited Knowledge drafts;
- update one or two MOCs;
- review active Projects and Areas;
- run `uv run python scripts/validate_vault.py`;
- inspect the Git diff before committing.

### Monthly

- review orphaned or stale notes;
- regenerate important Wiki pages from their declared inputs;
- archive completed Projects with explicit approval;
- test that your backup can actually be restored.

## 8. Choose sync and backup deliberately

Use one real-time file-sync system for the vault. Obsidian Sync or an Apple-only iCloud setup can handle device synchronization; Git provides version history and review, not real-time coordination.

Do not point two real-time sync services at the same vault. Avoid editing the same note simultaneously on multiple devices, wait for file synchronization before Git operations, and keep at least one recoverable backup outside the live sync folder.

## 9. Protect personal material

- Keep the personal repository private.
- Store secrets in a password manager, not in Markdown.
- Treat `.gitignore` as convenience rather than a security boundary.
- Inspect staged files and history before every push.
- Do not copy entire copyrighted sources into a public repository.
- Re-create generic framework improvements in the public Loreloom checkout with synthetic examples; never merge personal-vault history upstream.

## 10. First-week checklist

- [ ] Private repository created from the template.
- [ ] Repository root opens correctly as an Obsidian vault.
- [ ] `uv sync --locked --dev` and validation succeed.
- [ ] `MOCs/Home.md` reflects a few real interests.
- [ ] One Daily or Inbox note has been captured.
- [ ] One owner-controlled Asset or absolute HTTP(S) URL has a processing Source with complete provenance.
- [ ] The Source has completed owner review and current-byte Asset revalidation.
- [ ] One cited Knowledge draft has been created and linked.
- [ ] Codex has completed a read-only audit before being allowed to write.
- [ ] One sync system and one recoverable backup are configured.
- [ ] The Git diff has been reviewed before the first personal commit.

Once this cycle feels natural, expand gradually. The goal is not to fill every directory; it is to create a trustworthy path from raw experience and evidence to connected, reviewable knowledge.
