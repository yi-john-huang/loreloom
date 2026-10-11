# Loreloom

An AI-first Obsidian vault framework that weaves captured sources into an agent-maintained wiki and a connected multi-topic graph.

The framework treats Markdown as the durable source format and separates raw evidence from the pages an agent writes about it. It is intentionally model-agnostic: your vault should outlive any particular AI provider.

> [!IMPORTANT]
> This repository contains example content only. Create a new private repository from this template before adding personal or copyrighted material.

## 使用範圍 / Scope of use

- **Personal, single-user vault.** One owner captures sources, asks questions, and makes every review decision.
- **Life-domain personal notes.** Learning, health, travel, food, hobbies, personal finance, and similar subjects.
- **Not for company or work-confidential data.** Keep employer, client, and other confidential work material out of the vault.
- **Not multi-user collaboration.** There are no shared roles, no concurrent editors, and no multi-reviewer workflow.
- **No vector database or RAG in this phase.** Agents find pages through `index.md`, wikilinks, and ordinary file search.
- **Strict mode is optional.** Turn it on only when a vault needs high governance: signed review, Asset hashes, and claim checks.

## Lightweight flow (default)

The default flow is agent-first. The agent does the bookkeeping and the owner reviews exceptions only. Most sources should land in one or two minutes without a page-by-page review.

```text
Source (file in Sources/ or Assets/, URL, pasted text, Inbox capture)
                         |
                         v
        ingest: read index.md, then write Wiki pages
                         |
                         v
     auto-accept rule (scripts/ingest_gate.py)
          |                              |
 confidence high, no numbers,     anything else
 no contradiction                        |
          |                              v
          v                    status: draft (or Wiki/_review/)
  status: reviewed             + "Needs review:" line in log.md
          |                              |
          +--------------+---------------+
                         v
              index.md and log.md updated
                         |
                         v
   query: cited answer -> file-answer -> Wiki/synthesis/
```

| Action | Ask the agent | What happens |
|---|---|---|
| Ingest | "ingest `Sources/My article.md`" | The agent reads `index.md`, writes or updates pages in `Wiki/sources/`, `Wiki/entities/`, and `Wiki/concepts/`, applies the auto-accept rule, and updates `index.md` and `log.md`. |
| Query | "what do I know about …?" | The agent reads `index.md` first, answers with wikilink citations, and offers to file the answer. |
| File answer | "file it" | The agent saves the answer as one page in `Wiki/synthesis/` and links it from related pages. |
| Lint | "lint the wiki" | The agent reports orphan pages, broken links, stale pages, contradictions, low-confidence pages, and the review backlog. It changes nothing without approval. |

The full rules are in [CLAUDE.md](CLAUDE.md). The four skills are in `.agents/skills/ingest`, `query`, `file-answer`, and `lint`. Agents write Wiki prose in the plain style of the [Output clarity ladder](docs/output-clarity-ladder.md).

### Lightweight flow or strict mode?

| | Lightweight flow (default) | Strict mode (optional) |
|---|---|---|
| Fits | Everyday personal notes | A vault where each claim must be defensible |
| Who reviews | The agent accepts routine pages; the owner reviews numbers, contradictions, and low-confidence pages | The owner reviews every Source and every promoted claim |
| Working layer | `Wiki/sources`, `entities`, `concepts`, `synthesis` | `Knowledge/` Concepts and generated `type: wiki` pages |
| `Sources/` | Raw evidence; any Markdown file is accepted and agents never change it | Full Source frontmatter, capture fidelity, Asset hashes, and owner review state |
| Validation | `validate_vault.py --mode daily` | `validate_vault.py --mode strict` |
| Extras | `index.md`, `log.md`, `scripts/ingest_gate.py`, `scripts/lint_wiki.py` | `validate_change.py`, signed `source_review`, approval receipts, optional multi-agent execution |

Use strict mode when you publish a vault, when you depend on exact provenance, or before an important decision. Both modes read the same files, so you can run the strict validator on a lightweight vault at any time to see what it would require. To move old `Knowledge/` notes, see [Migrating to the lightweight flow](docs/migration-lightweight.md).

## Strict-mode model

```text
Owner Asset / absolute HTTP(S) URL / Inbox / Daily
                         |
                         v
Source processing (editable intake)
                         |
                         v
Owner review (direct or signed source_review)
                         |
                         v
Current-byte Asset revalidation
                         |
                         v
Concept draft -> owner claim/citation review -> optional evergreen
                         |
                         +------------------+
                         v                  v
                       Wiki               MOCs
                         |
                         v
                   Projects / Areas
```

Principles that hold in both flows:

- **One vault, many topics.** Technology, food, travel, hobbies, and other subjects connect through links and metadata instead of separate vaults.
- **Evidence before synthesis.** Source material is preserved; durable claims point back to it.
- **Numbers and contradictions are never auto-trusted.** They always go to the owner.
- **Agents are governed.** `CLAUDE.md`, `AGENTS.md`, and `.agents/policies/` define what an agent may read, create, or change.
- **Plain Markdown wins.** The vault remains usable without a plugin, database, or hosted service.

Strict mode adds:

- **Human-reviewed truth.** `Knowledge/` is canonical. AI may draft there, but a human changes `status` to `evergreen`.
- **Generated pages are replaceable.** `type: wiki` pages declare their inputs and can be rebuilt when models or prompts improve.
- **One root by default.** The active Codex session runs bounded skills sequentially; custom read-only agents are an owner-approved advanced option.
- **Skills are reusable.** Repo-scoped skills route capture, distillation, synthesis, auditing, and orchestration consistently.
- **Asset, URL, or Inbox intake.** Owners may supply local files in `Assets/`, record absolute HTTP(S) URLs, or identify exact existing Inbox provenance; `$capture-vault-source` creates editable processing Sources without fetching, copying, or overwriting resources.
- **Explicit capture fidelity.** Every Source separates `source_type` (what the evidence is), `capture_method` (how it entered the vault), and `capture_mode` (how the representation relates to original evidence). Conservative `unknown` classifications prevent manual summaries from masquerading as preserved evidence.

## Repository map

| Path | Purpose | Default owner |
|---|---|---|
| `CLAUDE.md` | Lightweight schema and workflow; agents read it first | Maintainers |
| `index.md` | List of every Wiki page; agents read it before ingest and query | Agent-maintained |
| `log.md` | Append-only history and `Needs review:` notes | Agent-maintained |
| `Inbox/` | Unprocessed capture | Human + agent |
| `Assets/` | Owner-supplied binary evidence | Human-led; agent read/bind only |
| `Sources/` | Raw evidence; agents add files and never change them. Strict mode: reviewed, append-only Source records | Human; agent adds new files |
| `Wiki/sources`, `entities`, `concepts`, `synthesis` | Lightweight pages with six-field frontmatter | Agent-written; owner reviews exceptions |
| `Wiki/_review/` | Optional queue of pages that wait for the owner | Agent proposes; owner decides |
| `Knowledge/` | Optional legacy layer. Strict mode: atomic, cited concept notes | Human-reviewed |
| `Wiki/*.md` with `type: wiki` | Strict mode: regenerable synthesis from Knowledge inputs | Agent-generated |
| `MOCs/` | Maps of Content and navigation | Shared |
| `Projects/` | Time-bound outcomes | Human-led |
| `Areas/` | Ongoing responsibilities | Human-led |
| `Daily/` | Chronological observations | Human-led |
| `Archive/` | Inactive material | Shared |
| `Templates/` | Note templates | Maintainers |
| `.agents/` | Prompts, policies, and workflows | Maintainers |
| `.codex/` | Project-scoped agent and orchestration configuration | Maintainers |
| `schemas/` | Machine-readable frontmatter contracts | Maintainers |

The lightweight plan names the wiki folder `wiki/`. Loreloom keeps the existing `Wiki/` and puts the new sections inside it, because a second folder that differs only by letter case breaks on macOS and Windows. See [Wiki/README.md](Wiki/README.md).

See [Architecture](docs/ARCHITECTURE.md) for the full lifecycle.

## How Loreloom compares

[Andrej Karpathy's LLM Wiki gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) is an intentionally abstract design pattern, Loreloom is the repository-and-vault framework documented here, and [Karpathy LLM Wiki](https://github.com/green-dalii/obsidian-llm-wiki) is Greener-Dalii's third-party Obsidian plugin inspired by the gist.

| Dimension | Karpathy's LLM Wiki gist | Loreloom | Karpathy LLM Wiki plugin |
|---|---|---|---|
| Form | An intentionally abstract idea file/prompt whose user and agent design the implementation | A GitHub template and Obsidian vault with schemas, validators, policies, skills, and portable core settings | A third-party Obsidian community plugin that implements an AI-generated wiki |
| First setup | Paste the gist into an agent and collaborate on structure and tooling | Create a private template copy, install Git and `uv`, run the read-only doctor, then open the repository root in Obsidian | Install and enable the plugin, then configure a supported cloud or local LLM provider |
| Knowledge boundary | Raw sources are immutable; the LLM owns and maintains the derived wiki; human review policy is left to the implementation | Default: `Sources/` is unchanged raw evidence and the agent maintains `Wiki/` pages, with numbers, contradictions, and low confidence sent to the owner. Strict mode: reviewed `Knowledge/` notes are canonical | Original vault notes are not modified; generated pages live under `wiki/`, and `reviewed: true` protects a generated page from overwrite |
| AI interface | Any external agent chosen by the user | An external agent (Claude Code, Codex, Grok, or another) that follows `CLAUDE.md` and the repository skills, plus terminal validators; no in-Obsidian AI command or query UI | Obsidian command-palette and side-panel workflows for ingest, query, lint, and maintenance |
| Retrieval | `index.md` first, with optional search such as `qmd`; no retrieval implementation is required by the gist | `index.md` first, then wikilinks, MOCs, and ordinary file search; no embedding database, RAG, or built-in query service | Lexical/LLM seed selection followed by Personalized PageRank over the generated wiki-link graph; no embedding index |
| Governance | A co-evolved schema/instruction file; enforcement depends on the implementation the user builds | Default: six-field page frontmatter, the auto-accept rule, a review log, and the daily validator. Strict mode: full frontmatter schema, provenance, Asset hashes, Source review, human promotion gates, and optional signed approvals | Plugin settings, lint/maintenance operations, contradiction states, and reviewed-page overwrite protection |
| Model and platform contract | Defined by the implementation the user chooses | Shipped Codex config has no model pin; core doctor/validator coverage runs on Ubuntu, macOS, and Windows with Python 3.11/3.13; advanced guarded changes require POSIX or WSL | The user configures a provider; [manifest metadata](https://github.com/green-dalii/obsidian-llm-wiki/blob/main/manifest.json) declares Obsidian 1.11+ and `isDesktopOnly: false` |
| Best fit | Building a minimal custom system from the original design pattern | A personal, Git-versioned vault that an agent keeps current, with an optional strict mode when provenance and human authority boundaries are the main requirement | Convenient in-Obsidian ingestion, generated-wiki navigation, and conversational query |

Choose the gist to design a bespoke system, the plugin for in-Obsidian AI operations, or Loreloom when you want a ready repository with a lightweight default and stricter traceability and review boundaries available on demand. Loreloom's contracts are detailed in [Architecture](docs/ARCHITECTURE.md), [Frontmatter schemas](docs/FRONTMATTER.md), and [Advanced multi-agent execution](docs/MULTI_AGENT.md).

External plugin facts above were checked on 2026-07-20. Volatile release, download, star, and test counts are intentionally omitted; use the linked primary sources for current details. The [Obsidian community registry entry](https://github.com/obsidianmd/obsidian-releases/blob/master/community-plugins.json) currently says the plugin has not been manually reviewed by Obsidian staff. It is not authored by Obsidian or Andrej Karpathy.

> [!WARNING]
> Do not install Karpathy LLM Wiki into a Loreloom vault during onboarding. The plugin defaults to `wiki/`, while Loreloom manages `Wiki/`; those names can resolve to the same directory on case-insensitive filesystems, and the two generated layers follow different authority rules. Use separate vaults rather than combining them without a separately designed integration.

## Start your own vault

1. On GitHub, choose **Use this template**, create a **private** repository, and do not include every branch. Use a fork only to contribute framework changes.
2. Clone your new repository by HTTPS or SSH and enter its root:

   ```sh
   git clone https://github.com/YOUR-NAME/YOUR-PRIVATE-VAULT.git
   cd YOUR-PRIVATE-VAULT
   ```

3. Install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/) from their official installers, then check both. `uv` provisions the required Python automatically.

   ```sh
   git --version
   uv --version
   ```

4. Run the read-only readiness check:

   ```sh
   uv run --locked python scripts/doctor_vault.py
   ```

   Continue only when the final line is `Core readiness: READY`. The public framework checkout intentionally fails its `remote-privacy` check; use a private template copy for personal material.

5. In Obsidian, choose **Open folder as vault** and select the repository root. Portable core settings for Properties, Templates, Daily Notes, attachments, and link updates are already committed. No community plugin is required.
6. Start with the lightweight flow: put one Markdown file in `Sources/`, open the repository in your agent, and say "ingest" with the file path. Check the new pages under `Wiki/`, the new line in `index.md`, and the new entry in `log.md`. Then ask a question about it.
7. Optional strict mode: follow [Build your personal vault](docs/BUILD_YOUR_VAULT.md) to complete one Asset → reviewed Source → draft Concept → MOC cycle. For optional read-only personalization help, use the single bootstrap prompt in [.agents/prompts/00-bootstrap-vault.md](.agents/prompts/00-bootstrap-vault.md).

Framework contributors may clone the public repository, but must keep personal material out of it:

```sh
git clone https://github.com/yi-john-huang/loreloom.git
cd loreloom
uv run --locked python scripts/doctor_vault.py
```

The public-origin failure is expected in that checkout; the remaining checks still diagnose framework readiness.

## Validation

Run:

```sh
uv run --locked python scripts/doctor_vault.py
uv run --locked python scripts/validate_vault.py --mode daily
uv run --locked python scripts/validate_vault.py --mode strict
uv run --locked pytest -q
```

The validator has two modes. `daily` is the default.

| Mode | Use it | Checks |
|---|---|---|
| `daily` | After every ingest or filed answer | Basic frontmatter and required fields (`type`, `title`, `status`) on lifecycle notes, the six-field contract on Wiki pages, and broken or ambiguous wikilinks |
| `strict` | Before publishing, for high-governance vaults, and in CI | Everything in `daily`, plus every check in the list below |

Daily mode treats `Sources/` as raw evidence: a file there needs no frontmatter, and a broken link inside it is a warning, because agents never change those files. Daily mode also warns when a Wiki page is missing from `index.md` or a queued page is missing from `log.md`. In both modes a page in `Wiki/_review/` must stay `status: draft`, and a `reviewed` or `evergreen` page needs at least one source.

Choose the default mode with `validation_mode` under `[tool.loreloom]` in `pyproject.toml`, or with the `LORELOOM_VALIDATION_MODE` environment variable. `--mode` overrides both. The doctor prints the configured mode and a recommendation on its `validation-mode` line, and runs the validator in that mode.

Two read-only helpers support the lightweight flow:

```sh
uv run --locked python scripts/ingest_gate.py "Wiki/concepts/My concept.md"   # accept or review, with reasons
uv run --locked python scripts/lint_wiki.py                                   # Wiki health report
```

Strict mode checks:

- required and type-specific YAML frontmatter;
- ISO dates and controlled values;
- unresolved Obsidian wikilinks;
- local Asset references, existence, hashes, and embedded attachment links;
- semantic rules such as reviewed evergreen Concepts and declared Wiki inputs;
- required Source capture-method/mode enums, provenance prerequisites, Capture Boundary entries, exact locators, and warning-only downstream Evidence limitations;
- repository hygiene such as ignored private files.

For **advanced owner-approved multi-agent changes**, `scripts/validate_change.py` additionally compares the diff with an immutable pre-task `HEAD` and filesystem snapshot, then enforces exact output scope, protected paths, strict processing Source admission, append-only reviewed Sources, signed `source_review`, review/archive gates, and preserved Wiki human blocks. Gated approvals require a short-lived, path-specific receipt under protected Git metadata. Native Windows users run this advanced path in WSL. See [Advanced multi-agent execution](docs/MULTI_AGENT.md).

GitHub Actions runs the vault validator in both modes, the Wiki lint report, and the adversarial guardrail tests on pushes and pull requests.

### Optional Jev advisory (default OFF)

`scripts/jev_advisory.py` can ask the third-party TypeSafe Jev decision API to rank Inbox captures (`inbox-triage`) and to flag weakly supported claims in draft Concepts (`claim-support`). It is advisory only: it never edits a note and never changes review or evergreen state.

The feature is OFF until you opt in:

| Setting | Where | Effect |
|---|---|---|
| `enabled` under `[tool.loreloom.jev]` | `pyproject.toml` | Committed default is `false`. |
| `LORELOOM_JEV_ENABLED` | Environment | `1`, `true`, `yes`, or `on` enables; `0`, `false`, `no`, or `off` disables. It overrides `pyproject.toml`. |
| `JEV_API_KEY` | Environment only | The Jev key. Never store it in the repository. |

Prefer the environment variable so the committed default stays OFF. When the feature is OFF, the command prints `Jev advisory is disabled` and the validator and doctor behave exactly as before. Optional `timeout_seconds` (default `20`) and `max_excerpt_chars` (default `4000`) keys tune the same table. Read [Agent workflows](docs/AGENT_WORKFLOWS.md) for the commands and [Privacy](docs/PRIVACY.md) for what leaves your machine.

### Python toolchain

- `.python-version` selects Python 3.13.
- `pyproject.toml` declares validation dependencies.
- `uv.lock` pins the complete cross-platform dependency graph and is committed.
- `uv sync --locked --dev` reproduces the environment without changing the lockfile.
- When intentionally updating dependencies, run `uv lock --upgrade`, validate, and commit `pyproject.toml` and `uv.lock` together.

## What this framework does not do

- It does not automatically trust numbers, contradictions, or low-confidence pages; those always wait for the owner.
- It does not support teams, shared review, or company and work-confidential data.
- It does not copy entire web pages into a public repository.
- It does not use embeddings, a vector database, or RAG in this phase.
- It does not prescribe PARA, Zettelkasten, or a single topic taxonomy.
- It does not make Git a real-time sync engine; choose sync separately from version control.

## Documentation

- [Agent guide for the lightweight flow](CLAUDE.md)
- [Migrating to the lightweight flow](docs/migration-lightweight.md)
- [Output clarity ladder](docs/output-clarity-ladder.md)
- [Build your personal vault (strict mode)](docs/BUILD_YOUR_VAULT.md)
- [Getting started](docs/GETTING_STARTED.md)
- [Architecture and lifecycle](docs/ARCHITECTURE.md)
- [Conventions](docs/CONVENTIONS.md)
- [Frontmatter schemas](docs/FRONTMATTER.md)
- [Agent workflows](docs/AGENT_WORKFLOWS.md)
- [Advanced multi-agent execution](docs/MULTI_AGENT.md)
- [Privacy and threat model](docs/PRIVACY.md)
- [Publishing and template setup](docs/PUBLISHING.md)
- [Contributing](CONTRIBUTING.md)

## License

Framework code, prompts, examples, and documentation are available under the [MIT License](LICENSE). Source material you add to your own vault retains its original rights and may not be redistributable.
