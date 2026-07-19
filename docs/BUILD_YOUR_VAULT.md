# Build your personal vault

This is the single end-to-end first-use guide. Complete one local evidence cycle before adding sync, plugins, custom agents, signed approvals, or a large taxonomy.

## 1. Create a private template copy

1. On GitHub, choose **Use this template → Create a new repository**.
2. Select **Private**. Do not use a public fork for personal notes.
3. Clone the new repository by HTTPS or SSH and enter its root.
4. Install Git and [uv](https://docs.astral.sh/uv/getting-started/installation/) from their official installers.

```sh
git --version
uv --version
uv run --locked python scripts/doctor_vault.py
```

Continue only when the final line is `Core readiness: READY`. The doctor is read-only: it does not install tools, change remotes, write settings, create notes, or generate keys. A warning means the repository's privacy cannot be proved from its remote URL; confirm privacy in your hosting service.

## 2. Open the vault in Obsidian

Choose **Open folder as vault** and select the repository root—the folder containing `AGENTS.md`, `Assets/`, `Sources/`, and `Knowledge/`.

The template already:

- updates internal links after renames;
- sends attachments to `Assets/`;
- enables Properties, Templates, and Daily Notes;
- uses `Templates/` for templates;
- creates daily notes under `Daily/YYYY-MM-DD.md` from `Templates/Daily.md`.

No community plugin is required. To confirm the baseline, run **Daily Notes: Open today's daily note**, then use **Templates: Insert template** in a disposable note.

## 3. Understand the lifecycle

Choose folders by a note's role, not its subject:

| You have | Put it in |
|---|---|
| Owner-controlled local evidence | `Assets/` |
| Faithful evidence record | `Sources/` |
| One durable cited claim | `Knowledge/` |
| Generated synthesis | `Wiki/` |
| Navigation | `MOCs/` |
| Quick capture or chronology | `Inbox/` or `Daily/` |
| Time-bound outcome or ongoing responsibility | `Projects/` or `Areas/` |

Keep subjects in links, aliases, tags, and MOCs. Do not add top-level topic folders.

## 4. Complete the first evidence cycle

The steps below use a small synthetic local Asset so the complete path is reproducible. You may instead choose another owner-controlled local file, but never add confidential or copyrighted material to the public framework checkout.

### 4.1 Add one local Asset

Create `Assets/First cycle.txt` with the exact UTF-8 bytes:

```text
Fixed retry intervals can synchronize client attempts.
```

The file must end with one newline. Compute its SHA-256 without loading it into an editor:

```sh
uv run --locked python -c "import hashlib, pathlib; p=pathlib.Path('Assets/First cycle.txt'); print(hashlib.file_digest(p.open('rb'), 'sha256').hexdigest())"
```

Keep the file unchanged after recording the digest.

### 4.2 Create a processing Source

Use **Templates: Insert template** with `Source`, or ask the root Codex agent to apply `$capture-vault-source` to the exact Asset path. Create `Sources/Fixed retry interval observation.md` with:

- `title: Fixed retry interval observation`;
- `status: processing`;
- `source_type: personal-observation`;
- `source_url: ""` and `inbox_source: null`;
- `review_status: needs-review` and `reviewed: null`;
- one Asset object:

```yaml
assets:
  - path: Assets/First cycle.txt
    media_type: text/plain
    role: primary
    sha256: <the computed lowercase digest>
    extraction_status: extracted
```

In the body, faithfully record the sentence and use `line 1` as its locator. Do not add a general conclusion that the Asset does not state.

Run:

```sh
uv run --locked python scripts/validate_vault.py
```

### 4.3 Perform direct owner review

The owner—not an agent—checks the path, current hash, rights, faithful text, and locator. Then edit only the review fields to:

```yaml
status: captured
review_status: reviewed
reviewed: YYYY-MM-DD
```

Replace `YYYY-MM-DD` with the current local date and run the validator again. Any missing, unreadable, unsafe, or hash-drifted bound Asset blocks distillation.

### 4.4 Create one draft Concept

Use **Templates: Insert template** with `Concept`, or let the root agent run `$distill-vault-sources` on the exact reviewed Source. Create `Knowledge/Fixed retry intervals can synchronize clients.md` with:

- `status: draft`;
- `confidence: medium` for this single personal observation;
- `reviewed: null`;
- `sources: ["[[Sources/Fixed retry interval observation]]"]`;
- one claim that stays within the Source wording.

Agents may draft the note, but only the owner may approve its claim, citation, or promotion to `evergreen`.

### 4.5 Link one MOC

Add the Concept link to `MOCs/Examples/Technology.md` with a short relationship phrase. Do not mass-link keywords or create placeholder notes.

Run the validator once more. The first cycle is complete when it passes and the Source, Concept, and MOC link all open in Obsidian.

## 5. Personalize with one bootstrap prompt

For optional read-only help, copy [.agents/prompts/00-bootstrap-vault.md](../.agents/prompts/00-bootstrap-vault.md). It is the sole onboarding prompt. Supply only topics you actually want; the agent must not infer private facts.

Keep example notes until the first cycle works. Later, remove only exact example paths you have reviewed and update links in `MOCs/Home.md`.

## 6. Add optional workflows gradually

After the first cycle:

1. use Inbox or Daily for quick capture;
2. use URL-only Source intake when a URL is exact and should be recorded without fetching;
3. add Wiki synthesis only after several cited Knowledge notes exist;
4. choose one real-time sync service and one recoverable backup;
5. consider owner-approved custom-agent delegation only when independent read-only tracks materially help.

The root agent runs lifecycle skills sequentially by default and inherits the model available in the active Codex session. Custom agents, detached validation, signed `source_review`, and approval receipts are advanced POSIX workflows; native Windows users run that guarded path in WSL. See [Advanced multi-agent execution](MULTI_AGENT.md).

## 7. Ongoing safety

- Keep the personal repository private.
- Store secrets in a password manager, not Markdown.
- Treat `.gitignore` as convenience, not a security boundary.
- Preserve reviewed Sources; put interpretation in Knowledge.
- Require direct human review for evergreen promotion and material Wiki conclusions.
- Inspect changes before commits or pushes.
- Never merge personal-vault history into the public framework.

## First-cycle checklist

- [ ] Private repository created from the template.
- [ ] Doctor reports `Core readiness: READY`.
- [ ] Repository root opens in Obsidian with portable settings.
- [ ] One local Asset is bound to a processing Source.
- [ ] The owner directly reviews the Source and current Asset bytes revalidate.
- [ ] One cited draft Concept exists.
- [ ] One MOC links the Concept.
- [ ] Vault validation passes.
