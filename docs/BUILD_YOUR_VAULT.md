# Build your personal vault

This is the single copy-ready first-use runbook. Complete it to produce a private template copy, a passing doctor, one reviewed Source, one cited draft Concept, and one MOC link before adding sync, plugins, custom agents, signed approvals, or a large taxonomy. Stop whenever an **Expected** result is not observed; diagnose the mismatch before continuing.

## 1. Create a private template copy and run the doctor

1. On GitHub, choose **Use this template → Create a new repository**.
2. Select **Private**. Do not use a public fork for personal notes.
3. Clone the new repository by HTTPS and enter its root.
4. Install [Git](https://git-scm.com/downloads) and [uv](https://docs.astral.sh/uv/getting-started/installation/) from their official installers. `uv` provisions the required Python and dependencies automatically.

Replace both `YOUR-*` tokens below before copying the block:

```sh
git clone https://github.com/YOUR-NAME/YOUR-PRIVATE-VAULT.git
cd YOUR-PRIVATE-VAULT
git --version
uv --version
uv run --locked python scripts/doctor_vault.py
```

**Expected:** the final line is exactly `Core readiness: READY`.

The doctor is read-only: it does not install tools, change remotes, write settings, create notes, or generate keys. `[WARN] remote-privacy` is non-blocking only after you confirm in the hosting service that this repository is private. Stop on any `[FAIL]` or `Core readiness: NOT READY`.

## 2. Open the vault in Obsidian

In Obsidian, choose **Open folder as vault** and select the repository root—the folder containing `AGENTS.md`, `Assets/`, `Sources/`, and `Knowledge/`.

Open the Command Palette and confirm that both commands are listed:

- **Daily Notes: Open today's daily note**
- **Templates: Insert template**

Do not execute either command yet. The doctor has already checked that Daily Notes uses `Daily/YYYY-MM-DD.md`, Templates uses `Templates/`, attachments use `Assets/`, Properties is enabled, and links update after renames. No community plugin is required.

Obsidian may normalize tracked settings when it opens the vault. The final Git-status check will expose any resulting change for review.

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

Every Source keeps three axes separate: `source_type` is what the evidence is, `capture_method` is how it entered the vault, and `capture_mode` is how the captured representation relates to original evidence. This synthetic cycle uses a hash-bound original Asset; manual text would default to `unknown`, not inherit stronger fidelity from confident wording.

## 4. Complete the first evidence cycle

The steps below use a small synthetic local Asset so the complete path is deterministic. Do not substitute personal, confidential, or copyrighted material during this first cycle.

### 4.1 Print the date and create the Asset

From the repository root, copy this block:

```sh
uv run --locked python -c "from datetime import date; print(date.today().isoformat())"
uv run --locked python -c "from pathlib import Path; Path('Assets/First cycle.txt').write_bytes(b'Fixed retry intervals can synchronize client attempts.\n')"
uv run --locked python -c "import hashlib; from pathlib import Path; p=Path('Assets/First cycle.txt'); print(hashlib.file_digest(p.open('rb'), 'sha256').hexdigest())"
```

Use the date printed by the first command for every `YYYY-MM-DD` below.

**Expected digest:**

```text
1992ea4fe993a56a5d965c84db14f2ceec44a37afa5c6eecddfc14f1cc20c135
```

Stop if the digest differs.

### 4.2 Create the processing Source

Create `Sources/Fixed retry interval observation.md`. Replace every `YYYY-MM-DD` with the date printed above, then paste the complete note:

```markdown
---
type: source
title: Fixed retry interval observation
status: processing
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
aliases: []
source_type: personal-observation
capture_method: asset
capture_mode: preserved-original
source_url: ""
inbox_source: null
author: ""
published: null
captured: YYYY-MM-DD
review_status: needs-review
reviewed: null
assets:
  - path: Assets/First cycle.txt
    media_type: text/plain
    role: primary
    sha256: 1992ea4fe993a56a5d965c84db14f2ceec44a37afa5c6eecddfc14f1cc20c135
    extraction_status: extracted
---

# Fixed retry interval observation

## Provenance

- Location: Assets/First cycle.txt
- Original URL:
- Accessed: YYYY-MM-DD
- Rights or sharing constraints: Synthetic Loreloom onboarding fixture; keep personal vault material private.

## Capture boundary

- Capture method: Exact local Asset bound in frontmatter.
- Capture mode: Preserved original synthetic one-line text Asset.
- Original evidence preserved: `Assets/First cycle.txt`, primary role, with the documented SHA-256.
- Verbatim material: The Key passage repeats line 1 exactly.
- Extracted or transcribed material: None
- Paraphrased material: None
- Unknown or unavailable evidence: None

## Assets

![[Assets/First cycle.txt]]

## Machine-assisted draft

None. This record transcribes the exact one-line synthetic Asset.

## Faithful summary

Fixed retry intervals can synchronize client attempts.

## Key passages

- “Fixed retry intervals can synchronize client attempts.” — line 1

## Amendments

None.

## Review checklist

- [ ] Title, origin, and dates verified
- [ ] Asset path and current SHA-256 verified
- [ ] Rights or sharing constraints recorded
- [ ] Capture method accurately describes how the content entered the vault
- [ ] Capture mode is supported by the preserved one-line Asset
- [ ] Original evidence availability is recorded
- [ ] Verbatim passage has the exact line locator
- [ ] Extracted or transcribed material is clearly labeled
- [ ] Paraphrased material is distinguished from evidence
- [ ] Unknown fidelity remains explicitly marked
- [ ] Transcription and summary verified against line 1
- [ ] Source is ready for human review
```

Run:

```sh
uv run --locked python scripts/validate_vault.py
```

**Expected:** a line beginning with `Vault validation passed:`. This proves schema and provenance validity only; it does not perform owner review.

### 4.3 Perform direct owner review

The owner—not an agent or script—must:

1. open `Assets/First cycle.txt` and compare it with the Source;
2. rerun the digest command from section 4.1;
3. verify every review-checklist item and change every box to `[x]`;
4. replace the four Source lifecycle fields with:

```yaml
status: captured
updated: YYYY-MM-DD
review_status: reviewed
reviewed: YYYY-MM-DD
```

Use the actual review date for `YYYY-MM-DD`. Run the validator again:

```sh
uv run --locked python scripts/validate_vault.py
```

**Expected:** a line beginning with `Vault validation passed:`. Stop on failure. No agent or script may make or attest this review transition.

### 4.4 Create the draft Concept

Create `Knowledge/Fixed retry intervals can synchronize clients.md`. Replace the date tokens, then paste the complete note:

```markdown
---
type: concept
title: Fixed retry intervals can synchronize clients
status: draft
created: YYYY-MM-DD
updated: YYYY-MM-DD
tags: []
aliases: []
confidence: medium
reviewed: null
sources:
  - "[[Sources/Fixed retry interval observation]]"
---

# Fixed retry intervals can synchronize clients

Fixed retry intervals can synchronize client attempts.

## Explanation

The reviewed Source records this as one synthetic personal observation.

## Implications and limits

- The Source provides no timing data, workload conditions, or comparison with other retry strategies.

## Related

- [[MOCs/Examples/Technology]]

## Sources

- [[Sources/Fixed retry interval observation]]
```

Agents may draft Concepts, but only the owner may approve a claim, citation, or promotion to `evergreen`.

### 4.5 Link the Technology MOC and inspect the result

Open `MOCs/Examples/Technology.md`, change its frontmatter `updated` date to today, and append:

```markdown
## Retry behavior

- [[Knowledge/Fixed retry intervals can synchronize clients]] records the Source claim about synchronized client attempts.
```

Run:

```sh
uv run --locked python scripts/validate_vault.py
git status --short
```

**Expected:** a line beginning with `Vault validation passed:`, and Git status includes these four cycle paths:

- `Assets/First cycle.txt`
- `Sources/Fixed retry interval observation.md`
- `Knowledge/Fixed retry intervals can synchronize clients.md`
- `MOCs/Examples/Technology.md`

Inspect and understand any additional tracked path before retaining or staging it; opening Obsidian may have normalized a setting. Inspect all four cycle paths before any commit. Do not stage everything blindly, and do not commit or push until you have reviewed the exact changes.

## 5. Personalize with one optional bootstrap prompt

Only after the manual cycle passes, send this copyable message to the root Codex session:

```text
Follow .agents/prompts/00-bootstrap-vault.md in read-only mode.
My explicitly chosen topics are: <replace with your topics>.
Do not infer any other personal facts or change files.
```

For later real evidence, the owner may invoke [`$capture-vault-source`](../.agents/skills/capture-vault-source/SKILL.md) for one exact input and processing Source output path, or [`$distill-vault-sources`](../.agents/skills/distill-vault-sources/SKILL.md) for one exact reviewed Source and draft Concept output path. These are alternatives to manual creation, not alternatives to direct owner Source review. Keep example notes until the first cycle works.

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
- [ ] Deterministic Asset has the expected SHA-256.
- [ ] Processing Source passes validation.
- [ ] The owner directly reviews the Source and current Asset bytes revalidate.
- [ ] One cited draft Concept exists.
- [ ] Technology MOC links the Concept.
- [ ] Final vault validation passes and Git status is understood.
