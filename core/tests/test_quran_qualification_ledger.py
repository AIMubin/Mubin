"""R0.1d qualification ledger: synthetic axis-isolation and tamper tests."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from engines.quran.research.qualification import (
    QualificationError, append_decision, current_state, decisions_for,
    verify_ledger,
)
from qa.private_evidence_v01 import _VaultLock

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

    def record(self, **overrides):
        return append_decision(self.ledger, self.anchor_dir, self.key,
                               decision(**overrides), "lead-operator")

    def test_axes_are_independent(self):
        self.record(axis="scholarly",
                    decision="SOURCE_TEXT_INTEGRITY_REVIEWED")
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "rights"),
                         "legal_review_pending")
        self.record(axis="rights", decision="INTERNAL_USE_CLEARED",
                    decision_id="review-0002")
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "scholarly"),
                         "SOURCE_TEXT_INTEGRITY_REVIEWED")
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "rights"),
                         "INTERNAL_USE_CLEARED")
        report = verify_ledger(self.ledger, self.anchor_dir, self.key)
        self.assertEqual(report["entries"], 2)
        self.assertFalse(report["publication_granted"])

    def test_absent_decisions_leave_pending_defaults(self):
        self.assertEqual(current_state(self.ledger, "qe_ar_yaseer", "scholarly"),
                         "UNREVIEWED")
        self.assertEqual(current_state(self.ledger, "qe_ar_yaseer", "rights"),
                         "legal_review_pending")

    def test_cross_axis_decision_refused(self):
        with self.assertRaisesRegex(QualificationError, "AXIS_INVALID|DECISION_NOT"):
            self.record(axis="rights", decision="SOURCE_TEXT_INTEGRITY_REVIEWED",
                        decision_id="review-x1")

    def test_record_quarantine_scoped_without_source_wide_effect(self):
        self.record(axis="scholarly", decision_id="review-q1",
                    decision="SOURCE_TEXT_INTEGRITY_REVIEWED")
        self.record(axis="scholarly", decision_id="review-q2",
                    decision="RECORD_QUARANTINED",
                    scope={"record_coordinates": ["2:1", "2:2"]})
        states = decisions_for(self.ledger, "qe_ar_muyassar", "scholarly")
        self.assertEqual(len(states), 2)
        self.assertEqual(states[-1]["scope"]["record_coordinates"], ["2:1", "2:2"])
        # latest decision wins per axis; the quarantine is scoped and additive
        self.assertEqual(current_state(self.ledger, "qe_ar_muyassar", "scholarly"),
                         "RECORD_QUARANTINED")
        # a different source is unaffected
        self.assertEqual(current_state(self.ledger, "qe_ar_yaseer", "scholarly"),
                         "UNREVIEWED")

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
        self.ledger.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(QualificationError, "LEDGER_CHAIN_INVALID"):
            verify_ledger(self.ledger, self.anchor_dir, self.key)

    def test_forged_head_without_key_refused(self):
        self.record()
        anchor = self.anchor_dir / "qualification-ledger.qualification-head-anchor.json"
        body = json.loads(anchor.read_text(encoding="utf-8"))
        body["head_entry_sha256"] = "d" * 64
        anchor.write_text(json.dumps(body, ensure_ascii=False, sort_keys=True),
                          encoding="utf-8")
        with self.assertRaisesRegex(QualificationError,
                                    "HEAD_ANCHOR_(MAC_INVALID|HEAD_MISMATCH)"):
            verify_ledger(self.ledger, self.anchor_dir, self.key)

    def test_no_publication_authority_ever_reported(self):
        self.record()
        report = verify_ledger(self.ledger, self.anchor_dir, self.key)
        for flag in ("publication_granted", "scholarly_verified_globally",
                     "juristic_inference_allowed", "public_fatwa_authorized"):
            self.assertFalse(report[flag])


if __name__ == "__main__":
    unittest.main()
