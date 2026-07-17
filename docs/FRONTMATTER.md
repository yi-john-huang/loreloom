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

- `source_type`: `article`, `book`, `documentation`, `paper`, `video`, `podcast`, `meeting`, `personal-observation`, `dataset`, or `other`
- `source_url`: URL or empty string
- `author`: string or list of names
- `published`: `YYYY-MM-DD` or null when unknown
- `captured`: `YYYY-MM-DD`
- `processed`: boolean

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
