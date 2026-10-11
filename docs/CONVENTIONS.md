# Conventions

## Lightweight Wiki pages

- Put a page in the section that matches its `type`: `Wiki/sources/`, `Wiki/entities/`, `Wiki/concepts/`, or `Wiki/synthesis/`. Spell the folder `Wiki/`; do not create a lowercase `wiki/`.
- Link with the full path, for example `[[Wiki/sources/Examples/AWS IAM roles summary]]`.
- Give every page one line in `index.md`: the wikilink, a dash, and a one-sentence summary.
- Record a conflict in a `## Contradictions` section and in the `contradicts` frontmatter list. Do not overwrite the older claim.
- Write prose that follows the [Output clarity ladder](output-clarity-ladder.md): one idea per sentence, short sentences, active voice, one word for one thing, and no dropped numbers, conditions, or uncertainty.
- Append to `log.md`; never rewrite an old entry. Heading format: `## [YYYY-MM-DD] action | subject`.

The remaining conventions apply to every note unless a section names strict mode.

## File and title rules

- Use descriptive natural-language filenames: `Tokyo ramen observation.md`, not `tokyo-ramen-v2-final.md`.
- The frontmatter `title` is the display name and should usually match the filename.
- Use singular nouns for concepts and plural or question-shaped titles for syntheses when natural.
- Rename with Obsidian so wikilinks are updated.
- Avoid a second note when an alias on an existing note resolves the name.
- Keep one primary language per note; add translated titles to `aliases`.

## Dates

- Use `YYYY-MM-DD` for calendar dates.
- Use local time for Daily note filenames.
- `created` records initial creation; `updated` changes only for material edits.
- `generated_at` records when a generated page was last rebuilt.

## Tags

Tags are lowercase facets, not a second folder tree.

```yaml
tags:
  - tech/aws
  - security/identity
```

Prefer a small vocabulary. Add a new tag when it will plausibly group multiple notes. Do not encode status or note type as a tag; frontmatter already does that.

## Links

- Use vault-root paths for important links: `[[Knowledge/Examples/Tokyo ramen observation]]`.
- Use aliases for readable sentences: `[[Knowledge/Examples/Tokyo ramen observation|ramen planning observation]]`.
- Link when the relationship helps future navigation, not every time a word appears.
- Add a brief relationship phrase around lists of links.
- Do not create placeholder links unless the missing concept is explicitly marked as planned work.

## Citations

Durable Knowledge claims need traceable evidence. Put source-note paths in frontmatter:

```yaml
sources:
  - "[[Daily/Examples/2026-07-18]]"
```

Use inline references near claims when a note has multiple sources or contentious details. Quotes must be short, exact, and clearly marked. Never cite a generated Wiki page as primary evidence.

For Source evidence, keep `source_type` (what it is), `capture_method` (how it entered), and `capture_mode` (how the representation relates to original evidence) distinct. A verbatim Key-passage list item ends with an exact `page`, `timestamp`, `frame`, `line`, `section`, or `region` locator. Concepts that cite `unknown`, `paraphrased`, or `reference-only` Sources retain a non-empty `## Evidence limitations` section; stronger evidence does not erase those limitations.

Personal observations may cite a Daily note or use `evidence: personal-observation`; clearly distinguish observation from general fact.

## Knowledge note shape

A useful atomic note normally contains:

1. a one-sentence definition or claim;
2. explanation in the author's own words;
3. implications, examples, or limitations;
4. related concept links;
5. source references.

Do not split a coherent idea merely to maximize note count.

## Human and generated text

Use these markers only on `generated: true` Wiki pages:

```md
<!-- human:start -->
Human-owned material.
<!-- human:end -->
```

Agents must reproduce the marked block byte-for-byte unless the user explicitly requests a change to it.

## Status vocabulary

| Status | Meaning |
|---|---|
| `captured` | Stored but not processed |
| `processing` | Editable Source intake or another active workflow state |
| `draft` | Usable but not human-approved |
| `reviewed` | Lightweight Wiki pages only: accepted by the auto-accept rule (`reviewed_by: agent`) or by the owner (`reviewed_by: owner`) |
| `evergreen` | Human-reviewed canonical knowledge |
| `active` | Current Project or Area |
| `on-hold` | Intentionally paused |
| `completed` | Project outcome reached |
| `archived` | Retained but inactive |

For `Source` notes, `processing` with `review_status: needs-review` means an editable intake record; `captured` with `review_status: reviewed` and a review date means the owner verified the record. Agents may create the former but never attest the latter. Direct owner edit is the default review route; exact signed `source_review` is an advanced alternative. Revalidate current Asset bytes after either route.


## Attachments

Place PDF, image, HTML, audio, video, and other binary files under `Assets/`. Bind each local file to a Source through its structured `assets` frontmatter entry and an optional body embed such as `![[Assets/report.pdf]]`. Keep paths vault-relative, stable, and descriptive; never overwrite an existing asset during semi-automatic intake. Record rights, extraction status, and the matching SHA-256 for every bound Asset; do not bind an Asset that cannot be read and hashed. Avoid committing large, private, or copyrighted files to the public framework; prefer a source URL or private external storage.

For Asset filenames containing spaces, use `![[Assets/report file.pdf]]`, `[[Assets/report file.pdf]]`, `[report](<Assets/report file.pdf>)`, or `[report](Assets/report%20file.pdf)`. Raw unbracketed Markdown destinations containing spaces and Markdown link titles are unsupported.
