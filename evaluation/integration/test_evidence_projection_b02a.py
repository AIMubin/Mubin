"""B02-A: no synthetic proof laundering; verify redacted projection semantics."""
from __future__ import annotations
import copy
import json
import unittest

from core.tests.test_inference_foundation import fixture
from core.orchestration.evidence_projection import (
    ProjectionError, project_p0_bundle, verify_redacted_projection,
    verify_private_projection,
)

class ProjectionTests(unittest.TestCase):
    def test_full_p0_creates_redacted_topology_not_another_p0(self):
        raw = fixture()
        view = project_p0_bundle(raw)
        self.assertTrue(view["p0_structural_passed"])
        self.assertTrue(verify_redacted_projection(view))
        self.assertFalse(view["projection_is_p0_bundle"])
        self.assertFalse(view["scholarly_verified"])
        self.assertFalse(view["external_source_authenticated"])
        self.assertEqual(len(view["nodes"]), sum(view["counts"].values()))
        exposed = json.dumps(view, ensure_ascii=False)
        self.assertNotIn("Hypothetical sample", exposed)
        self.assertNotIn("Scholar-published", exposed)
        self.assertNotIn("clm.asl", exposed)
        self.assertNotIn("ev.001", exposed)
        self.assertNotIn("folio-1", exposed)
        self.assertNotIn("qiyas conclusion", exposed)

    def test_projection_deterministic_at_exact_same_private_snapshot(self):
        raw = fixture()
        self.assertEqual(project_p0_bundle(raw), project_p0_bundle(copy.deepcopy(raw)))

    def test_invalid_hash_redacted_without_echoing_private_content(self):
        raw = fixture()
        raw["evidence"][0]["excerpt"] = "CONFIDENTIAL_VALUE_ONLY_IN_PRIVATE_VAULT"
        result = project_p0_bundle(raw)
        self.assertEqual(result["status"], "P0_REJECTED")
        self.assertTrue(verify_redacted_projection(result))
        self.assertNotIn("CONFIDENTIAL_VALUE", str(result))
        self.assertIsNone(result["private_bundle_sha256"])

    def test_trusted_vault_replay_requires_exact_private_bundle(self):
        raw = fixture()
        view = project_p0_bundle(raw)
        self.assertTrue(verify_private_projection(raw, view))
        changed = copy.deepcopy(raw)
        changed["sources"][0]["work_title"] = "Changed private source title"
        self.assertFalse(verify_private_projection(changed, view))
        self.assertTrue(verify_redacted_projection(view))  # not a custody proof

    def test_non_string_edge_id_rejected_without_crash(self):
        view = project_p0_bundle(fixture())
        view["edges"][0]["from"] = []
        self.assertFalse(verify_redacted_projection(view))

    def test_missing_source_ref_rejected_without_echo(self):
        raw = fixture()
        raw["evidence"][0]["source_id"] = "src.secret"
        self.assertEqual(project_p0_bundle(raw)["status"], "P0_REJECTED")

    def test_rejected_projection_cannot_fake_p0_pass(self):
        raw = fixture()
        raw["evidence"][0]["excerpt"] = "TAMPER"
        result = project_p0_bundle(raw)
        result["p0_structural_passed"] = True
        self.assertFalse(verify_redacted_projection(result))

    def test_graph_tampering_detected(self):
        view = project_p0_bundle(fixture())
        view["edges"].pop()
        self.assertFalse(verify_redacted_projection(view))

    def test_count_tampering_detected(self):
        view = project_p0_bundle(fixture())
        view["counts"]["sources"] += 1
        self.assertFalse(verify_redacted_projection(view))

    def test_unrecognized_privilege_marker_rejected(self):
        view = project_p0_bundle(fixture())
        view["public_fatwa_authorized"] = True
        self.assertFalse(verify_redacted_projection(view))

    def test_no_links_without_engine_receipt(self):
        with self.assertRaises(ProjectionError):
            project_p0_bundle(fixture(), links=[{
                "node_id": "req.001", "engine_evidence_ref": "ev.any",
                "p0_evidence_id": "ev.001"}])

    @staticmethod
    def engine_receipt():
        return {
            "contract_version": "engine-contract/1.0",
            "source_snapshot_ids": ["snap.001"],
            "nodes": [{
                "node_id": "req.001",
                "result": {
                    "contract_version": "engine-contract/1.0",
                    "request_id": "req.001", "engine": "quran",
                    "status": "OK", "evidence_refs": ["ev.engine.001"],
                    "provenance": {"snapshot_ids": ["snap.001"]},
                }
            }],
        }

    def test_explicit_receipt_to_p0_link(self):
        view = project_p0_bundle(
            fixture(), case_receipt=self.engine_receipt(), links=[{
                "node_id": "req.001", "engine_evidence_ref": "ev.engine.001",
                "p0_evidence_id": "ev.001"}])
        self.assertEqual(len(view["engine_bindings"]), 1)
        self.assertTrue(verify_redacted_projection(view))
        self.assertEqual(view["engine_bindings"][0]["scope"],
                         "MATCHED_SUBMITTED_RECEIPT_ONLY")
        self.assertNotIn("ev.engine.001", json.dumps(view))

    def test_nonexistent_engine_evidence_ref_refused(self):
        with self.assertRaises(ProjectionError):
            project_p0_bundle(
                fixture(), case_receipt=self.engine_receipt(), links=[{
                    "node_id": "req.001", "engine_evidence_ref": "ev.fake",
                    "p0_evidence_id": "ev.001"}])

    def test_nonexistent_p0_evidence_ref_refused(self):
        with self.assertRaises(ProjectionError):
            project_p0_bundle(
                fixture(), case_receipt=self.engine_receipt(), links=[{
                    "node_id": "req.001", "engine_evidence_ref": "ev.engine.001",
                    "p0_evidence_id": "ev.fake"}])

    def test_duplicate_link_refused(self):
        link = {"node_id": "req.001", "engine_evidence_ref": "ev.engine.001",
                "p0_evidence_id": "ev.001"}
        with self.assertRaises(ProjectionError):
            project_p0_bundle(
                fixture(), case_receipt=self.engine_receipt(), links=[link, link])

    def test_unverified_claim_cannot_be_silently_promoted(self):
        raw = fixture()
        raw["evidence"][0]["verification_status"] = "unverified"
        raw["evidence"][0]["verification_method"] = "unverified"
        self.assertEqual(project_p0_bundle(raw)["status"], "P0_REJECTED")

    def test_no_external_attestation_even_with_p0_structural_success(self):
        raw = fixture()
        view = project_p0_bundle(raw)
        self.assertTrue(view["p0_structural_passed"])
        self.assertFalse(view["external_source_authenticated"])
        self.assertFalse(view["scholarly_verified"])

    def test_bad_graph_digest_detected(self):
        view = project_p0_bundle(fixture())
        view["graph_sha256"] = "0" * 64
        self.assertFalse(verify_redacted_projection(view))


if __name__ == "__main__":
    unittest.main()
