# Loreloom

An AI-first Obsidian vault framework that weaves captured sources into reviewed knowledge, generated wiki pages, and a connected multi-topic graph.

The framework treats Markdown as the durable source format and separates captured material, reviewed knowledge, and generated synthesis. It is intentionally model-agnostic: your vault should outlive any particular AI provider.

> [!IMPORTANT]
> This repository contains example content only. Create a new private repository from this template before adding personal, confidential, or copyrighted material.

## Core model

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

- **One vault, many topics.** Technology, food, travel, career, and other subjects connect through links and metadata instead of separate vaults.
- **Evidence before synthesis.** Source material is preserved; durable claims point back to it.
- **Human-reviewed truth.** `Knowledge/` is canonical. AI may draft there, but a human changes `status` to `evergreen`.
- **Generated pages are replaceable.** `Wiki/` pages declare their inputs and can be rebuilt when models or prompts improve.
- **Agents are governed.** `AGENTS.md` and `.agents/policies/` define what an agent may read, create, or change.
- **One root by default.** The active Codex session runs bounded skills sequentially; custom read-only agents are an owner-approved advanced option.
- **Skills are reusable.** Repo-scoped skills route capture, distillation, synthesis, auditing, and orchestration consistently.
- **Asset or URL intake.** Owners may supply local files in `Assets/` or record absolute HTTP(S) URLs; `$capture-vault-source` creates editable processing Sources without fetching, copying, or overwriting resources.
- **Plain Markdown wins.** The vault remains usable without a plugin, database, or hosted service.

## Repository map

| Path | Purpose | Default owner |
|---|---|---|
| `Inbox/` | Unprocessed capture | Human + agent |
| `Assets/` | Owner-supplied binary evidence | Human-led; agent read/bind only |
| `Sources/` | Editable processing intake, then faithful append-only reviewed records | Human; agent creates processing intake |
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
6. Follow [Build your personal vault](docs/BUILD_YOUR_VAULT.md) to complete one Asset → reviewed Source → draft Concept → MOC cycle. For optional read-only personalization help, use the single bootstrap prompt in [.agents/prompts/00-bootstrap-vault.md](.agents/prompts/00-bootstrap-vault.md).

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
uv run --locked python scripts/validate_vault.py
uv run --locked python -m unittest discover -s tests -v
```

The validator checks:

- required and type-specific YAML frontmatter;
- ISO dates and controlled values;
- unresolved Obsidian wikilinks;
- local Asset references, existence, hashes, and embedded attachment links;
- semantic rules such as reviewed evergreen Concepts and declared Wiki inputs;
- repository hygiene such as ignored private files.

For **advanced owner-approved multi-agent changes**, `scripts/validate_change.py` additionally compares the diff with an immutable pre-task `HEAD` and filesystem snapshot, then enforces exact output scope, protected paths, strict processing Source admission, append-only reviewed Sources, signed `source_review`, review/archive gates, and preserved Wiki human blocks. Gated approvals require a short-lived, path-specific receipt under protected Git metadata. Native Windows users run this advanced path in WSL. See [Advanced multi-agent execution](docs/MULTI_AGENT.md).

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
- [Advanced multi-agent execution](docs/MULTI_AGENT.md)
- [Privacy and threat model](docs/PRIVACY.md)
- [Publishing and template setup](docs/PUBLISHING.md)
- [Contributing](CONTRIBUTING.md)

## License

Framework code, prompts, examples, and documentation are available under the [MIT License](LICENSE). Source material you add to your own vault retains its original rights and may not be redistributable.
