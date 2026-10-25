"""R0.1d qualification ledger: synthetic axis-isolation and tamper tests."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from hashlib import sha256

from engines.quran.research.qualification import (
    QualificationError, append_decision, current_state, decisions_for,
    initialize_ledger, verify_ledger,
)
from qa.private_evidence_v01 import _VaultLock, _canonical

HEAD = "c" * 64


def decision(**overrides):
    base = {
        "decision_id": "review-0001",
        "axis": "scholarly",
        "source_id": "qe_ar_muyassar",
        "scope": {"full_source": True},
        "decision": "SOURCE_TEXT_INTEGRITY_REVIEWED",
        "reviewer": "independent-scholarly-reviewer",
        "reviewed_at_utc": "2026-10-24T12:00:00Z",
        "evidence_head_sha256": HEAD,
        "notes": "sample-based integrity review; not an edition authentication",
    }
    base.update(overrides)
    return base


class QualificationLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.ledger = self.base / "qualification-ledger.jsonl"
        self.anchor_dir = self.base / "anchors"
        self.key = self.base / "qualification.key"
        self.vault = self.base / "synthetic-vault"
        evidence_report = {
            "status": "EVIDENCE_REGISTRY_VERIFIED",
            "byte_integrity_verified": True,
            "head_entry_sha256": HEAD,
            "rights_status": "legal_review_pending",
            "source_authenticated": False, "scholarly_verified": False}
        evidence_mock = patch("engines.quran.research.qualification.evidence.verify_evidence",
                              return_value=evidence_report)
        self.mock_evidence = evidence_mock.start()
        self.addCleanup(evidence_mock.stop)
        self.initialized = False

    def initialize(self):
        report = initialize_ledger(
            self.ledger, self.anchor_dir, self.key,
            vault=self.vault,
            evidence_registry=self.base / "mock-evidence.jsonl",
            evidence_anchor_dir=self.base / "mock-evidence-anchor",
            evidence_key=self.base / "mock-evidence.key",
            sidecar_db=self.base / "synthetic-sidecar.db",
            operator="lead-operator")
        self.initialized = True
        return report

    def record(self, **overrides):
        if not self.initialized:
            self.initialize()
        return append_decision(
            self.ledger, self.anchor_dir, self.key,
            decision(**overrides), "lead-operator",
            evidence_registry=self.base / "mock-evidence.jsonl",
            evidence_anchor_dir=self.base / "mock-evidence-anchor",
            evidence_key=self.base / "mock-evidence.key",
            vault=self.vault,
            sidecar_db=self.base / "synthetic-sidecar.db")

    def test_axes_are_independent(self):
        self.record(axis="scholarly",
                    decision="SOURCE_TEXT_INTEGRITY_REVIEWED")
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "rights", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault),
                         "legal_review_pending")
        self.record(axis="rights", decision="INTERNAL_USE_CLEARED",
                    decision_id="review-0002")
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "scholarly", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault),
                         "SOURCE_TEXT_INTEGRITY_REVIEWED")
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "rights", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault),
                         "INTERNAL_USE_CLEARED")
        report = verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)
        self.assertEqual(report["entries"], 2)
        self.assertFalse(report["publication_granted"])

    def test_absent_decisions_leave_pending_defaults(self):
        # Hardened contract: queries require an explicitly initialized ledger.
        self.initialize()
        self.assertEqual(current_state(self.ledger, "qe_ar_yaseer", "scholarly", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault),
                         "UNREVIEWED")
        self.assertEqual(current_state(self.ledger, "qe_ar_yaseer", "rights", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault),
                         "legal_review_pending")

    def test_cross_axis_decision_refused(self):
        with self.assertRaisesRegex(QualificationError, "CROSS_AXIS_DECISION_REFUSED"):
            self.record(axis="rights", decision="SOURCE_TEXT_INTEGRITY_REVIEWED",
                        decision_id="review-x1")

    def test_record_quarantine_scoped_without_source_wide_effect(self):
        self.record(axis="scholarly", decision_id="review-q1",
                    decision="SOURCE_TEXT_INTEGRITY_REVIEWED")
        self.record(axis="scholarly", decision_id="review-q2",
                    decision="RECORD_QUARANTINED",
                    scope={"record_coordinates": ["2:1", "2:2"]})
        states = decisions_for(self.ledger, "qe_ar_muyassar", "scholarly", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault)
        self.assertEqual(len(states), 2)
        self.assertEqual(states[-1]["scope"]["record_coordinates"], ["2:1", "2:2"])
        # latest decision wins per axis; the quarantine is scoped and additive
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "scholarly", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault),
                         "SOURCE_TEXT_INTEGRITY_REVIEWED")
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "scholarly", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault, reference="2:1"),
                         "RECORD_QUARANTINED")
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "scholarly", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault, reference="2:3"),
                         "SOURCE_TEXT_INTEGRITY_REVIEWED")
        # a different source is unaffected
        self.assertEqual(current_state(self.ledger, "qe_ar_yaseer", "scholarly", anchor_dir=self.anchor_dir, key_file=self.key,vault=self.vault),
                         "UNREVIEWED")

    def test_source_rejection_takes_precedence_over_record_quarantine(self):
        self.record(decision_id="review-r1", decision="SOURCE_REJECTED")
        self.record(decision_id="review-r2", decision="RECORD_QUARANTINED",
                    scope={"record_coordinates":["2:1"]})
        self.assertEqual("SOURCE_REJECTED",current_state(
            self.ledger,"qe_ar_muyassar","scholarly",
            anchor_dir=self.anchor_dir,key_file=self.key,vault=self.vault,reference="2:1"))
        self.assertEqual("SOURCE_REJECTED",current_state(
            self.ledger,"qe_ar_muyassar","scholarly",
            anchor_dir=self.anchor_dir,key_file=self.key,vault=self.vault,reference="2:3"))

    def test_self_review_and_system_reviewer_refused(self):
        for reviewer in ("system", "automation", "llm"):
            with self.assertRaisesRegex(QualificationError, "REVIEWER_INVALID"):
                self.record(reviewer=reviewer)

    def test_duplicate_decision_id_refused(self):
        self.record()
        with self.assertRaisesRegex(QualificationError,
                                    "DECISION_ID_ALREADY_RECORDED"):
            self.record()

    def test_evidence_head_binding_required(self):
        with self.assertRaisesRegex(QualificationError, "EVIDENCE_HEAD_INVALID"):
            self.record(evidence_head_sha256="not-a-sha")

    def test_chain_tamper_detected(self):
        self.record()
        lines = self.ledger.read_text(encoding="utf-8").splitlines()
        body = json.loads(lines[0])
        body["payload"]["decision"] = "SOURCE_REJECTED"
        lines[0] = json.dumps(body, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
        self.ledger.write_bytes((chr(10).join(lines) + chr(10)).encode("utf-8"))
        with self.assertRaisesRegex(QualificationError, "LEDGER_CHAIN_INVALID"):
            verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)

    def test_forged_head_without_key_refused(self):
        self.record()
        anchor = self.anchor_dir / "qualification-ledger.qualification-head-anchor.json"
        body = json.loads(anchor.read_text(encoding="utf-8"))
        body["head_entry_sha256"] = "d" * 64
        anchor.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True),
                          encoding="utf-8")
        with self.assertRaisesRegex(QualificationError,
                                    "HEAD_ANCHOR_(MAC_INVALID|HEAD_MISMATCH)"):
            verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)

    def test_recomputed_history_cannot_be_legitimized_by_append(self):
        self.record()
        anchor=(self.anchor_dir/"qualification-ledger.qualification-head-anchor.json")
        original_anchor=anchor.read_bytes()
        item=json.loads(self.ledger.read_text(encoding="utf-8").strip())
        item["payload"]["decision"]="SOURCE_REJECTED"
        item["entry_sha256"]=sha256(_canonical({k:v for k,v in item.items()
                                                  if k!="entry_sha256"})).hexdigest()
        forged=_canonical(item)+bytes([10])
        self.ledger.write_bytes(forged)
        with self.assertRaisesRegex(QualificationError,"HEAD_ANCHOR_HEAD_MISMATCH"):
            self.record(decision_id="review-0002")
        self.assertEqual(forged,self.ledger.read_bytes())
        self.assertEqual(original_anchor,anchor.read_bytes())

    def test_missing_lf_fails_closed_before_new_append(self):
        self.record()
        anchor=self.anchor_dir/"qualification-ledger.qualification-head-anchor.json"
        old_anchor=anchor.read_bytes()
        self.ledger.write_bytes(self.ledger.read_bytes().rstrip(bytes([10])))
        with self.assertRaisesRegex(QualificationError,"LEDGER_NONCANONICAL_BYTES"):
            self.record(decision_id="review-0002")
        self.assertEqual(old_anchor,anchor.read_bytes())

    def test_read_state_refuses_tampered_unattested_ledger(self):
        self.record()
        anchor=self.anchor_dir/"qualification-ledger.qualification-head-anchor.json"
        anchor.unlink()
        with self.assertRaisesRegex(QualificationError,"HEAD_ANCHOR_MISSING"):
            current_state(self.ledger,"qe_ar_muyassar","rights",
                          anchor_dir=self.anchor_dir,key_file=self.key,vault=self.vault)
        with self.assertRaisesRegex(QualificationError,"HEAD_ANCHOR_MISSING"):
            decisions_for(self.ledger,"qe_ar_muyassar",
                          anchor_dir=self.anchor_dir,key_file=self.key,vault=self.vault)

    def test_actual_r01a_head_must_match_decision(self):
        self.mock_evidence.return_value={
            "status":"EVIDENCE_REGISTRY_VERIFIED",
            "byte_integrity_verified":True,"head_entry_sha256":"d"*64,
            "rights_status":"legal_review_pending",
            "source_authenticated":False,"scholarly_verified":False}
        with self.assertRaisesRegex(QualificationError,"EVIDENCE_HEAD_NOT_ATTESTED"):
            self.record()
        self.assertFalse(self.ledger.exists())

    def test_human_reviewer_name_cannot_be_operator_name(self):
        with self.assertRaisesRegex(QualificationError,"SELF_REVIEW_REFUSED"):
            self.record(reviewer="lead-operator")

    def test_critical_scope_validation(self):
        for scope in ({"full_source":False}, {"record_coordinates":["115:1"]},
                      {"record_coordinates":["2:999"]}, {"record_coordinates":["2:1","2:1"]}):
            with self.subTest(scope=scope),self.assertRaisesRegex(
                    QualificationError,"SCOPE_INVALID|SCOPE_COORDINATES_INVALID"):
                self.record(decision="RECORD_QUARANTINED",scope=scope)
        with self.assertRaisesRegex(QualificationError,"SCOPE_INVALID"):
            self.record(decision="INTERNAL_USE_CLEARED",axis="rights",
                        scope={"record_coordinates":["2:1"]})
        with self.assertRaisesRegex(QualificationError,"SOURCE_NOT_ALLOWLISTED"):
            self.record(source_id="fabricated_book_v1")

    def test_lost_key_is_not_regenerated_and_verify_is_read_only(self):
        self.record()
        self.key.unlink()
        with self.assertRaisesRegex(QualificationError,"LEDGER_KEY_UNAVAILABLE"):
            verify_ledger(self.ledger,self.anchor_dir,self.key,vault=self.vault)
        self.assertFalse(self.key.exists())
        with self.assertRaisesRegex(QualificationError,"LEDGER_KEY_UNAVAILABLE"):
            self.record(decision_id="review-0002")
        self.assertFalse(self.key.exists())

    def test_hmac_anchor_inside_vault_refused_without_creating_ledger(self):
        inside = self.vault / "nested" / "anchors"
        with self.assertRaisesRegex(QualificationError,
                                    "QUALIFICATION_SECRET_IN_VAULT_REFUSED"):
            append_decision(
                self.ledger,inside,self.key,decision(),"lead-operator",
                evidence_registry=self.base/"mock-evidence.jsonl",
                evidence_anchor_dir=self.base/"mock-evidence-anchor",
                evidence_key=self.base/"mock-evidence.key",
                vault=self.vault,sidecar_db=self.base/"synthetic-sidecar.db")
        self.assertFalse(inside.exists())
        self.assertFalse(self.ledger.exists())

    def test_hmac_key_inside_vault_refused_for_append_and_verify(self):
        inside = self.vault / "private" / "qualification.key"
        with self.assertRaisesRegex(QualificationError,
                                    "QUALIFICATION_SECRET_IN_VAULT_REFUSED"):
            append_decision(
                self.ledger,self.anchor_dir,inside,decision(),"lead-operator",
                evidence_registry=self.base/"mock-evidence.jsonl",
                evidence_anchor_dir=self.base/"mock-evidence-anchor",
                evidence_key=self.base/"mock-evidence.key",
                vault=self.vault,sidecar_db=self.base/"synthetic-sidecar.db")
        self.assertFalse(inside.exists())
        self.record()
        with self.assertRaisesRegex(QualificationError,
                                    "QUALIFICATION_SECRET_IN_VAULT_REFUSED"):
            verify_ledger(self.ledger,self.anchor_dir,inside,vault=self.vault)
        with self.assertRaisesRegex(QualificationError,
                                    "QUALIFICATION_SECRET_IN_VAULT_REFUSED"):
            current_state(self.ledger,"qe_ar_muyassar","scholarly",
                          anchor_dir=self.anchor_dir,key_file=inside,vault=self.vault)

    def test_append_refused_without_explicit_initialization(self):
        # A fresh location with no continuity anchor must not silently
        # start decision history: explicit init is mandatory. Bypass the
        # auto-initializing record() helper to prove the refusal.
        with self.assertRaisesRegex(QualificationError, "LEDGER_NOT_INITIALIZED"):
            append_decision(
                self.ledger, self.anchor_dir, self.key,
                decision(), "lead-operator",
                evidence_registry=self.base / "mock-evidence.jsonl",
                evidence_anchor_dir=self.base / "mock-evidence-anchor",
                evidence_key=self.base / "mock-evidence.key",
                vault=self.vault,
                sidecar_db=self.base / "synthetic-sidecar.db")
        self.assertFalse(self.initialized)

    def test_double_initialization_refused(self):
        self.initialize()
        with self.assertRaisesRegex(QualificationError, "LEDGER_ALREADY_INITIALIZED"):
            self.initialize()

    def test_history_deletion_refused_after_real_appends(self):
        self.record()
        self.record(decision_id="review-0002", axis="rights",
                    decision="INTERNAL_USE_CLEARED")
        # delete BOTH the ledger and the head anchor (the flagged attack)
        self.ledger.unlink()
        (self.anchor_dir /
         "qualification-ledger.qualification-head-anchor.json").unlink()
        with self.assertRaisesRegex(QualificationError,
                                    "LEDGER_HISTORY_DESTROYED_REFUSED"):
            self.record(decision_id="review-0003", axis="rights",
                        decision="NOT_CLEARED")
        with self.assertRaisesRegex(QualificationError,
                                    "LEDGER_HISTORY_DESTROYED_REFUSED"):
            verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)

    def test_forged_continuity_body_refused(self):
        self.initialize()
        continuity = self.anchor_dir / "qualification-ledger.continuity-anchor.json"
        body = json.loads(continuity.read_text(encoding="utf-8"))
        body["sequence"] = 7
        continuity.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True),
                              encoding="utf-8")
        # A continuity anchor failing its HMAC is treated as absent:
        # the append then refuses as not-initialized (fail-closed).
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_ANCHOR_INVALID"):
            self.record()

    def test_continuity_inside_vault_refused(self):
        inside = self.vault / "anchors"
        with self.assertRaisesRegex(QualificationError,
                                    "QUALIFICATION_SECRET_IN_VAULT_REFUSED"):
            initialize_ledger(
                self.ledger, inside, self.key,
                vault=self.vault,
                evidence_registry=self.base / "mock-evidence.jsonl",
                evidence_anchor_dir=self.base / "mock-evidence-anchor",
                evidence_key=self.base / "mock-evidence.key",
                sidecar_db=self.base / "synthetic-sidecar.db",
                operator="lead-operator")


    def test_nonempty_ledger_refuses_missing_continuity(self):
        self.record()
        old_ledger = self.ledger.read_bytes()
        old_head = (self.anchor_dir /
                    "qualification-ledger.qualification-head-anchor.json").read_bytes()
        (self.anchor_dir / "qualification-ledger.continuity-anchor.json").unlink()
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_ANCHOR_INVALID"):
            verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_ANCHOR_INVALID"):
            current_state(self.ledger, "qe_ar_muyassar", "scholarly",
                          anchor_dir=self.anchor_dir, key_file=self.key, vault=self.vault)
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_ANCHOR_INVALID"):
            self.record(decision_id="review-0002")
        self.assertEqual(self.ledger.read_bytes(), old_ledger)
        self.assertEqual((self.anchor_dir /
                          "qualification-ledger.qualification-head-anchor.json").read_bytes(),
                         old_head)

    def test_rollback_of_ledger_and_head_detected(self):
        self.record()
        head_path = self.anchor_dir / "qualification-ledger.qualification-head-anchor.json"
        first_ledger = self.ledger.read_bytes()
        first_head = head_path.read_bytes()
        self.record(decision_id="review-0002", axis="rights",
                    decision="INTERNAL_USE_CLEARED")
        self.ledger.write_bytes(first_ledger)
        head_path.write_bytes(first_head)
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_HEAD_MISMATCH"):
            verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_HEAD_MISMATCH"):
            self.record(decision_id="review-0003")

    def test_rollback_of_continuity_witness_detected(self):
        self.record()
        path = self.anchor_dir / "qualification-ledger.continuity-anchor.json"
        old = path.read_bytes()
        self.record(decision_id="review-0002", axis="rights",
                    decision="INTERNAL_USE_CLEARED")
        path.write_bytes(old)
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_HEAD_MISMATCH"):
            verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_HEAD_MISMATCH"):
            self.record(decision_id="review-0003")

    def test_bad_hmac_type_is_refused_as_untrusted_continuity(self):
        self.record()
        path = self.anchor_dir / "qualification-ledger.continuity-anchor.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        body["continuity_hmac"] = 10
        path.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_ANCHOR_INVALID"):
            verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)

    def test_bad_sequence_type_is_refused_as_untrusted_continuity(self):
        self.record()
        path = self.anchor_dir / "qualification-ledger.continuity-anchor.json"
        body = json.loads(path.read_text(encoding="utf-8"))
        body["sequence"] = "two"
        path.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaisesRegex(QualificationError, "CONTINUITY_ANCHOR_INVALID"):
            verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)

    def test_initialize_rejects_inconsistent_evidence_flags(self):
        self.mock_evidence.return_value = {
            "status": "EVIDENCE_REGISTRY_VERIFIED",
            "byte_integrity_verified": False,
            "head_entry_sha256": HEAD,
            "rights_status": "legal_review_pending",
            "source_authenticated": False, "scholarly_verified": False}
        with self.assertRaisesRegex(QualificationError, "EVIDENCE_NOT_QUALIFIED"):
            self.initialize()
        self.assertFalse(self.key.exists())
        self.assertFalse(
            (self.anchor_dir / "qualification-ledger.continuity-anchor.json").exists())

    def test_cli_has_explicit_initialize(self):
        from contextlib import redirect_stdout
        from io import StringIO
        from engines.quran.research.qualification import main
        out = StringIO()
        with redirect_stdout(out):
            code = main([
                "init", "--ledger", str(self.ledger),
                "--anchor-dir", str(self.anchor_dir),
                "--key-file", str(self.key),
                "--operator", "lead-operator",
                "--evidence-registry", str(self.base / "mock-evidence.jsonl"),
                "--evidence-anchor-dir", str(self.base / "mock-evidence-anchor"),
                "--evidence-key", str(self.base / "mock-evidence.key"),
                "--vault", str(self.vault),
                "--sidecar-db", str(self.base / "synthetic-sidecar.db")])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out.getvalue())["status"],
                         "QUALIFICATION_LEDGER_INITIALIZED")

    def test_no_publication_authority_ever_reported(self):
        self.record()
        report = verify_ledger(self.ledger, self.anchor_dir, self.key, vault=self.vault)
        for flag in ("publication_granted", "scholarly_verified_globally",
                     "juristic_inference_allowed", "public_fatwa_authorized"):
            self.assertFalse(report[flag])


if __name__ == "__main__":
    unittest.main()
