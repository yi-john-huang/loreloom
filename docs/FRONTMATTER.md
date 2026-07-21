# Frontmatter schemas

Every managed note begins with YAML frontmatter. The machine-readable contract is in [`schemas/frontmatter.schema.json`](../schemas/frontmatter.schema.json).

## Common fields

| Field | Required | Meaning |
|---|---:|---|
| `type` | yes | Note kind: `inbox`, `source`, `concept`, `wiki`, `moc`, `project`, `area`, or `daily` |
| `title` | yes | Human-readable canonical title |
| `status` | yes | Controlled lifecycle value |
| `created` | yes | Creation date, `YYYY-MM-DD` |
| `updated` | yes | Last material edit, `YYYY-MM-DD` |
| `tags` | yes | List of lowercase topic facets |
| `aliases` | yes | Alternate names, possibly empty |
| `agent` | no | Agent responsible for a material generated change |

Unknown fields are permitted for local extension, but templates and agents should use established fields when possible.

## Type-specific fields

### Inbox

- `captured_from`: `manual`, `web`, `email`, `meeting`, `chat`, `file`, or `other`

### Source

- `source_type`: semantic evidence type: `article`, `book`, `documentation`, `paper`, `video`, `podcast`, `meeting`, `personal-observation`, `dataset`, or `other`
- `capture_method`: intake route: `asset`, `url-reference`, `web-clipper`, `manual-entry`, `file-extraction`, `ocr`, `transcription`, `import`, or `mixed`
- `capture_mode`: representation relationship: `preserved-original`, `verbatim-excerpt`, `extracted`, `transcribed`, `paraphrased`, `firsthand-observation`, `reference-only`, `unknown`, or `mixed`
- `source_url`: absolute HTTP(S) URL with a hostname, or empty string for Asset/Inbox-backed evidence; recorded only and never fetched
- `inbox_source`: optional existing `[[Inbox/...]]` provenance link
- `author`: string or list of names
- `published`: `YYYY-MM-DD` or null when unknown
- `captured`: `YYYY-MM-DD`
- `review_status`: `needs-review` or `reviewed`
- `reviewed`: `YYYY-MM-DD` after owner review, otherwise null
- `assets`: list of local asset objects; each object requires `path`, `media_type`, `role`, `sha256`, and `extraction_status`

Asset objects use vault-relative paths such as `Assets/report.pdf`. `media_type` describes the file representation, not the semantic evidence type. `role` is `primary`, `supporting`, or `derived`; `sha256` is a required lowercase hexadecimal digest of the referenced file; and `extraction_status` is `not-requested`, `extracted`, `partial`, or `unavailable`. Every Source needs at least one valid non-empty HTTP(S) URL, verified Asset binding, or existing Inbox provenance link.

The three axes are independent:

```text
source_type = what the evidence is
capture_method = how it entered the vault
capture_mode = how the captured representation relates to the original evidence
```

For example:

```yaml
source_type: paper
capture_method: asset
capture_mode: preserved-original
```

```yaml
source_type: paper
capture_method: manual-entry
capture_mode: unknown
```

```yaml
source_type: paper
capture_method: manual-entry
capture_mode: paraphrased
```

```yaml
source_type: video
capture_method: transcription
capture_mode: transcribed
```

Classify conservatively because the risks are asymmetric: a false low-fidelity label can be reviewed and upgraded by the owner, while a false high-fidelity label can launder a summary into apparent evidence. Manual entry therefore defaults to `unknown`; writing style, quotation marks, file extension, tool name, a hash, and owner confidence do not prove semantic fidelity.

Cross-field validation checks only mechanically observable facts:

- `asset` requires a declared Asset; `preserved-original` requires a primary Asset whose current hash is validated.
- `url-reference` and `reference-only` require a valid HTTP(S) `source_url`.
- `file-extraction`, `ocr`, and `extracted` require an Asset with `extraction_status: extracted` or `partial` and a populated `Extracted or transcribed material` boundary.
- `transcription` and `transcribed` require audio/video Asset provenance, or a valid URL with `source_type: video` or `podcast`, plus the extraction/transcription boundary. Quoted transcript passages require timestamps.
- `verbatim-excerpt` requires a Key-passages list item ending in `— page <value>`, `— timestamp <value>`, `— frame <value>`, `— line <value>`, `— section <value>`, or `— region <value>`.
- `firsthand-observation` requires `source_type: personal-observation`.
- `paraphrased` requires a populated `Paraphrased material` boundary and forbids quoted Key-passages evidence.
- `mixed` requires at least two populated concrete categories in `## Capture boundary`.
- `web-clipper`, `manual-entry`, `import`, and `unknown` make no stronger mechanically provable claim. Existing Asset, URL, or Inbox provenance remains mandatory.

Every Source uses this exact body contract:

```markdown
## Capture boundary

- Capture method:
- Capture mode:
- Original evidence preserved:
- Verbatim material:
- Extracted or transcribed material:
- Paraphrased material:
- Unknown or unavailable evidence:
```

The validator ignores fenced code and treats blank values, `None`, `N/A`, HTML comments, template tokens, and angle-bracket placeholders as empty. It validates structure, provenance, hashes, locators, and internal consistency; it cannot prove that prose is semantically faithful.

#### Manual migration

Inventory legacy Sources by running `uv run --locked python scripts/validate_vault.py`; missing-field diagnostics name both fields and state that no value was inferred. For each Source, inspect the original evidence, add `capture_method` and `capture_mode`, update `updated`, and complete the Capture Boundary. For a reviewed Source, append a dated Amendment recording the classification and its evidence basis. Use `capture_mode: unknown` when fidelity cannot be established. If the intake method itself is ambiguous, the owner must classify it rather than accepting an invented value. Agents must not bulk-rewrite legacy personal Sources, and there is intentionally no automatic migration script.

Body references to bound Assets may use Obsidian embeds or links. For filenames containing spaces, use `![[Assets/report file.pdf]]`, `[[Assets/report file.pdf]]`, `[report](<Assets/report file.pdf>)`, or percent-encoded destinations such as `[report](Assets/report%20file.pdf)`; raw unbracketed spaces and Markdown link titles are unsupported.

Source state is intentionally gated: `status: processing` requires `review_status: needs-review` and `reviewed: null`; `status: captured` requires `review_status: reviewed` and a non-null review date. The owner performs this transition directly by default; an exact signed `source_review` is an advanced trusted-UI/multi-agent alternative. Agents never attest review. Revalidate current Asset bytes immediately afterward and before distillation. The legacy `processed` field is invalid.

### Concept

- `confidence`: `low`, `medium`, or `high`
- `reviewed`: `YYYY-MM-DD` or null
- `sources`: non-empty list of Source/Daily wikilinks or allowed evidence markers

Only a human may set `status: evergreen` and a non-null `reviewed` date.

When a draft or evergreen Concept cites a Source whose `capture_mode` is `unknown`, `paraphrased`, or `reference-only`, retain a non-empty `## Evidence limitations` section. The validator warns without failing when it is absent and emits a stronger warning when an evergreen Concept relies exclusively on those modes. A Daily citation or a stronger Source suppresses only the exclusive-evidence warning. Human-only evergreen promotion plus review of the retained section is the acceptance mechanism; there is no separate acceptance field.

### Wiki

- `generated`: must be `true`
- `generated_at`: `YYYY-MM-DD`
- `generator`: agent or workflow name
- `inputs`: non-empty list of Knowledge wikilinks
- `review_status`: `unreviewed`, `reviewed`, or `needs-review`

### MOC

- `scope`: short description of the navigation boundary
- `curation`: `human`, `assisted`, or `generated`

### Project

- `outcome`: a testable desired result
- `started`: `YYYY-MM-DD`
- `due`: `YYYY-MM-DD` or null
- `area`: Area wikilink or null

### Area

- `review_cycle`: `weekly`, `monthly`, `quarterly`, `yearly`, or `ad-hoc`
- `owner`: person or role responsible

### Daily

- `date`: must match the note's `YYYY-MM-DD` filename

## Empty values

Use `null` for an unknown date or link and `[]` for an empty list. Use `""` only where the schema explicitly permits an empty string, such as `source_url` for an offline source.

## Template tokens

Files under `Templates/` use `{{date}}`, `{{title}}`, and similar readable placeholders. The validator intentionally excludes templates because placeholder values are not valid instances of the schema.
