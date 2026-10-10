from __future__ import annotations
import ast
import contextlib
import hashlib
import io
import json
import os
import socket

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from scripts import validate_vault


class LocalToolExclusionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        self.original_root = validate_vault.ROOT
        validate_vault.ROOT = self.repo
        subprocess.run(
            ["git", "init", "-q", "-b", "master"],
            cwd=self.repo,
            check=True,
        )
        self.write(
            ".gitignore",
            "\n".join(
                (
                    ".agents/skills/sdd-*/",
                    ".codex/agents/reviewer.toml",
                    "",
                )
            ),
        )

    def tearDown(self) -> None:
        validate_vault.ROOT = self.original_root
        shutil.rmtree(self.repo)

    def write(self, relative_path: str, content: str) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def add_valid_repository_tooling(self) -> None:
        self.write(
            ".codex/config.toml",
            """
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[sandbox_workspace_write]
network_access = false

[agents]
max_depth = 1
max_threads = 4
""",
        )
        self.write(
            ".codex/agents/vault-reviewer.toml",
            """name = "vault-reviewer"
description = "Review bounded Loreloom changes"
sandbox_mode = "read-only"
approval_policy = "never"
developer_instructions = "Review only; never edit files."
""",
        )
        self.write(
            ".agents/skills/audit-vault-health/SKILL.md",
            """---
name: audit-vault-health
description: Audit a bounded Loreloom vault without changing any repository files.
---

# Audit vault health
""",
        )
        self.write(
            ".agents/skills/audit-vault-health/agents/openai.yaml",
            """interface:
  display_name: Audit vault health
  short_description: Review a bounded vault safely
  default_prompt: Use $audit-vault-health for this read-only audit.
""",
        )

    def test_ignored_sdd_tools_do_not_fail_repository_validation(self) -> None:
        self.add_valid_repository_tooling()
        self.write(
            ".codex/agents/reviewer.toml",
            """name = "reviewer"
description = "Third-party local reviewer"
developer_instructions = "May edit files."
sandbox_mode = "workspace-write"
approval_policy = "on-request"
""",
        )
        self.write(
            ".agents/skills/sdd-review/SKILL.md",
            """---
name: sdd-review
description: Third-party local review skill without Loreloom UI metadata.
---
""",
        )

        self.assertEqual(validate_vault.codex_agent_errors(), [])
        self.assertEqual(validate_vault.skill_errors(), [])
        self.assertEqual(
            [path.name for path in validate_vault.custom_agent_paths()],
            ["vault-reviewer.toml"],
        )
        self.assertEqual(
            [path.name for path in validate_vault.repository_skill_dirs()],
            ["audit-vault-health"],
        )

    def test_nonignored_tools_remain_strictly_validated(self) -> None:
        self.add_valid_repository_tooling()
        self.write(
            ".codex/agents/unsafe-local.toml",
            """name = "unsafe-local"
description = "Unsafe repository agent"
developer_instructions = "May edit files."
sandbox_mode = "workspace-write"
approval_policy = "on-request"
""",
        )
        self.write(
            ".agents/skills/unsafe-local/SKILL.md",
            """---
name: unsafe-local
description: Repository skill intentionally missing required user-interface metadata.
---
""",
        )

        agent_errors = validate_vault.codex_agent_errors()
        skill_errors = validate_vault.skill_errors()
        self.assertTrue(
            any("unsafe-local.toml: custom vault agents" in error for error in agent_errors)
        )
        self.assertTrue(
            any("unsafe-local: missing agents/openai.yaml" in error for error in skill_errors)
        )


class AssetValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        self.original_root = validate_vault.ROOT
        validate_vault.ROOT = self.repo
        (self.repo / "schemas").mkdir(parents=True)
        shutil.copy2(
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "frontmatter.schema.json",
            self.repo / "schemas" / "frontmatter.schema.json",
        )

    def tearDown(self) -> None:
        validate_vault.ROOT = self.original_root
        shutil.rmtree(self.repo)

    def write(self, relative_path: str, content: str) -> Path:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def write_source(self, content: str) -> Path:
        return self.write("Sources/report.md", content)

    def valid_source(self, asset_hash: str | None = None) -> str:
        digest = asset_hash or "a" * 64
        return f"""---
type: source
title: report
status: processing
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
source_type: other
capture_method: asset
capture_mode: preserved-original
source_url: ""
author: ""
published: null
captured: 2026-07-18
review_status: needs-review
reviewed: null
assets:
  - path: Assets/report.pdf
    media_type: application/pdf
    role: primary
    sha256: {digest}
    extraction_status: extracted
---

# report

![[Assets/report.pdf]]
"""

    def url_source(self, url: str, body: str = "# report\n") -> str:
        return f"""---
type: source
title: report
status: processing
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
source_type: other
capture_method: url-reference
capture_mode: reference-only
source_url: "{url}"
author: ""
published: null
captured: 2026-07-18
review_status: needs-review
reviewed: null
assets: []
---

{body}
"""

    def test_copied_source_template_ignores_fenced_placeholders(self) -> None:
        source = self.write_source(
            self.url_source(
                "https://example.com/report",
                """# report

```md
![[Assets/example.pdf]]
[[Knowledge/Example concept]]
```

   ~~~~
[[Missing note]]
   ~~~~
""",
            )
        )

        errors = validate_vault.embedded_asset_errors([source])
        errors.extend(validate_vault.wikilink_errors([source]))

        self.assertEqual(errors, [])

    def test_invalid_backtick_fence_does_not_mask_live_links(self) -> None:
        source = self.write_source(
            self.url_source(
                "https://example.com/report",
                "# report\n\n``` `invalid`\n[[Missing note]]\n```\n",
            )
        )

        errors = validate_vault.wikilink_errors([source])

        self.assertTrue(any("unresolved wikilink" in error for error in errors), errors)

    def test_http_source_urls_satisfy_provenance(self) -> None:
        urls = (
            "http://example.com",
            "HTTPS://user:pass@localhost:8443/report?q=1#section",
            "https://127.0.0.1/report",
            "https://[::1]:8443/report",
            "https://example.com:99999/report",
        )
        for url in urls:
            with self.subTest(url=url):
                source = self.write_source(self.url_source(url))
                self.assertEqual(validate_vault.schema_errors([source]), [])

    def test_non_http_and_malformed_source_urls_are_rejected(self) -> None:
        urls = (
            "https:///report",
            "https://",
            "ftp://example.com/report",
            "file:///tmp/report",
            "mailto:owner@example.com",
            "custom:report",
            "relative/report",
            "https://example.com/white space",
            "https://example.com:",
            "https://user@@example.com",
        )
        for url in urls:
            with self.subTest(url=url):
                source = self.write_source(self.url_source(url))
                errors = validate_vault.schema_errors([source])
                self.assertTrue(
                    any(": source_url:" in error for error in errors),
                    errors,
                )
                self.assertTrue(
                    any(
                        "traceable non-empty URL, existing Asset, or Inbox" in error
                        for error in errors
                    ),
                    errors,
                )

    def test_markdown_assets_are_not_note_scanned(self) -> None:
        readme = self.write("Assets/README.md", "# Asset documentation\n")
        untrusted = self.write(
            "Assets/untrusted.md",
            "# Captured data\n\n[[Missing note]]\n",
        )

        note_paths = validate_vault.all_note_paths()

        self.assertIn(readme, note_paths)
        self.assertNotIn(untrusted, note_paths)
        self.assertEqual(validate_vault.wikilink_errors(note_paths), [])

    def test_source_asset_reference_requires_metadata_binding(self) -> None:
        self.write("Assets/report.pdf", "report")
        source = self.write_source(
            self.url_source(
                "https://example.com/report",
                "# report\n\n![[Assets/report.pdf]]\n",
            )
        )

        errors = validate_vault.embedded_asset_errors([source])

        self.assertTrue(
            any(
                "Source Asset reference 'Assets/report.pdf' is not declared in assets"
                in error
                for error in errors
            ),
            errors,
        )

    def test_markdown_asset_reference_preserves_extension(self) -> None:
        asset = self.repo / "Assets" / "report.md"
        asset.parent.mkdir(parents=True)
        asset.write_text("# captured Markdown\n", encoding="utf-8")
        source = self.write_source(
            self.valid_source(hashlib.sha256(asset.read_bytes()).hexdigest())
            .replace("Assets/report.pdf", "Assets/report.md")
            .replace("application/pdf", "text/markdown")
        )

        self.assertEqual(validate_vault.embedded_asset_errors([source]), [])

    def test_asset_references_support_space_containing_paths(self) -> None:
        asset = self.repo / "Assets" / "report file.pdf"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"%PDF-1.7\nreport\n")
        references = """![[Assets/report file.pdf]]
[[Assets/report file.pdf]]
[report](<Assets/report file.pdf>)
[report](Assets/report%20file.pdf)"""
        source = self.write_source(
            self.valid_source(hashlib.sha256(asset.read_bytes()).hexdigest())
            .replace("Assets/report.pdf", "Assets/report file.pdf")
            .replace("![[Assets/report file.pdf]]", references)
        )

        errors = validate_vault.embedded_asset_errors([source])
        errors.extend(validate_vault.wikilink_errors([source]))

        self.assertEqual(errors, [])

    def test_concept_requires_owner_reviewed_source(self) -> None:
        self.write_source(self.url_source("https://example.com/report"))
        concept = self.write(
            "Knowledge/concept.md",
            """---
type: concept
title: concept
status: draft
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
confidence: medium
reviewed: null
sources:
  - "[[Sources/report]]"
---

# concept
""",
        )

        errors = validate_vault.schema_errors([concept])

        self.assertTrue(
            any(
                "Concept source must be owner-reviewed before use "
                "(found '[[Sources/report]]')"
                in error
                for error in errors
            ),
            errors,
        )

    def test_concept_allows_owner_reviewed_source(self) -> None:
        self.write_source(
            self.url_source("https://example.com/report")
            .replace("status: processing", "status: captured")
            .replace("review_status: needs-review", "review_status: reviewed")
            .replace("reviewed: null", "reviewed: 2026-07-19")
        )
        concept = self.write(
            "Knowledge/concept.md",
            """---
type: concept
title: concept
status: draft
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
confidence: medium
reviewed: null
sources:
  - "[[Sources/report]]"
---

# concept
""",
        )

        self.assertEqual(validate_vault.schema_errors([concept]), [])

    def test_bound_asset_drift_fails_even_with_url_provenance(self) -> None:
        asset = self.repo / "Assets" / "report.pdf"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"original")
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        source = self.write_source(
            self.valid_source(digest).replace(
                'source_url: ""',
                'source_url: "https://example.com/report"',
            )
        )
        asset.write_bytes(b"changed")

        errors = validate_vault.asset_metadata_errors([source])

        self.assertTrue(any("asset SHA-256 mismatch" in error for error in errors), errors)

    def test_daily_concept_source_remains_allowed(self) -> None:
        daily = self.write(
            "Daily/2026-07-18.md",
            """---
type: daily
title: 2026-07-18
status: captured
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
date: 2026-07-18
---

# 2026-07-18
""",
        )
        concept = self.write(
            "Knowledge/concept.md",
            """---
type: concept
title: concept
status: draft
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
confidence: medium
reviewed: null
sources:
  - "[[Daily/2026-07-18]]"
---

# concept
""",
        )

        self.assertEqual(validate_vault.schema_errors([daily, concept]), [])

    def test_valid_processing_source_and_asset_pass(self) -> None:
        asset = self.repo / "Assets" / "report.pdf"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"%PDF-1.7\nreport\n")
        source = self.write_source(
            self.valid_source(hashlib.sha256(asset.read_bytes()).hexdigest())
        )

        errors = validate_vault.schema_errors([source])
        errors.extend(validate_vault.asset_metadata_errors([source]))
        errors.extend(validate_vault.embedded_asset_errors([source]))

        self.assertEqual(errors, [])

    def test_source_requires_traceable_provenance(self) -> None:
        source = self.write_source(
            """---
type: source
title: report
status: processing
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
source_type: other
capture_method: manual-entry
capture_mode: unknown
source_url: ""
author: ""
published: null
captured: 2026-07-18
review_status: needs-review
reviewed: null
assets: []
---

# report
"""
        )

        errors = validate_vault.schema_errors([source])

        self.assertTrue(any("traceable non-empty URL, existing Asset, or Inbox" in error for error in errors))

    def test_invalid_url_does_not_satisfy_source_provenance(self) -> None:
        source = self.write_source(
            self.valid_source().replace('source_url: ""', "source_url: not-a-url")
        )

        errors = validate_vault.schema_errors([source])

        self.assertTrue(
            any(
                "traceable non-empty URL, existing Asset, or Inbox" in error
                for error in errors
            )
        )

    def test_missing_inbox_provenance_is_reported(self) -> None:
        source = self.write_source(
            self.valid_source()
            .replace('source_url: ""', 'source_url: ""\ninbox_source: "[[Inbox/missing]]"')
            .replace(
                "  - path: Assets/report.pdf\n"
                "    media_type: application/pdf\n"
                "    role: primary\n"
                "    sha256: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\n"
                "    extraction_status: extracted\n",
                "",
            )
        )

        errors = validate_vault.schema_errors([source])

        self.assertTrue(
            any("inbox_source must resolve to an existing Inbox" in error for error in errors)
        )

    def test_asset_hash_mismatch_does_not_satisfy_source_provenance(self) -> None:
        asset = self.repo / "Assets" / "report.pdf"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"%PDF-1.7\nreport\n")
        source = self.write_source(self.valid_source("a" * 64))

        errors = validate_vault.schema_errors([source])

        self.assertTrue(
            any(
                "traceable non-empty URL, existing Asset, or Inbox" in error
                for error in errors
            )
        )

    def test_inbox_provenance_satisfies_source_requirement(self) -> None:
        self.write("Inbox/capture.md", "# Capture\n")
        source = self.write_source(
            """---
type: source
title: report
status: processing
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
source_type: other
capture_method: manual-entry
capture_mode: unknown
source_url: ""
inbox_source: "[[Inbox/capture]]"
author: ""
published: null
captured: 2026-07-18
review_status: needs-review
reviewed: null
assets: []
---

# report
"""
        )

        errors = validate_vault.schema_errors([source])

        self.assertEqual(errors, [])

    def test_duplicate_asset_path_is_reported(self) -> None:
        asset = self.repo / "Assets" / "report.pdf"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"%PDF-1.7\nreport\n")
        digest = hashlib.sha256(asset.read_bytes()).hexdigest()
        source = self.write_source(
            self.valid_source(digest).replace(
                "    extraction_status: extracted",
                "    extraction_status: extracted\n"
                "  - path: Assets/report.pdf\n"
                "    media_type: application/pdf\n"
                "    role: supporting\n"
                f"    sha256: {digest}\n"
                "    extraction_status: extracted",
                1,
            )
        )

        errors = validate_vault.asset_metadata_errors([source])

        self.assertTrue(any("duplicate asset path" in error for error in errors))

    def test_readable_asset_requires_sha256(self) -> None:
        asset = self.repo / "Assets" / "report.pdf"
        asset.parent.mkdir(parents=True)
        asset.write_bytes(b"%PDF-1.7\nreport\n")
        source = self.write_source(self.valid_source("null"))

        errors = validate_vault.asset_metadata_errors([source])
        schema_errors = validate_vault.schema_errors([source])

        self.assertTrue(
            any("SHA-256 is required for readable asset" in error for error in errors)
        )
        self.assertTrue(any("sha256" in error for error in schema_errors))

    def test_asset_hashing_streams_files(self) -> None:
        asset = self.repo / "Assets" / "report.pdf"
        asset.parent.mkdir(parents=True)
        content = b"report" * 200_000
        asset.write_bytes(content)

        with mock.patch.object(Path, "read_bytes", side_effect=AssertionError):
            digest = validate_vault.file_sha256(asset)

        self.assertEqual(digest, hashlib.sha256(content).hexdigest())

    def test_missing_asset_and_embed_are_reported(self) -> None:
        source = self.write_source(self.valid_source())

        metadata_errors = validate_vault.asset_metadata_errors([source])
        embed_errors = validate_vault.embedded_asset_errors([source])

        self.assertTrue(any("missing asset" in error for error in metadata_errors))
        self.assertTrue(any("missing asset" in error for error in embed_errors))

    def test_source_review_state_mismatch_is_reported(self) -> None:
        source = self.write_source(
            self.valid_source().replace(
                "review_status: needs-review\nreviewed: null",
                "review_status: reviewed\nreviewed: null",
            )
        )

        errors = validate_vault.schema_errors([source])

        self.assertTrue(
            any("Source review state is inconsistent" in error for error in errors)
        )

    def test_unsafe_asset_path_is_reported(self) -> None:
        source = self.write_source(
            self.valid_source().replace("Assets/report.pdf", "../outside.pdf")
        )

        errors = validate_vault.asset_metadata_errors([source])

        self.assertTrue(any("unsafe asset path" in error for error in errors))


class CaptureFidelityValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        self.original_root = validate_vault.ROOT
        validate_vault.ROOT = self.repo
        (self.repo / "schemas").mkdir(parents=True)
        shutil.copy2(
            Path(__file__).resolve().parents[1]
            / "schemas"
            / "frontmatter.schema.json",
            self.repo / "schemas" / "frontmatter.schema.json",
        )

    def tearDown(self) -> None:
        validate_vault.ROOT = self.original_root
        shutil.rmtree(self.repo)

    def write(self, relative_path: str, content: str) -> Path:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def metadata(self, method: str, mode: str, **overrides: object) -> dict[str, object]:
        metadata: dict[str, object] = {
            "type": "source",
            "source_type": "other",
            "source_url": "https://example.com/evidence",
            "capture_method": method,
            "capture_mode": mode,
            "assets": [],
        }
        metadata.update(overrides)
        return metadata

    def boundary(self, **values: str) -> str:
        defaults = {
            "Capture method": "Recorded route.",
            "Capture mode": "Recorded representation.",
            "Original evidence preserved": "None",
            "Verbatim material": "None",
            "Extracted or transcribed material": "None",
            "Paraphrased material": "None",
            "Unknown or unavailable evidence": "None",
        }
        defaults.update(values)
        return "## Capture boundary\n\n" + "\n".join(
            f"- {label}: {defaults[label]}"
            for label in validate_vault.CAPTURE_BOUNDARY_LABELS
        )

    def fidelity_errors(
        self, metadata: dict[str, object], body: str = ""
    ) -> list[str]:
        return validate_vault.source_capture_fidelity_errors(
            self.repo / "Sources" / "evidence.md", metadata, body
        )

    def test_valid_capture_method_and_mode_contracts(self) -> None:
        primary = {
            "path": "Assets/evidence.pdf",
            "media_type": "application/pdf",
            "role": "primary",
            "sha256": "a" * 64,
            "extraction_status": "extracted",
        }
        audio = {
            **primary,
            "path": "Assets/evidence.wav",
            "media_type": "audio/wav",
        }
        extracted_boundary = self.boundary(
            **{"Extracted or transcribed material": "Parser output from the primary Asset."}
        )
        mixed_boundary = self.boundary(
            **{
                "Original evidence preserved": "Primary Asset bytes.",
                "Paraphrased material": "Summary paragraph.",
            }
        )
        cases = (
            (
                self.metadata(
                    "manual-entry",
                    "unknown",
                    source_url="",
                    inbox_source="[[Inbox/capture]]",
                ),
                "",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "The summary is owner-declared paraphrase."}
                ),
            ),
            (self.metadata("asset", "preserved-original", assets=[primary]), ""),
            (self.metadata("url-reference", "reference-only"), ""),
            (
                self.metadata("file-extraction", "extracted", assets=[primary]),
                extracted_boundary,
            ),
            (
                self.metadata("transcription", "transcribed", assets=[audio]),
                extracted_boundary
                + '\n\n## Key passages\n\n- “Spoken words.” — timestamp 00:00:04',
            ),
            (
                self.metadata(
                    "transcription",
                    "transcribed",
                    source_type="video",
                ),
                extracted_boundary
                + '\n\n## Key passages\n\n- “Spoken words.” — timestamp 00:00:04',
            ),
            (
                self.metadata(
                    "manual-entry",
                    "firsthand-observation",
                    source_type="personal-observation",
                ),
                "",
            ),
            (self.metadata("mixed", "mixed"), mixed_boundary),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                '## Key passages\n\n- “Exact words.” — page 12',
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                '## Key passages\n\n* “Exact star item.” — line 12',
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                '## Key passages\n\n1. “Exact ordered item.” — section Abstract',
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "- “Visible passage\n"
                "  ``` `not-a-fence`\n"
                "  continued.” — page 1",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "> - “Exact blockquoted item.” — page 12",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "## Capture boundary\n\n"
                + "\n".join(
                    f"- \n  2. {label}: concrete value"
                    for label in validate_vault.CAPTURE_BOUNDARY_LABELS
                ),
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "## Capture boundary\n\n"
                + "\n".join(
                    f"- preface\n  ### context\n  2. {label}: concrete value"
                    for label in validate_vault.CAPTURE_BOUNDARY_LABELS
                ),
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "## Capture boundary\n\n"
                + "\n".join(
                    f"- preface\n  >   2. {label}: concrete value"
                    for label in validate_vault.CAPTURE_BOUNDARY_LABELS
                ),
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "intro\n"
                "> 2. “Exact wording in a new quote.” — page 12",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "Owner-declared summary."}
                )
                + "\n\n## Key passages\n\n"
                '- <span title="context">Owner summary.</span> — page 1',
            ),
        )
        for metadata, body in cases:
            with self.subTest(
                method=metadata["capture_method"], mode=metadata["capture_mode"]
            ):
                self.assertEqual(self.fidelity_errors(metadata, body), [])

    def test_multiline_capture_boundary_value_is_accepted(self) -> None:
        base = self.boundary(
            **{"Paraphrased material": "Owner-declared summary."}
        )
        bodies = (
            base.replace(
                "- Paraphrased material: Owner-declared summary.",
                "- Paraphrased material:\n  Owner-declared summary.",
            ),
            base.replace(
                "- Paraphrased material: Owner-declared summary.",
                "- Paraphrased material:\nOwner-declared summary.",
            ),
        )

        for body in bodies:
            with self.subTest(body=body):
                self.assertEqual(
                    self.fidelity_errors(
                        self.metadata("manual-entry", "paraphrased"),
                        body,
                    ),
                    [],
                )

    def test_multiline_quoted_passages_are_checked(self) -> None:
        cases = (
            (
                self.metadata(
                    "transcription",
                    "transcribed",
                    source_type="video",
                ),
                self.boundary(
                    **{"Extracted or transcribed material": "Typed transcript."}
                )
                + "\n\n## Key passages\n\n"
                "- “Quoted transcript\n"
                "  continuation.” — page 7",
                "require a timestamp locator",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "Owner-declared summary."}
                )
                + "\n\n## Key passages\n\n"
                "- “Quoted summary\n"
                "  continuation.” — page 7",
                "must not use quoted Key passages",
            ),
            (
                self.metadata(
                    "transcription",
                    "transcribed",
                    source_type="video",
                ),
                self.boundary(
                    **{"Extracted or transcribed material": "Typed transcript."}
                )
                + "\n\n## Key passages\n\n"
                "- “Lazy transcript\n"
                "continuation.” — page 8",
                "require a timestamp locator",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "Owner-declared summary."}
                )
                + "\n\n## Key passages\n\n"
                "- “Lazy summary\n"
                "continuation.” — page 8",
                "must not use quoted Key passages",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "Owner-declared summary."}
                )
                + "\n\n## Key passages\n\n"
                "- &quot;Quoted summary.&quot; — page 1",
                "must not use quoted Key passages",
            ),
        )
        for metadata, body, expected in cases:
            with self.subTest(mode=metadata["capture_mode"]):
                errors = self.fidelity_errors(metadata, body)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_html_and_fence_states_do_not_interfere(self) -> None:
        body = (
            "<script>\n"
            "```\n"
            "</script>\n"
            "```\n"
            "inside fenced code\n"
            "```\n"
            "## Key passages\n\n"
            "- “Visible evidence.” — page 3"
        )

        self.assertEqual(
            self.fidelity_errors(
                self.metadata("manual-entry", "verbatim-excerpt"),
                body,
            ),
            [],
        )
        paragraph_body = (
            "intro\n"
            "<custom-element>\n"
            "## Key passages\n\n"
            "- “Visible after paragraph HTML.” — page 4"
        )
        self.assertEqual(
            self.fidelity_errors(
                self.metadata("manual-entry", "verbatim-excerpt"),
                paragraph_body,
            ),
            [],
        )

        for list_body in (
            "intro\n"
            "2. continuation\n"
            "<custom-element>\n"
            "## Key passages\n\n"
            "- “Visible after ordered marker.” — page 5",
            "- intro\n"
            "<custom-element>\n"
            "## Key passages\n\n"
            "- “Visible after list paragraph.” — page 6",
            "intro\n"
            "2. <script>\n"
            "## Key passages\n\n"
            "- “Visible after noninterrupting marker.” — page 7",
        ):
            with self.subTest(list_body=list_body):
                self.assertEqual(
                    self.fidelity_errors(
                        self.metadata("manual-entry", "verbatim-excerpt"),
                        list_body,
                    ),
                    [],
                )

    def test_invalid_capture_prerequisites_fail_closed(self) -> None:
        primary_not_extracted = {
            "path": "Assets/evidence.pdf",
            "media_type": "application/pdf",
            "role": "supporting",
            "sha256": "a" * 64,
            "extraction_status": "not-requested",
        }
        cases = (
            (self.metadata("asset", "unknown"), "", "requires a declared Asset"),
            (
                self.metadata("url-reference", "unknown", source_url=""),
                "",
                "requires a valid source_url",
            ),
            (
                self.metadata(
                    "asset",
                    "preserved-original",
                    assets=[primary_not_extracted],
                ),
                "",
                "requires a primary Asset",
            ),
            (
                self.metadata("file-extraction", "extracted", assets=[]),
                self.boundary(
                    **{
                        "Extracted or transcribed material": "Parser output was declared."
                    }
                ),
                "requires an extracted or partial Asset",
            ),
            (
                self.metadata(
                    "file-extraction",
                    "extracted",
                    assets=[primary_not_extracted],
                ),
                "",
                "requires an extracted or partial Asset",
            ),
            (
                self.metadata("ocr", "unknown", assets=[primary_not_extracted]),
                "",
                "Extracted or transcribed material",
            ),
            (
                self.metadata("transcription", "transcribed"),
                self.boundary(
                    **{"Extracted or transcribed material": "Typed transcript."}
                ),
                "requires audio/video provenance",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "## Capture boundary\n\n"
                + "\n".join(
                    f"> preface\n2. {label}: concrete value"
                    for label in validate_vault.CAPTURE_BOUNDARY_LABELS
                ),
                "requires all exact Capture Boundary labels",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "## Capture boundary\n\n"
                + "\n".join(
                    f"> - preface\n  2. {label}: concrete value"
                    for label in validate_vault.CAPTURE_BOUNDARY_LABELS
                ),
                "requires all exact Capture Boundary labels",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(**{"Paraphrased material": "**None**"}),
                "Paraphrased material",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "## Capture boundary\n\n"
                + "\n".join(
                    f"- preface\n  2. {label}: concrete value"
                    for label in validate_vault.CAPTURE_BOUNDARY_LABELS
                ),
                "requires all exact Capture Boundary labels",
            ),
            (
                self.metadata("manual-entry", "preserved-original"),
                "",
                "requires a primary Asset",
            ),
            (
                self.metadata("manual-entry", "reference-only", source_url=""),
                "",
                "requires a valid source_url",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "```md\n## Key passages\n- “Fake.” — page 1\n```",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "transcribed"),
                self.boundary(
                    **{"Extracted or transcribed material": "Typed transcript."}
                )
                + '\n\n## Key passages\n\n- “No locator.” — page 2',
                "requires audio/video provenance",
            ),
            (
                self.metadata(
                    "transcription",
                    "transcribed",
                    source_type="podcast",
                ),
                self.boundary(
                    **{"Extracted or transcribed material": "Typed transcript."}
                )
                + '\n\n## Key passages\n\n- “No timestamp.” — section opening',
                "require a timestamp locator",
            ),
            (
                self.metadata("manual-entry", "firsthand-observation"),
                "",
                "requires source_type 'personal-observation'",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary()
                + '\n\n## Key passages\n\n- “Quotation laundering.” — page 1',
                "requires a non-empty Paraphrased material",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "## Capture boundary\n\n"
                "- Paraphrased material: Owner-declared summary.",
                "requires all exact Capture Boundary labels",
            ),
            (
                self.metadata("mixed", "mixed"),
                self.boundary(
                    **{"Original evidence preserved": "One concrete category."}
                ),
                "requires at least two concrete Capture Boundary entries",
            ),
        )
        for metadata, body, expected in cases:
            with self.subTest(
                method=metadata["capture_method"], mode=metadata["capture_mode"]
            ):
                errors = self.fidelity_errors(metadata, body)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_hidden_sections_and_placeholder_locators_fail_closed(self) -> None:
        cases = (
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "---\nnotes: |\n  ## Key passages\n  - “Fake.” — page 1\n---\n",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "    ## Key passages\n\n    - “Fake.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n    - “Fake.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<!--\n## Key passages\n- “Fake.” — page 1\n-->",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<script>\n"
                "## Key passages\n"
                "- “Hidden.” — page 1\n"
                "</script>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<div>\n"
                "## Key passages\n"
                "- “Hidden.” — page 1\n"
                "</div>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<script>\n"
                "## Key passages\n"
                "- “Hidden through EOF.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                "<div>\n"
                + self.boundary(
                    **{"Paraphrased material": "Hidden owner summary."}
                )
                + "\n</div>",
                "requires all exact Capture Boundary labels",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<?processor\n"
                "## Key passages\n"
                "- “Hidden.” — page 1\n"
                "?>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<!DECLARATION\n"
                "## Key passages\n"
                "- “Hidden.” — page 1\n"
                ">",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<![CDATA[\n"
                "## Key passages\n"
                "- “Hidden.” — page 1\n"
                "]]>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "<custom-element>\n"
                "## Key passages\n"
                "- “Hidden.” — page 1\n"
                "</custom-element>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "Title\n"
                "===\n"
                "<custom-element>\n"
                "## Key passages\n"
                "- “Hidden after Setext.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                '<custom title=">">\n'
                "## Key passages\n"
                "- “Hidden by quoted attribute.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n"
                "  - context\n"
                "    ```\n"
                "    “Hidden in nested fence.” — page 1\n"
                "    ```",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "- <script>\n"
                "  “Hidden item evidence.” — page 1\n"
                "  </script>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "- intro\n"
                "    <div>\n"
                "  ## Key passages\n"
                "  - “Hidden in nested HTML.” — page 1\n"
                "    </div>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "- intro\n"
                "    ```\n"
                "  ## Key passages\n"
                "  - “Hidden in list fence.” — page 1\n"
                "    ```",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "- intro\n"
                "\t<div>\n"
                "  ## Key passages\n"
                "  - “Hidden in tabbed HTML.” — page 1\n"
                "\t</div>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "- intro\n"
                "\t```\n"
                "  ## Key passages\n"
                "  - “Hidden in tabbed fence.” — page 1\n"
                "\t```",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "intro\n"
                "01. <script>\n"
                "    “Hidden after zero-padded marker.” — page 1\n"
                "    </script>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "- context\n\n"
                "\t\t“Hidden in indented code.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "- ### context\n"
                "“Outside item.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "- context\n"
                "> “Outside block quote.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "intro\n"
                "2. “Not a list item.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "- context\n\n"
                "      first code line\n"
                "      “Hidden later code.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "-     first code line\n"
                "      “Hidden after marker-line code.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "-     “Hidden first-line code.” — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "- **<excerpt>** — page **<page>**",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n"
                "- “Visible quotation.” <!-- — page 1 -->",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata(
                    "transcription",
                    "transcribed",
                    source_type="video",
                ),
                self.boundary(
                    **{"Extracted or transcribed material": "Typed transcript."}
                )
                + "\n\n## Key passages\n\n"
                "- “Visible quotation.” <!-- — timestamp 00:01 -->",
                "require a timestamp locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n- “Fake.” fake-page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n- “Fake.” — page <page>",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n- — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n- <excerpt> — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n- — — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata("manual-entry", "verbatim-excerpt"),
                "## Key passages\n\n- ... — page 1",
                "requires an exact Key passages locator",
            ),
            (
                self.metadata(
                    "transcription",
                    "transcribed",
                    source_type="video",
                ),
                self.boundary(
                    **{"Extracted or transcribed material": "Typed transcript."}
                )
                + "\n\n## Key passages\n\n"
                '- “Fake.” — timestamp {{timestamp}}',
                "require a timestamp locator",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary().replace(
                    "- Paraphrased material: None",
                    "- Paraphrased material: <!--\n"
                    "  add a substantive explanation\n"
                    "  -->",
                ),
                "requires a non-empty Paraphrased material",
            ),
            (
                self.metadata("manual-entry", "paraphrased"),
                self.boundary(
                    **{"Paraphrased material": "Owner-declared summary."}
                ).replace("\n-", "\n    -"),
                "requires all exact Capture Boundary labels",
            ),
        )
        for metadata, body, expected in cases:
            with self.subTest(body=body):
                errors = self.fidelity_errors(metadata, body)
                self.assertTrue(any(expected in error for error in errors), errors)

    def test_missing_fields_and_invalid_enums_are_reported(self) -> None:
        metadata = self.metadata("manual-entry", "unknown")
        del metadata["capture_method"]
        del metadata["capture_mode"]
        errors = self.fidelity_errors(metadata)
        self.assertIn(
            "Source missing required capture classification field(s): "
            "capture_method, capture_mode; classify manually (no value was inferred)",
            errors,
        )

        self.write("Inbox/capture.md", "# capture\n")
        source = self.write(
            "Sources/evidence.md",
            """---
type: source
title: evidence
status: processing
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
source_type: other
capture_method: invented
capture_mode: synthetic
source_url: ""
inbox_source: "[[Inbox/capture]]"
author: ""
published: null
captured: 2026-07-18
review_status: needs-review
reviewed: null
assets: []
---

# evidence
""",
        )
        schema_errors = validate_vault.schema_errors([source])
        self.assertTrue(any("capture_method" in error for error in schema_errors))
        self.assertTrue(any("capture_mode" in error for error in schema_errors))

    def reviewed_source(self, mode: str, title: str) -> str:
        return f"""---
type: source
title: {title}
status: captured
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
source_type: other
capture_method: url-reference
capture_mode: {mode}
source_url: "https://example.com/{title}"
author: ""
published: null
captured: 2026-07-18
review_status: reviewed
reviewed: 2026-07-18
assets: []
---

# {title}
"""

    def concept(self, status: str, sources: list[str], limitation: str = "") -> str:
        reviewed = "2026-07-18" if status == "evergreen" else "null"
        links = "\n".join(f'  - "{source}"' for source in sources)
        limitation_section = (
            f"\n## Evidence limitations\n\n{limitation}\n" if limitation else ""
        )
        return f"""---
type: concept
title: claim
status: {status}
created: 2026-07-18
updated: 2026-07-18
tags: []
aliases: []
confidence: low
reviewed: {reviewed}
sources:
{links}
---

# claim
{limitation_section}"""

    def test_placeholder_limitations_do_not_suppress_warnings(self) -> None:
        weak = self.write(
            "Sources/weak.md", self.reviewed_source("unknown", "weak")
        )
        draft = self.write(
            "Knowledge/claim.md",
            self.concept("draft", ["[[Sources/weak]]"]),
        )
        contents = (
            self.concept("draft", ["[[Sources/weak]]"], "-"),
            self.concept(
                "draft",
                ["[[Sources/weak]]"],
                "- <!-- limitation -->",
            ),
            self.concept(
                "draft",
                ["[[Sources/weak]]"],
                "*<!--\nhidden limitation text\n-->",
            ),
            self.concept(
                "draft",
                ["[[Sources/weak]]"],
                "    Hidden in an indented code block.",
            ),
            self.concept(
                "draft",
                ["[[Sources/weak]]"],
                "-     Hidden code on the marker line.",
            ),
            self.concept(
                "draft",
                ["[[Sources/weak]]"],
                "<span></span>",
            ),
            self.concept(
                "draft",
                ["[[Sources/weak]]"],
                "[]()",
            ),
            *(
                self.concept("draft", ["[[Sources/weak]]"], limitation)
                for limitation in (
                    "---",
                    "***",
                    "___",
                    ">",
                    "> <!-- limitation -->",
                    "- [ ]",
                )
            ),
            self.concept("draft", ["[[Sources/weak]]"]).replace(
                "sources:\n",
                "notes: |\n"
                "  ## Evidence limitations\n"
                "  - Hidden in frontmatter.\n"
                "sources:\n",
            ),
        )
        for content in contents:
            with self.subTest(content=content):
                draft.write_text(content, encoding="utf-8")
                warnings = validate_vault.concept_capture_fidelity_warnings(
                    [weak, draft]
                )
                self.assertTrue(
                    any("Concept cites unknown" in warning for warning in warnings),
                    warnings,
                )

    def test_low_fidelity_concept_warnings_and_suppression(self) -> None:
        weak = self.write(
            "Sources/weak.md", self.reviewed_source("unknown", "weak")
        )
        strong = self.write(
            "Sources/strong.md", self.reviewed_source("verbatim-excerpt", "strong")
        )
        draft = self.write(
            "Knowledge/claim.md",
            self.concept("draft", ["[[Sources/weak]]"]),
        )
        warnings = validate_vault.concept_capture_fidelity_warnings(
            [weak, strong, draft]
        )
        self.assertTrue(any("Concept cites unknown" in warning for warning in warnings))

        draft.write_text(
            self.concept("draft", ["[[Sources/strong]]"]), encoding="utf-8"
        )
        self.assertEqual(
            validate_vault.concept_capture_fidelity_warnings([weak, strong, draft]),
            [],
        )

        draft.write_text(
            self.concept(
                "draft",
                ["[[Sources/weak]]"],
                "Capture fidelity is unknown; the original was not revalidated.",
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            validate_vault.concept_capture_fidelity_warnings([weak, strong, draft]),
            [],
        )

        for limitation in (
            "> Capture fidelity remains unknown.",
            "- [ ] Revalidate the original evidence before relying on exact wording.",
            "- \n    Actual visible limitation.",
        ):
            with self.subTest(limitation=limitation):
                draft.write_text(
                    self.concept(
                        "draft",
                        ["[[Sources/weak]]"],
                        limitation,
                    ),
                    encoding="utf-8",
                )
                self.assertEqual(
                    validate_vault.concept_capture_fidelity_warnings(
                        [weak, strong, draft]
                    ),
                    [],
                )

        draft.write_text(
            self.concept("evergreen", ["[[Sources/weak]]"]), encoding="utf-8"
        )
        warnings = validate_vault.concept_capture_fidelity_warnings(
            [weak, strong, draft]
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("relies exclusively", warnings[0])

        draft.write_text(
            self.concept(
                "evergreen",
                ["[[Sources/weak]]", "[[Sources/strong]]"],
            ),
            encoding="utf-8",
        )
        warnings = validate_vault.concept_capture_fidelity_warnings(
            [weak, strong, draft]
        )
        self.assertEqual(len(warnings), 1)
        self.assertIn("Concept cites unknown", warnings[0])
        self.assertNotIn("relies exclusively", warnings[0])

        daily = self.write(
            "Daily/2026-07-18.md",
            "---\ntype: daily\ntitle: 2026-07-18\nstatus: captured\n"
            "created: 2026-07-18\nupdated: 2026-07-18\ntags: []\n"
            "aliases: []\ndate: 2026-07-18\n---\n",
        )
        draft.write_text(
            self.concept(
                "evergreen",
                ["[[Sources/weak]]", "[[Daily/2026-07-18]]"],
            ),
            encoding="utf-8",
        )
        warnings = validate_vault.concept_capture_fidelity_warnings(
            [weak, strong, daily, draft]
        )
        self.assertEqual(len(warnings), 1)
        self.assertNotIn("relies exclusively", warnings[0])

        draft.write_text(
            self.concept(
                "draft",
                ["[[Sources/weak]]", "[[Sources/missing]]"],
            ),
            encoding="utf-8",
        )
        self.assertEqual(
            validate_vault.concept_capture_fidelity_warnings([weak, strong, draft]),
            [],
        )


class CodexAgentConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        self.original_root = validate_vault.ROOT
        validate_vault.ROOT = self.repo
        subprocess.run(
            ["git", "init", "-q", "-b", "master"],
            cwd=self.repo,
            check=True,
        )

    def tearDown(self) -> None:
        validate_vault.ROOT = self.original_root
        shutil.rmtree(self.repo)

    def write(self, relative_path: str, content: str) -> None:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def valid_root(self, extra: str = "") -> str:
        return (
            f"{extra}"
            'sandbox_mode = "workspace-write"\n'
            'approval_policy = "on-request"\n\n'
            "[sandbox_workspace_write]\n"
            "network_access = false\n\n"
            "[agents]\n"
            "max_depth = 1\n"
            "max_threads = 4\n"
        )

    def valid_agent(self, extra: str = "") -> str:
        return (
            'name = "vault-reviewer"\n'
            'description = "Review bounded Loreloom changes"\n'
            f"{extra}"
            'sandbox_mode = "read-only"\n'
            'approval_policy = "never"\n'
            'developer_instructions = "Review only; never edit files."\n'
        )

    def configure(self, root_extra: str = "", agent_extra: str = "") -> None:
        self.write(".codex/config.toml", self.valid_root(root_extra))
        self.write(
            ".codex/agents/vault-reviewer.toml",
            self.valid_agent(agent_extra),
        )

    def test_omitted_model_preferences_are_valid(self) -> None:
        self.configure()
        self.assertEqual(validate_vault.codex_agent_errors(), [])

    def test_non_empty_model_preferences_are_valid(self) -> None:
        preferences = (
            'model = "owner-selected-model"\n'
            'model_reasoning_effort = "owner-selected-effort"\n'
        )
        self.configure(preferences, preferences)
        self.assertEqual(validate_vault.codex_agent_errors(), [])

    def test_empty_or_non_string_model_preferences_are_invalid(self) -> None:
        invalid_values = ('model = ""\n', "model = 7\n", 'model_reasoning_effort = " "\n')
        for value in invalid_values:
            with self.subTest(value=value):
                self.configure(value, value)
                errors = validate_vault.codex_agent_errors()
                self.assertTrue(
                    any("must be a non-empty string when set" in error for error in errors),
                    errors,
                )

    def test_security_and_concurrency_invariants_remain_strict(self) -> None:
        self.configure()
        self.write(
            ".codex/config.toml",
            self.valid_root().replace(
                'sandbox_mode = "workspace-write"',
                'sandbox_mode = "danger-full-access"',
            ),
        )
        self.write(
            ".codex/agents/vault-reviewer.toml",
            self.valid_agent().replace(
                'approval_policy = "never"',
                'approval_policy = "on-request"',
            ),
        )

        errors = validate_vault.codex_agent_errors()

        self.assertTrue(any("sandbox_mode must remain 'workspace-write'" in e for e in errors))
        self.assertTrue(any("approval_policy must remain 'never'" in e for e in errors))


class MissingConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        self.original_root = validate_vault.ROOT
        validate_vault.ROOT = self.repo

    def tearDown(self) -> None:
        validate_vault.ROOT = self.original_root
        shutil.rmtree(self.repo)

    def test_missing_codex_config_is_invalid(self) -> None:
        errors = validate_vault.codex_agent_errors()

        self.assertTrue(any("missing .codex/config.toml" in error for error in errors))


class JevSidecarValidationTests(unittest.TestCase):
    SCHEMA = "schemas/jev-advisory.schema.json"

    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        self.original_root = validate_vault.ROOT
        validate_vault.ROOT = self.repo
        (self.repo / "schemas").mkdir(parents=True)
        framework_root = Path(__file__).resolve().parents[1]
        for name in ("frontmatter.schema.json", "jev-advisory.schema.json"):
            shutil.copy2(framework_root / "schemas" / name, self.repo / "schemas" / name)
        common = (
            "status: {status}\ncreated: 2026-07-18\nupdated: 2026-07-18\n"
            "tags: []\naliases: []\n"
        )
        self.write(
            "Inbox/Capture.md",
            "---\ntype: inbox\ntitle: Capture\n"
            + common.format(status="captured")
            + "captured_from: manual\n---\n\n# Capture\n",
        )
        self.write(
            "Daily/2026-07-18.md",
            '---\ntype: daily\ntitle: "2026-07-18"\n'
            + common.format(status="captured")
            + "date: 2026-07-18\n---\n\n# 2026-07-18\n",
        )
        self.write(
            "Knowledge/Draft.md",
            "---\ntype: concept\ntitle: Draft\n"
            + common.format(status="draft")
            + 'confidence: low\nreviewed: null\nsources:\n  - "[[Daily/2026-07-18]]"\n'
            "---\n\n# Draft\n\n## Sources\n\n- [[Daily/2026-07-18]]\n",
        )

    def tearDown(self) -> None:
        validate_vault.ROOT = self.original_root
        shutil.rmtree(self.repo)

    def write(self, relative_path: str, content: str | bytes) -> Path:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        data = content if isinstance(content, bytes) else content.encode("utf-8")
        path.write_bytes(data)
        return path

    def record(self, kind: str = "inbox-triage", status: str = "ok") -> dict:
        score = {
            "type": "score",
            "score": 2.5,
            "confidence": 0.5,
            "legend": None,
            "probabilities": None,
        }
        answers = {
            "inbox-triage": {
                "promotion_value": score,
                "noise": {"type": "noul", "noul": 0.25},
                "kind": {
                    "type": "choice",
                    "choice": "idea",
                    "confidence": None,
                    "probabilities": None,
                },
            },
            "claim-support": {
                "claims_supported": {"type": "noul", "noul": 0.75},
                "citation_quality": score,
            },
        }[kind]
        record = {
            "schema_version": 1,
            "advisory_only": True,
            "kind": kind,
            "target": "Inbox/Capture.md" if kind == "inbox-triage" else "Knowledge/Draft.md",
            "status": status,
            "reason": None if status == "ok" else "timeout",
            "generated_at": "2026-10-10T03:00:00Z",
            "input_sha256": "a" * 64,
            "model": "synthetic-model-1" if status == "ok" else None,
            "answers": answers if status == "ok" else None,
        }
        if kind == "claim-support":
            record["unresolved_sources"] = 0
        return record

    def write_sidecar(self, record: dict, location: str | None = None) -> str:
        location = location or (
            f".loreloom/jev/{record['kind']}/{record['target'][:-3]}.json"
        )
        self.write(location, json.dumps(record))
        return location

    def run_main(self) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch.object(
            validate_vault, "codex_agent_errors", return_value=[]
        ), mock.patch.object(
            validate_vault, "skill_errors", return_value=[]
        ), contextlib.redirect_stdout(output):
            code = validate_vault.main()
        return code, output.getvalue()

    def test_no_sidecar_directory_yields_no_findings(self) -> None:
        self.assertEqual(validate_vault.jev_sidecar_findings(), ([], []))

    def test_directory_without_sidecars_yields_no_findings(self) -> None:
        (self.repo / ".loreloom" / "jev" / "inbox-triage").mkdir(parents=True)
        self.write(".loreloom/jev/notes.txt", "not a sidecar")
        (self.repo / "schemas" / "jev-advisory.schema.json").unlink()

        self.assertEqual(validate_vault.jev_sidecar_findings(), ([], []))

    def test_valid_sidecars_yield_no_findings(self) -> None:
        for kind in ("inbox-triage", "claim-support"):
            for status in ("ok", "unavailable"):
                with self.subTest(kind=kind, status=status):
                    self.write_sidecar(self.record(kind, status))

                    self.assertEqual(validate_vault.jev_sidecar_findings(), ([], []))

    def test_schema_violation_is_a_path_specific_error(self) -> None:
        record = self.record()
        record["answers"]["noise"]["noul"] = 1.2
        record["reviewed"] = "2026-10-10"
        location = self.write_sidecar(record)

        errors, warnings = validate_vault.jev_sidecar_findings()

        self.assertEqual(warnings, [])
        self.assertGreaterEqual(len(errors), 2)
        self.assertTrue(all(error.startswith(f"{location}: ") for error in errors))
        self.assertTrue(any("reviewed" in error for error in errors), errors)

    def test_invalid_json_is_an_error(self) -> None:
        for content in (b"{not json", b"\xff\xfe", b"[" * 200000):
            with self.subTest(content=content[:10]):
                location = ".loreloom/jev/inbox-triage/Inbox/Capture.json"
                self.write(location, content)

                errors, warnings = validate_vault.jev_sidecar_findings()

                self.assertEqual(warnings, [])
                self.assertEqual(len(errors), 1)
                self.assertTrue(errors[0].startswith(f"{location}: "), errors)
                self.assertIn("valid JSON", errors[0])

    def test_location_must_match_kind_and_target(self) -> None:
        for location in (
            ".loreloom/jev/inbox-triage/Inbox/Other.json",
            ".loreloom/jev/claim-support/Inbox/Capture.json",
            ".loreloom/jev/Capture.json",
        ):
            with self.subTest(location=location):
                path = self.repo / self.write_sidecar(self.record(), location)

                errors, warnings = validate_vault.jev_sidecar_findings()

                self.assertEqual(warnings, [])
                self.assertEqual(len(errors), 1)
                self.assertTrue(errors[0].startswith(f"{location}: "), errors)
                self.assertIn("location", errors[0])
                path.unlink()

    def test_missing_target_is_a_warning_and_validation_still_passes(self) -> None:
        location = self.write_sidecar(self.record())
        (self.repo / "Inbox" / "Capture.md").unlink()

        errors, warnings = validate_vault.jev_sidecar_findings()
        code, output = self.run_main()

        self.assertEqual(errors, [])
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0].startswith(f"{location}: "), warnings)
        self.assertIn("Inbox/Capture.md", warnings[0])
        self.assertEqual(code, 0)
        self.assertIn("Vault validation warning(s):", output)
        self.assertIn(warnings[0], output)
        self.assertTrue(output.splitlines()[-1].startswith("Vault validation passed:"))

    def test_symlinked_sidecar_is_an_error(self) -> None:
        real = self.write("elsewhere.json", json.dumps(self.record()))
        location = ".loreloom/jev/inbox-triage/Inbox/Capture.json"
        link = self.repo / location
        link.parent.mkdir(parents=True)
        try:
            link.symlink_to(real)
        except (OSError, NotImplementedError):
            self.skipTest("symbolic links are unavailable on this platform")

        errors, warnings = validate_vault.jev_sidecar_findings()

        self.assertEqual(warnings, [])
        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith(f"{location}: "), errors)
        self.assertIn("symbolic link", errors[0])

    def test_oversized_sidecar_is_an_error(self) -> None:
        location = ".loreloom/jev/inbox-triage/Inbox/Capture.json"
        self.write(location, json.dumps(self.record()) + " " * (1024 * 1024))

        errors, _ = validate_vault.jev_sidecar_findings()

        self.assertEqual(len(errors), 1)
        self.assertTrue(errors[0].startswith(f"{location}: "), errors)
        self.assertIn("1 MiB", errors[0])

    def test_missing_or_invalid_schema_is_one_error_and_fails_validation(self) -> None:
        self.write_sidecar(self.record())
        self.write_sidecar(self.record("claim-support"))
        schema = self.repo / "schemas" / "jev-advisory.schema.json"
        for name, content in (
            ("missing", None),
            ("not JSON", "{not json"),
            ("not a schema", '{"type": 7}'),
        ):
            with self.subTest(name=name):
                if content is None:
                    schema.unlink()
                else:
                    schema.write_text(content, encoding="utf-8")

                errors, warnings = validate_vault.jev_sidecar_findings()
                code, output = self.run_main()

                self.assertEqual(warnings, [])
                self.assertEqual(len(errors), 1)
                self.assertTrue(errors[0].startswith(f"{self.SCHEMA}: "), errors)
                self.assertEqual(code, 1)
                self.assertIn(errors[0], output)

    def test_malformed_sidecars_are_aggregated_with_other_errors(self) -> None:
        first = self.write_sidecar(
            {"schema_version": 1}, ".loreloom/jev/inbox-triage/Inbox/Capture.json"
        )
        second = ".loreloom/jev/claim-support/Knowledge/Draft.json"
        self.write(second, "{not json")
        self.write("Inbox/Linked.md", "See [[Knowledge/Missing note]].\n")

        code, output = self.run_main()

        self.assertEqual(code, 1)
        self.assertIn(f"- {first}: ", output)
        self.assertIn(f"- {second}: ", output)
        self.assertIn("unresolved wikilink", output)

    def test_output_is_identical_without_sidecars(self) -> None:
        _, without_directory = self.run_main()
        (self.repo / ".loreloom" / "jev" / "inbox-triage").mkdir(parents=True)
        code_empty, with_empty_directory = self.run_main()
        self.write_sidecar(self.record())
        code_valid, with_valid_sidecar = self.run_main()

        self.assertEqual(code_empty, 0)
        self.assertEqual(with_empty_directory, without_directory)
        self.assertEqual(code_valid, 0)
        self.assertEqual(with_valid_sidecar, without_directory)
        self.assertEqual(len(without_directory.splitlines()), 1)

    def test_validation_with_sidecars_opens_no_socket(self) -> None:
        self.write_sidecar(self.record())
        self.write_sidecar(self.record("claim-support", "unavailable"))

        with mock.patch.object(
            socket, "socket", side_effect=AssertionError("validator must stay offline")
        ), mock.patch.dict(os.environ, {"LORELOOM_JEV_ENABLED": "1"}, clear=False):
            code, output = self.run_main()

        self.assertEqual(code, 0)
        self.assertTrue(output.startswith("Vault validation passed:"))

    def test_validator_has_no_network_or_jev_runtime_dependency(self) -> None:
        source = Path(validate_vault.__file__).read_text(encoding="utf-8")
        imported: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                imported.add(module)
                imported.update(f"{module}.{alias.name}" for alias in node.names)

        for forbidden in ("jev_advisory", "scripts.jev_advisory", "socket"):
            self.assertNotIn(forbidden, imported)
        self.assertFalse(
            any(name.split(".")[:2] == ["urllib", "request"] for name in imported)
        )
        self.assertFalse(any("jev_advisory" in name for name in imported))
        self.assertNotIn("JEV_API_KEY", source)
        self.assertNotIn("LORELOOM_JEV_ENABLED", source)


if __name__ == "__main__":
    unittest.main()
