# Knowledge

> Optional legacy layer. The default lightweight flow in [`CLAUDE.md`](../CLAUDE.md) writes concept pages to `Wiki/concepts/` and does not need this folder. Notes here stay readable. `scripts/migrate_knowledge_to_wiki.py` copies them to `Wiki/concepts/` when you choose; see [Migrating to the lightweight flow](../docs/migration-lightweight.md). The rest of this page describes strict mode.

In strict mode this is the canonical layer: one durable concept per note, written in your own words and grounded in sources.

Agents may create `status: draft` notes. A human verifies important claims and changes a note to `status: evergreen`. Use links and tags to connect subjects rather than adding top-level topic folders.

Source fidelity remains visible downstream. A draft citing any `capture_mode: unknown`, `paraphrased`, or `reference-only` Source includes a non-empty `## Evidence limitations` section with the applicable mode-specific wording. Stronger evidence does not erase weaker-source limitations, and paraphrased material must never become quotation-like wording. The validator warns rather than blocking drafts; only the owner may accept retained limitations during claim/citation review and optional evergreen promotion.
