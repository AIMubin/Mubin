"""Dry-run tests for versioned GitHub ruleset import templates (no API writes)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FOLDER = ROOT / "docs" / "governance"

BASE = (
    "Baseline contracts and public-preview (ubuntu-latest)",
    "Baseline contracts and public-preview (windows-latest)",
    "Public tracked-artifact safety (ubuntu-latest)",
    "Public tracked-artifact safety (windows-latest)",
)


def template(name):
    return json.loads((FOLDER / name).read_text(encoding="utf-8"))


class MainRulesetTests(unittest.TestCase):
    def setUp(self):
        self.bootstrap = template("main-bootstrap.ruleset.json")
        self.strict = template("main-strict.ruleset.json")

    def test_both_target_only_main_with_no_bypass(self):
        for p in (self.bootstrap, self.strict):
            with self.subTest(name=p["name"]):
                self.assertEqual(p["target"], "branch")
                self.assertEqual(p["enforcement"], "active")
                self.assertEqual(p["bypass_actors"], [])
                self.assertEqual(p["conditions"]["ref_name"],
                                 {"include": ["refs/heads/main"], "exclude": []})
                rules = {r["type"]: r for r in p["rules"]}
                self.assertIn("deletion", rules)
                self.assertIn("non_fast_forward", rules)
                self.assertIn("pull_request", rules)
                self.assertEqual(rules["pull_request"]["parameters"]
                                 ["allowed_merge_methods"], ["squash"])
                self.assertTrue(rules["pull_request"]["parameters"]
                                ["required_review_thread_resolution"])

    def test_bootstrap_never_requires_absent_ci(self):
        rules = {r["type"]: r for r in self.bootstrap["rules"]}
        self.assertNotIn("required_status_checks", rules)
        self.assertNotIn("required_linear_history", rules)
        self.assertEqual(rules["pull_request"]["parameters"]
                         ["required_approving_review_count"], 0)

    def test_strict_requires_four_exact_cross_platform_checks(self):
        rules = {r["type"]: r for r in self.strict["rules"]}
        self.assertIn("required_linear_history", rules)
        params = rules["required_status_checks"]["parameters"]
        self.assertTrue(params["strict_required_status_checks_policy"])
        contexts = tuple(c["context"] for c in params["required_status_checks"])
        self.assertEqual(contexts, BASE)
        self.assertEqual(len(set(contexts)), 4)
        reviews = rules["pull_request"]["parameters"]
        self.assertEqual(reviews["required_approving_review_count"], 1)
        self.assertTrue(reviews["require_last_push_approval"])

    def test_operator_script_is_explicit_dry_run_first(self):
        script = (ROOT / "scripts/governance/activate-main-ruleset.ps1").read_text(
            encoding="utf-8")
        for required in ("[switch]$Apply", "if (-not $Apply)",
                         "INDEPENDENT_REVIEWER_CONFIRMATION_REQUIRED",
                         "REQUIRED_MAIN_HEAD_CHECK_MISSING",
                         "BOOTSTRAP_RULESET_ID_INVALID",
                         "RULESET_REMOTE_BYPASS_DETECTED",
                         "RULESET_REMOTE_CHECKS_MISMATCH",
                         "RULESET_TEMPLATE_REQUIRED_RULE_MISSING",
                         "ConfirmRulesetMatches", "DRY_RUN"):
            self.assertIn(required, script)
        workflow = (ROOT / ".github/workflows/governance-template-checks.yml"
                    ).read_text(encoding="utf-8")
        self.assertIn("pwsh -NoProfile -File", workflow)
        self.assertNotIn(" -Apply", workflow)
        self.assertIn("test-activation-readback.ps1", workflow)

    def test_documentation_explicitly_rejects_premature_enforcement(self):
        readme = (FOLDER / "README.md").read_text(encoding="utf-8")
        for required in ("#142", "#144", "#146", "deadlock",
                         "templates only", "independent reviewer"):
            self.assertIn(required.lower(), readme.lower())


if __name__ == "__main__":
    unittest.main()
