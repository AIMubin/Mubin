"""B02-C.3 chain metadata security negatives, no private source reads."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from qa.check_b02c3_chain import (
    RECEIPT, HOPS, ENGINE_IDS, ChainHandoffError, is_sha, validate,
)


def fixture():
    edges = [{
        "edge": edge, "from": start, "to": end,
        "link_kind": kind, "status": status, "basis": {},
        "objections": [{"type": "open", "open": True}],
        "reason": "Synthetic claim for metadata structure test only"
    } for edge, start, end, kind, status in HOPS]
    return {
        "contract": "mubin-b02c3-evidence-chain-v0.1",
        "case_id": "case.synthetic",
        "nodes": [{"node": k, "anchors": {}} for k in ENGINE_IDS],
        "edges": edges,
        "chain_summary": {
            "edges_total": 4,
            "edges_established_byte_pinned": 1,
            "edges_candidate_lexical": 1,
            "edges_structurally_bound": 1,
            "edges_unassessed_no_certifier": 1,
            "weakest_hop": "e.hadith-usul",
            "overall_status": "PARTIALLY_BOUND_CHAIN_OPEN",
            "scientifically_established_chain": False,
        },
        "flags": {
            "scholarly_verified": False,
            "juristic_inference_allowed": False,
            "completed_inference_claimed": False,
            "text_included": False,
        },
        "evidence_payload_sha256": "0" * 64,
    }


def run_with_metadata(root, chain, *, selected=False):
    directory = Path(root) / "research/b02b"
    directory.mkdir(parents=True)
    for name, data in (
        (RECEIPT, chain),
        ("evidence-receipt.json", {
            "case_id": "case.synthetic",
            "preserved_candidate": {"selected": selected},
            "strict_gate_v3": {"verdict": "REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR"},
        }),
        ("b02c2-kernel-receipt-6-145-v1.json", {}),
    ):
        (directory / name).write_text(
            json.dumps(data, ensure_ascii=False), encoding="utf-8")


class ChainReviewNegativeTests(unittest.TestCase):
    def test_digest_must_be_lowercase_sha256(self):
        self.assertTrue(is_sha("a" * 64))
        self.assertFalse(is_sha("A" * 64))
        self.assertFalse(is_sha(None))
        self.assertFalse(is_sha("0" * 63))

    def test_missing_chain_is_not_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                validate(tmp)

    def check(self, changed, expected, *, selected=False):
        with tempfile.TemporaryDirectory() as tmp:
            run_with_metadata(tmp, changed, selected=selected)
            with self.assertRaisesRegex(ChainHandoffError, expected):
                validate(tmp)

    def test_candidate_selection_forgery_rejected(self):
        self.check(fixture(), "CHAIN_STRICT_SELECTION_PROMOTED", selected=True)

    def test_hop_forgery_rejected(self):
        x = fixture()
        x["edges"][2]["status"] = "ESTABLISHED_BYTE_PINNED"
        self.check(x, "CHAIN_HOP_IDENTITY_MISMATCH")

    def test_missing_hadith_usul_link_rejected(self):
        x = fixture()
        x["edges"].pop(2)
        self.check(x, "CHAIN_HOPS_INVALID")

    def test_scholarly_promotion_rejected(self):
        x = fixture()
        x["chain_summary"]["scientifically_established_chain"] = True
        self.check(x, "CHAIN_FALSE_SCIENTIFIC_CLAIM")

    def test_closed_objections_rejected(self):
        x = fixture()
        x["edges"][2]["objections"][0]["open"] = False
        self.check(x, "CHAIN_OPEN_OBJECTION_REMOVED")

    def test_missing_self_digest_rejected(self):
        x = fixture()
        x["evidence_payload_sha256"] = None
        self.check(x, "CHAIN_SELF_DIGEST_MISSING")

    def test_arabic_excerpt_never_in_public_chain(self):
        x = fixture()
        x["edges"][0]["reason"] = "نص عربي خاص لا يرفع"
        self.check(x, "CHAIN_SENSITIVE_CONTENT_PRESENT")


if __name__ == "__main__":
    unittest.main()
