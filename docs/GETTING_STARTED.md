# Getting started

Use [Build your personal vault](BUILD_YOUR_VAULT.md) for the only complete tutorial. This page is a short entry checklist.

## Core setup

- [ ] Create a **private** repository with GitHub's **Use this template** action.
- [ ] Clone it by HTTPS or SSH.
- [ ] Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/).
- [ ] Run `git --version` and `uv --version`.
- [ ] Run `uv run --locked python scripts/doctor_vault.py`.
- [ ] Continue only when the doctor reports `Core readiness: READY`.
- [ ] Open the repository root as an Obsidian vault.
- [ ] Follow [the first evidence cycle](BUILD_YOUR_VAULT.md#4-complete-the-first-evidence-cycle).

Portable Obsidian settings are already committed: attachments use `Assets/`, link renames update automatically, and Properties, Templates, and Daily Notes are enabled. No community plugin is required.

## First successful cycle

Complete this sequence before adding optional branches:

1. one owner-controlled local Asset;
2. one faithful processing Source;
3. direct owner Source review and current-byte validation;
4. one cited draft Concept created manually or by the root agent;
5. one useful MOC link;
6. a passing vault validator.

## Add later

After the first cycle works, consider Inbox/Daily capture, URL-only intake, generated Wiki pages, sync, example deletion, and custom agents. The root workflow is the default. Multi-agent execution, detached validation, signed review, and receipts are advanced POSIX/WSL features described in [Advanced multi-agent execution](MULTI_AGENT.md).

For optional read-only personalization, use only [.agents/prompts/00-bootstrap-vault.md](../.agents/prompts/00-bootstrap-vault.md).
