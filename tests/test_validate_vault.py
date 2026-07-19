from __future__ import annotations
import hashlib

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
            """model = "gpt-5.6-sol"
model_reasoning_effort = "max"
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
model = "gpt-5.6-sol"
model_reasoning_effort = "max"
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


if __name__ == "__main__":
    unittest.main()
