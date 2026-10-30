"""B02-C.3: narrated cue is not a witnessed/graded Hadith."""
import json
from pathlib import Path
import unittest
from core.orchestration.cross_engine_chain import audit_cross_engine_chain

ROOT = Path(__file__).resolve().parents[2]


class HadithCueBoundaryTests(unittest.TestCase):
    def test_tafsir_to_hadith_context_is_not_witness(self):
        case = json.loads((ROOT / "research/b02b/b02c2-kernel-receipt-6-145-v1.json")
                          .read_text(encoding="utf-8"))
        tafsir = case["nodes"][2]
        hadith = case["nodes"][3]
        assert tafsir["result"]["engine"] == "tafsir"
        assert hadith["result"]["engine"] == "hadith"
        assert all(x["candidate_only"] and not x["grade_assigned"]
                   for x in hadith["result"]["findings"])
        proposed = [{
            "from_node": tafsir["node_id"],
            "from_ref": tafsir["result"]["evidence_refs"][0],
            "to_node": hadith["node_id"],
            "to_ref": hadith["result"]["evidence_refs"][0],
            "relation": "CONTEXT_PROPOSAL",
            "assessment_sha256": None,
        }]
        view = audit_cross_engine_chain(case, proposed)
        self.assertEqual(view["counts"]["unverified_proposals"], 1)
        self.assertFalse(view["hadith_identity_verified"])
        self.assertFalse(view["semantic_links_verified"])
        self.assertEqual(view["counts"]["qualified_semantic_links"], 0)

    def test_context_candidate_never_sets_scholarly_permission(self):
        case = json.loads((ROOT / "research/b02b/b02c2-kernel-receipt-6-145-v1.json")
                          .read_text(encoding="utf-8"))
        view = audit_cross_engine_chain(case, [])
        self.assertFalse(view["juristic_inference_allowed"])
        self.assertFalse(view["strict_selection_verified"])
        self.assertEqual(view["status"], "TRANSPORT_ONLY_INCOMPLETE")


if __name__=="__main__":
    unittest.main()
