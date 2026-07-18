# Loreloom

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
- **Specialists are bounded.** Project agents split read-heavy work by role while one orchestrator owns decisions and writes.
- **Skills are reusable.** Repo-scoped skills route capture, distillation, synthesis, auditing, and orchestration consistently.
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
| `.codex/` | Project-scoped agent and orchestration configuration | Maintainers |
| `schemas/` | Machine-readable frontmatter contract | Maintainers |

See [Architecture](docs/ARCHITECTURE.md) for the full lifecycle.

## Start your own vault

For the complete onboarding workflow, follow [Build your personal vault](docs/BUILD_YOUR_VAULT.md).

### Recommended: GitHub template

1. Publish this repository to GitHub and enable **Settings -> General -> Template repository**.
2. Choose **Use this template**, create a **private** repository, and do not include every branch.
3. Clone the new repository to a folder available to your devices.
4. In Obsidian, choose **Open folder as vault** and select the repository root.
5. Replace the example links in `MOCs/Home.md`, delete the `Examples/` folders when you no longer need them, and run validation.
6. Review and personalize `AGENTS.md`, then run the first prompt in [.agents/prompts/00-bootstrap-vault.md](.agents/prompts/00-bootstrap-vault.md).

Use a fork when contributing improvements back to this public framework. Use a template-created private repository for personal notes; this avoids accidentally proposing private content to the public project.

### Framework development setup

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first. It manages the Python version and validation environment; no manual virtual environment or pip command is needed.

```sh
git clone https://github.com/yi-john-huang/loreloom.git
cd loreloom
uv sync --locked --dev
uv run python scripts/validate_vault.py
```

This checkout keeps the public Loreloom repository as `origin`; use it only for framework work and synthetic examples. For personal notes, create a private repository with the template workflow above.

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
uv run python scripts/validate_vault.py
uv run python -m unittest discover -s tests -v
```

The validator checks:

- required and type-specific YAML frontmatter;
- ISO dates and controlled values;
- unresolved Obsidian wikilinks;
- semantic rules such as reviewed evergreen Concepts and declared Wiki inputs;
- repository hygiene such as ignored private files.

For agent-authored changes, `scripts/validate_change.py` additionally compares the diff with an immutable pre-task commit and filesystem snapshot, then enforces exact output scope, protected paths, Source immutability, review and archive gates, and preserved Wiki human blocks. Gated approvals require a short-lived, path-specific receipt created by the owner under protected Git metadata.

GitHub Actions runs the vault validator and adversarial guardrail tests on pushes and pull requests.

### Python toolchain

- `.python-version` selects Python 3.13.
- `pyproject.toml` declares validation dependencies.
- `uv.lock` pins the complete cross-platform dependency graph and is committed.
- `uv sync --locked --dev` reproduces the environment without changing the lockfile.
- When intentionally updating dependencies, run `uv lock --upgrade`, validate, and commit `pyproject.toml` and `uv.lock` together.

## What this framework does not do

- It does not automatically trust AI output.
- It does not copy entire web pages into a public repository.
- It does not require embeddings or a vector database.
- It does not prescribe PARA, Zettelkasten, or a single topic taxonomy.
- It does not make Git a real-time sync engine; choose sync separately from version control.

## Documentation

- [Build your personal vault](docs/BUILD_YOUR_VAULT.md)
- [Getting started](docs/GETTING_STARTED.md)
- [Architecture and lifecycle](docs/ARCHITECTURE.md)
- [Conventions](docs/CONVENTIONS.md)
- [Frontmatter schemas](docs/FRONTMATTER.md)
- [Agent workflows](docs/AGENT_WORKFLOWS.md)
- [Multi-agent and model routing](docs/MULTI_AGENT.md)
- [Privacy and threat model](docs/PRIVACY.md)
- [Publishing and template setup](docs/PUBLISHING.md)
- [Contributing](CONTRIBUTING.md)

## License

Framework code, prompts, examples, and documentation are available under the [MIT License](LICENSE). Source material you add to your own vault retains its original rights and may not be redistributable.
