# Workflow: source to knowledge

## Goal

Turn captured evidence into a small set of cited Knowledge drafts without altering or laundering the original source.

## Inputs

- exact Source note paths;
- accessible source attachments or URLs explicitly allowed by the owner;
- relevant existing Knowledge notes found by title, alias, and synonym.

## Procedure

1. Confirm the exact input set and output boundary.
2. Read each Source fully; record inaccessible material as unavailable.
3. Extract candidate claims with source locations and distinguish fact, inference, opinion, and observation.
4. Search for existing canonical notes and aliases.
5. Propose the minimal atomic-note split and citations.
6. Create or update only authorized `status: draft` Concept notes.
7. Optionally append a `Derived notes` link to a Source when explicitly authorized; never rewrite its summary.
8. Add useful cross-topic links and one appropriate MOC suggestion.
9. Run `uv run python scripts/validate_vault.py`.
10. Hand off claims, uncertainty, duplicates, and human review needs.

## Stop conditions

Stop and ask the owner when provenance is missing, sources materially conflict, the output would expose restricted data, or the proper note boundary would require a broad reorganization.

## Completion criteria

- every draft has at least one valid evidence link;
- no draft is marked evergreen;
- interpretation is not inserted into Sources;
- the validator passes;
- uncertain claims are visible in the handoff.
