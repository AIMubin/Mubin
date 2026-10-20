"""Synthetic end-to-end semantic-bind and source-citation regression tests."""
import copy
import unittest

from engines.usul.p0_bridge import build_and_run
from engines.usul.semantic_binding import rule_fingerprint
from engines.usul.tests.test_p0_bridge import bundle, rule, spec, facts


def bound_scenario():
    p0_rule = rule("demo:rule1")
    data = bundle([p0_rule])
    executable = spec()
    executable["demo:rule1"]["binding"] = {
        "version": "0.1.0",
        "rule_sha256": rule_fingerprint(p0_rule),
        "preconditions": [{
            "label": "demo:precondition", "claim_id": "demo:c-premise1",
            "atom": "demo:premise", "truth": "true",
        }],
        "exceptions": [],
        "conclusion": {
            "claim_id": "demo:c-conclusion1",
            "atom": "demo:output", "truth": "true",
        },
    }
    return data, executable, facts(("demo:premise", "true"))


class BoundSourceCitationTests(unittest.TestCase):
    def test_full_source_attribution_and_binding_are_emitted(self):
        data, specs, asserted = bound_scenario()
        out = build_and_run(data, specs, asserted)
        self.assertIsNone(out["derivation_refused"])
        self.assertEqual(out["attribution"]["rules_rejected"], [])
        self.assertEqual(out["semantic_bindings"]["demo:rule1"]["status"],
                         "STRUCTURALLY_BOUND")
        self.assertEqual(out["usul_result"]["conclusions"]["demo:output"]["status"],
                         "CONDITIONALLY_SUPPORTED")
        self.assertFalse(out["semantic_equivalence_verified"])
        self.assertFalse(out["scholarly_verified"])
        self.assertFalse(out["public_fatwa_authorized"])
        citations = out["source_citations"]
        self.assertGreater(len(citations), 0)
        self.assertEqual({c["source_id"] for c in citations}, {"demo:src"})
        self.assertEqual({c["work_title"] for c in citations}, {"synthetic"})
        self.assertEqual({c["edition"] for c in citations}, {"demo"})
        self.assertIn("demo:ev1", [c["evidence_id"] for c in citations])
        self.assertIn("demo:ev2", [c["evidence_id"] for c in citations])
        self.assertTrue(all(not c["source_excerpt_reproduced"] for c in citations))
        self.assertTrue(all(not c["redistribution_permission_inferred"] for c in citations))

    def test_stale_rule_hash_fails_closed(self):
        data, specs, asserted = bound_scenario()
        data["rules"][0]["expression"] = "altered human prose after spec freeze"
        out = build_and_run(data, specs, asserted)
        self.assertEqual(out["attribution"]["rules_rejected"][0]["reason"],
                         "REJECTED_INVALID_SEMANTIC_BINDING")
        self.assertEqual(out["usul_result"]["conclusions"], {})

    def test_missing_or_reordered_clause_fails_closed(self):
        data, specs, asserted = bound_scenario()
        for mutate in (
            lambda x: x["demo:rule1"]["binding"]["preconditions"][0].update(
                {"label": "demo:unknown"}),
            lambda x: x["demo:rule1"]["binding"]["preconditions"][0].update(
                {"truth": "false"}),
            lambda x: x["demo:rule1"]["binding"].update({"preconditions": []}),
            lambda x: x["demo:rule1"]["binding"].update({"exceptions": [
                {"label": "demo:invented", "atom": "demo:exception",
                 "truth": "true", "source_evidence_ids": ["demo:ev1"]}]}),
        ):
            changed = copy.deepcopy(specs)
            mutate(changed)
            out = build_and_run(data, changed, asserted)
            self.assertEqual(out["attribution"]["rules_rejected"][0]["reason"],
                             "REJECTED_INVALID_SEMANTIC_BINDING")

    def test_fabricated_and_unrelated_claims_fail(self):
        data, specs, asserted = bound_scenario()
        for claim_id in ("demo:no-claim", "demo:c-conclusion1"):
            changed = copy.deepcopy(specs)
            changed["demo:rule1"]["binding"]["preconditions"][0]["claim_id"] = claim_id
            out = build_and_run(data, changed, asserted)
            self.assertEqual(out["attribution"]["rules_rejected"][0]["reason"],
                             "REJECTED_INVALID_SEMANTIC_BINDING")

    def test_unverified_bound_premise_evidence_cannot_pass(self):
        data, specs, asserted = bound_scenario()
        # P0 rejects the entire bundle before attempting a human/semantic
        # assertion about how the evidence ought to be interpreted.
        data["evidence"][1]["verification_status"] = "unverified"
        data["evidence"][1]["verification_method"] = "unverified"
        out = build_and_run(data, specs, asserted)
        self.assertEqual(out["derivation_refused"]["code"],
                         "STRUCTURAL_VALIDATION_FAILED")

    def test_legacy_stays_explicitly_unbound(self):
        data, _specs, asserted = bound_scenario()
        out = build_and_run(data, spec(), asserted)
        self.assertEqual(out["semantic_bindings"]["demo:rule1"]["status"],
                         "LEGACY_UNBOUND")
        self.assertFalse(out["semantic_bindings"]["demo:rule1"]["semantic_equivalence_verified"])
        self.assertFalse(out["external_source_authentication_verified"])


    def test_bound_cli_example_uses_metadata_citations_and_no_fatwa(self):
        import json
        import subprocess
        import sys
        from pathlib import Path
        repo = Path(__file__).resolve().parents[3]
        directory = repo / "engines" / "usul" / "examples"
        names = (
            "p0-bridge-demo-bundle.json",
            "p0-bridge-demo-bound-specs.json",
            "p0-bridge-demo-facts.json",
        )
        proc = subprocess.run(
            [sys.executable, "-m", "engines.usul.p0_bridge",
             *(str(directory / name) for name in names)],
            capture_output=True, text=True, cwd=repo, check=False)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        output = json.loads(proc.stdout)
        self.assertEqual(output["semantic_bindings"]["demo:rule1"]["status"],
                         "STRUCTURALLY_BOUND")
        self.assertTrue(output["source_citations"])
        self.assertEqual(output["usul_result"]["conclusions"]["demo:output"]["status"],
                         "CONDITIONALLY_SUPPORTED")
        self.assertFalse(output["scholarly_verified"])
        self.assertFalse(output["external_source_authentication_verified"])
        self.assertFalse(output["public_fatwa_authorized"])

    def test_strict_mode_rejects_legacy_rules_but_accepts_bound_sources(self):
        data, specs, asserted = bound_scenario()
        bound = build_and_run(data, specs, asserted, require_semantic_binding=True)
        self.assertEqual(bound["attribution"]["rules_rejected"], [])
        self.assertEqual(bound["binding_policy"], "REQUIRE_BOUND")
        self.assertEqual(bound["semantic_bindings"]["demo:rule1"]["status"],
                         "STRUCTURALLY_BOUND")
        old = build_and_run(data, spec(), asserted, require_semantic_binding=True)
        self.assertEqual(old["attribution"]["rules_rejected"][0]["reason"],
                         "REJECTED_UNBOUND_RULE")
        self.assertEqual(old["usul_result"]["conclusions"], {})

    def test_conclusion_citations_include_only_supporting_rules(self):
        data, specs, asserted = bound_scenario()
        # The source evidence on a rule which is NOT applicable should not
        # appear as backing for the accepted conclusion.
        extra = rule("demo:rule2", evidence=("demo:ev3",))
        data["rules"].append(extra)
        # P0 bundle needs a matching inference for a new rule; use a simpler
        # model with a single qualified rule and a supplemental unrelated fact.
        data, specs, asserted = bound_scenario()
        asserted.append({"atom": "demo:unrelated", "truth": "true",
                         "source_evidence_ids": ["demo:ev3"]})
        outcome = build_and_run(data, specs, asserted)
        all_ids = {c["evidence_id"] for c in outcome["source_citations"]}
        citations = outcome["conclusion_citations"]["demo:output"]
        direct_ids = {c["evidence_id"] for c in citations["source_references"]}
        self.assertIn("demo:ev3", all_ids)
        self.assertNotIn("demo:ev3", direct_ids)
        self.assertEqual(citations["scope"],
                         "RECORD_PROVENANCE_ONLY_NOT_SEMANTIC_ENTAILMENT")

    def test_strict_cli_succeeds_only_for_bound_example(self):
        import json
        import subprocess
        import sys
        from pathlib import Path
        repo = Path(__file__).resolve().parents[3]
        directory = repo / "engines" / "usul" / "examples"
        prefix = [sys.executable, "-m", "engines.usul.p0_bridge"]
        common = [str(directory / "p0-bridge-demo-bundle.json"),
                  str(directory / "p0-bridge-demo-facts.json")]
        good = subprocess.run(
            prefix + [common[0], str(directory / "p0-bridge-demo-bound-specs.json"),
                      common[1], "--require-semantic-binding"],
            capture_output=True, text=True, cwd=repo, check=False)
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        self.assertTrue(json.loads(good.stdout)["conclusion_citations"]["demo:output"]["source_references"])
        old = subprocess.run(
            prefix + [common[0], str(directory / "p0-bridge-demo-specs.json"),
                      common[1], "--require-semantic-binding"],
            capture_output=True, text=True, cwd=repo, check=False)
        self.assertEqual(old.returncode, 1, old.stdout + old.stderr)


if __name__ == "__main__":
    unittest.main()
