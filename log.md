# Log

This file is the append-only history of the vault. An agent adds one entry at the end for every ingest, filed answer, lint pass, and migration. Nobody rewrites an old entry.

Entry heading format: `## [YYYY-MM-DD] action | subject`. The action is `ingest`, `query`, `lint`, `review`, or `migrate`.

A page that needs the owner gets a line that starts with `Needs review:` and gives the reason. When the owner settles the item, the agent adds a new `review` entry. The old line stays.

## [2026-10-11] ingest | AWS IAM roles - AWS docs

- Source: [[Sources/Examples/AWS IAM roles - AWS docs]]
- Created: [[Wiki/sources/Examples/AWS IAM roles summary]] with status draft.
- Needs review: [[Wiki/sources/Examples/AWS IAM roles summary]] — confidence is medium because the Source is a reference-only summary and does not hold the original text.
