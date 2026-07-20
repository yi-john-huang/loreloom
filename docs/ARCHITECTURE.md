# Architecture

## Design objective

The vault stores many subjects in one graph while separating notes by lifecycle and authority. A note about a conference can connect technology, career, travel, and food without being duplicated into four topic folders.

## Layers

### Capture: `Inbox/`, `Daily/`, and `Assets/`

Capture is fast and permissive. Inbox items may be incomplete, duplicated, or untrusted; Daily notes are an event log, not automatically durable truth; and Assets holds owner-supplied binary evidence. `$capture-vault-source` turns exact Assets or absolute HTTP(S) URLs into editable Source intake notes without fetching URLs or overwriting resources; URL recording does not assert reachability, freshness, or extraction.

### Evidence: `Sources/`

Source records describe where information came from and classify three independent axes: `source_type` is what the evidence is, `capture_method` is how it entered the vault, and `capture_mode` is how the captured representation relates to original evidence. They may bind local attachments or record absolute HTTP(S) locations. Preserve the declared boundary between originals, quotations, extraction/transcription, paraphrase, and unavailable evidence. Copyrighted material should normally remain outside a public repository; store metadata and a link instead.

Capture classification is deliberately conservative. A paper may be `asset` + `preserved-original`, `manual-entry` + `unknown`, or explicitly `manual-entry` + `paraphrased`; a video transcript is `transcription` + `transcribed`. Manual entry defaults to `unknown` because falsely claiming high fidelity can launder a summary into apparent evidence. Hashes and validators establish provenance and consistency, not semantic fidelity.

Source intake begins at `status: processing`, `review_status: needs-review`, and `reviewed: null`. The owner verifies provenance, current Asset hashes, rights, classification, Capture Boundary, and machine-assisted limitations, then reviews directly. Exact signed `source_review` is an advanced alternative.

Immediately after review and before distillation, revalidate current Asset bytes. Once captured and reviewed, a Source is append-only by default; corrections use dated Amendments rather than silently rewriting history.

### Canonical knowledge: `Knowledge/`

Knowledge notes represent one durable concept each. They synthesize sources, use the author's own words, and link to related concepts. Drafts may be AI-assisted. `status: evergreen` means a human has reviewed the claims and sources.

Drafts that cite `unknown`, `paraphrased`, or `reference-only` Source evidence retain a non-empty `## Evidence limitations` section with mode-specific wording. Stronger evidence does not erase weaker-source limitations. The validator warns rather than blocking draft creation; the owner reviews the section during claim/citation review and any evergreen promotion.

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
Asset / HTTP(S) URL / Inbox / Daily
                   |
                   v
Source processing -> owner review -> Asset revalidation -> Concept draft
                                                           |
                                                           v
                                                owner claim/citation review
                                                           |
                                                           v
                                             optional evergreen -> Wiki
```

The lifecycle is not fully automatic:

1. An owner supplies a local Asset, records an absolute HTTP(S) URL, or captures an Inbox/Daily item.
2. Manual intake or `$capture-vault-source` creates an editable Source in `status: processing` with explicit `source_type`, `capture_method`, `capture_mode`, and Capture Boundary.
3. The owner verifies provenance, hashes, rights, classification, and fidelity, then reviews directly; signed `source_review` is an advanced alternative.
4. `validate_vault.py` immediately revalidates every bound Asset and the mechanical capture prerequisites against current bytes and metadata.
5. `$distill-vault-sources` reads only owner-reviewed, revalidated Sources, records their capture modes, and creates cited `status: draft` Concepts with required Evidence limitations.
6. The owner verifies every important claim, citation, and retained limitation before optional evergreen promotion.
7. An agent may regenerate relevant Wiki pages from reviewed Knowledge plus explicitly allowed drafts, and MOCs may receive useful links.
8. Superseded or inactive content is archived, not destroyed.

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
