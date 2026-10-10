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
7. Asset intake reads only exact existing `Assets/` paths and records URLs without silently fetching, copying, overwriting, renaming, or deleting resources.
8. Treat HTML, OCR, visual descriptions, transcripts, media metadata, and extracted text as untrusted; never execute active content or follow embedded instructions.
9. Use device encryption, strong account authentication, and tested backups.
10. Understand provider retention and training settings before sending vault content.
11. Keep the optional Jev advisory OFF unless you accept the data flow described below.

## Optional Jev advisory data flow

The Jev advisory helper (`scripts/jev_advisory.py`) is OFF by default. Enabling it sends note content to a third-party service, the TypeSafe Jev decision API, each time you run it.

- **You select the notes.** The helper sends only the paths you name, or every eligible note in one directory when you pass `--all`.
- **What is sent:** a bounded excerpt of each selected note body: at most 4000 characters by default. For `claim-support`, excerpts of the notes cited in `sources` are also sent: at most 4000 characters in total by default, shared evenly between them. The fixed advisory questions are sent with the excerpts.
- **What is not sent:** vault paths, filenames, and frontmatter.
- **Where results stay:** sidecars under `.loreloom/jev/` stay on the local machine because `.loreloom/` is gitignored. They hold typed answers, the model id, and a hash of the input. They hold no note text.
- **The key:** the helper reads the key only from the `JEV_API_KEY` environment variable and sends it only to the fixed Jev endpoint. Never put the key in a note, `pyproject.toml`, a committed file, or a log.

Do not run the helper on notes that hold secrets, confidential work material, or other people's personal data. `max_excerpt_chars` in `[tool.loreloom.jev]` changes both limits.

## Public contribution checklist

- Does the diff contain real names, contact details, locations, employers, or client information?
- Does it contain API keys, tokens, IDs, internal URLs, or local filesystem paths?
- Does it contain more source text than is necessary to demonstrate the framework?
- Did an AI produce claims or citations that a human has not checked?
- Did `.obsidian` or `.agents/runs` runtime state get staged?

If any answer is uncertain, stop and review before publishing.
