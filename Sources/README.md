# Sources

Source notes preserve evidence and provenance from exact owner-controlled Assets, absolute HTTP(S) URLs recorded without fetching, Inbox captures, or combinations of those routes.

Manual and root-agent intake both begin as editable `status: processing`, `review_status: needs-review`, `reviewed: null` Sources. Agents may create complete processing records but never attest review. The simple default is direct owner review: verify provenance, current Asset hashes, rights, faithful summary, and machine-assisted limitations, then set the exact `captured / reviewed / <date>` state.

Immediately run `uv run --locked python scripts/validate_vault.py` after review. Unsafe, missing, unreadable, or hash-drifted bound Assets block distillation even when URL or Inbox provenance also exists. `$distill-vault-sources` runs sequentially in the root by default and returns draft Concepts for final owner claim and citation review. Signed `source_review` is an advanced trusted-UI/multi-agent alternative, not required for direct owner review.

After capture and review, treat Sources as append-only; corrections use dated Amendments. Interpretations belong in `Knowledge/`, broad synthesis belongs in `Wiki/`, and copyrighted material should normally remain linked rather than copied into a public vault.
