# Architecture

## Design objective

The vault stores many subjects in one graph while separating notes by lifecycle and authority. A note about a conference can connect technology, career, travel, and food without being duplicated into four topic folders.

## Layers

### Capture: `Inbox/` and `Daily/`

Capture is fast and permissive. Content here may be incomplete, duplicated, or untrusted. Inbox items should eventually be processed, deliberately deferred, or archived. Daily notes are an event log, not automatically durable truth.

### Evidence: `Sources/`

Source records describe where information came from. They may point to local attachments or external locations. Preserve the original meaning and distinguish quotations from summaries. Copyrighted material should normally remain outside a public repository; store metadata and a link instead.

Once captured, a Source note is append-only by default. Corrections are recorded in a dated `## Amendments` section rather than silently rewriting history.

### Canonical knowledge: `Knowledge/`

Knowledge notes represent one durable concept each. They synthesize sources, use the author's own words, and link to related concepts. Drafts may be AI-assisted. `status: evergreen` means a human has reviewed the claims and sources.

Knowledge notes are the canonical input for generated Wiki pages. They are not generated build artifacts.

### Synthesis: `Wiki/`

Wiki pages answer broader questions by combining Knowledge notes. They are reproducible views, comparisons, guides, or handbooks. Each generated page declares `inputs` and carries generation metadata.

Generated pages may include a protected human section:

```md
<!-- human:start -->
This text is preserved across regeneration.
<!-- human:end -->
```

Everything outside that boundary may be regenerated after review.

### Navigation: `MOCs/`

Maps of Content are intentionally curated entry points into the graph. A MOC may represent a subject, question, place, or goal. Unlike a Wiki page, its primary job is navigation, not comprehensive explanation.

### Action: `Projects/` and `Areas/`

A Project has a desired outcome and an end condition. An Area is an ongoing responsibility with a review cadence. Both link into Knowledge instead of becoming isolated topic silos.

### History: `Archive/`

Archive inactive material without erasing its provenance. Moving a note does not make it less searchable or break a full-path wikilink if links are updated in the same change.

## Promotion lifecycle

```text
captured -> processing -> draft -> evergreen
    |            |           |
    +------------+-----------+-> archived
```

The lifecycle is not fully automatic:

1. A human or agent captures an Inbox item or Source record.
2. An agent can propose atomic Knowledge drafts with citations.
3. A human verifies important claims and promotes drafts to `evergreen`.
4. An agent regenerates relevant Wiki pages from reviewed Knowledge plus explicitly allowed drafts.
5. MOCs receive links to useful new pages.
6. Superseded or inactive content is archived, not destroyed.

## Topic model

Topics are expressed through three complementary mechanisms:

- **Links** capture meaningful relationships.
- **Tags** provide broad, filterable facets such as `tech/aws` or `food/ramen`.
- **MOCs** provide a human-designed path through a subject.

Folders answer “what lifecycle and authority does this note have?” Metadata answers “what is it about?”

## Reproducibility

A generated Wiki page is reproducible when it records:

- the input note paths;
- the generation date and agent name;
- its review state;
- preserved human-authored regions;
- enough workflow context to regenerate it.

The system does not promise byte-identical output from a probabilistic model. It promises traceable inputs, bounded authority, and reviewable diffs.
