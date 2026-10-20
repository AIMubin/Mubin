"""P0↔U0.1 bridge: semantic positives, negative table, and integration proof.

All atoms are synthetic (demo:*). No Quran, hadith or legal claim is encoded.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

from engines.usul.p0_bridge import build_and_run

REPO = Path(__file__).resolve().parents[3]
EXCERPT = "synthetic excerpt"
DIGEST = hashlib.sha256(EXCERPT.encode("utf-8")).hexdigest()


def ev(evidence_id, verified=True):
    return {"id": evidence_id, "source_id": "demo:src", "locator": "p1",
            "excerpt": EXCERPT, "excerpt_sha256": DIGEST,
            "verification_status": "verified" if verified else "unverified",
            "verification_method": "exact_source_match" if verified else "unverified"}


def rule(rule_id, kind="deduction", status="machine_checkable", evidence=("demo:ev1",),
         methodology="demo:profile"):
    return {"id": rule_id, "methodology_id": methodology, "rule_type": kind,
            "expression": "free text; never interpreted as instructions",
            "preconditions": ["demo:precondition"], "exceptions": [],
            "source_evidence_ids": list(evidence), "formalization_status": status}


def bundle(rules=None, objections=None):
    """Build a structurally valid P0 bundle around the given rules."""
    rules = rules if rules is not None else [rule("demo:rule1")]
    groups = {}
    for rule_obj in rules:
        groups.setdefault(rule_obj["methodology_id"], []).append(rule_obj)
    methodologies, claims, inferences, proofs = [], [], [], []
    for index, (mid, group) in enumerate(sorted(groups.items()), start=1):
        methodologies.append({"id": mid, "label": f"synthetic profile {index}",
                              "version": "0.1.0", "source_evidence_ids": ["demo:ev1"]})
        inference_id = f"demo:inf{index}"
        claims.append({"id": f"demo:c-premise{index}", "statement": "synthetic premise",
                       "claim_type": "source_attributed", "conclusion_kind": "source_derived",
                       "evidence_ids": ["demo:ev2"], "modality": "actual",
                       "assessment_status": "no_recorded_objection"})
        claims.append({"id": f"demo:c-conclusion{index}", "statement": "synthetic conclusion",
                       "claim_type": "inferred", "conclusion_kind": "rule_derived",
                       "evidence_ids": ["demo:ev1"], "inference_id": inference_id,
                       "modality": "actual", "assessment_status": "no_recorded_objection"})
        inferences.append({"id": inference_id, "inference_kind": "deduction",
                           "methodology_id": mid,
                           "rule_ids": [r["id"] for r in group],
                           "premise_claim_ids": [f"demo:c-premise{index}"],
                           "conclusion_claim_id": f"demo:c-conclusion{index}",
                           "exception_checks": []})
        proofs.append({"id": f"demo:proof{index}",
                       "conclusion_claim_id": f"demo:c-conclusion{index}",
                       "inference_ids": [inference_id], "methodology_id": mid,
                       "verification_scope": "structural_only",
                       "verification_status": "structurally_checked"})
    return {
        "contract_version": "0.1.0",
        "sources": [{"id": "demo:src", "kind": "usul", "work_title": "synthetic",
                     "edition": "demo", "locator": "p1", "content_sha256": DIGEST}],
        "evidence": [ev("demo:ev1"), ev("demo:ev2"), ev("demo:ev3")],
        "methodologies": methodologies, "claims": claims, "rules": rules,
        "inferences": inferences, "objections": objections or [],
        "proofs": proofs, "historical_availability": [],
    }


def spec(rule_id="demo:rule1", premise="demo:premise", then="demo:output",
         truth="true", exceptions=()):
    return {rule_id: {"if_all": [{"atom": premise, "truth": "true"}],
                      "unless_any": [{"atom": e, "truth": "true"} for e in exceptions],
                      "then": {"atom": then, "truth": truth}}}


def facts(*items):
    return [{"atom": a, "truth": t, "source_evidence_ids": ["demo:ev2"]} for a, t in items]


class BridgeSemanticTests(unittest.TestCase):
    def test_1_proven_condition_applies(self):
        out = build_and_run(bundle([rule("demo:rule1")]), spec(),
                            facts(("demo:premise", "true")))
        self.assertEqual(out["usul_result"]["conclusions"]["demo:output"]["status"],
                         "CONDITIONALLY_SUPPORTED")
        self.assertEqual(out["usul_result"]["conclusions"]["demo:output"]["supported_truth"], "true")

    def test_2_missing_condition_undetermined(self):
        out = build_and_run(bundle([rule("demo:rule1")]), spec(), [])
        self.assertEqual(out["usul_result"]["conclusions"]["demo:output"]["status"], "UNDETERMINED")

    def test_3_sustained_exception_blocks(self):
        out = build_and_run(bundle([rule("demo:rule1")]),
                            spec(exceptions=("demo:exception",)),
                            facts(("demo:premise", "true"), ("demo:exception", "true")))
        self.assertEqual(out["usul_result"]["trace"][0]["status"], "BLOCKED_BY_EXCEPTION")

    def test_4_unknown_exception_undetermined(self):
        out = build_and_run(bundle([rule("demo:rule1")]),
                            spec(exceptions=("demo:exception",)),
                            facts(("demo:premise", "true")))
        self.assertEqual(out["usul_result"]["trace"][0]["status"], "UNDETERMINED")
        self.assertIn("demo:exception", out["usul_result"]["trace"][0]["unresolved_exceptions"])

    def test_5_open_objection_blocks(self):
        objection = {"id": "demo:obj1", "target_inference_id": "demo:inf1",
                     "objection_kind": "counterexample", "statement": "synthetic",
                     "evidence_ids": ["demo:ev3"], "status": "open"}
        scenario = bundle([rule("demo:rule1")], [objection])
        # P0 coherence: an open objection forces the target conclusion claim and
        # its proof out of the clean states.
        scenario["claims"][1]["assessment_status"] = "contested"
        scenario["proofs"][0]["verification_status"] = "undetermined"
        out = build_and_run(scenario, spec(), facts(("demo:premise", "true")))
        self.assertEqual(out["usul_result"]["trace"][0]["status"], "BLOCKED_BY_OBJECTION")

    def test_6_two_opposite_rules_contested(self):
        specs = {**spec("demo:rule1", then="demo:output", truth="true"),
                 **spec("demo:rule2", then="demo:output", truth="false")}
        out = build_and_run(bundle([rule("demo:rule1"), rule("demo:rule2")]), specs,
                            facts(("demo:premise", "true")))
        self.assertEqual(out["usul_result"]["conclusions"]["demo:output"]["status"], "CONTESTED")

    def test_7_methodology_mixing_refused(self):
        rules = [rule("demo:rule1"), rule("demo:rule2", methodology="demo:other")]
        out = build_and_run(bundle(rules), spec("demo:rule1"), [])
        self.assertEqual(out["derivation_refused"]["code"], "METHODOLOGY_MIXING_REFUSED")
        self.assertIsNone(out["usul_result"])

    def test_8_fact_with_unknown_evidence_rejected(self):
        shaky_facts = [{"atom": "demo:premise", "truth": "true",
                        "source_evidence_ids": ["demo:ghost"]}]
        out = build_and_run(bundle([rule("demo:rule1")]), spec(), shaky_facts)
        self.assertEqual(out["attribution"]["facts_rejected"][0]["reason"],
                         "REJECTED_UNKNOWN_EVIDENCE")
        self.assertEqual(out["usul_result"]["conclusions"]["demo:output"]["status"],
                         "UNDETERMINED")

    def test_9_rule_without_valid_source_is_never_qualified(self):
        broken = bundle([rule("demo:rule1")])
        broken["evidence"][0]["verification_status"] = "unverified"
        broken["evidence"][0]["verification_method"] = "unverified"
        out = build_and_run(broken, spec(), [])
        self.assertEqual(out["derivation_refused"]["code"], "STRUCTURAL_VALIDATION_FAILED")
        self.assertTrue(any("is not verified" in e for e in out["derivation_refused"]["errors"]))
        self.assertIsNone(out["usul_result"])
        # an unverified fact source is refused at the attribution layer instead
        shaky_facts = [{"atom": "demo:premise", "truth": "true",
                        "source_evidence_ids": ["demo:ev-shaky"]}]
        shaky_entry = {"id": "demo:ev-shaky", "source_id": "demo:src", "locator": "p9",
                       "excerpt": EXCERPT, "excerpt_sha256": DIGEST,
                       "verification_status": "unverified",
                       "verification_method": "unverified"}
        fresh = bundle([rule("demo:rule1")])
        broken2 = {**fresh, "evidence": fresh["evidence"] + [shaky_entry]}
        out2 = build_and_run(broken2, spec(), shaky_facts)
        self.assertEqual(out2["attribution"]["facts_rejected"][0]["reason"],
                         "REJECTED_UNVERIFIED_EVIDENCE")

    def test_10_derivation_cycle_refused(self):
        rules = [rule("demo:rule1"), rule("demo:rule2")]
        specs = {**spec("demo:rule1", premise="demo:b", then="demo:a"),
                 **spec("demo:rule2", premise="demo:a", then="demo:b")}
        out = build_and_run(bundle(rules), specs, [])
        self.assertEqual(out["derivation_refused"]["code"], "DERIVATION_CYCLE")
        self.assertIsNone(out["usul_result"])

    def test_11_qiyas_refused_explicitly(self):
        scenario = bundle([rule("demo:rule1", kind="qiyas")])
        scenario["inferences"][0]["inference_kind"] = "qiyas"
        scenario["inferences"][0]["qiyas_elements"] = {
            "asl": "demo:asl", "far": "demo:far",
            "hukm_al_asl": "demo:hukm", "illah": "demo:illah"}
        scenario["inferences"][0]["premise_claim_ids"] = [
            "demo:c-premise1", "demo:asl", "demo:far", "demo:hukm", "demo:illah"]
        scenario["claims"][1]["conclusion_kind"] = "qiyas_derived"
        scenario["proofs"][0]["verification_status"] = "undetermined"
        for element in ("asl", "far", "hukm", "illah"):
            scenario["claims"].append({
                "id": f"demo:{element}", "statement": f"synthetic {element}",
                "claim_type": "source_attributed", "conclusion_kind": "source_derived",
                "evidence_ids": ["demo:ev2"], "modality": "actual",
                "assessment_status": "no_recorded_objection"})
        out = build_and_run(scenario, spec(), [])
        self.assertEqual(out["structural_validation"]["passed"], True)
        self.assertEqual(out["attribution"]["rules_rejected"][0]["reason"],
                         "REJECTED_UNSUPPORTED_RULE_KIND")
        self.assertEqual(out["usul_result"]["conclusions"], {})
        self.assertEqual(out["usul_result"]["trace"], [])

    def test_12_structural_failure_refuses_derivation(self):
        broken = bundle([rule("demo:rule1")])
        broken["evidence"][0]["excerpt_sha256"] = "0" * 64
        out = build_and_run(broken, spec(), [])
        self.assertEqual(out["derivation_refused"]["code"], "STRUCTURAL_VALIDATION_FAILED")


class BridgeInvariantTests(unittest.TestCase):
    def test_scholarly_flags_never_flip(self):
        out = build_and_run(bundle([rule("demo:rule1")]), spec(),
                            facts(("demo:premise", "true")))
        self.assertFalse(out["usul_result"]["scholarly_verified"])
        self.assertFalse(out["usul_result"]["valid_juristic_ruling"])
        self.assertFalse(out["usul_result"]["public_fatwa_authorized"])
        self.assertFalse(out["scholarly_verified"])
        self.assertFalse(out["valid_juristic_ruling"])

    def test_expression_free_text_is_not_interpreted(self):
        hostile = rule("demo:rule1")
        hostile["expression"] = "__import__('os').system('echo pwned')"
        baseline = build_and_run(bundle([rule("demo:rule1")]), spec(),
                                 facts(("demo:premise", "true")))
        hostile_run = build_and_run(bundle([hostile]), spec(),
                                    facts(("demo:premise", "true")))
        self.assertEqual(baseline["usul_result"], hostile_run["usul_result"])

    def test_structural_only_rules_are_reported(self):
        out = build_and_run(bundle([rule("demo:rule1", status="draft")]), spec(), [])
        self.assertEqual(out["attribution"]["rules_structural_only"][0]["reason"],
                         "REPRESENTATION_ONLY_NO_EXECUTABLE_SPEC")
        self.assertNotIn("demo:output", out["usul_result"]["conclusions"])

    def test_reproducible_offline_identical_output(self):
        run = lambda: build_and_run(bundle([rule("demo:rule1")]), spec(),
                                    facts(("demo:premise", "true")))
        self.assertEqual(run(), run())
        self.assertTrue(run()["reproducible_offline"])

    def test_provenance_chain_records_methodology_and_evidence(self):
        out = build_and_run(bundle([rule("demo:rule1")]), spec(),
                            facts(("demo:premise", "true")))
        self.assertEqual(out["methodology_provenance"]["id"], "demo:profile")
        self.assertEqual(out["methodology_provenance"]["version"], "0.1.0")
        trace = out["usul_result"]["trace"][0]
        self.assertEqual(trace["rule_source_evidence_ids"], ["demo:ev1"])


class BridgeIntegrationTests(unittest.TestCase):
    def test_cli_end_to_end_deterministic(self):
        demo_dir = REPO / "engines" / "usul" / "examples"
        paths = [demo_dir / "p0-bridge-demo-bundle.json",
                 demo_dir / "p0-bridge-demo-specs.json",
                 demo_dir / "p0-bridge-demo-facts.json"]
        for path in paths:
            self.assertTrue(path.exists(), f"missing demo file: {path}")
        runs = [subprocess.run(
            [sys.executable, "-m", "engines.usul.p0_bridge",
             str(paths[0]), str(paths[1]), str(paths[2])],
            capture_output=True, text=True, cwd=str(REPO)) for _ in range(2)]
        for run in runs:
            self.assertEqual(run.returncode, 0, run.stderr)
        first, second = (json.loads(run.stdout) for run in runs)
        self.assertEqual(first, second)
        self.assertEqual(first["usul_result"]["conclusions"]["demo:output"]["status"],
                         "CONDITIONALLY_SUPPORTED")
        self.assertFalse(first["scholarly_verified"])


    def test_cli_rejection_returns_nonzero_not_false_success(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = [
                bundle([rule("demo:rule1")]),
                spec(),
                [{"atom": "demo:premise", "truth": "true",
                  "source_evidence_ids": ["demo:missing_evidence"]}],
            ]
            paths = [root / f"case{j}.json" for j in range(3)]
            for path, document in zip(paths, docs):
                path.write_text(json.dumps(document), encoding="utf-8")
            process = subprocess.run(
                [sys.executable, "-m", "engines.usul.p0_bridge",
                 *(str(p) for p in paths)],
                capture_output=True, text=True, cwd=str(REPO), check=False)
            self.assertEqual(process.returncode, 1, process.stderr)
            result = json.loads(process.stdout)
            self.assertEqual(result["attribution"]["facts_rejected"][0]["reason"],
                             "REJECTED_UNKNOWN_EVIDENCE")
            self.assertFalse(result["scholarly_verified"])

    def test_malformed_p0_bundle_refuses_without_crash(self):
        output = build_and_run({"contract_version": "0.1.0"}, {}, [])
        self.assertFalse(output["structural_validation"]["passed"])
        self.assertEqual(output["derivation_refused"]["code"], "STRUCTURAL_VALIDATION_FAILED")

    def test_bridge_rejects_invalid_spec_or_fact_collections(self):
        valid = bundle([rule("demo:rule1")])
        for specs, fact_rows in (([], []), ({}, {})):
            outcome = build_and_run(valid, specs, fact_rows)
            self.assertEqual(outcome["derivation_refused"]["code"], "INVALID_EXECUTION_INPUT")
            self.assertIsNone(outcome["usul_result"])


if __name__ == "__main__":
    unittest.main()
