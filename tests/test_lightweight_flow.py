from __future__ import annotations

import contextlib
import io
import os
import shutil
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

from scripts import (
    doctor_vault,
    ingest_gate,
    lint_wiki,
    migrate_knowledge_to_wiki,
    validate_vault,
)

REPOSITORY = Path(__file__).resolve().parent.parent

MOC = """---
type: moc
title: Home
status: evergreen
created: 2026-07-18
updated: 2026-07-19
tags: []
aliases: []
scope: Test navigation
curation: human
---

# Home
"""

RAW_SOURCE = "A raw clipping without frontmatter.\n"


def wiki_page(
    title: str = "Tea",
    page_type: str = "concept",
    status: str = "draft",
    confidence: str = "high",
    sources: str = '\n  - "[[Sources/Raw clip]]"',
    extra: str = "",
    body: str = "Tea is a drink made from leaves.\n",
) -> str:
    return (
        f"---\ntitle: {title}\ntype: {page_type}\nstatus: {status}\n"
        f"confidence: {confidence}\nsources:{sources}\nupdated: 2026-10-11\n"
        f"{extra}---\n\n# {title}\n\n{body}"
    )


class VaultTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.repo = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.repo)
        for module in (validate_vault, ingest_gate, migrate_knowledge_to_wiki):
            patcher = mock.patch.object(module, "ROOT", self.repo)
            patcher.start()
            self.addCleanup(patcher.stop)
        environment = mock.patch.dict(os.environ, {}, clear=False)
        environment.start()
        self.addCleanup(environment.stop)
        os.environ.pop(validate_vault.VALIDATION_MODE_ENV, None)
        (self.repo / "schemas").mkdir()
        for name in ("frontmatter.schema.json", "wiki-page.schema.json"):
            shutil.copy(REPOSITORY / "schemas" / name, self.repo / "schemas" / name)
        self.write("MOCs/Home.md", MOC)
        self.write("Sources/Raw clip.md", RAW_SOURCE)

    def write(self, relative_path: str, content: str) -> Path:
        path = self.repo / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def run_validator(self, *argv: str) -> tuple[int, str]:
        output = io.StringIO()
        with mock.patch.object(
            validate_vault, "codex_agent_errors", return_value=[]
        ), mock.patch.object(
            validate_vault, "skill_errors", return_value=[]
        ), contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            code = validate_vault.main(list(argv))
        return code, output.getvalue()


class ValidationModeTests(VaultTestCase):
    def test_daily_accepts_raw_evidence_that_strict_rejects(self) -> None:
        daily_code, daily_output = self.run_validator("--mode", "daily")
        strict_code, strict_output = self.run_validator("--mode", "strict")

        self.assertEqual(daily_code, 0, daily_output)
        self.assertIn("Vault validation passed: daily mode", daily_output)
        self.assertEqual(strict_code, 1)
        self.assertIn("in strict mode", strict_output)
        self.assertIn("Sources/Raw clip.md: missing YAML frontmatter", strict_output)

    def test_default_mode_is_daily(self) -> None:
        code, output = self.run_validator()

        self.assertEqual(code, 0, output)
        self.assertIn("daily mode", output)

    def test_strict_passes_on_a_schema_valid_vault(self) -> None:
        (self.repo / "Sources" / "Raw clip.md").unlink()

        code, output = self.run_validator("--mode", "strict")

        self.assertEqual(code, 0, output)
        self.assertIn("Vault validation passed: strict mode", output)
        self.assertIn("custom agents", output)

    def test_daily_skips_strict_only_schema_fields(self) -> None:
        self.write(
            "MOCs/Home.md", "---\ntype: moc\ntitle: Start\nstatus: evergreen\n---\n"
        )

        daily_code, daily_output = self.run_validator("--mode", "daily")
        (self.repo / "Sources" / "Raw clip.md").unlink()
        strict_code, strict_output = self.run_validator("--mode", "strict")

        self.assertEqual(daily_code, 0, daily_output)
        self.assertEqual(strict_code, 1)
        self.assertIn("'created' is a required property", strict_output)
        self.assertIn("title must match filename", strict_output)

    def test_daily_reports_basic_frontmatter_problems(self) -> None:
        self.write("MOCs/No frontmatter.md", "# Plain\n")
        self.write("MOCs/Missing.md", "---\ntype: moc\ntitle: Missing\n---\n")
        self.write(
            "MOCs/Wrong type.md",
            "---\ntype: concept\ntitle: Wrong type\nstatus: draft\nupdated: soon\n---\n",
        )

        code, output = self.run_validator("--mode", "daily")

        self.assertEqual(code, 1)
        self.assertIn("MOCs/No frontmatter.md: missing YAML frontmatter", output)
        self.assertIn("MOCs/Missing.md: missing required field(s): status", output)
        self.assertIn("MOCs/Wrong type.md: notes in MOCs/ must use type 'moc'", output)
        self.assertIn("MOCs/Wrong type.md: updated: must be a YYYY-MM-DD date", output)

    def test_daily_broken_wikilink_is_an_error_except_in_raw_evidence(self) -> None:
        self.write("Sources/Raw clip.md", "See [[Missing from source]].\n")
        code, output = self.run_validator("--mode", "daily")
        self.assertEqual(code, 0, output)
        self.assertIn("Vault validation warning(s):", output)
        self.assertIn("Sources/Raw clip.md: unresolved wikilink", output)

        self.write("index.md", "- [[Wiki/concepts/Nowhere]]\n")
        code, output = self.run_validator("--mode", "daily")
        self.assertEqual(code, 1)
        self.assertIn("index.md: unresolved wikilink [[Wiki/concepts/Nowhere]]", output)

    def test_mode_resolution_order(self) -> None:
        self.assertEqual(
            validate_vault.configured_validation_mode(), ("daily", "built-in default")
        )
        self.write("pyproject.toml", '[tool.loreloom]\nvalidation_mode = "strict"\n')
        self.assertEqual(validate_vault.configured_validation_mode()[0], "strict")
        code, output = self.run_validator()
        self.assertEqual(code, 1)
        self.assertIn("in strict mode", output)

        os.environ[validate_vault.VALIDATION_MODE_ENV] = "Daily"
        mode, origin = validate_vault.configured_validation_mode()
        self.assertEqual(mode, "daily")
        self.assertIn(validate_vault.VALIDATION_MODE_ENV, origin)

        code, output = self.run_validator("--mode", "strict")
        self.assertEqual(code, 1)
        self.assertIn("in strict mode", output)

    def test_invalid_configured_mode_exits_two(self) -> None:
        os.environ[validate_vault.VALIDATION_MODE_ENV] = "relaxed"

        code, output = self.run_validator()

        self.assertEqual(code, 2)
        self.assertIn("Invalid validation mode", output)
        with self.assertRaises(SystemExit) as raised, contextlib.redirect_stderr(
            io.StringIO()
        ):
            validate_vault.parse_args(["--mode", "relaxed"])
        self.assertEqual(raised.exception.code, 2)


class WikiPageValidationTests(VaultTestCase):
    def test_valid_indexed_page_passes_both_modes_without_warnings(self) -> None:
        (self.repo / "Sources" / "Raw clip.md").unlink()
        self.write("Daily/2026-10-11.md", "---\ntype: daily\ntitle: '2026-10-11'\nstatus: captured\ncreated: 2026-10-11\nupdated: 2026-10-11\ntags: []\naliases: []\ndate: 2026-10-11\n---\n")
        self.write(
            "Wiki/concepts/Tea.md",
            wiki_page(status="reviewed", sources='\n  - "[[Daily/2026-10-11]]"'),
        )
        self.write("index.md", "- [[Wiki/concepts/Tea]] — About tea.\n")

        for mode in validate_vault.VALIDATION_MODES:
            with self.subTest(mode=mode):
                code, output = self.run_validator("--mode", mode)
                self.assertEqual(code, 0, output)
                self.assertEqual(len(output.splitlines()), 1, output)
                self.assertIn("1 Wiki pages", output)

    def test_wiki_pages_are_not_lifecycle_notes(self) -> None:
        page = self.write("Wiki/concepts/Tea.md", wiki_page())
        legacy = self.write("Wiki/Overview.md", "# Legacy\n")

        self.assertEqual(validate_vault.wiki_pages(), [page])
        self.assertIn(legacy, validate_vault.managed_notes())
        self.assertNotIn(page, validate_vault.managed_notes())

    def test_frontmatter_contract_errors(self) -> None:
        self.write(
            "Wiki/concepts/Bad.md",
            "---\ntitle: Bad\ntype: essay\nstatus: final\nconfidence: sure\n"
            "sources: none\n---\n",
        )
        self.write("Wiki/entities/Tea.md", wiki_page())
        self.write("Wiki/_review/Queued.md", wiki_page("Queued", status="reviewed"))
        self.write(
            "Wiki/synthesis/Empty.md",
            wiki_page("Empty", "synthesis", "reviewed", sources=" []"),
        )
        self.write(
            "Wiki/synthesis/Loose.md",
            wiki_page("Loose", "synthesis", sources="\n  - some book"),
        )

        code, output = self.run_validator("--mode", "daily")

        self.assertEqual(code, 1)
        for expected in (
            "Wiki/concepts/Bad.md: type: 'essay' is not one of",
            "Wiki/concepts/Bad.md: status: 'final' is not one of",
            "Wiki/concepts/Bad.md: confidence: 'sure' is not one of",
            "Wiki/concepts/Bad.md: sources: 'none' is not of type 'array'",
            "Wiki/concepts/Bad.md: frontmatter: 'updated' is a required property",
            "Wiki/entities/Tea.md: pages in Wiki/entities/ must use type 'entity'",
            "Wiki/_review/Queued.md: pages in Wiki/_review/ must stay status 'draft'",
            "Wiki/synthesis/Empty.md: status 'reviewed' requires at least one source",
            "Wiki/synthesis/Loose.md: source must be a wikilink or an HTTP(S) URL",
        ):
            self.assertIn(expected, output)

    def test_index_and_log_warnings_do_not_fail_validation(self) -> None:
        self.write("Wiki/concepts/Tea.md", wiki_page())
        self.write("Wiki/_review/Queued.md", wiki_page("Queued", sources=" []"))

        code, output = self.run_validator("--mode", "daily")

        self.assertEqual(code, 0, output)
        self.assertIn("Wiki/concepts/Tea.md: page is not listed in index.md", output)
        self.assertIn(
            "Wiki/_review/Queued.md: review-queue page is not recorded in log.md", output
        )
        self.assertIn("Wiki/_review/Queued.md: draft page has no sources yet", output)

        self.write("index.md", "- [[Wiki/concepts/Tea]]\n")
        self.write("log.md", "- Needs review: [[Wiki/_review/Queued]] — numbers.\n")
        _, output = self.run_validator("--mode", "daily")
        self.assertNotIn("not listed in index.md", output)
        self.assertNotIn("not recorded in log.md", output)

    def test_strict_adds_citation_and_title_rules(self) -> None:
        self.write(
            "Wiki/concepts/Tea.md",
            wiki_page("Green tea", status="reviewed"),
        )
        self.write(
            "Wiki/concepts/Coffee.md",
            wiki_page("Coffee", sources='\n  - "[[MOCs/Home]]"'),
        )
        self.write("index.md", "- [[Wiki/concepts/Tea]]\n- [[Wiki/concepts/Coffee]]\n")

        daily_code, daily_output = self.run_validator("--mode", "daily")
        strict_code, strict_output = self.run_validator("--mode", "strict")

        self.assertEqual(daily_code, 0, daily_output)
        self.assertEqual(strict_code, 1)
        self.assertIn(
            "Wiki/concepts/Tea.md: title must match filename 'Tea'", strict_output
        )
        self.assertIn(
            "Wiki/concepts/Tea.md: reviewed page cites a Source that is not owner-reviewed",
            strict_output,
        )
        self.assertIn(
            "Wiki/concepts/Coffee.md: source must be a Sources/, Daily/, Assets/ wikilink",
            strict_output,
        )

    def test_missing_schema_is_one_error(self) -> None:
        self.write("Wiki/concepts/Tea.md", wiki_page())
        (self.repo / "schemas" / "wiki-page.schema.json").unlink()

        code, output = self.run_validator("--mode", "daily")

        self.assertEqual(code, 1)
        self.assertIn("schemas/wiki-page.schema.json: missing or invalid", output)

    def test_lowercase_wiki_directory_is_rejected(self) -> None:
        (self.repo / "Wiki").mkdir()
        (self.repo / "wiki").mkdir(exist_ok=True)
        if len([item for item in self.repo.iterdir() if item.name.lower() == "wiki"]) < 2:
            self.skipTest("filesystem is case-insensitive")

        code, output = self.run_validator("--mode", "daily")

        self.assertEqual(code, 1)
        self.assertIn("wiki/: conflicts with Wiki/", output)


class IngestGateTests(VaultTestCase):
    def reasons(self, **options: str) -> list[str]:
        metadata, body = ingest_gate.split_note(wiki_page(**options))
        return ingest_gate.gate_reasons(metadata, body)

    def test_high_confidence_page_without_numbers_is_accepted(self) -> None:
        self.assertEqual(self.reasons(), [])
        self.assertEqual(
            self.reasons(
                body="AWS S3, GPT-4, IPv6, and v1.2 are names. See [[Daily/2026-10-11]] "
                "and `rate=5`.\n\n1. First step\n\n```\ncount = 42\n```\n"
            ),
            [],
        )

    def test_each_failed_condition_is_reported(self) -> None:
        self.assertIn("confidence is 'medium'", self.reasons(confidence="medium")[0])
        self.assertEqual(self.reasons(sources=" []"), ["no sources"])
        numeric = self.reasons(body="It costs 5 USD and rose 3.5% in 2023.\n")
        self.assertEqual(len(numeric), 1)
        self.assertIn("3 numeric claim(s)", numeric[0])
        self.assertIn("3.5%", numeric[0])
        self.assertEqual(
            self.reasons(body="Text.\n\n## Contradictions\n\n- Source A disagrees.\n"),
            ["records a contradiction"],
        )
        self.assertEqual(
            self.reasons(extra='contradicts:\n  - "[[Wiki/concepts/Coffee]]"\n'),
            ["records a contradiction"],
        )
        self.assertEqual(self.reasons(body="Text.\n\n## Contradictions\n\nNone\n"), [])
        self.assertEqual(
            ingest_gate.gate_reasons(*ingest_gate.split_note("# No frontmatter\n")),
            ["frontmatter is missing or invalid"],
        )

    def run_gate(self, *argv: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = ingest_gate.main(list(argv))
        return code, output.getvalue()

    def test_cli_reports_decisions_and_check_flags_unreviewed_acceptance(self) -> None:
        self.write("Wiki/concepts/Tea.md", wiki_page())
        self.write(
            "Wiki/concepts/Price.md",
            wiki_page("Price", status="reviewed", body="Tea costs 5 USD.\n"),
        )
        before = (self.repo / "Wiki/concepts/Price.md").read_bytes()

        code, output = self.run_gate("Wiki/concepts/Tea.md", "Wiki/concepts/Price.md")
        self.assertEqual(code, 0)
        self.assertIn("Wiki/concepts/Tea.md: accept -> status: reviewed", output)
        self.assertIn("Wiki/concepts/Price.md: review -> status: draft", output)

        code, output = self.run_gate("--all", "--check")
        self.assertEqual(code, 1)
        self.assertIn("already reviewed without reviewed_by: owner", output)
        self.assertEqual((self.repo / "Wiki/concepts/Price.md").read_bytes(), before)

        self.write(
            "Wiki/concepts/Price.md",
            wiki_page(
                "Price",
                status="reviewed",
                extra="reviewed_by: owner\n",
                body="Tea costs 5 USD.\n",
            ),
        )
        self.assertEqual(self.run_gate("--all", "--check")[0], 0)
        self.assertEqual(self.run_gate()[0], 2)


class MigrationTests(VaultTestCase):
    CONCEPT = """---
type: concept
title: Tokyo ramen observation
status: {status}
created: 2026-07-18
updated: 2026-07-19
tags:
  - food/ramen
aliases: []
confidence: {confidence}
reviewed: null
sources:
  - "[[Sources/Raw clip]]"
agent: codex
---

# Tokyo ramen observation

Body stays the same.
"""

    def concept(self, status: str = "draft", confidence: str = "medium") -> str:
        return self.CONCEPT.format(status=status, confidence=confidence)

    def run_migration(self, *argv: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = migrate_knowledge_to_wiki.main(list(argv))
        return code, output.getvalue()

    def test_dry_run_is_the_default_and_writes_nothing(self) -> None:
        self.write("Knowledge/Trips/Tokyo ramen observation.md", self.concept())

        code, output = self.run_migration()

        self.assertEqual(code, 0)
        self.assertIn(
            "would create: Knowledge/Trips/Tokyo ramen observation.md -> "
            "Wiki/concepts/Trips/Tokyo ramen observation.md (status draft -> draft)",
            output,
        )
        self.assertIn("Dry run: 1 page(s) would be created, 0 skipped.", output)
        self.assertFalse((self.repo / "Wiki").exists())

    def test_apply_maps_frontmatter_and_keeps_the_original(self) -> None:
        source = self.write(
            "Knowledge/Tokyo ramen observation.md", self.concept("evergreen", "high")
        )
        original = source.read_bytes()

        code, output = self.run_migration("--apply")

        self.assertEqual(code, 0)
        self.assertIn("Migration applied: 1 page(s) created, 0 skipped.", output)
        self.assertEqual(source.read_bytes(), original)
        target = self.repo / "Wiki/concepts/Tokyo ramen observation.md"
        metadata, parse_error = validate_vault.load_frontmatter(target)
        self.assertIsNone(parse_error)
        self.assertEqual(
            metadata,
            {
                "title": "Tokyo ramen observation",
                "type": "concept",
                "status": "evergreen",
                "confidence": "high",
                "sources": ["[[Sources/Raw clip]]"],
                "updated": "2026-07-19",
                "reviewed_by": "owner",
                "created": "2026-07-18",
                "tags": ["food/ramen"],
                "migrated_from": "Knowledge/Tokyo ramen observation.md",
            },
        )
        self.assertTrue(target.read_text(encoding="utf-8").endswith("Body stays the same.\n"))
        self.assertEqual(
            validate_vault.wiki_page_findings([target], "daily")[0], []
        )

    def test_unmappable_notes_are_skipped_and_existing_pages_are_kept(self) -> None:
        self.write("Knowledge/Archived.md", self.concept("archived"))
        self.write("Knowledge/No frontmatter.md", "# Plain\n")
        self.write("Knowledge/Kept.md", self.concept())
        existing = self.write("Wiki/concepts/Kept.md", "owner edit\n")
        self.write(
            "Knowledge/Weak.md",
            self.concept("evergreen", "certain").replace(
                'sources:\n  - "[[Sources/Raw clip]]"', "sources: []"
            ),
        )

        code, output = self.run_migration("--apply")

        self.assertEqual(code, 0)
        self.assertIn("skipped: Knowledge/Archived.md", output)
        self.assertIn("status 'archived' has no Wiki mapping", output)
        self.assertIn("missing YAML frontmatter", output)
        self.assertIn("target already exists", output)
        self.assertEqual(existing.read_text(encoding="utf-8"), "owner edit\n")
        self.assertIn("Migration applied: 1 page(s) created, 3 skipped.", output)
        metadata, _ = validate_vault.load_frontmatter(self.repo / "Wiki/concepts/Weak.md")
        self.assertEqual(metadata["status"], "draft")
        self.assertEqual(metadata["confidence"], "low")
        self.assertNotIn("reviewed_by", metadata)

    def test_selected_paths_must_be_knowledge_notes(self) -> None:
        self.write("Knowledge/One.md", self.concept())
        self.write("Knowledge/Two.md", self.concept())

        code, output = self.run_migration("--apply", "Knowledge/One.md")
        self.assertEqual(code, 0)
        self.assertTrue((self.repo / "Wiki/concepts/One.md").is_file())
        self.assertFalse((self.repo / "Wiki/concepts/Two.md").exists())

        code, output = self.run_migration("--apply", "MOCs/Home.md", "Knowledge/Nope.md")
        self.assertEqual(code, 2)
        self.assertIn("MOCs/Home.md: not inside Knowledge/", output)
        self.assertIn("Knowledge/Nope.md: not an existing Markdown note", output)


class LintTests(VaultTestCase):
    def test_report_categories(self) -> None:
        self.write("Wiki/concepts/Tea.md", wiki_page(status="reviewed"))
        self.write(
            "Wiki/concepts/Price.md",
            wiki_page(
                "Price",
                status="reviewed",
                confidence="low",
                body="Tea costs 5 USD. See [[Wiki/concepts/Tea]] and [[Missing]].\n\n"
                "## Contradictions\n\n- Another source says 6 USD.\n",
            ),
        )
        self.write("Wiki/_review/Queued.md", wiki_page("Queued"))
        self.write("index.md", "- [[Wiki/concepts/Tea]]\n- [[Wiki/concepts/Price]]\n")

        findings = lint_wiki.lint_findings(date(2027, 10, 11), 180)

        self.assertEqual(len(findings["broken"]), 1)
        self.assertIn("[[Missing]]", findings["broken"][0])
        self.assertEqual(findings["orphan"], ["Wiki/concepts/Price.md"])
        self.assertEqual(findings["unindexed"], [])
        self.assertEqual(findings["contradiction"], ["Wiki/concepts/Price.md"])
        self.assertEqual(findings["low"], ["Wiki/concepts/Price.md"])
        self.assertEqual(len(findings["gate"]), 1)
        self.assertTrue(findings["gate"][0].startswith("Wiki/concepts/Price.md: "))
        self.assertEqual(findings["queue"], ["Wiki/_review/Queued.md: draft"])
        self.assertEqual(len(findings["stale"]), 3)
        self.assertEqual(lint_wiki.lint_findings(date(2026, 10, 12), 180)["stale"], [])

    def test_cli_is_read_only_and_always_exits_zero(self) -> None:
        page = self.write("Wiki/concepts/Tea.md", wiki_page())
        before = page.read_bytes()
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            code = lint_wiki.main([])

        self.assertEqual(code, 0)
        self.assertIn("Wiki lint: 1 page(s)", output.getvalue())
        self.assertIn("Pages missing from index.md: 1", output.getvalue())
        self.assertEqual(page.read_bytes(), before)


class DoctorModeTests(VaultTestCase):
    def test_mode_check_shows_mode_origin_and_recommendation(self) -> None:
        check = doctor_vault._mode_check(self.repo, validate_vault)
        self.assertEqual((check.status, check.name), ("PASS", "validation-mode"))
        self.assertTrue(check.detail.startswith("daily (from built-in default)"))
        self.assertIn("--mode strict", check.detail)

        self.write("pyproject.toml", '[tool.loreloom]\nvalidation_mode = "strict"\n')
        check = doctor_vault._mode_check(self.repo, validate_vault)
        self.assertEqual(check.status, "PASS")
        self.assertTrue(check.detail.startswith("strict (from pyproject.toml"))
        self.assertIn("use daily", check.detail)

        os.environ[validate_vault.VALIDATION_MODE_ENV] = "relaxed"
        check = doctor_vault._mode_check(self.repo, validate_vault)
        self.assertEqual(check.status, "FAIL")
        self.assertIn("daily, strict", check.detail)
        self.assertEqual(
            doctor_vault._validation_check(self.repo, validate_vault).status, "FAIL"
        )

    def test_validation_check_runs_the_configured_mode(self) -> None:
        with mock.patch.object(validate_vault, "main", return_value=0) as main:
            doctor_vault._validation_check(self.repo, validate_vault)
        main.assert_called_once_with(["--mode", "daily"])

        self.write("pyproject.toml", '[tool.loreloom]\nvalidation_mode = "strict"\n')
        with mock.patch.object(validate_vault, "main", return_value=1) as main:
            check = doctor_vault._validation_check(self.repo, validate_vault)
        main.assert_called_once_with(["--mode", "strict"])
        self.assertEqual(check.status, "FAIL")
        self.assertIn("validate_vault.py --mode strict", check.detail)

    def test_lightweight_layout_is_a_warning_only(self) -> None:
        check = doctor_vault._light_layout_check(self.repo, validate_vault)
        self.assertEqual(check.status, "WARN")
        self.assertIn("index.md", check.detail)
        self.assertIn("Wiki/_review", check.detail)

        for name in ("index.md", "log.md"):
            self.write(name, "# Navigation\n")
        for section in ("sources", "entities", "concepts", "synthesis", "_review"):
            (self.repo / "Wiki" / section).mkdir(parents=True)
        self.assertEqual(
            doctor_vault._light_layout_check(self.repo, validate_vault).status, "PASS"
        )

    def test_doctor_output_lists_the_mode(self) -> None:
        output = io.StringIO()
        with mock.patch.object(doctor_vault, "ROOT", self.repo), contextlib.redirect_stdout(
            output
        ):
            doctor_vault.main([])

        lines = output.getvalue().splitlines()
        self.assertTrue(
            any(line.startswith("[PASS] validation-mode: daily (from ") for line in lines),
            lines,
        )
        self.assertTrue(any("vault-validation" in line for line in lines), lines)


CLARITY_SKILL_URL = (
    "https://github.com/yi-john-huang/sdd-mcp/blob/master/"
    "skills/output-clarity-ladder/SKILL.md"
)


class RepositoryContractTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (REPOSITORY / relative_path).read_text(encoding="utf-8")

    def test_lightweight_skills_exist_and_cite_the_writing_rule(self) -> None:
        for name in ("ingest", "query", "lint", "file-answer"):
            with self.subTest(skill=name):
                text = self.read(f".agents/skills/{name}/SKILL.md")
                self.assertIn(f"name: {name}\n", text)
                self.assertIn("index.md", text)
                self.assertIn("`output-clarity-ladder` skill", text)
                self.assertIn(CLARITY_SKILL_URL, text)
                self.assertNotIn("docs/output-clarity-ladder.md", text)
                self.assertIn(
                    f"${name}", self.read(f".agents/skills/{name}/agents/openai.yaml")
                )

    def test_existing_skills_are_marked_strict_mode(self) -> None:
        skills = sorted((REPOSITORY / ".agents" / "skills").glob("*-vault-*/SKILL.md"))
        self.assertEqual(len(skills), 7)
        for path in skills:
            with self.subTest(skill=path.parent.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("description: Strict-mode (optional)", text)
                self.assertNotRegex(text, r"validate_vault\.py(?! --mode strict)")

    def test_agent_guides_describe_the_same_default_flow(self) -> None:
        claude = self.read("CLAUDE.md")
        agents = self.read("AGENTS.md")
        readme = self.read("README.md")
        for text in (claude, readme):
            self.assertIn("使用範圍 / Scope of use", text)
        self.assertIn("CLAUDE.md", agents)
        self.assertIn("`output-clarity-ladder` skill", claude)
        self.assertIn(CLARITY_SKILL_URL, claude)
        self.assertIn("zh-TW", claude)
        self.assertNotIn("docs/output-clarity-ladder.md", claude)
        self.assertIn("Wiki/_review/", claude)
        self.assertIn("Wiki/synthesis/", claude)
        self.assertFalse((REPOSITORY / "docs" / "output-clarity-ladder.md").exists())
        for name in ("index.md", "log.md", "docs/migration-lightweight.md"):
            self.assertTrue((REPOSITORY / name).is_file(), name)

    def test_shipped_vault_passes_both_modes_and_the_gate(self) -> None:
        for mode in validate_vault.VALIDATION_MODES:
            with self.subTest(mode=mode), contextlib.redirect_stdout(io.StringIO()) as output:
                code = validate_vault.main(["--mode", mode])
            self.assertEqual(code, 0, output.getvalue())
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = ingest_gate.main(["--all", "--check"])
        self.assertEqual(code, 0, output.getvalue())


if __name__ == "__main__":
    unittest.main()
