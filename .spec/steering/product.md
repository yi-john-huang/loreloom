# Product Overview

## Description

- **Project:** Loreloom
- **Version:** 0.1.0
- **Product type:** Public knowledge-vault framework and GitHub template

Loreloom is an AI-first, model-agnostic Obsidian vault framework that turns captured material into traceable knowledge using plain Markdown, YAML frontmatter, wikilinks, review gates, and bounded agent workflows. It is a repository framework—not a web application, hosted service, or database.

## Vision

Provide a durable personal knowledge system that remains useful without any particular AI provider, Obsidian community plugin, vector database, or hosted platform. AI assists with organization and synthesis; evidence, human review, and portable files remain authoritative.

## Target Users

- **Primary:** Individuals building a private, multi-topic knowledge vault with Obsidian or any Markdown-capable editor.
- **Secondary:** Maintainers and contributors improving the public framework with synthetic examples, policies, templates, schemas, and validators.
- **Operational:** AI agents performing bounded capture, distillation, linking, synthesis, audit, and framework-maintenance tasks under human control.

## Knowledge Lifecycle

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
                Projects / Areas -> Archive
```

Folders express lifecycle and authority. Links, tags, and Maps of Content express subject relationships across technology, travel, food, career, and other topics.

## Core Capabilities

1. **Fast, untrusted capture** — `Inbox/` and `Daily/` accept incomplete observations without treating them as durable truth.
2. **Local or URL evidence intake** — owners supply exact Assets or absolute HTTP(S) URLs; URLs are recorded without fetching or implying reachability, freshness, or extraction.
3. **Evidence preservation** — Sources remain editable while processing, then become faithful append-only records after owner review.
4. **Owner-controlled review** — Source review is a direct owner edit or an exact signed `source_review`; current Asset bytes are revalidated before distillation.
5. **Canonical knowledge** — `Knowledge/` contains one durable concept per note with traceable sources and explicit confidence; the owner reviews draft claims and citations.
6. **Regenerable synthesis** — `Wiki/` pages declare their Knowledge inputs, generation metadata, and review state while preserving marked human-owned blocks.
7. **Connected navigation** — wikilinks, lowercase hierarchical tags, and curated `MOCs/` connect subjects without topic-folder duplication.
8. **Governed, portable automation** — policies, exact scopes, validators, human gates, UTF-8 Markdown, and YAML keep agent work bounded and the vault usable without a hosted service.

## Public Framework and Private Vault Boundary

This public repository contains framework files and synthetic, public-domain, or safely attributed examples only. Personal, confidential, proprietary, licensed, or copyrighted material belongs in a separate private repository created from the template.

- Use a template-created private repository for a personal vault and independent history.
- Use a fork or clean framework branch only for public contributions.
- Never merge or cherry-pick commits that mix personal notes with framework changes.
- Before any public commit or push, inspect the complete diff for names, emails, credentials, internal URLs, local paths, private facts, and restricted source text.

## Value Propositions

- Evidence remains distinguishable from interpretation and generated synthesis.
- Human review controls what becomes canonical.
- Generated views can improve without rewriting original evidence.
- One graph supports many topics without imposing PARA, Zettelkasten, or another fixed taxonomy.
- Agent behavior is reviewable, bounded, and subordinate to repository policy.
- The vault remains usable as ordinary files over the long term.

## Non-Goals

Loreloom does not:

- automatically trust AI-generated claims or citations;
- provide a web server, database, embeddings store, or production build;
- require Obsidian community plugins;
- copy full external sources into the public repository;
- prescribe a real-time synchronization solution;
- allow agent consensus to replace source evidence or human approval.

## Success Criteria

Product quality is measured through repository invariants rather than usage telemetry:

- vault schema, semantic, hygiene, and wikilink validation passes;
- validator guardrail tests pass locally and in GitHub Actions;
- durable Knowledge claims retain traceable evidence;
- Sources remain faithful and generated Wiki pages remain reproducible;
- when the guarded change workflow is used, protected human content and review-state changes require explicit approval and reviewable diffs;
- the public framework remains free of private or restricted material;
- a user can open and navigate the vault as plain Markdown without required plugins.
