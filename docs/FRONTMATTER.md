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
- `source_url`: absolute HTTP(S) URL with a hostname, or empty string for Asset/Inbox-backed evidence; recorded only and never fetched
- `inbox_source`: optional existing `[[Inbox/...]]` provenance link
- `author`: string or list of names
- `published`: `YYYY-MM-DD` or null when unknown
- `captured`: `YYYY-MM-DD`
- `review_status`: `needs-review` or `reviewed`
- `reviewed`: `YYYY-MM-DD` after owner review, otherwise null
- `assets`: list of local asset objects; each object requires `path`, `media_type`, `role`, `sha256`, and `extraction_status`

Asset objects use vault-relative paths such as `Assets/report.pdf`. `media_type` describes the file representation, not the semantic evidence type. `role` is `primary`, `supporting`, or `derived`; `sha256` is a required lowercase hexadecimal digest of the referenced file; and `extraction_status` is `not-requested`, `extracted`, `partial`, or `unavailable`. Every Source needs at least one valid non-empty HTTP(S) URL, verified Asset binding, or existing Inbox provenance link.

Body references to bound Assets may use Obsidian embeds or links. For filenames containing spaces, use `![[Assets/report file.pdf]]`, `[[Assets/report file.pdf]]`, `[report](<Assets/report file.pdf>)`, or percent-encoded destinations such as `[report](Assets/report%20file.pdf)`; raw unbracketed spaces and Markdown link titles are unsupported.

Source state is intentionally gated: `status: processing` requires `review_status: needs-review` and `reviewed: null`; `status: captured` requires `review_status: reviewed` and a non-null review date. The owner performs this transition directly or initiates an exact signed `source_review`; agents never attest review. Revalidate current Asset bytes immediately afterward and before distillation. The legacy `processed` field is invalid.

### Concept

- `confidence`: `low`, `medium`, or `high`
- `reviewed`: `YYYY-MM-DD` or null
- `sources`: non-empty list of Source/Daily wikilinks or allowed evidence markers

Only a human may set `status: evergreen` and a non-null `reviewed` date.

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
