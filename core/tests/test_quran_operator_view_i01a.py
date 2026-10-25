"""I0.1a operator-facing integration: synthetic-only gate and nonpromotion tests."""
from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import unittest
from unittest.mock import patch

from engines.quran.research import qualification as qual
from engines.quran.research.operator_view import (
    CONTRACT, OperatorViewError, main, operator_lookup,
)
from engines.quran.research.private_adapters import ResearchAdapterError

HEAD = "a" * 64
LEDGER_HEAD = "b" * 64
NEW_LEDGER_HEAD = "c" * 64


class FakeAdapters:
    def __init__(self):
        self.head = HEAD
        self.head_calls = 0
        self.change_after_second = False

    def evidence_head(self):
        self.head_calls += 1
        if self.change_after_second and self.head_calls >= 3:
            return "d" * 64
        return self.head

    def corpus_sources(self):
        return [{"source_id": "qe_ar_muyassar",
                 "source_kind": "tafsir", "adapter": "corpus"}]

    def sidecar_sources(self):
        return [{"source_id": "tafsir_tabary",
                 "source_kind": "tafsir", "adapter": "sidecar"}]

    def lookup(self, reference, source_id, *, adapter, include_text=False):
        if include_text:
            raise AssertionError("private text must not be fetched")
        return {"text": "DO-NOT-EXPOSE-PRIVATE-TEXT",
                "footnotes": "DO-NOT-EXPOSE-FOOTNOTES"}


def decision(axis="scholarly", status="SOURCE_TEXT_INTEGRITY_REVIEWED",
             sha=HEAD, scope=None):
    return {"axis": axis, "decision": status,
            "scope": scope or {"full_source": True},
            "evidence_head_sha256": sha}


class OperatorViewTests(unittest.TestCase):
    def setUp(self):
        self.adapters = FakeAdapters()
        self.patch_verify = patch.object(qual, "verify_ledger", return_value={
            "status": "QUALIFICATION_LEDGER_VERIFIED",
            "head_entry_sha256": LEDGER_HEAD, "entries": 0})
        self.patch_decisions = patch.object(qual, "decisions_for", return_value=[])
        self.mock_verify = self.patch_verify.start()
        self.mock_decisions = self.patch_decisions.start()
        self.addCleanup(self.patch_verify.stop)
        self.addCleanup(self.patch_decisions.stop)

    def lookup(self, **kwargs):
        return operator_lookup(
            self.adapters, "2:1", ledger="/unused/ledger",
            qualification_anchor_dir="/unused/anchors",
            qualification_key="/unused/key", vault="/unused/vault", **kwargs)

    def test_two_adapters_and_no_text_or_authority(self):
        result = self.lookup()
        self.assertEqual(result["contract"], CONTRACT)
        self.assertEqual(result["reference"], "2:1")
        self.assertEqual(result["research_mode"], "metadata_only")
        self.assertEqual(result["evidence_head_sha256"], HEAD)
        self.assertEqual(len(result["sources"]), 2)
        self.assertEqual({s["adapter"] for s in result["sources"]},
                         {"corpus", "sidecar"})
        self.assertNotIn("DO-NOT-EXPOSE", json.dumps(result))
        self.assertNotIn('"text":', json.dumps(result))
        for row in result["sources"]:
            self.assertEqual(row["scholarly_decision_state"], "UNREVIEWED")
            self.assertEqual(row["rights_decision_state"], "legal_review_pending")
            self.assertFalse(row["text_included"])
        for name in ("source_authenticated", "scholarly_verified",
                     "rights_verified", "publication_allowed",
                     "juristic_inference_allowed", "public_fatwa_authorized",
                     "redistribution_approved", "p1_admitted"):
            self.assertFalse(result[name])
        self.assertEqual(result["public_quran_reader"], "separate_loopback_only")
        self.assertEqual(result["tafsir_catalog"], "external_navigation_metadata_only")
        self.assertEqual(self.mock_verify.call_count, 2)

    def test_r01d_scholarly_and_rights_states_are_independent(self):
        self.mock_decisions.side_effect = lambda *args, **kwargs: [
            decision(), decision(axis="rights", status="INTERNAL_USE_CLEARED")]
        report = self.lookup()
        for row in report["sources"]:
            self.assertEqual(row["scholarly_decision_state"],
                             "SOURCE_TEXT_INTEGRITY_REVIEWED")
            self.assertEqual(row["rights_decision_state"], "INTERNAL_USE_CLEARED")
            self.assertEqual(row["matching_evidence_decisions"], 2)
        self.assertFalse(report["publication_allowed"])
        self.assertFalse(report["rights_verified"])
        self.assertFalse(report["scholarly_verified"])

    def test_stale_positive_decision_never_promotes(self):
        self.mock_decisions.return_value = [
            decision(sha="f" * 64),
            decision(axis="rights", status="INTERNAL_USE_CLEARED", sha="f" * 64)]
        row = self.lookup()["sources"][0]
        self.assertEqual(row["scholarly_decision_state"], "UNREVIEWED")
        self.assertEqual(row["rights_decision_state"], "legal_review_pending")
        self.assertEqual(row["matching_evidence_decisions"], 0)
        self.assertTrue(row["historical_evidence_decisions_present"])

    def test_rejection_and_quarantine_remain_conservative_after_evidence_update(self):
        self.mock_decisions.return_value = [
            decision(status="SOURCE_REJECTED", sha="f" * 64),
            decision(status="RECORD_QUARANTINED", sha="f" * 64,
                     scope={"record_coordinates": ["2:1"]}),
            decision(axis="rights", status="NOT_CLEARED", sha="f" * 64),
            decision(status="SOURCE_TEXT_INTEGRITY_REVIEWED"),
            decision(axis="rights", status="INTERNAL_USE_CLEARED")]
        row = self.lookup()["sources"][0]
        self.assertEqual(row["scholarly_decision_state"], "SOURCE_REJECTED")
        self.assertEqual(row["rights_decision_state"], "NOT_CLEARED")
        self.assertTrue(row["historical_evidence_decisions_present"])

    def test_coordinate_quarantine_stays_per_record(self):
        # Qualification.decisions_for(reference=...) has already filtered
        # nonmatching coordinates; never inject them from the caller.
        self.mock_decisions.return_value = [
            decision(status="RECORD_QUARANTINED",
                     scope={"record_coordinates": ["2:1"]})]
        row = self.lookup()["sources"][0]
        self.assertEqual(row["scholarly_decision_state"], "RECORD_QUARANTINED")
        self.assertEqual(self.mock_decisions.call_args.kwargs["reference"], "2:1")

    def test_filter_reaches_source_adapters(self):
        rows = self.lookup(adapter_filter="corpus")["sources"]
        self.assertEqual([s["adapter"] for s in rows], ["corpus"])

    def test_invalid_reference_rejected_before_retrieval(self):
        with self.assertRaises(qual.QualificationError):
            operator_lookup(self.adapters, "115:1", ledger="/unused/ledger",
                            qualification_anchor_dir="/unused/anchors",
                            qualification_key="/unused/key", vault="/unused/vault")
        self.assertEqual(self.adapters.head_calls, 0)

    def test_no_unsigned_ledger_fallback(self):
        self.mock_verify.side_effect = qual.QualificationError("LEDGER_NOT_INITIALIZED")
        with self.assertRaisesRegex(qual.QualificationError, "LEDGER_NOT_INITIALIZED"):
            self.lookup()
        self.assertEqual(self.adapters.head_calls, 0)

    def test_ledger_head_changing_during_query_refused(self):
        self.mock_verify.side_effect = [
            {"head_entry_sha256": LEDGER_HEAD, "entries": 1},
            {"head_entry_sha256": NEW_LEDGER_HEAD, "entries": 2}]
        with self.assertRaisesRegex(OperatorViewError,
                                    "QUALIFICATION_HEAD_CHANGED_DURING_LOOKUP"):
            self.lookup()

    def test_evidence_head_changing_after_query_refused(self):
        self.adapters.change_after_second = True
        with self.assertRaisesRegex(OperatorViewError,
                                    "EVIDENCE_HEAD_CHANGED_DURING_QUALIFICATION"):
            self.lookup()

    def test_lookup_rejects_private_text_request_by_construction(self):
        # Even if a lower-level adapter returns private text unexpectedly,
        # only whitelisted metadata fields can leave the operator view.
        result = self.lookup()
        self.assertNotIn("DO-NOT-EXPOSE-PRIVATE-TEXT", json.dumps(result))

    def test_fake_research_response_cannot_promote_privileges(self):
        from engines.quran.research import operator_view
        for override in ({"text_included": True},
                         {"publication_allowed": True},
                         {"rights_verified": True}):
            fake = {"contract": "mubin-private-retrieval-v0.1",
                    "reference": "2:1", "research_mode": "metadata_only",
                    "evidence_head_sha256": HEAD, "sources": [],
                    "text_included": False,
                    "source_authenticated": False, "scholarly_verified": False,
                    "rights_verified": False, "publication_allowed": False,
                    "redistribution_approved": False, "edition_verified": False,
                    "p1_admitted": False, "juristic_inference_allowed": False,
                    "public_fatwa_authorized": False}
            fake.update(override)
            with patch.object(operator_view, "unified_lookup", return_value=fake):
                with self.assertRaisesRegex(OperatorViewError, "RESEARCH_NOT_METADATA_ONLY"):
                    self.lookup()

    def test_cli_refuses_bad_ref_without_text_or_traceback(self):
        argv = ["lookup", "--ref", "115:1", "--vault", "/unused/vault",
                "--corpus-db", "/unused/corpus", "--sidecar-db", "/unused/sidecar",
                "--registry", "/unused/evidence", "--anchor-dir", "/unused/anchors",
                "--evidence-key", "/unused/ev.key",
                "--qualification-ledger", "/unused/ledger",
                "--qualification-anchor-dir", "/unused/qanchors",
                "--qualification-key", "/unused/q.key"]
        buf = StringIO()
        with redirect_stdout(buf):
            status = main(argv)
        self.assertEqual(status, 1)
        data = json.loads(buf.getvalue())
        self.assertEqual(data["status"], "REFUSED")
        self.assertEqual(data["reason_code"], "SCOPE_COORDINATES_INVALID")
        self.assertFalse(data["text_included"])
        self.assertNotIn("/unused", buf.getvalue())


class OperatorSignedEndToEndTests(unittest.TestCase):
    def test_real_hmac_ledger_and_two_private_adapters_on_synthetic_fixture(self):
        """Real SQLite adapters and HMAC continuity; mocked R0.1a source proof."""
        from pathlib import Path
        from core.tests.test_quran_research_unified_r01c import UnifiedRetrievalTests

        fixture = UnifiedRetrievalTests("test_metadata_contract_shape_and_nonpromotion")
        fixture.setUp()
        try:
            ledger = fixture.root / "qualification-ledger.jsonl"
            anchors = fixture.root / "qualification-anchors"
            key = fixture.root / "qualification.key"
            qual.initialize_ledger(
                ledger, anchors, key, vault=fixture.vault,
                evidence_registry=fixture.registry,
                evidence_anchor_dir=fixture.anchor,
                evidence_key=fixture.evidence_key,
                sidecar_db=fixture.sidecar,
                operator="human-operator-id")
            initial = operator_lookup(
                fixture.adapters, "2:1", ledger=ledger,
                qualification_anchor_dir=anchors,
                qualification_key=key, vault=fixture.vault)
            self.assertEqual(len(initial["sources"]), 11)
            self.assertEqual(initial["qualification_decisions"], 0)
            self.assertFalse(initial["publication_allowed"])
            self.assertNotIn("invented-tafsir-test-only", json.dumps(initial))
            from datetime import datetime, timezone
            decision_record = {
                "decision_id": "synthetic-review-001",
                "axis": "scholarly", "source_id": "qe_ar_muyassar",
                "scope": {"full_source": True},
                "decision": "SOURCE_TEXT_INTEGRITY_REVIEWED",
                "reviewer": "independent-scholarly-reviewer",
                "reviewed_at_utc": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"),
                "evidence_head_sha256": fixture.mock_evidence.return_value[
                    "head_entry_sha256"],
                "notes": "synthetic-only marker; no source authentication",
            }
            qual.append_decision(
                ledger, anchors, key, decision_record, "human-operator-id",
                evidence_registry=fixture.registry,
                evidence_anchor_dir=fixture.anchor,
                evidence_key=fixture.evidence_key, vault=fixture.vault,
                sidecar_db=fixture.sidecar)
            result = operator_lookup(
                fixture.adapters, "2:1", ledger=ledger,
                qualification_anchor_dir=anchors,
                qualification_key=key, vault=fixture.vault)
            one = next(row for row in result["sources"]
                       if row["source_id"] == "qe_ar_muyassar")
            untouched = next(row for row in result["sources"]
                             if row["source_id"] == "tafsir_tabary")
            self.assertEqual(one["scholarly_decision_state"],
                             "SOURCE_TEXT_INTEGRITY_REVIEWED")
            self.assertEqual(untouched["scholarly_decision_state"],
                             "UNREVIEWED")
            self.assertFalse(result["scholarly_verified"])
            self.assertFalse(result["publication_allowed"])
            self.assertFalse(result["juristic_inference_allowed"])
            self.assertNotIn("invented-quran-coordinate-fixture",
                             json.dumps(result))
        finally:
            fixture.doCleanups()


if __name__ == "__main__":
    unittest.main()
