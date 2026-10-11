# Getting started

This page is a short entry checklist. The default is the lightweight flow in [`CLAUDE.md`](../CLAUDE.md). [Build your personal vault](BUILD_YOUR_VAULT.md) is the complete tutorial for the optional strict mode. If you are still choosing a tool, start with [How Loreloom compares](../README.md#how-loreloom-compares).

## Core setup

- [ ] Create a **private** repository with GitHub's **Use this template** action.
- [ ] Clone it by HTTPS or SSH and enter its root.
- [ ] Install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/) from their official installers.
- [ ] Run `git --version` and `uv --version`.
- [ ] Run `uv run --locked python scripts/doctor_vault.py`.
- [ ] Continue only when the final line is `Core readiness: READY`.
- [ ] Open the repository root as an Obsidian vault; the portable baseline is already committed.

Portable Obsidian settings are already committed: attachments use `Assets/`, link renames update automatically, and Properties, Templates, and Daily Notes are enabled. No community plugin is required.

## First lightweight cycle

1. Put one Markdown file in `Sources/`. It needs no frontmatter.
2. Open the repository root in your agent and say: "ingest `Sources/<file name>.md`".
3. Check the result: new pages under `Wiki/`, one new line per page in `index.md`, and one new entry in `log.md`.
4. Read any `Needs review:` line in `log.md`. A page with numbers, a contradiction, or less than high confidence waits there as a draft.
5. Ask a question about the source. When the answer is good, say "file it".
6. Say "lint" for a health report.
7. Run `uv run --locked python scripts/validate_vault.py --mode daily`.

Keep the vault personal. Do not add company or work-confidential material; see the scope section in the [README](../README.md).

## First strict-mode cycle (optional)

Use this path when you need owner-reviewed Sources, Asset hashes, and claim checks. Follow [the deterministic first evidence cycle](BUILD_YOUR_VAULT.md#4-complete-the-first-evidence-cycle) and complete this sequence before adding optional branches:

1. the deterministic `Assets/First cycle.txt` with its expected SHA-256;
2. one faithful processing Source that passes validation;
3. direct owner Source review and current-byte validation;
4. one cited draft Concept created manually or by the root agent;
5. the exact Technology MOC link;
6. a passing final validator and an understood `git status --short`.

## Add later

After the first cycle works, consider Inbox/Daily capture, URL-only intake, generated Wiki pages, sync, example deletion, and custom agents. The root workflow is the default. Multi-agent execution, detached validation, signed review, and receipts are advanced POSIX/WSL features described in [Advanced multi-agent execution](MULTI_AGENT.md).

For optional read-only personalization, use only [.agents/prompts/00-bootstrap-vault.md](../.agents/prompts/00-bootstrap-vault.md).
