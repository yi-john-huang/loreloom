# Migrating to the lightweight flow

This guide is for a vault that was built with the earlier strict flow. It explains what changed, what stays the same, and how to move `Knowledge/` notes to `Wiki/` pages step by step.

You do not have to migrate. Old notes stay readable, old wikilinks keep working, and strict mode still runs every earlier check.

## What changed

| Area | Before | Now |
|---|---|---|
| Default flow | Source review, then Concept draft, then owner review of each claim | `ingest`, `query`, `file-answer`, and `lint`; the owner reviews exceptions only |
| Agent instructions | `AGENTS.md` | `CLAUDE.md` for the default flow; `AGENTS.md` for safety rules and strict mode |
| Working layer | `Knowledge/` Concepts | `Wiki/sources`, `Wiki/entities`, `Wiki/concepts`, `Wiki/synthesis` |
| Navigation | MOCs | `index.md` first; MOCs still work |
| History | Git only | `log.md` plus Git |
| Validator | One mode with every check | `--mode daily` (default) and `--mode strict` |
| `Sources/` | Full Source schema required | Raw evidence; any Markdown file passes daily mode |

## What stays the same

- `Sources/` and `Assets/` hold the evidence. Agents never change an existing file there.
- Markdown is the only store. There is no database and no vector index.
- Only the owner sets `status: evergreen`.
- Numbers and contradictions are never auto-trusted.
- The Jev advisory toggle, `validate_change.py`, signed review, and approval receipts work as before. They belong to strict mode.

## The `Wiki/` folder name

The lightweight plan writes the folder as lowercase `wiki/`. Loreloom keeps the existing `Wiki/` folder and puts the new sections inside it:

```text
Wiki/
  sources/  entities/  concepts/  synthesis/  _review/
```

The reason is the case clash. `Wiki/` and `wiki/` are the same folder on macOS and Windows and different folders on Linux, so a vault with both would break when it moves between machines. The validator reports an error when both exist.

Old generated pages that sit directly under `Wiki/` with `type: wiki` keep their strict-mode rules. The validator tells the two kinds apart by location: a page inside one of the five sections is a lightweight page, and any other page under `Wiki/` is a legacy generated page.

## Step 1: switch the daily check

Run the two modes once and compare:

```sh
uv run --locked python scripts/validate_vault.py --mode daily
uv run --locked python scripts/validate_vault.py --mode strict
uv run --locked python scripts/doctor_vault.py
```

The doctor prints the configured mode on its `validation-mode` line. The default is `daily`. To keep strict as your default, set this in `pyproject.toml`:

```toml
[tool.loreloom]
validation_mode = "strict"
```

The `LORELOOM_VALIDATION_MODE` environment variable overrides `pyproject.toml`, and `--mode` overrides both.

## Step 2: start using the new flow

Create `index.md`, `log.md`, and the five `Wiki/` sections if your vault does not have them. Copy them from the template repository. Then ask your agent to ingest one source. New work goes to `Wiki/`; nothing forces you to touch old notes.

## Step 3: copy Knowledge notes when you want to

`scripts/migrate_knowledge_to_wiki.py` copies Concept notes from `Knowledge/` to `Wiki/concepts/`. It keeps the folder structure and the note body.

```sh
# Dry run (default): print the plan and write nothing
uv run --locked python scripts/migrate_knowledge_to_wiki.py

# Write the planned pages
uv run --locked python scripts/migrate_knowledge_to_wiki.py --apply

# Migrate chosen notes only
uv run --locked python scripts/migrate_knowledge_to_wiki.py --apply "Knowledge/My note.md"
```

The script never changes, moves, or deletes a Knowledge note, and it never overwrites an existing Wiki page. You can run it again at any time; pages that already exist are skipped.

### Frontmatter mapping

| Knowledge field | Wiki field | Rule |
|---|---|---|
| `title` | `title` | Copied |
| `type: concept` | `type: concept` | Notes of any other type are skipped |
| `status: draft` | `status: draft` | Copied |
| `status: evergreen` | `status: evergreen` with `reviewed_by: owner` | A human already approved the note |
| `status: archived` or any other value | none | The note is skipped and stays in `Knowledge/` |
| `confidence` | `confidence` | Copied; a missing or invalid value becomes `low` |
| `sources` | `sources` | Copied; an evergreen note with no sources becomes `draft` |
| `updated` | `updated` | Copied; a missing value becomes today |
| `created`, `tags`, `aliases`, `reviewed` | same names | Copied when they are not empty |
| none | `migrated_from` | The path of the Knowledge note |
| `agent` and other fields | none | Not copied |

A migrated draft is not auto-accepted. It stays `draft` until the owner reviews it or the agent runs the gate on it during a later ingest.

### After the copy

1. Add each new page to `index.md` under `## Concepts`. Ask the agent to do it, or write the lines yourself.
2. Add one `migrate` entry to `log.md` that lists the copied notes.
3. Run `uv run --locked python scripts/validate_vault.py --mode daily`.
4. Decide what to do with each old note. Until you retire it, the vault holds two notes with the same file name, so a wikilink that uses only the note name becomes ambiguous and the validator reports it. Links that use the full path, such as `Knowledge/My note`, keep pointing at the old note.
5. To retire an old note, update the links that point to it, then delete it in Obsidian or move it to `Archive/` with archival metadata. An agent needs your exact approval for either action.

## Legacy generated Wiki pages

A `type: wiki` page lists `Knowledge/` notes as `inputs`. The script does not convert these pages. Keep them as they are, or ask the agent to file a new synthesis page in `Wiki/synthesis/` that cites the migrated concept pages and then retire the old page yourself.

## Strict mode on a lightweight vault

Strict mode checks lightweight pages too, with three extra rules:

- `title` must match the file name;
- each wikilink in `sources` must point to `Sources/`, `Daily/`, or `Assets/` (a synthesis page may also cite `Wiki/` pages);
- a `reviewed` or `evergreen` page may cite a Source only when that Source has the full strict frontmatter and the owner has reviewed it.

Raw files that the lightweight flow added to `Sources/` fail strict mode until they carry the full Source frontmatter. Use `$capture-vault-source` and owner review for the Sources that matter, and keep the rest for daily mode.

The guarded change validator (`scripts/validate_change.py`) and the Jev `claim-support` advisory still target the strict layout: `Sources/` records and `Knowledge/` drafts. They do not apply the auto-accept rule to lightweight pages.
