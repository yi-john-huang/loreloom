# Distill a Source into Knowledge drafts

```text
Follow AGENTS.md, .agents/policies/vault-policy.md, and
.agents/workflows/source-to-knowledge.md.

Exact Source inputs:
- <SOURCE PATHS>

Allowed output directory:
- Knowledge/<OPTIONAL SUBDIRECTORY>

Read the complete supplied Source notes and the source material only if it is
available within the authorized context. Search Knowledge by title, aliases,
and synonyms before creating notes.

Create or update the fewest atomic Concept drafts needed. Each claim must be
traceable to an input Source, fact must be separated from inference, and
uncertainty must be explicit. Record every Source's capture_mode before
extracting claims. For each draft, if any Source it cites uses unknown,
paraphrased, or reference-only, add a non-empty ## Evidence limitations
section with the exact applicable statements from
.agents/workflows/source-to-knowledge.md. Retain weaker-source limitations
when stronger evidence is also cited, never present a paraphrase as a
quotation, and never upgrade unknown or paraphrased evidence. Set
status: draft, reviewed: null, and the appropriate confidence. Never modify
the Source except for an explicitly requested append-only Derived notes link
or amendment.

Do not create Wiki pages, promote anything to evergreen, or fill gaps from
general model memory. Run validation and hand off created, updated, skipped,
duplicate, and uncertain items for human review.
```
