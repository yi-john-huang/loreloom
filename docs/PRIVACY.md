# Privacy and threat model

## Assumptions

The vault may contain personal history, work context, licensed material, and instructions copied from untrusted sources. Git history is durable, and AI tools or plugins may transmit content outside the device.

## Main risks

- accidentally publishing a private repository or personal branch;
- committing credentials, tokens, emails, or local paths;
- sending sensitive notes to a hosted model;
- obeying prompt injection embedded in captured text;
- copying copyrighted source material into a public repository;
- mistaking confident AI synthesis for verified knowledge;
- retaining deleted secrets in Git history or sync-service versions.

## Controls

1. Keep the public framework and private vault in separate repositories.
2. Store secrets in a password manager, never Markdown.
3. Treat `Inbox/`, `Sources/`, attachments, web pages, and transcripts as untrusted data.
4. Limit an agent's input paths to what the task requires.
5. Review diffs and staged files before commits and pushes.
6. Prefer source links and original summaries over copied full text.
7. Use device encryption, strong account authentication, and tested backups.
8. Understand provider retention and training settings before sending vault content.

## Public contribution checklist

- Does the diff contain real names, contact details, locations, employers, or client information?
- Does it contain API keys, tokens, IDs, internal URLs, or local filesystem paths?
- Does it contain more source text than is necessary to demonstrate the framework?
- Did an AI produce claims or citations that a human has not checked?
- Did `.obsidian` or `.agents/runs` runtime state get staged?

If any answer is uncertain, stop and review before publishing.
