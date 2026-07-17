# Conventions

## File and title rules

- Use descriptive natural-language filenames: `IAM role.md`, not `iam-role-v2-final.md`.
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

- Use vault-root paths for important links: `[[Knowledge/Examples/IAM role]]`.
- Use aliases for readable sentences: `[[Knowledge/Examples/IAM role|IAM roles]]`.
- Link when the relationship helps future navigation, not every time a word appears.
- Add a brief relationship phrase around lists of links.
- Do not create placeholder links unless the missing concept is explicitly marked as planned work.

## Citations

Durable Knowledge claims need traceable evidence. Put source-note paths in frontmatter:

```yaml
sources:
  - "[[Sources/Examples/AWS IAM roles - AWS docs]]"
```

Use inline references near claims when a note has multiple sources or contentious details. Quotes must be short, exact, and clearly marked. Never cite a generated Wiki page as primary evidence.

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
| `processing` | Currently being reviewed or distilled |
| `draft` | Usable but not human-approved |
| `evergreen` | Human-reviewed canonical knowledge |
| `active` | Current Project or Area |
| `on-hold` | Intentionally paused |
| `completed` | Project outcome reached |
| `archived` | Retained but inactive |

## Attachments

Place binary files under `Assets/` and link them from a Source note. Use stable, descriptive names. Avoid committing large or copyrighted files to the public framework; prefer a source URL or private external storage.
