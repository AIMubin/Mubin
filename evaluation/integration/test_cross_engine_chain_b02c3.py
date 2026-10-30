"""Adversarial B02-C.3 regression over committed research metadata, never corpus text."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import unittest
from core.orchestration.cross_engine_chain import (
    ChainAuditError, audit_cross_engine_chain,
    verify_redacted_chain_audit, verify_private_chain_replay,
)

ROOT = Path(__file__).resolve().parents[2]
CASE = ROOT / "research/b02b/b02c2-kernel-receipt-6-145-v1.json"


def fixture():
    return json.loads(CASE.read_text(encoding="utf-8"))


def relays(x):
    src, target = x["nodes"][0], x["nodes"][-1]
    return [{"from_node": src["node_id"], "from_ref": ref,
             "to_node": target["node_id"], "to_ref": ref,
             "relation": "EXACT_REF_RELAY", "assessment_sha256": None}
            for ref in src["result"]["evidence_refs"]]


def candidate(x, kind="CONTEXT_PROPOSAL"):
    q, taf = x["nodes"][1:3]
    return {"from_node": q["node_id"], "to_node": taf["node_id"],
            "from_ref": q["result"]["evidence_refs"][0],
            "to_ref": taf["result"]["evidence_refs"][0], "relation": kind,
            "assessment_sha256": "a"*64 if kind == "SEMANTIC_PROPOSAL" else None}


class CrossEngineChainTests(unittest.TestCase):
    def test_real_metadata_has_four_relays_not_scientific_proofs(self):
        x = fixture()
        view = audit_cross_engine_chain(x, relays(x))
        self.assertEqual(view["node_count"], 6)
        self.assertEqual(view["engine_count"], 5)
        self.assertEqual(view["counts"]["observed_reference_relays"], 4)
        self.assertEqual(view["counts"]["qualified_semantic_links"], 0)
        self.assertFalse(view["plan_dependencies_verified"])
        self.assertFalse(view["scholarly_verified"])
        self.assertTrue(verify_redacted_chain_audit(view))
        self.assertTrue(verify_private_chain_replay(x, relays(x), view))
        output = json.dumps(view, ensure_ascii=False)
        self.assertNotIn("ev.usul.", output)
        self.assertNotIn("tafsir:tafsir_", output)

    def test_context_proposal_does_not_complete_chain(self):
        x=fixture()
        result=audit_cross_engine_chain(x, relays(x)+[candidate(x)])
        self.assertEqual(result["counts"]["unverified_proposals"], 1)
        self.assertFalse(result["semantic_links_verified"])
        self.assertEqual(result["status"], "TRANSPORT_ONLY_INCOMPLETE")

    def test_semantic_sha_is_declaration_only(self):
        x=fixture()
        result=audit_cross_engine_chain(x, [candidate(x,"SEMANTIC_PROPOSAL")])
        self.assertEqual(result["counts"]["qualified_semantic_links"], 0)
        self.assertEqual(result["links"][0]["status"], "UNVERIFIED_RESEARCH_PROPOSAL")

    def test_empty_proposals_do_not_pass(self):
        x=fixture()
        result=audit_cross_engine_chain(x, [])
        self.assertEqual(result["counts"]["observed_reference_relays"], 0)
        self.assertEqual(result["status"], "TRANSPORT_ONLY_INCOMPLETE")

    def test_forged_evidence_ref_rejected(self):
        x=fixture()
        y=relays(x)
        y[0]["from_ref"]=y[0]["to_ref"]="ev.not.present"
        with self.assertRaisesRegex(ChainAuditError,"CHAIN_ENDPOINT_UNVERIFIED"):
            audit_cross_engine_chain(x,y)

    def test_unequal_relay_ref_rejected(self):
        x=fixture()
        y=relays(x)
        y[0]["to_ref"]=y[1]["to_ref"]
        with self.assertRaisesRegex(ChainAuditError,"CHAIN_RELAY_NOT_EXACT"):
            audit_cross_engine_chain(x,y)

    def test_same_node_rejected(self):
        x=fixture()
        y=relays(x)
        y[0]["to_node"]=y[0]["from_node"]
        with self.assertRaises(ChainAuditError):
            audit_cross_engine_chain(x,y)

    def test_same_engine_rejected(self):
        x=fixture()
        y=relays(x)
        y[0]["to_node"]="b02c2.u2"
        with self.assertRaises(ChainAuditError):
            audit_cross_engine_chain(x,y)

    def test_missing_semantic_review_sha_rejected(self):
        x=fixture()
        y=candidate(x,"SEMANTIC_PROPOSAL")
        y["assessment_sha256"]=None
        with self.assertRaisesRegex(ChainAuditError,"CHAIN_REVIEW_DIGEST_REQUIRED"):
            audit_cross_engine_chain(x,[y])

    def test_context_fake_attestation_rejected(self):
        x=fixture()
        y=candidate(x)
        y["assessment_sha256"]="b"*64
        with self.assertRaisesRegex(ChainAuditError,"CHAIN_CONTEXT_HAS_ATTESTATION"):
            audit_cross_engine_chain(x,[y])

    def test_duplicate_links_rejected(self):
        x=fixture()
        with self.assertRaisesRegex(ChainAuditError,"CHAIN_DUPLICATE_LINK"):
            audit_cross_engine_chain(x,relays(x)[:1]*2)

    def test_bad_source_snapshot_rejected(self):
        x=fixture()
        x["nodes"][0]["result"]["provenance"]["snapshot_ids"]=["snap.other"]
        with self.assertRaisesRegex(ChainAuditError,"CHAIN_NODE_CONTRACT_INVALID"):
            audit_cross_engine_chain(x,[])

    def test_untrusted_runtime_status_rejected(self):
        x=fixture()
        x["nodes"][0]["result"]["status"]="UNAVAILABLE"
        with self.assertRaises(ChainAuditError):
            audit_cross_engine_chain(x,relays(fixture()))

    def test_partial_is_allowed_only_downstream(self):
        x=fixture()
        y=relays(x)
        y[0]["from_node"]="b02c2.f1"
        y[0]["to_node"]="b02c2.us1"
        with self.assertRaises(ChainAuditError):
            audit_cross_engine_chain(x,y)

    def test_public_audit_tampering_fails(self):
        x=fixture()
        view=audit_cross_engine_chain(x,relays(x))
        view["links"].pop()
        self.assertFalse(verify_redacted_chain_audit(view))

    def test_public_scholarly_flag_fails(self):
        x=fixture()
        view=audit_cross_engine_chain(x,relays(x))
        view["scholarly_verified"]=True
        self.assertFalse(verify_redacted_chain_audit(view))

    def test_public_unhashable_relation_fails_closed(self):
        x=fixture()
        view=audit_cross_engine_chain(x,relays(x))
        view["links"][0]["relation"]=[]
        self.assertFalse(verify_redacted_chain_audit(view))

    def test_local_replay_detects_private_metadata_mutation(self):
        x=fixture()
        view=audit_cross_engine_chain(x,relays(x))
        changed=copy.deepcopy(x)
        changed["nodes"][0]["result"]["findings"][0]["rule_id"]="other.rule"
        self.assertTrue(verify_redacted_chain_audit(view))
        self.assertFalse(verify_private_chain_replay(changed,relays(x),view))

    def test_case_id_swap_breaks_replay(self):
        x=fixture()
        view=audit_cross_engine_chain(x,relays(x))
        changed=copy.deepcopy(x)
        changed["case_id"]="case.altered"
        self.assertFalse(verify_private_chain_replay(changed,relays(x),view))

    def test_no_model_vote_can_promote_source_authenticity(self):
        x=fixture()
        view=audit_cross_engine_chain(x,[candidate(x,"SEMANTIC_PROPOSAL")])
        for field in ("source_authenticated","strict_selection_verified",
                      "hadith_identity_verified","juristic_inference_allowed",
                      "opinion_attribution_verified","semantic_links_verified"):
            self.assertFalse(view[field], field)


if __name__=="__main__":
    unittest.main()
