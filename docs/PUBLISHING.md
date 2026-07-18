# Publishing and template setup

## Prepare the public framework repository

1. Confirm the public repository URLs point to `yi-john-huang/loreloom`.
2. Review `LICENSE`, governance files, and issue labels for the project.
3. Run `uv run python scripts/validate_vault.py`.
4. Review the complete Git history and staged diff for private information.
5. Create the empty public GitHub repository without adding a README or license.
6. Add it as the local repository's `origin` and push the `master` branch.
7. In GitHub **Settings -> General**, enable **Template repository**.
8. Optionally enable private vulnerability reporting and Discussions.

Publishing changes external state and should remain a separate, deliberate step when someone reuses the scaffold under another account.

## Create a personal vault

On the public repository page, select **Use this template -> Create a new repository**. Choose private visibility and a name unrelated to the public framework if desired. A template-created repository starts with independent history and is safer for personal use than a fork connected to the public contribution graph.

Clone the private repository and open its root as an Obsidian vault. Keep its remote private. After onboarding, replace the example links in `MOCs/Home.md`, delete the example subdirectories, run validation, and then personalize the ownership rules in `AGENTS.md`.

## Contribute framework improvements later

Keep the personal vault and public framework as separate working copies. Re-create a generic improvement in a clean branch of the public repository using synthetic fixtures. Do not merge or cherry-pick commits that also contain personal notes.

Before publishing a contribution:

- inspect every changed file rather than relying only on `.gitignore`;
- verify examples contain no personal facts or restricted source text;
- run validation;
- disclose material AI assistance in the pull request;
- push only the public-framework branch.

## Release checklist

- [ ] Public repository URLs point to the intended owner and repository.
- [ ] Validation passes locally and in GitHub Actions.
- [ ] Default branch protection and required checks configured.
- [ ] Repository description and topics added.
- [ ] Template repository setting enabled.
- [ ] A test private vault was created from the template.
- [ ] Restore and rollback procedures were tested before real notes were added.
