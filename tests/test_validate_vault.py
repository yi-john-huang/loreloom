from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
