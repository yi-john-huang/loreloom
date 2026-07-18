# Getting started

For a complete, task-oriented walkthrough from template repository to daily use, see [Build your personal vault](BUILD_YOUR_VAULT.md). This page summarizes the most important setup decisions.

## 1. Create a safe personal copy

For personal use, create a private repository from the GitHub template rather than forking the public framework. A template copy has independent history and no pull-request relationship that might expose notes upstream.

Open the repository root as an Obsidian vault. Keep the framework documentation until the workflow feels familiar.

## 2. Choose sync separately

Git provides history and review; it is not a real-time sync protocol. Use one primary sync system. If the vault is also inside a cloud-synced folder, avoid editing the same note simultaneously on multiple devices and wait for file sync before Git operations.

Never configure two file-sync services for the same vault. Test restore procedures before trusting any setup.

## 3. Configure Obsidian

The framework works with core Obsidian features. Suggested settings:

- enable automatic link updates on rename;
- use `Assets/` as the attachment folder;
- enable Properties view for frontmatter editing;
- enable Templates and point it at `Templates/`;
- enable Daily Notes and point it at `Daily/` with format `YYYY-MM-DD`.

Optional community plugins can improve templating or queries, but the committed notes should remain readable without them. Audit every plugin because it runs with access to vault content.

## 4. Personalize without creating topic silos

Edit `MOCs/Home.md` and add a few subjects that matter to you. Use tags and links for topics; keep the top-level lifecycle folders stable.

Create Projects only for outcomes with an end condition. Create Areas for ongoing responsibilities. A subject such as “AWS” usually belongs in a MOC, not a Project or Area by default.

## 5. Capture the first source

1. Create a Source note from `Templates/Source.md`.
2. Record provenance and a short faithful summary; link rather than copy large copyrighted content.
3. Run `.agents/prompts/02-distill-source.md` with the exact Source path.
4. Review proposed Knowledge drafts and their citations.
5. Promote a draft to evergreen only after checking the source yourself.

## 6. Introduce Codex gradually

Begin with read-only audits. Then allow creation of draft notes. Allow updates to canonical Knowledge only after you are comfortable reviewing diffs.

The repository's `AGENTS.md` is the standing instruction set. Prompts in `.agents/prompts/` are task-specific contracts. Workflows in `.agents/workflows/` describe repeatable sequences and checkpoints.

## 7. Remove examples

After experimenting, remove only the `Examples/` subdirectories and update `MOCs/Home.md`. Keep directory `README.md` files, templates, schemas, and agent policies.

## 8. Publish the framework, not your vault

If you improve the framework, copy the generic change to a clean branch of the public repository. Never merge personal vault history into the public project. Before any push, inspect staged files for personal names, local filesystem paths, source documents, secrets, and `.obsidian` plugin data.
