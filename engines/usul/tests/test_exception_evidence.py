"""U0.1 exception provenance: absence in a declared synthetic scope is not universal absence."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.p0_bridge import build_and_run
from engines.usul.pilots.amr_default import example_bundle, example_spec, scenarios


RULE = "pilot:rule-amr-default"
ATOM = "pilot:diverting-indicator"
OUTPUT = "pilot:default-obligation-candidate"
SOURCE = "pilot:ev-indicator"


def assessment(finding="ABSENT_IN_DECLARED_SCOPE", *,
               checked=None, evidence_ids=None, kind="synthetic_fixture"):
    return [{
        "rule_id": RULE,
        "exception_atom": ATOM,
        "finding": finding,
        "evidence_ids": evidence_ids if evidence_ids is not None else (
            [] if finding == "NOT_CHECKED" else [SOURCE]
        ),
        "scope": {
            "id": "pilot:searchscope",
            "kind": kind,
            "declared_items": ["pilot:item1", "pilot:item2"],
            "checked_items": checked if checked is not None else (
                [] if finding == "NOT_CHECKED" else ["pilot:item1", "pilot:item2"]
            ),
        },
    }]


def run(assessments, facts=None, strict=True):
    return build_and_run(
        example_bundle(), example_spec(example_bundle()),
        scenarios()["indicator_unknown"] if facts is None else facts,
        require_semantic_binding=True,
        exception_assessments=assessments, require_evidence_exceptions=strict,
    )


class ScopedExceptionEvidenceTests(unittest.TestCase):
    def test_closed_declared_synthetic_scope_supports_candidate_not_universal_absence(self):
        result = run(assessment())
        self.assertIsNone(result["derivation_refused"])
        self.assertEqual(result["usul_result"]["conclusions"][OUTPUT]["status"],
                         "CONDITIONALLY_SUPPORTED")
        trace = result["exception_assessment_trace"][0]
        self.assertEqual(trace["finding"], "ABSENT_IN_DECLARED_SCOPE")
        self.assertTrue(trace["declared_scope_coverage_complete"])
        self.assertFalse(trace["real_world_absence_verified"])
        self.assertFalse(result["real_world_absence_verified"])
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["public_fatwa_authorized"])
        cited_ids = {c["evidence_id"] for c in result["conclusion_citations"][OUTPUT]["source_references"]}
        self.assertIn(SOURCE, cited_ids)
        self.assertEqual(result, run(assessment()))

    def test_detected_indication_blocks_rule(self):
        result = run(assessment("PRESENT", checked=["pilot:item1"]))
        self.assertEqual(result["usul_result"]["trace"][0]["status"], "BLOCKED_BY_EXCEPTION")
        self.assertEqual(result["usul_result"]["conclusions"][OUTPUT]["status"], "UNDETERMINED")
        self.assertTrue(result["exception_assessment_trace"][0]["checked_count"] == 1)

    def test_not_checked_never_means_false(self):
        result = run(assessment("NOT_CHECKED"))
        self.assertEqual(result["usul_result"]["trace"][0]["status"], "UNDETERMINED")
        self.assertEqual(result["exception_assessment_trace"][0]["checked_count"], 0)

    def test_partial_search_cannot_prove_absence(self):
        result = run(assessment(checked=["pilot:item1"]))
        self.assertEqual(result["derivation_refused"]["code"], "INVALID_EXCEPTION_ASSESSMENT")
        self.assertIsNone(result["usul_result"])

    def test_absence_with_zero_evidence_cannot_pass(self):
        result = run(assessment(evidence_ids=[]))
        self.assertEqual(result["derivation_refused"]["code"], "INVALID_EXCEPTION_ASSESSMENT")

    def test_fake_and_unverified_evidence_cannot_pass(self):
        fake = run(assessment(evidence_ids=["pilot:ghost"]))
        self.assertEqual(fake["derivation_refused"]["code"], "INVALID_EXCEPTION_ASSESSMENT")
        modified = example_bundle()
        modified["evidence"][2]["verification_status"] = "unverified"
        modified["evidence"][2]["verification_method"] = "unverified"
        result = build_and_run(
            modified, example_spec(modified), scenarios()["indicator_unknown"],
            require_semantic_binding=True, exception_assessments=assessment(),
            require_evidence_exceptions=True)
        self.assertEqual(result["derivation_refused"]["code"], "STRUCTURAL_VALIDATION_FAILED")

    def test_real_world_scope_is_explicitly_unsupported(self):
        result = run(assessment(kind="real_world"))
        self.assertEqual(result["derivation_refused"]["code"], "INVALID_EXCEPTION_ASSESSMENT")

    def test_duplicate_assessment_rejected(self):
        items = assessment() + assessment()
        result = run(items)
        self.assertEqual(result["derivation_refused"]["code"], "INVALID_EXCEPTION_ASSESSMENT")

    def test_direct_boolean_override_blocked_in_strict_mode(self):
        result = run(assessment(), facts=scenarios()["fully_declared_no_indicator"])
        self.assertEqual(result["derivation_refused"]["code"], "UNSCOPED_EXCEPTION_FACT_REFUSED")
        self.assertIsNone(result["usul_result"])

    def test_unsearched_with_claimed_evidence_is_rejected(self):
        result = run(assessment("NOT_CHECKED", evidence_ids=[SOURCE]))
        self.assertEqual(result["derivation_refused"]["code"], "INVALID_EXCEPTION_ASSESSMENT")

    def test_unknown_atom_or_rule_rejected(self):
        for field, value in (("rule_id", "pilot:nonexistent"),
                             ("exception_atom", "pilot:not-an-exception")):
            values = assessment()
            values[0][field] = value
            with self.subTest(field=field):
                self.assertEqual(run(values)["derivation_refused"]["code"],
                                 "INVALID_EXCEPTION_ASSESSMENT")

    def test_legacy_mode_remains_available_but_not_evidence_certified(self):
        result = build_and_run(
            example_bundle(), example_spec(example_bundle()),
            scenarios()["fully_declared_no_indicator"],
            require_semantic_binding=True)
        self.assertEqual(result["usul_result"]["conclusions"][OUTPUT]["status"],
                         "CONDITIONALLY_SUPPORTED")
        self.assertEqual(result["exception_evidence_policy"], "ALLOW_LEGACY_EXPLICIT_FACTS")
        self.assertEqual(result["exception_assessment_trace"], [])
        self.assertFalse(result["real_world_absence_verified"])

    def test_cli_strict_assessments_and_error_code(self):
        root = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as directory:
            paths = [Path(directory) / name for name in
                     ("bundle.json", "specs.json", "facts.json", "assessments.json")]
            documents = [example_bundle(), example_spec(example_bundle()),
                         scenarios()["indicator_unknown"], assessment()]
            for path, doc in zip(paths, documents):
                path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
            command = [sys.executable, "-m", "engines.usul.p0_bridge",
                       *(str(p) for p in paths[:3]),
                       "--require-semantic-binding",
                       "--require-evidence-exceptions",
                       "--exception-assessments", str(paths[3])]
            result = subprocess.run(command, cwd=root, capture_output=True,
                                    text=True, check=False)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["exception_assessment_trace"][0]["finding"],
                             "ABSENT_IN_DECLARED_SCOPE")
            documents[3][0]["scope"]["checked_items"] = ["pilot:item1"]
            paths[3].write_text(json.dumps(documents[3]), encoding="utf-8")
            failed = subprocess.run(command, cwd=root, capture_output=True,
                                    text=True, check=False)
            self.assertEqual(failed.returncode, 1, failed.stderr)
            self.assertEqual(json.loads(failed.stdout)["derivation_refused"]["code"],
                             "INVALID_EXCEPTION_ASSESSMENT")


if __name__ == "__main__":
    unittest.main()
