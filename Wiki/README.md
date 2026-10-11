# Wiki

`Wiki/` is the working layer of the lightweight flow. An agent writes and maintains these pages. The owner reviews exceptions only.

## Sections

| Folder | `type` | Holds |
|---|---|---|
| `Wiki/sources/` | `source` | One summary page per ingested Source |
| `Wiki/entities/` | `entity` | People, places, organizations, products, and tools |
| `Wiki/concepts/` | `concept` | One idea per page |
| `Wiki/synthesis/` | `synthesis` | Comparisons, overviews, and filed query answers |
| `Wiki/_review/` | any of the four | Optional queue of pages that wait for the owner |

Every page starts with this frontmatter:

```yaml
---
title: Page title
type: source|entity|concept|synthesis
status: draft|reviewed|evergreen
confidence: high|medium|low
sources: []
updated: YYYY-MM-DD
---
```

`sources` holds wikilinks to `Sources/`, `Daily/`, or `Assets/`, or an absolute HTTP(S) URL. A synthesis page may also cite other Wiki pages. See [`docs/FRONTMATTER.md`](../docs/FRONTMATTER.md) for the full contract and [`CLAUDE.md`](../CLAUDE.md) for the workflow.

## Directory name

The plan for the lightweight flow writes this folder as lowercase `wiki/`. Loreloom keeps the existing capitalized `Wiki/` and puts the new sections inside it. A second `wiki/` folder would be the same directory as `Wiki/` on macOS and Windows and a different directory on Linux, so the vault would break when it moves between machines. The validator reports an error when both exist.

## Legacy generated pages

A page directly under `Wiki/` with `type: wiki` and `generated: true` is a strict-mode generated page built from `Knowledge/` inputs. Those pages keep their old rules, including the protected `<!-- human:start -->` and `<!-- human:end -->` block. Use `$regenerate-vault-wiki` for them.

Wiki pages are not primary evidence. Evidence lives in `Sources/`.
