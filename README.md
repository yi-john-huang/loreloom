# Sourceweave

An AI-first Obsidian vault framework that weaves captured sources into reviewed knowledge, generated wiki pages, and a connected multi-topic graph.

The framework treats Markdown as the durable source format and separates captured material, reviewed knowledge, and generated synthesis. It is intentionally model-agnostic: your vault should outlive any particular AI provider.

> [!IMPORTANT]
> This repository contains example content only. Create a new private repository from this template before adding personal, confidential, or copyrighted material.

## Core model

```text
Inbox / Daily
      |
      v
Sources (immutable evidence)
      |
      v
Knowledge (atomic, reviewed concepts)
      |
      +------------------+
      v                  v
Wiki (generated)       MOCs (navigation)
      |
      v
Projects / Areas (action and responsibility)
```

- **One vault, many topics.** Technology, food, travel, career, and other subjects connect through links and metadata instead of separate vaults.
- **Evidence before synthesis.** Source material is preserved; durable claims point back to it.
- **Human-reviewed truth.** `Knowledge/` is canonical. AI may draft there, but a human changes `status` to `evergreen`.
- **Generated pages are replaceable.** `Wiki/` pages declare their inputs and can be rebuilt when models or prompts improve.
- **Agents are governed.** `AGENTS.md` and `.agents/policies/` define what an agent may read, create, or change.
- **Plain Markdown wins.** The vault remains usable without a plugin, database, or hosted service.

## Repository map

| Path | Purpose | Default owner |
|---|---|---|
| `Inbox/` | Unprocessed capture | Human + agent |
| `Sources/` | Original or faithful source records | Human; agent append-only |
| `Knowledge/` | Atomic, cited concept notes | Human-reviewed |
| `Wiki/` | Regenerable synthesis | Agent-generated |
| `MOCs/` | Maps of Content and navigation | Shared |
| `Projects/` | Time-bound outcomes | Human-led |
| `Areas/` | Ongoing responsibilities | Human-led |
| `Daily/` | Chronological observations | Human-led |
| `Archive/` | Inactive material | Shared |
| `Templates/` | Note templates | Maintainers |
| `.agents/` | Prompts, policies, and workflows | Maintainers |
| `schemas/` | Machine-readable frontmatter contract | Maintainers |

See [Architecture](docs/ARCHITECTURE.md) for the full lifecycle.

## Start your own vault

### Recommended: GitHub template

1. Publish this repository to GitHub and enable **Settings -> General -> Template repository**.
2. Choose **Use this template**, create a **private** repository, and do not include every branch.
3. Clone the new repository to a folder available to your devices.
4. In Obsidian, choose **Open folder as vault** and select the repository root.
5. Delete the `Examples/` folders when you no longer need them.
6. Review and personalize `AGENTS.md`, then run the first prompt in [.agents/prompts/00-bootstrap-vault.md](.agents/prompts/00-bootstrap-vault.md).

Use a fork when contributing improvements back to this public framework. Use a template-created private repository for personal notes; this avoids accidentally proposing private content to the public project.

### Local setup

```sh
git clone https://github.com/YOUR-NAME/sourceweave.git my-vault
cd my-vault
python3 -m pip install -r requirements-dev.txt
python3 scripts/validate_vault.py
```

No Obsidian community plugin is required. Optional plugins are listed in [Getting Started](docs/GETTING_STARTED.md).

## A first Codex session

Open Codex at the vault root and use:

```text
Read AGENTS.md and .agents/policies/vault-policy.md. Audit this new vault
without changing files. Then propose a minimal personalization plan. Keep
Sources immutable, do not invent citations, and show which example files can
be removed after onboarding.
```

Then try a bounded workflow:

```text
Follow .agents/workflows/source-to-knowledge.md for the unprocessed notes in
Inbox. Create drafts only. Do not mark anything evergreen and do not rewrite
files in Sources. Summarize the resulting changes and any uncertain claims.
```

The reusable prompts in `.agents/prompts/` are deliberately explicit about inputs, outputs, and approval boundaries.

## Validation

Run:

```sh
python3 scripts/validate_vault.py
```

The validator checks:

- required and type-specific YAML frontmatter;
- ISO dates and controlled values;
- unresolved Obsidian wikilinks;
- semantic rules such as reviewed evergreen Concepts and declared Wiki inputs;
- repository hygiene such as ignored private files.

GitHub Actions runs the same check on pushes and pull requests.

## What this framework does not do

- It does not automatically trust AI output.
- It does not copy entire web pages into a public repository.
- It does not require embeddings or a vector database.
- It does not prescribe PARA, Zettelkasten, or a single topic taxonomy.
- It does not make Git a real-time sync engine; choose sync separately from version control.

## Documentation

- [Getting started](docs/GETTING_STARTED.md)
- [Architecture and lifecycle](docs/ARCHITECTURE.md)
- [Conventions](docs/CONVENTIONS.md)
- [Frontmatter schemas](docs/FRONTMATTER.md)
- [Agent workflows](docs/AGENT_WORKFLOWS.md)
- [Privacy and threat model](docs/PRIVACY.md)
- [Publishing and template setup](docs/PUBLISHING.md)
- [Contributing](CONTRIBUTING.md)

## License

Framework code, prompts, examples, and documentation are available under the [MIT License](LICENSE). Source material you add to your own vault retains its original rights and may not be redistributable.
