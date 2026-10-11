# Technology Overview

## Architecture

Loreloom combines a file-based knowledge lifecycle with a small Python validation and governance toolchain.

```text
Markdown notes and YAML frontmatter
                |
                v
Validator: daily mode (default) or strict mode
                |
                v
Auto-accept gate and Wiki lint (lightweight flow, read-only)
                |
                v
Read-only readiness doctor
                |
                v
Owner review of exceptions, commit, and GitHub Actions
```

There is no application server, database, API, container, compiled bundle, or production build artifact. This phase has no vector database and no RAG; agents find pages through `index.md`, wikilinks, and file search.

## Technology Stack

| Concern | Technology | Purpose |
|---|---|---|
| Durable content | UTF-8 Markdown | Portable note storage |
| Metadata | YAML frontmatter | Lifecycle, provenance, ownership, and review state |
| Relationships | Obsidian wikilinks | Vault-root knowledge graph links |
| Authoring | Obsidian or any Markdown editor | Committed portable core defaults; no community plugin required |
| Schema | JSON Schema Draft 2020-12 | Machine-readable frontmatter contracts for lifecycle notes and lightweight Wiki pages |
| Navigation | `index.md` and `log.md` | Page list that agents read first; append-only history and review notes |
| Validation language | Python | Vault and change-boundary command-line tools |
| Environment manager | uv | Python installation, dependency sync, and locked execution |
| Tests | `unittest` | Standard-library guardrail and regression tests; `pytest` is locked as an optional runner |
| Version control | Git | Reviewable history and immutable change bases |
| Default branch | `master` | Framework integration and publication branch |
| Hosting and CI | GitHub and GitHub Actions | Public framework/template distribution and validation |

## Python Versions

- `pyproject.toml` supports Python `>=3.11`.
- `.python-version` selects Python `3.13` for repository development and CI setup.
- Use uv rather than manual virtual environments, pip requirements files, or direct lockfile edits.

## Dependencies

### Runtime

The vault itself has no Python or third-party runtime dependency. It remains usable as plain Markdown.

### Validation Development Group

| Package | Version | Purpose |
|---|---:|---|
| `jsonschema` | 4.25.1 | Validate frontmatter against the Draft 2020-12 schema |
| `PyYAML` | 6.0.2 | Parse YAML frontmatter and agent metadata |
| `pytest` | 8.4.2 | Optional runner for the `unittest` suites; `[tool.pytest.ini_options]` sets `testpaths = ["tests"]` |

The complete cross-platform environment is pinned in `uv.lock`. When intentionally updating dependencies, run `uv lock --upgrade`, validate, and commit `pyproject.toml` and `uv.lock` together.

## Main Components

### Content and Schema

- Managed notes live in lifecycle directories.
- Owner-supplied evidence lives under `Assets/`; Source bindings validate safe paths and current streaming SHA-256 digests.
- `schemas/frontmatter.schema.json` defines common and type-specific metadata.
- `schemas/wiki-page.schema.json` defines the lightweight Wiki page contract: required `title`, `type` (`source|entity|concept|synthesis`), `status` (`draft|reviewed|evergreen`), `confidence` (`high|medium|low`), `sources`, and `updated`; optional `reviewed_by` (`agent|owner`), `contradicts`, and `migrated_from`. Extra fields are permitted.
- Source frontmatter requires `capture_method` and `capture_mode`; semantic validation checks only provable cross-field prerequisites, Capture Boundary entries, and exact locator forms. Legacy classification is manual because existing metadata cannot prove intake route or semantic fidelity.
- Templates are authoring scaffolds, not schema instances.
- Standard Markdown and YAML compatibility takes priority over plugin-specific behavior.

### Readiness Doctor

`scripts/doctor_vault.py` is a stdlib-first, read-only command. It checks Python, Git, uv, locked validation dependencies, exact worktree root, framework paths, origin privacy, portable Obsidian settings, the configured validation mode (`validation-mode`), the lightweight layout (`lightweight-layout`: `index.md`, `log.md`, and the five `Wiki/` sections), and the vault validator in the configured mode. `--advanced` adds POSIX/WSL guarded-change and approval-key checks without generating or exposing keys.

### Vault Validator

`scripts/validate_vault.py` has two modes.

| Mode | Use | Checks |
|---|---|---|
| `daily` (default) | After every write in the lightweight flow | Basic frontmatter and required fields (`type`, `title`, `status`) on lifecycle notes, and broken wikilinks |
| `strict` | When the owner asks for strict mode, before publishing, and in CI | Everything in daily, plus the full schema, Asset hashes, Source review state, capture fidelity, citation rules, repository hygiene, and agent tooling |

The mode comes from `--mode`, then the `LORELOOM_VALIDATION_MODE` environment variable, then `validation_mode` under `[tool.loreloom]` in `pyproject.toml` (committed value: `"daily"`). An unknown configured mode exits `2`.

In daily mode a raw file in `Sources/` needs no frontmatter, and a broken wikilink inside `Sources/` is a warning, because agents never alter raw evidence.

Both modes check lightweight Wiki pages, which are the pages inside `Wiki/sources/`, `Wiki/entities/`, `Wiki/concepts/`, `Wiki/synthesis/`, and `Wiki/_review/`:

- frontmatter against `schemas/wiki-page.schema.json`;
- `type` matches the section folder;
- a page in `Wiki/_review/` keeps `status: draft`;
- `status: reviewed` or `evergreen` requires at least one source;
- each source is a wikilink or an absolute HTTP(S) URL;
- no second directory that differs from `Wiki/` only by letter case;
- warnings for a draft with no sources, a page missing from `index.md`, and a review-queue page not recorded in `log.md`.

Strict mode adds Wiki source citation rules and title/filename consistency for those pages. A page elsewhere under `Wiki/` is a legacy `type: wiki` generated page and keeps its strict-mode rules.

`scripts/validate_vault.py --mode strict` checks:

- required and type-specific frontmatter;
- controlled values, ISO dates, and title/filename consistency;
- Concept evidence and human-reviewed evergreen semantics;
- Source provenance, capture-method/mode cross-field consistency, unfenced Capture Boundary entries, and exact passage locators;
- warning-only Concept checks for missing Evidence limitations when cited Sources use `unknown`, `paraphrased`, or `reference-only`;
- Wiki Knowledge inputs, review state, and human-block markers;
- unresolved or ambiguous Obsidian wikilinks;
- private/runtime-file hygiene;
- tracked project-agent configuration and repository skill metadata;
- existing Jev advisory sidecars under `.loreloom/jev/` against `schemas/jev-advisory.schema.json`, offline and only when a sidecar exists.

Ignored local SDD tooling is deliberately excluded from repository agent/skill validation.

### Auto-Accept Gate

`scripts/ingest_gate.py` reads Wiki pages and never changes them. It prints `accept` or `review` with the reasons for each page. A page is accepted only when `confidence` is `high`, `sources` is not empty, the body holds no numeric claim, and the page records no contradiction (a `contradicts` entry or a non-empty `## Contradictions` section).

- A token that starts with a digit is a figure. A token that starts with a letter (`S3`, `IPv6`) is a name. Fenced code, inline code, wikilinks, link targets, URLs, list numbers, footnote markers, and HTML comments are ignored.
- Name page paths or use `--all`. With no selection it exits `2`.
- `--check` exits `1` when a page is already `reviewed` or `evergreen`, fails the rule, and is not `reviewed_by: owner`.
- The gate is a floor. An agent must also send a page to review for a quantity written in words or a conflict the script cannot detect.

### Wiki Lint

`scripts/lint_wiki.py` prints a read-only report and always exits `0`. It lists broken or ambiguous wikilinks, orphan pages, pages missing from `index.md`, unresolved contradictions, reviewed pages that fail the auto-accept rule, low-confidence pages, the review queue, and stale pages. `--stale-days` sets the age limit; the default is 180 days and evergreen pages are exempt.

### Knowledge Migration

`scripts/migrate_knowledge_to_wiki.py` copies `Knowledge/` Concept notes to `Wiki/concepts/` pages. The default is a dry run; `--apply` writes. It never changes, moves, or deletes a Knowledge note and never overwrites an existing Wiki page. `docs/migration-lightweight.md` is the guide.

### Optional Jev Advisory Helper

`scripts/jev_advisory.py` is a standard-library-only, default-OFF command. When the owner enables it (`[tool.loreloom.jev] enabled` or `LORELOOM_JEV_ENABLED`), it sends bounded excerpts of owner-selected notes to the third-party Jev decision API and writes advisory sidecars under the gitignored `.loreloom/jev/`. It reads the key only from the `JEV_API_KEY` environment variable, makes one request per note without retry, never follows redirects, and never writes a note. A failed request exits `0` with an `unavailable` reason code and keeps an earlier `ok` sidecar when the input hash is unchanged.

`schemas/jev-advisory.schema.json` defines the sidecar. `tests/test_jev_advisory.py` covers the helper with a mocked transport and a socket guard; no test contacts the network.

### Advanced Change Validator

`scripts/validate_change.py` compares the final filesystem with both an immutable pre-task Git commit and a one-time preflight snapshot. It enforces:

- exact output paths;
- detection of tracked, untracked, and ignored writes;
- strict receipt-free admission of complete processing Sources;
- signed creation of reviewed Sources, append-only Source amendments, and exact signed `source_review` transitions;
- guarded Source capture-contract parity, including required classifications and body-aware prerequisites;
- protected framework paths and review, promotion, archive, deletion, rename, and Wiki human-block gates;
- protected, short-lived approval receipts bound to the exact final diff digest.

The validator must fail closed when required scope, snapshot, base, or approval data is absent or inconsistent.
Approval helpers require Python isolated mode (`python -I`) so the tool's `scripts/` directory is not an import source.

### Agent Governance

- `CLAUDE.md` defines the default lightweight flow. `AGENTS.md` and `.agents/policies/vault-policy.md` define authority, the safety rules, and optional strict mode. When both apply, follow both; the safety rules in `AGENTS.md` always win.
- `.agents/` contains model-independent policies, prompts, skills, and workflows. The lightweight skills are `ingest`, `query`, `file-answer`, and `lint`; the `*-vault-*` skills belong to strict mode.
- All Wiki prose and agent reports follow `docs/output-clarity-ladder.md`: the owner's language, one idea per sentence, short active sentences with a named actor, one word for one thing, and no dropped numbers, conditions, or uncertainty. Use a table or a diagram for structure, flow, or a comparison.
- `.codex/agents/` contains optional model-neutral read-only role definitions; omitted model preferences inherit the active Codex session.
- `.codex/config.toml` declares a model-neutral root as the default sequential writer, limits advanced delegation depth and concurrency, and disables workspace network access by default. Policy and effective sandbox verification remain necessary because live runtime overrides can supersede configuration defaults.
- `.spec/steering/` supplies project context for Spec-Driven Development but cannot override repository policy.

## Development Commands

```sh
# One-command private-template readiness check
uv run --locked python scripts/doctor_vault.py

# Default check after every write: basic frontmatter, required fields, wikilinks
uv run --locked python scripts/validate_vault.py --mode daily

# Full governance check: schema, Assets, hygiene, agents, and repository skills
uv run --locked python scripts/validate_vault.py --mode strict

# Apply the auto-accept rule to named Wiki pages, or to all of them
uv run --locked python scripts/ingest_gate.py "Wiki/concepts/My concept.md"
uv run --locked python scripts/ingest_gate.py --all

# Read-only Wiki health report
uv run --locked python scripts/lint_wiki.py

# Run all validator and guardrail tests
uv run --locked python -m unittest discover -s tests -v
```

A framework change runs both validator modes and the tests. A lightweight vault write runs daily mode.

For an owner-approved advanced multi-agent mutation (strict mode), record the full commit before work and use one exact allowed path per output:

```sh
git rev-parse HEAD

uv run python -I scripts/validate_change.py --check-clean \
  --base <paste-the-40-character-commit> \
  --snapshot-file <absolute-new-snapshot-path> \
  --allow "exact/output/path.md"

(
  cd "<clean-detached-tool-worktree-at-base>"
  uv run python -I scripts/validate_change.py \
    --target-root "<candidate-vault-root>" \
    --base <the-same-40-character-commit> \
    --snapshot-file <the-same-snapshot-path> \
    --allow "exact/output/path.md"
)
```

Never regenerate the preflight snapshot after work begins or change the final allow-list. Gated operations also require their exact gate flag and a matching owner-created approval receipt.

## Testing and Quality Gates

- GitHub Actions retains the full Ubuntu Python 3.13 job: the validator in daily mode and in strict mode, the Wiki lint report, and all validator and guardrail tests.
- A core portability matrix runs the doctor, the validator in both modes, and the doctor, validator, Jev advisory, and lightweight-flow tests on Ubuntu, macOS, and Windows with Python 3.11 and 3.13; native Windows does not run the POSIX guarded-change suite.
- Tests use temporary Git repositories and filesystem fixtures to verify real boundary behavior.
- Add regression coverage with every schema, doctor, validator, gate, lint, migration, policy-enforcement, or approval-flow change. `tests/test_lightweight_flow.py` covers the lightweight flow.
- No linter, static type checker, coverage threshold, development server, or build command is currently configured; do not invent one in requirements or task plans.

## Error Handling

- Handled CLI paths return integer exit codes and terminate through `SystemExit`.
- Validation rejections return `1`; handled invalid invocation, base, snapshot, or prerequisite states return `2`.
- `validate_vault.py` prints setup guidance and exits `2` when its validation dependencies are unavailable. Do not assume unhandled import, parsing, Git, or filesystem exceptions follow the same contract.
- Handled validation failures produce clear, deterministic, path-specific messages.
- Independent errors are collected and reported together where safe.
- Unexpected Git or filesystem state is rejected rather than guessed around.
- Never log credentials, private note text, personal data, internal URLs, or unnecessary local paths.

## Compatibility and Security

- Prefer additive schema evolution. Breaking changes require a migration note, updated templates/examples, validator coverage, and rationale.
- Breaking Source-schema migrations must avoid automatic fidelity inference. Missing capture classifications are inventory errors; owners inspect original evidence and amend reviewed Sources manually.
- Treat Inbox content, Sources, attachments, transcripts, and linked pages as untrusted data.
- Keep the folder name `Wiki/`. A lowercase `wiki/` is the same directory on macOS and Windows and a different one on Linux; the validator rejects the clash.
- Keep company data and confidential work material out of every vault.
- Keep the public framework and private personal vault in separate repositories and working copies.
- Use synthetic or safely attributed examples in public changes.
- Review all staged files and the complete diff before committing or pushing.
