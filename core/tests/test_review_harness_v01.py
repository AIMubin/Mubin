"""R1 test-first review safety, not AI model review or source certification."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.review_harness import assess_packet, build_review_plan, validate_packet

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "research/review_harness/review-packet.example.json"
GOOD = "a" * 40
RUN = "https://github.com/AIMubin/Mubin/actions/runs/39102381920"
CHANNELS = ("code_security", "source_attribution", "methodology_falsifier")


def check(k, result="pass", head=GOOD):
    return dict(check_id=k, result=result, target_sha=head, claimed_run_url=RUN)


def attempt(channel, verdict="pass", findings=None, head=GOOD):
    return dict(channel=channel, attempt_id="attempt_"+channel,
                model_label="self-reported-model", target_sha=head,
                origin="unverified_external_submission", verdict=verdict,
                findings=[] if findings is None else findings)


def finding(severity="high"):
    return dict(finding_id="observed_bug", category="provenance",
                severity=severity, reproduction_note="Replace editorial attribution and rerun the validator")


class ReviewHarnessTests(unittest.TestCase):
    def setUp(self):
        self.packet = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def reject(self, packet):
        problems = validate_packet(packet)
        self.assertTrue(problems, "expected invalid untrusted input to fail closed")
        return problems

    def complete(self):
        p = copy.deepcopy(self.packet)
        p["deterministic_checks"] = [check(c) for c in
                                      ("unit_tests", "negative_tests", "schema_validation")]
        p["review_attempts"] = [attempt(c) for c in CHANNELS]
        return p

    def test_no_reviews_means_no_evidence(self):
        report = assess_packet(self.packet)
        self.assertTrue(report["valid_metadata"])
        self.assertEqual("T2", report["inferred_tier"])
        self.assertEqual("NEEDS_EVIDENCE", report["disposition"])
        self.assertEqual(3, len(report["missing_channels"]))
        self.assertEqual(3, len(report["missing_checks"]))
        self.assertFalse(report["eligible_for_auto_merge"])

    def test_complete_self_report_does_not_grant_any_authority(self):
        report = assess_packet(self.complete())
        self.assertEqual("PASS_SCOPED_UNVERIFIED", report["disposition"])
        self.assertTrue(report["claim_only_pass"])
        self.assertEqual(64, len(report["packet_sha256"]))
        for field in ("ci_head_verified", "reviewer_identity_verified",
                      "independent_execution_verified", "source_authenticity_verified",
                      "rights_verified", "scholarly_authority_verified", "human_review_performed",
                      "h392_gold_eligible", "eligible_for_engine", "eligible_for_release",
                      "eligible_for_auto_merge"):
            self.assertFalse(report[field], field)
        self.assertEqual(0, report["agent_invocations_performed"])

    def test_plan_is_not_agent_execution(self):
        report = build_review_plan(self.packet)
        self.assertTrue(report["valid_metadata"])
        self.assertEqual(CHANNELS, tuple(c["channel"] for c in report["tasks"]))
        self.assertEqual(0, report["agent_invocations_performed"])
        self.assertFalse(report["eligible_for_auto_merge"])

    def test_tier_zero_scoped_docs_only(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["changed_paths"] = ["docs/research/small-note.md"]
        p["candidate"]["impact_tags"] = ["documentation"]
        self.assertEqual("T0", assess_packet(p)["inferred_tier"])

    def test_tier_one_code_change(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["changed_paths"] = ["core/inference/validator.py"]
        p["candidate"]["impact_tags"] = ["code_change"]
        self.assertEqual("T1", assess_packet(p)["inferred_tier"])

    def test_tier_three_frozen_hadith(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["changed_paths"] = ["engines/hadith/qualification/H3.9.2/artifacts/HOLDOUT_MANIFEST.json"]
        p["candidate"]["impact_tags"] = ["documentation"]
        r = assess_packet(p)
        self.assertEqual("T3", r["inferred_tier"])
        self.assertEqual("ESCALATE_RISK", r["disposition"])

    def test_tier_three_sensitive_impacts_overrule_doc_path(self):
        for tag in ("source_rights", "real_human_identity", "authoritative_scholarly_decision", "frozen_holdout", "release_action"):
            with self.subTest(tag=tag):
                p = copy.deepcopy(self.packet)
                p["candidate"]["changed_paths"] = ["docs/research/new-note.md"]
                p["candidate"]["impact_tags"] = ["documentation", tag]
                self.assertEqual("T3", assess_packet(p)["inferred_tier"])

    def test_unknown_path_defaults_to_tier_two(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["changed_paths"] = ["secret.txt"]
        self.assertEqual("T2", assess_packet(p)["inferred_tier"])

    def test_adversarial_findings_escalate(self):
        p = self.complete()
        p["review_attempts"][0] = attempt("code_security", "fail", [finding("high")])
        r = assess_packet(p)
        self.assertEqual("ESCALATE_RISK", r["disposition"])
        self.assertEqual(["provenance"], r["findings_reported"])
        self.assertFalse(r["eligible_for_auto_merge"])

    def test_low_finding_is_reported_not_proven(self):
        p = self.complete()
        p["review_attempts"] = [attempt("code_security", "fail", [finding("low")])]
        self.assertEqual("FAIL_REPORTED", assess_packet(p)["disposition"])

    def test_failing_check_is_reported_not_reproduced(self):
        p = self.complete()
        p["deterministic_checks"][0]["result"] = "fail"
        result = assess_packet(p)
        self.assertEqual("FAIL_REPORTED", result["disposition"])
        self.assertEqual(["unit_tests"], result["check_failures_reported"])

    def test_review_disagreement_escalates(self):
        p = self.complete()
        p["review_attempts"][1]["verdict"] = "abstain"
        r = assess_packet(p)
        self.assertTrue(r["review_disagreement"])
        self.assertEqual("ESCALATE_RISK", r["disposition"])

    def test_unanimous_abstention_is_not_approval(self):
        p = self.complete()
        for r in p["review_attempts"]:
            r["verdict"] = "abstain"
        self.assertEqual("NEEDS_EVIDENCE", assess_packet(p)["disposition"])

    def test_unknown_check_not_a_pass(self):
        p = self.complete()
        p["deterministic_checks"][0]["result"] = "unknown"
        self.assertEqual("NEEDS_EVIDENCE", assess_packet(p)["disposition"])

    def test_missing_channel_not_silently_independent(self):
        p = self.complete()
        p["review_attempts"].pop()
        r = assess_packet(p)
        self.assertEqual(["methodology_falsifier"], r["missing_channels"])
        self.assertEqual("NEEDS_EVIDENCE", r["disposition"])

    def test_stale_check_sha_rejected(self):
        p = self.complete()
        p["deterministic_checks"][0]["target_sha"] = "b"*40
        self.reject(p)

    def test_stale_reviewer_sha_rejected(self):
        p = self.complete()
        p["review_attempts"][1]["target_sha"] = "b"*40
        self.reject(p)

    def test_identical_base_head_rejected(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["base_sha"] = GOOD
        self.reject(p)

    def test_duplicate_check_rejected(self):
        p = self.complete()
        p["deterministic_checks"].append(copy.deepcopy(p["deterministic_checks"][0]))
        self.reject(p)

    def test_duplicate_channel_rejected(self):
        p = self.complete()
        p["review_attempts"][2]["channel"] = "code_security"
        self.reject(p)

    def test_duplicate_attempt_id_rejected(self):
        p = self.complete()
        p["review_attempts"][2]["attempt_id"] = p["review_attempts"][0]["attempt_id"]
        self.reject(p)

    def test_pass_with_findings_is_inconsistent(self):
        p = self.complete()
        p["review_attempts"][0]["findings"] = [finding()]
        self.reject(p)

    def test_fail_without_finding_is_inconsistent(self):
        p = self.complete()
        p["review_attempts"][0]["verdict"] = "fail"
        self.reject(p)

    def test_duplicate_finding_id_rejected(self):
        p = self.complete()
        p["review_attempts"][0] = attempt("code_security", "fail", [finding(), finding()])
        self.reject(p)

    def test_duplicate_paths_rejected(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["changed_paths"] *= 2
        self.reject(p)

    def test_unsafe_paths_rejected(self):
        for name in ("../README.md", "/etc/passwd", "docs//note.md", ".github/./workflow", "docs/../README.md", "docs\\README.md", "docs/file\ntrick.md", "docs/\u202eevil.md"):
            with self.subTest(name=name):
                p = copy.deepcopy(self.packet)
                p["candidate"]["changed_paths"] = [name]
                self.reject(p)

    def test_duplicate_impact_tag_rejected(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["impact_tags"].append("code_change")
        self.reject(p)

    def test_cannot_add_false_authority_fields(self):
        for key,val in (("human_review_verified", True),("source_rights_granted", True),
                        ("automerge", True),("h392_gold_eligible", True)):
            with self.subTest(field=key):
                p = copy.deepcopy(self.packet)
                p[key] = val
                self.reject(p)

    def test_reviewer_cannot_claim_verified_origin(self):
        p = self.complete()
        p["review_attempts"][0]["origin"] = "independently_verified_human"
        self.reject(p)

    def test_custom_container_subclass_rejected(self):
        class Lie(dict):
            def __eq__(self, other): return True
        self.reject(Lie(self.packet))
        p = copy.deepcopy(self.packet)
        p["candidate"] = Lie(p["candidate"])
        self.reject(p)

    def test_shared_alias_rejected(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["impact_tags"] = p["candidate"]["changed_paths"]
        self.reject(p)

    def test_cycle_rejected(self):
        p = copy.deepcopy(self.packet)
        p["evil"] = p
        self.reject(p)

    def test_unicode_surrogate_rejected(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["changed_paths"] = ["docs/" + chr(0xD800) + ".md"]
        self.reject(p)

    def test_nonfinite_float_rejected(self):
        p = copy.deepcopy(self.packet)
        p["danger"] = float("nan")
        self.reject(p)

    def test_depth_bomb_rejected(self):
        p = copy.deepcopy(self.packet)
        deep = []
        current = deep
        for _ in range(29):
            sub=[]; current.append(sub); current=sub
        p["danger"] = deep
        self.reject(p)

    def test_invalid_candidate_fields_rejected(self):
        p = copy.deepcopy(self.packet)
        p["candidate"]["head_sha"] = "123"
        self.reject(p)

    def test_cli_assess_and_plan(self):
        for extra in ((), ("--mode", "plan")):
            with self.subTest(mode=extra):
                r=subprocess.run([sys.executable, "-m", "core.review_harness", str(FIXTURE),
                                  *extra, "--json"],cwd=ROOT,text=True,capture_output=True,timeout=15)
                self.assertEqual(0,r.returncode,r.stderr)
                j=json.loads(r.stdout)
                self.assertTrue(j["valid_metadata"])
                self.assertFalse(j["eligible_for_auto_merge"])

    def test_cli_duplicate_member_nan_and_bad_utf8(self):
        original = FIXTURE.read_text(encoding="utf-8")
        mutations = [
            original.replace('"contract": ', '"contract": "spoof", "contract": ', 1).encode(),
            original.replace('"review_attempts": []', '"review_attempts": NaN').encode(),
            b"\xff" + original.encode(),
        ]
        with tempfile.TemporaryDirectory() as td:
            path=Path(td)/"bad.json"
            for content in mutations:
                with self.subTest(kind=content[:25]):
                    path.write_bytes(content)
                    r=subprocess.run([sys.executable,"-m","core.review_harness",str(path),"--json"],
                                     cwd=ROOT,text=True,capture_output=True,timeout=15)
                    self.assertEqual(2,r.returncode,(r.stdout,r.stderr))

    def test_cli_symlink_and_oversize_blocked(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/"test.json"
            target.write_text(FIXTURE.read_text(encoding="utf-8"), encoding="utf-8")
            link=Path(td)/"link.json"
            link.symlink_to(target)
            for path in (link,):
                r=subprocess.run([sys.executable,"-m","core.review_harness",str(path),"--json"],
                                 cwd=ROOT,text=True,capture_output=True,timeout=15)
                self.assertEqual(2,r.returncode)
            target.write_bytes(b" " * (128*1024+1))
            r=subprocess.run([sys.executable,"-m","core.review_harness",str(target),"--json"],
                             cwd=ROOT,text=True,capture_output=True,timeout=15)
            self.assertEqual(2,r.returncode)

    def test_historical_defect_dataset_is_public_calibration_not_independent_discovery(self):
        doc=json.loads((ROOT/"research/review_harness/public-defect-challenges.json").read_text(encoding="utf-8"))
        self.assertEqual("public_dev_set_not_holdout", doc["split"])
        self.assertEqual(4, len(doc["cases"]))
        self.assertEqual({"U02-EDITORIAL", "U03-DIGEST", "U04-SPEAKER", "U05-RISK"},
                         {x["challenge_id"] for x in doc["cases"]})
        self.assertTrue(all(x["expected_category"] in ("provenance", "semantic_contract", "speaker_attribution", "methodology") for x in doc["cases"]))
        self.assertFalse(doc["independent_reviewer_model_executed"])
        self.assertFalse(doc["replayed_original_broken_code"])

if __name__ == "__main__":
    unittest.main()
