"""B02-C.6 negative metadata checks: no private source texts or identifiers upgraded."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from qa.check_b02c6_witness_prep import (
    WitnessPrepError, validate, validate_view,
)

ROOT = Path(__file__).resolve().parents[2]
DIR = ROOT / "research/b02b"


def load():
    return (json.loads((DIR / "b02c6-witness-prep-6-145-v1.json").read_text(
            encoding="utf-8-sig")),
            json.loads((DIR / "evidence-receipt.json").read_text(
            encoding="utf-8-sig")))


def resign(obj):
    base = {k: v for k, v in obj.items() if k != "evidence_payload_sha256"}
    raw = json.dumps(base, sort_keys=True, ensure_ascii=False,
                     allow_nan=False, separators=(",", ":")).encode("utf-8")
    obj["evidence_payload_sha256"] = hashlib.sha256(raw).hexdigest()


class WitnessPrepMetadataTests(unittest.TestCase):
    def mutate(self, update, expected, *, resign_sha=True):
        rec, evidence = (deepcopy(x) for x in load())
        update(rec, evidence)
        if resign_sha:
            resign(rec)
            evidence["b02c6_witness_identity_prep"]["public_receipt_sha256"] = (
                rec["evidence_payload_sha256"])
        with self.assertRaisesRegex(WitnessPrepError, expected):
            validate_view(rec, evidence)

    def test_published_handoff_valid_in_scope_only(self):
        r = validate(ROOT)
        self.assertEqual(r["source_hits_within_four"], 1)
        self.assertEqual(r["search_probes"], 2)
        self.assertFalse(r["identity_verified"])
        self.assertFalse(r["raw_unicode_offset_converted_to_bytes"])
        self.assertFalse(r["identity_contract_executed"])

    def test_unrecomputed_payload_digest_fails(self):
        self.mutate(
            lambda r,e: r["witness_candidate_block"].update(chars=291),
            "SELF_DIGEST_INVALID", resign_sha=False)

    def test_forged_textual_excerpt_detected(self):
        self.mutate(
            lambda r,e: r["negative_control"][
                "shared_span_containment_check"].update(
                    shared_span_folded="مقتطف مصدر خاص"),
            "PRIVATE_CONTENT_PRESENT")

    def test_raw_cue_word_disclosed_rejected(self):
        self.mutate(
            lambda r,e: r["witness_candidate_block"][
                "isnad_cue_counts"].update({"أخبرنا":1}),
            "PRIVATE_CONTENT_PRESENT")

    def test_false_byte_offset_claim_refused(self):
        self.mutate(
            lambda r,e: r.update(
                span_coordinate_unit="UTF8_BYTES"),
            "CONTRACT_OR_OFFSET_INVALID")

    def test_false_multisource_hits_rejected(self):
        self.mutate(
            lambda r,e: r["cross_source_variant_search"][0].update(
                sources_with_hits=4),
            "SOURCE_COUNT_INVALID")

    def test_no_match_absence_claim_cannot_be_absolute(self):
        self.mutate(
            lambda r,e: r["cross_source_variant_search"][0]["per_source"][0].update(
                absence_is_not_proof_of_absence=False),
            "FALSE_ABSENCE_CLAIM")

    def test_second_source_hit_requires_new_evidence(self):
        self.mutate(
            lambda r,e: r["cross_source_variant_search"][0]["per_source"][0].update(
                occurrences=1, status="CANDIDATE_MATCH"),
            "FALSE_ABSENCE_CLAIM")

    def test_source_id_duplicate_rejected(self):
        self.mutate(
            lambda r,e: r["cross_source_variant_search"][0]["per_source"][0].update(
                source_id="openiti:0458Bayhaqi.SunanKubra"),
            "SOURCE_SET_INVALID")

    def test_forged_bayhaqi_span_rejected(self):
        self.mutate(
            lambda r,e: r["cross_source_variant_search"][0]["per_source"][1].update(
                first_span=[5, 100]),
            "BAYHAQI_HIT_INVALID")

    def test_false_hadith_grade_rejected(self):
        self.mutate(
            lambda r,e: r["flags"].update(grade_assigned=True),
            "SCIENTIFIC_PROMOTION")

    def test_narration_identity_not_issued_yet(self):
        self.mutate(
            lambda r,e: r.update(identity_decision="CONFIRMED"),
            "SCIENTIFIC_PROMOTION")

    def test_missing_negative_quran_control_refused(self):
        self.mutate(
            lambda r,e: r["negative_control"][
                "shared_span_containment_check"].update(
                    is_substring_of_folded_verse_6_145=False),
            "NEGATIVE_CONTROL_NOT_CONSERVATIVE")

    def test_handoff_wrong_digest_rejected(self):
        self.mutate(
            lambda r,e: e["b02c6_witness_identity_prep"].update(
                public_receipt_sha256="0"*64),
            "HANDOFF_MISMATCH")

    def test_strict_selection_cannot_be_promoted(self):
        self.mutate(
            lambda r,e: e["strict_gate_v3"].update(
                verdict="SCIENTIFICALLY_ACCEPTED"),
            "STRICT_GATE_CHANGED")

    def test_duplicate_probe_does_not_count_twice(self):
        self.mutate(
            lambda r,e: r["cross_source_variant_search"][1].update(
                probe_id="witness-fragment-full"),
            "PROBES_INVALID")

    def test_cannot_forge_bayhaqi_two_occurrences_in_full_probe(self):
        self.mutate(
            lambda r,e: r["cross_source_variant_search"][0]["per_source"][1].update(
                occurrences_within_probe_limit=2),
            "PRIMARY_HIT_MISMATCH")


if __name__ == "__main__":
    unittest.main()
