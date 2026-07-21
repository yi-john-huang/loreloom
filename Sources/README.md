# Sources

Source notes preserve provenance-bound evidence from exact owner-controlled Assets, absolute HTTP(S) URLs recorded without fetching, Inbox captures, or combinations of those routes.

Every Source classifies three independent axes:

```text
source_type = what the evidence is
capture_method = how it entered the vault
capture_mode = how the captured representation relates to the original evidence
```

A paper can therefore be `asset` + `preserved-original`, `manual-entry` + `unknown`, or an explicitly owner-declared `manual-entry` + `paraphrased`. A video transcript is `transcription` + `transcribed`. The asymmetric-risk rule is conservative: a false low-fidelity label is reviewable, but a false high-fidelity label can launder a summary into apparent evidence. Manual input defaults to `unknown`; quotation marks, style, extension, tool name, hash, or confidence do not prove fidelity.

Use the exact `## Capture boundary` labels from `Templates/Source.md`. Verbatim Key passages require page, timestamp, frame, line, section, or region locators; quoted transcripts require timestamps. Extraction/OCR requires an extracted or partial Asset, transcription requires audio/video provenance, preserved originals require a hash-validated primary Asset, reference-only intake requires a URL, and mixed intake requires at least two concrete boundary categories. The validator proves only structural consistency, provenance, hashes, and locators—not semantic fidelity.

Manual and root-agent intake both begin as editable `status: processing`, `review_status: needs-review`, `reviewed: null` Sources. Agents may create complete processing records but never attest review or upgrade fidelity. The simple default is direct owner review: verify provenance, current Asset hashes, rights, capture classification, boundary, summary, and machine-assisted limitations, then set the exact `captured / reviewed / <date>` state.

Immediately run `uv run --locked python scripts/validate_vault.py` after review. Unsafe, missing, unreadable, or hash-drifted bound Assets block distillation even when URL or Inbox provenance also exists. `$distill-vault-sources` records each Source's `capture_mode`; drafts using `unknown`, `paraphrased`, or `reference-only` evidence retain a non-empty `## Evidence limitations` section for final owner review. Signed `source_review` is an advanced trusted-UI/multi-agent alternative, not required for direct owner review.

After capture and review, treat Sources as append-only; corrections use dated Amendments. To classify a reviewed legacy Source, the owner adds `capture_method` and `capture_mode`, completes the Capture Boundary, updates `updated`, and appends a dated Amendment recording the classification and evidence basis. Interpretations belong in `Knowledge/`, broad synthesis belongs in `Wiki/`, and copyrighted material should normally remain linked rather than copied into a public vault. See `docs/FRONTMATTER.md` for the exact enum, locator, boundary, and manual-migration contracts.
