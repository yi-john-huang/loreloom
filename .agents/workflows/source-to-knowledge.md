# Workflow: source to knowledge

## Goal

Turn captured evidence into a small set of cited Knowledge drafts without altering or laundering the original source.

## Inputs

- exact Source note paths;
- accessible source attachments or URLs explicitly allowed by the owner;
- relevant existing Knowledge notes found by title, alias, and synonym.

## Procedure

1. Confirm the exact input set and output boundary.
2. For every Source input, require `status: captured`, `review_status: reviewed`, and a non-null `reviewed` date. Stop before reading or writing when a Source is still processing or needs review; Daily inputs are exempt.
3. Run `uv run python scripts/validate_vault.py` before reading or extraction. Stop, report the exact failure, and write no Knowledge if any bound Asset is unsafe, missing, unreadable, or hash-drifted, even when URL or Inbox provenance also exists.
4. Read each Source fully; record inaccessible material as unavailable.
5. Extract candidate claims with source locations and distinguish fact, inference, opinion, and observation.
6. Search for existing canonical notes and aliases.
7. Propose the minimal atomic-note split and citations.
8. Create or update only authorized `status: draft` Concept notes.
9. Optionally append a `Derived notes` link to a Source when explicitly authorized; never rewrite its summary.
10. Add useful cross-topic links and one appropriate MOC suggestion.
11. Run `uv run python scripts/validate_vault.py` again after writes.
12. Hand off revalidated Source paths, draft paths and citations, conflicts and limitations, and the owner-only final claim/citation review and optional evergreen promotion.

## Stop conditions

Stop and ask the owner when provenance is missing, a Source is not owner-reviewed, sources materially conflict, the output would expose restricted data, or the proper note boundary would require a broad reorganization.

## Completion criteria

- every Source input was revalidated against current Asset bytes before extraction;
- every draft has at least one valid evidence link;
- no draft is marked evergreen;
- interpretation is not inserted into Sources;
- the validator passes;
- uncertain claims and conflicts are visible in the handoff;
- the owner retains final claim, citation, and promotion review.
