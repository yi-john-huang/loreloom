# Product Overview

## Description

- **Project:** Loreloom
- **Version:** 0.1.0
- **Product type:** Public knowledge-vault framework and GitHub template

Loreloom is a plug-and-play, model-agnostic Obsidian vault framework and GitHub template. A private template copy ships portable Obsidian core settings, a read-only readiness doctor, plain Markdown, YAML frontmatter, wikilinks, review gates, and bounded root-agent workflows. It is not a web application, hosted service, plugin, or database.

The default is the lightweight agent-first flow in `CLAUDE.md`: the agent writes and maintains pages under `Wiki/`, and the owner reviews exceptions only. The earlier high-governance flow is optional strict mode, described in `AGENTS.md`.

## Scope of Use

- A vault is a personal knowledge vault for one user. One owner makes every review decision; it is not a multi-user collaboration tool.
- It holds personal notes about life domains such as learning, health, travel, food, hobbies, and money.
- Company data and confidential work material do not belong in it.
- This phase has no vector database and no RAG. Agents find pages through `index.md`, wikilinks, and file search.
- Strict mode is for a vault that needs high governance: signed review, Asset hashes, and claim checks. Use it only when the owner asks for it or sets `validation_mode = "strict"`.

## Vision

Provide a durable personal knowledge system that remains useful without any particular AI provider, Obsidian community plugin, vector database, or hosted platform. AI assists with organization and synthesis; evidence, human review, and portable files remain authoritative.

## Target Users

- **Primary:** One individual per vault, building a private, multi-topic personal knowledge vault with Obsidian or any Markdown-capable editor.
- **Secondary:** Maintainers and contributors improving the public framework with synthetic examples, policies, templates, schemas, and validators.
- **Operational:** AI agents (Claude Code, Codex, Grok, and others) performing ingest, query, answer filing, lint, and framework-maintenance tasks under the owner's control; in strict mode, bounded capture, distillation, linking, synthesis, and audit.

## Knowledge Lifecycle

### Lightweight flow (default)

```text
Owner names a Source, Asset, Inbox capture, URL, or pasted text
                         |
                         v
ingest: raw file in Sources/ -> pages in Wiki/sources, entities, concepts
                         |
                         v
Auto-accept rule (scripts/ingest_gate.py)
        |                                   |
        v                                   v
status: reviewed,                 status: draft in its section or
reviewed_by: agent                Wiki/_review/, plus a `Needs review:`
                                  line in log.md for the owner
                         |
                         v
index.md and log.md updated -> query -> file-answer -> Wiki/synthesis/
                         |
                         v
lint: read-only Wiki health report
```

| Owner says | Skill | Result |
|---|---|---|
| "ingest this", "add this source" | `.agents/skills/ingest/SKILL.md` | Wiki pages, `index.md`, and `log.md` updated |
| "what do I know about …" | `.agents/skills/query/SKILL.md` | A cited answer; nothing is written |
| "file it", "save this answer" | `.agents/skills/file-answer/SKILL.md` | One page in `Wiki/synthesis/` |
| "lint", "check the wiki" | `.agents/skills/lint/SKILL.md` | A health report; nothing is written until the owner approves a repair |

### Auto-accept rule

An agent sets `status: reviewed` with `reviewed_by: agent` only when all of these hold:

1. `confidence` is `high`;
2. the page has at least one source;
3. the page body has no numeric claim: no amount, count, percentage, measurement, date, or year;
4. the page has no contradiction with another page or source.

Every other page keeps `status: draft`, in its section or in `Wiki/_review/`, and gets a `Needs review:` line with the reason in `log.md`. The gate is a floor: an agent also sends a page to review when it sees a quantity written in words or a conflict the gate did not detect.

- An agent never edits a page with `status: evergreen` or `reviewed_by: owner`. It writes the proposed update to `Wiki/_review/`.
- Only the owner sets `status: evergreen` or `reviewed_by: owner`.
- A contradiction is recorded on the page, never resolved by the agent; the owner decides which claim stands.

### Strict mode (optional)

```text
Owner Asset / absolute HTTP(S) URL / Inbox / Daily
                         |
                         v
Source processing (editable intake)
                         |
                         v
Owner review (direct; signed source_review is advanced)
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
                Projects / Areas -> Archive
```

Folders express lifecycle and authority. Links, tags, and Maps of Content express subject relationships across technology, travel, food, career, and other topics.

## Core Capabilities

Lightweight flow (default):

1. **Agent-maintained Wiki** — `ingest` turns one source into a summary page in `Wiki/sources/` and updates entity and concept pages; it updates the existing page for a topic before creating a new one.
2. **Review by exception** — the auto-accept rule accepts high-confidence, sourced pages with no numeric claim and no contradiction; everything else waits for the owner as a draft with a logged reason.
3. **Cited answers** — `query` answers from the vault with a wikilink per claim, names draft and low-confidence pages, shows contradictions, and writes nothing; `file-answer` saves an accepted answer as one page in `Wiki/synthesis/`.
4. **Index and history** — `index.md` lists every Wiki page outside the review queue and is read first; `log.md` is the append-only history and review record.
5. **Read-only health report** — `lint` reports broken links, orphans, unindexed pages, contradictions, gate failures, low-confidence pages, the review backlog, and stale pages.
6. **Immutable evidence** — agents may add a raw file to `Sources/` but never change an existing file in `Sources/` or `Assets/`.
7. **Clear prose** — all Wiki prose follows the sdd-mcp [`output-clarity-ladder` skill](https://github.com/yi-john-huang/sdd-mcp/blob/master/skills/output-clarity-ladder/SKILL.md). The repository keeps no copy of it.

Strict mode and shared foundations:

1. **Fast, untrusted capture** — `Inbox/` and `Daily/` accept incomplete observations without treating them as durable truth.
2. **Local, URL, or Inbox evidence intake** — owners supply exact Assets, absolute HTTP(S) URLs, or exact existing Inbox provenance; URLs are recorded without fetching or implying reachability, freshness, or extraction.
3. **Classified evidence preservation** — Sources remain editable while processing, require `source_type` (what the evidence is), `capture_method` (how it entered), and `capture_mode` (how the representation relates to original evidence), then become append-only after owner review. Fidelity may remain explicitly unknown.
4. **Owner-controlled review** — direct owner Source review is the default; exact signed `source_review` is an advanced alternative. Current Asset bytes and mechanical capture prerequisites are revalidated before distillation.
5. **Canonical knowledge (strict mode)** — `Knowledge/` contains one durable concept per note with traceable sources and explicit confidence; low-fidelity Source modes propagate mode-specific Evidence limitations, and the owner reviews draft claims, citations, and limitations.
6. **Regenerable synthesis (strict mode)** — `type: wiki` pages directly under `Wiki/` declare their Knowledge inputs, generation metadata, and review state while preserving marked human-owned blocks.
7. **Connected navigation** — wikilinks, lowercase hierarchical tags, and curated `MOCs/` connect subjects without topic-folder duplication.
8. **Plug-and-play, portable automation** — a read-only doctor, committed Obsidian core settings, model-neutral root workflow, policies, exact scopes, validators, human gates, UTF-8 Markdown, and YAML make first use deterministic without a hosted service.

## Public Framework and Private Vault Boundary

This public repository contains framework files and synthetic, public-domain, or safely attributed examples only. Personal, confidential, proprietary, licensed, or copyrighted material belongs in a separate private repository created from the template.

- Use a template-created private repository for a personal vault and independent history.
- Use a fork or clean framework branch only for public contributions.
- Never merge or cherry-pick commits that mix personal notes with framework changes.
- Before any public commit or push, inspect the complete diff for names, emails, credentials, internal URLs, local paths, private facts, and restricted source text.

## Value Propositions

- Evidence remains distinguishable from interpretation and generated synthesis.
- The owner reviews exceptions rather than every page; numbers and contradictions are never auto-trusted.
- Human review controls what becomes evergreen or, in strict mode, canonical.
- Generated views can improve without rewriting original evidence.
- One graph supports many topics without imposing PARA, Zettelkasten, or another fixed taxonomy.
- Agent behavior is reviewable, bounded, and subordinate to repository policy.
- The vault remains usable as ordinary files over the long term.

## Non-Goals

Loreloom does not:

- automatically trust AI-generated claims or citations;
- provide a web server, database, vector database, embeddings store, RAG pipeline, or production build;
- support multi-user collaboration or shared review;
- hold company data or confidential work material;
- require Obsidian community plugins;
- copy full external sources into the public repository;
- prescribe a real-time synchronization solution;
- allow agent consensus to replace source evidence or human approval.

## Success Criteria

Product quality is measured through repository invariants rather than usage telemetry:

- `validate_vault.py` passes in `daily` mode after every write, and in `strict` mode before publishing and in CI;
- every Wiki page outside `Wiki/_review/` is listed in `index.md`, and every page that needs the owner has a `Needs review:` line in `log.md`;
- no page is `status: reviewed` without `reviewed_by: owner` while it fails the auto-accept rule;
- validator guardrail tests pass locally and in GitHub Actions;
- durable Knowledge claims retain traceable evidence;
- Sources remain provenance-bound and explicitly classified without implying that hashes, validators, or owner confidence prove semantic fidelity; generated Wiki pages remain reproducible;
- when the guarded change workflow is used, protected human content and review-state changes require explicit approval and reviewable diffs;
- the public framework remains free of private or restricted material;
- a user can open and navigate the vault as plain Markdown without required plugins.
- a private template copy can reach `Core readiness: READY`, open with portable Obsidian defaults, and complete one Asset-to-MOC cycle without custom agents or community plugins.
