# Product Overview

## Description

- **Project:** Loreloom
- **Version:** 0.1.0
- **Product type:** Public knowledge-vault framework and GitHub template

Loreloom is a plug-and-play, model-agnostic Obsidian vault framework and GitHub template. A private template copy ships portable Obsidian core settings, a read-only readiness doctor, plain Markdown, YAML frontmatter, wikilinks, review gates, and bounded root-agent workflows. It is not a web application, hosted service, plugin, or database.

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

1. **Fast, untrusted capture** — `Inbox/` and `Daily/` accept incomplete observations without treating them as durable truth.
2. **Local, URL, or Inbox evidence intake** — owners supply exact Assets, absolute HTTP(S) URLs, or exact existing Inbox provenance; URLs are recorded without fetching or implying reachability, freshness, or extraction.
3. **Classified evidence preservation** — Sources remain editable while processing, require `source_type` (what the evidence is), `capture_method` (how it entered), and `capture_mode` (how the representation relates to original evidence), then become append-only after owner review. Fidelity may remain explicitly unknown.
4. **Owner-controlled review** — direct owner Source review is the default; exact signed `source_review` is an advanced alternative. Current Asset bytes and mechanical capture prerequisites are revalidated before distillation.
5. **Canonical knowledge** — `Knowledge/` contains one durable concept per note with traceable sources and explicit confidence; low-fidelity Source modes propagate mode-specific Evidence limitations, and the owner reviews draft claims, citations, and limitations.
6. **Regenerable synthesis** — `Wiki/` pages declare their Knowledge inputs, generation metadata, and review state while preserving marked human-owned blocks.
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
- Sources remain provenance-bound and explicitly classified without implying that hashes, validators, or owner confidence prove semantic fidelity; generated Wiki pages remain reproducible;
- when the guarded change workflow is used, protected human content and review-state changes require explicit approval and reviewable diffs;
- the public framework remains free of private or restricted material;
- a user can open and navigate the vault as plain Markdown without required plugins.
- a private template copy can reach `Core readiness: READY`, open with portable Obsidian defaults, and complete one Asset-to-MOC cycle without custom agents or community plugins.
