"""U0.2 concept-definition metadata tests. Only pinned public receipt is used."""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from engines.usul.concept_definitions import (
    build_definitions, normalize_manifest, canonical, sha, CatalogError, SCHEMA,
)

ROOT = Path(__file__).resolve().parents[3]
RECEIPT_FILE = ROOT / "corpus/reviews/u02-waraqat-private-source-acceptance-PASS.json"
TRUSTED_RECEIPT_SHA = "00f0d1c71f55dc226cd6b840decfcdada152a40746a5cdc39b1e4f019c6bf7df"


class DefinitionMetadataTests(unittest.TestCase):
    def setUp(self):
        self.receipt = json.loads(RECEIPT_FILE.read_text(encoding="utf-8"))
        self.concepts = [
            ("concept:amr-term", "pilot:amr-term"),
            ("concept:qarinah-candidate", "pilot:qarinah-term"),
            ("concept:wujub-candidate", "pilot:wujub-term"),
        ]
        self.manifest = {
            "schema_version": SCHEMA,
            "basis_receipt_sha256": TRUSTED_RECEIPT_SHA,
            "previous_manifest_sha256": None,
            "sources": [
                {"id": "source:waraqat-w1", "witness_id": "pilot:waraqat-primary",
                 "work_id": "work:waraqat-candidate",
                 "claimed_author_id": "author:unassessed",
                 "edition_id": "edition:w1-digital-capture",
                 "locator_id": "locator:bab-amr",
                 "section_sha256": self.receipt["original_private_witness_pins"]["w1_bab_amr_sha256"],
                 "rights_status": "NOT_CLEARED",
                 "attribution_review_status": "UNASSESSED",
                 "edition_review_status": "UNASSESSED",
                 "version": "0.1.0"},
            ],
            "source_observations": [
                {"id": "observation:"+qid.split(":")[1],
                 "concept_id": cid, "source_id": "source:waraqat-w1",
                 "query_id": qid, "version": "0.1.0",
                 "observation_status": "LEXICAL_ONLY",
                 "source_text_included": False}
                for cid, qid in self.concepts
            ],
            "definition_candidates": [
                {"id": "definition:amr-a", "concept_id": "concept:amr-term",
                 "source_observation_id": "observation:amr-term",
                 "version": "0.1.0", "definition_commitment_sha256": sha(b"synthetic-A"),
                 "claimed_author_id": "author:unassessed",
                 "commitment_scheme": "SYNTHETIC_SHA256_TEST_VECTOR",
                 "commitment_key_id": None,
                 "review_status": "UNASSESSED", "source_text_included": False},
                {"id": "definition:amr-b", "concept_id": "concept:amr-term",
                 "source_observation_id": "observation:amr-term",
                 "version": "0.1.0", "definition_commitment_sha256": sha(b"synthetic-B"),
                 "claimed_author_id": "author:unassessed",
                 "commitment_scheme": "SYNTHETIC_SHA256_TEST_VECTOR",
                 "commitment_key_id": None,
                 "review_status": "UNASSESSED", "source_text_included": False},
            ],
            "interpretation_candidates": [
                {"id": "interpretation:amr-a", "concept_id": "concept:amr-term",
                 "definition_candidate_ids": ["definition:amr-a"],
                 "version": "0.1.0",
                 "interpretation_commitment_sha256": sha(b"synthetic-interpretation"),
                 "commitment_scheme": "SYNTHETIC_SHA256_TEST_VECTOR",
                 "commitment_key_id": None,
                 "review_status": "UNASSESSED", "source_text_included": False}
            ],
            "definition_comparisons": [
                {"id": "comparison:amr-multiple",
                 "concept_id": "concept:amr-term",
                 "definition_candidate_ids": [
                     "definition:amr-a", "definition:amr-b"],
                 "kind": "MULTIPLE_DEFINITIONS",
                 "review_status": "UNASSESSED"}
            ],
        }

    def run_build(self):
        return build_definitions(self.receipt, TRUSTED_RECEIPT_SHA,
                                 self.manifest)

    def test_pinned_u02_3_receipt_and_research_only_success(self):
        report = self.run_build()
        self.assertEqual(report, self.run_build())
        self.assertEqual(report["status"], "U02_DEFINITION_METADATA_CANDIDATES_PASS")
        self.assertEqual(report["observation_count"], 3)
        self.assertEqual(report["source_count"], 1)
        self.assertEqual(report["definition_candidate_count"], 2)
        self.assertEqual(report["multiple_definitions_comparison_count"], 1)
        self.assertEqual(len(report["report_sha256"]), 64)
        for field in ("source_text_included", "private_paths_included",
                      "source_support_attested", "scholarly_verified",
                      "semantic_equivalence_verified", "redistribution_approved",
                      "juristic_inference_allowed", "rule_execution_performed",
                      "public_fatwa_authorized", "scholarly_attribution_verified",
                      "source_edition_authenticated",
                      "scholarly_disagreement_attested"):
            self.assertFalse(report[field])
        self.assertNotIn("synthetic-interpretation", json.dumps(report))

    def test_committed_synthetic_example_matches_contract(self):
        example = json.loads((ROOT / "engines/usul/examples/u02-concept-definitions-synthetic.json").read_text(encoding="utf-8"))
        report = build_definitions(self.receipt, TRUSTED_RECEIPT_SHA, example)
        self.assertEqual(report["status"], "U02_DEFINITION_METADATA_CANDIDATES_PASS")
        self.assertEqual(report["definition_candidate_count"], 2)
        self.assertFalse(report["scholarly_attribution_verified"])

    def test_unmarked_raw_sha256_commitment_rejected(self):
        self.manifest["definition_candidates"][0]["commitment_scheme"] = "SHA256_RAW"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_private_hmac_commitment_accepts_opaque_key_id(self):
        d = self.manifest["definition_candidates"][0]
        d["commitment_scheme"] = "HMAC_SHA256_PRIVATE"
        d["commitment_key_id"] = "hmac:local-key-one"
        result = self.run_build()
        self.assertEqual(result["status"], "U02_DEFINITION_METADATA_CANDIDATES_PASS")
        self.assertFalse(result["source_text_included"])

    def test_private_hmac_key_id_is_required(self):
        self.manifest["definition_candidates"][0]["commitment_scheme"] = "HMAC_SHA256_PRIVATE"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_hmac_secret_must_not_be_embedded_in_public_record(self):
        d = self.manifest["definition_candidates"][0]
        d["commitment_scheme"] = "HMAC_SHA256_PRIVATE"
        d["commitment_key_id"] = "hmac:opaque"
        d["hmac_secret"] = "never-publish-a-secret"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_CANDIDATE_FIELDS_INVALID"):
            self.run_build()

    def test_interpretation_hmac_key_id_required_and_valid(self):
        i = self.manifest["interpretation_candidates"][0]
        i["commitment_scheme"] = "HMAC_SHA256_PRIVATE"
        i["commitment_key_id"] = "hmac:private-interpretation-key"
        report = self.run_build()
        self.assertEqual(report["interpretation_candidate_count"], 1)

    def test_interpretation_raw_hash_promotion_rejected(self):
        self.manifest["interpretation_candidates"][0]["commitment_scheme"] = "SHA256_RAW"
        with self.assertRaisesRegex(CatalogError, "INTERPRETATION_UNANCHORED_OR_PROMOTED"):
            self.run_build()

    def test_synthetic_test_vector_cannot_claim_private_key(self):
        self.manifest["definition_candidates"][0]["commitment_key_id"] = "hmac:unused"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_collection_reordering_does_not_change_digest(self):
        a = self.run_build()
        for key in ("sources", "source_observations", "definition_candidates",
                    "interpretation_candidates", "definition_comparisons"):
            self.manifest[key].reverse()
        self.assertEqual(a, self.run_build())

    def test_wrong_external_pin_rejected(self):
        with self.assertRaisesRegex(CatalogError, "RECEIPT_PIN_MISMATCH"):
            build_definitions(self.receipt, "f"*64, self.manifest)

    def test_edited_pinned_receipt_rejected(self):
        self.receipt["independent_original_byte_literal_counts"][0][
            "independent_exact_count"] = 900
        with self.assertRaisesRegex(CatalogError, "RECEIPT_CANONICAL_DIGEST_MISMATCH"):
            self.run_build()

    def test_receipt_restricted_flag_cannot_be_overridden(self):
        self.receipt["public_fatwa_authorized"] = True
        self.receipt["acceptance_receipt_sha256"] = sha(canonical({
            k: v for k, v in self.receipt.items()
            if k != "acceptance_receipt_sha256"
        }))
        with self.assertRaisesRegex(CatalogError, "RECEIPT_PIN_MISMATCH"):
            self.run_build()

    def test_manifest_cannot_contain_raw_source_or_private_path(self):
        self.manifest["source_text"] = "confidential-private-witness"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_MANIFEST_FIELDS_INVALID"):
            self.run_build()

    def test_source_cannot_contain_title_or_source_excerpt(self):
        self.manifest["sources"][0]["title"] = "من الورقات"
        with self.assertRaisesRegex(CatalogError, "SOURCE_REGISTRY_FIELDS_INVALID"):
            self.run_build()

    def test_claimed_author_is_never_verified(self):
        self.manifest["sources"][0]["attribution_review_status"] = "VERIFIED"
        with self.assertRaisesRegex(CatalogError, "SOURCE_REGISTRY_UNVERIFIED_OR_UNPINNED"):
            self.run_build()

    def test_missing_rights_clearance_cannot_be_promoted(self):
        self.manifest["sources"][0]["rights_status"] = "CLEARED"
        with self.assertRaisesRegex(CatalogError, "SOURCE_REGISTRY_UNVERIFIED_OR_UNPINNED"):
            self.run_build()

    def test_wrong_source_section_pin_rejected(self):
        self.manifest["sources"][0]["section_sha256"] = "0"*64
        with self.assertRaisesRegex(CatalogError, "SOURCE_REGISTRY_UNVERIFIED_OR_UNPINNED"):
            self.run_build()

    def test_private_path_in_locator_id_rejected(self):
        self.manifest["sources"][0]["locator_id"] = "D:\\private\\somewhere"
        with self.assertRaisesRegex(CatalogError, "SOURCE_REGISTRY_IDENTIFIER_INVALID"):
            self.run_build()

    def test_missing_observation_fails_closed(self):
        self.manifest["source_observations"].pop()
        with self.assertRaisesRegex(CatalogError, "SOURCE_OR_OBSERVATION_COVERAGE_INVALID"):
            self.run_build()

    def test_cross_query_observation_refused(self):
        self.manifest["source_observations"][0]["query_id"] = "pilot:wujub-term"
        with self.assertRaisesRegex(CatalogError, "SOURCE_OBSERVATION_UNANCHORED_OR_PROMOTED"):
            self.run_build()

    def test_unrecognized_observation_field_refused(self):
        self.manifest["source_observations"][0]["text"] = "untrusted source"
        with self.assertRaisesRegex(CatalogError, "SOURCE_OBSERVATION_FIELDS_INVALID"):
            self.run_build()

    def test_observation_semantic_promotion_rejected(self):
        self.manifest["source_observations"][0]["observation_status"] = "PROVES_RULE"
        with self.assertRaisesRegex(CatalogError, "SOURCE_OBSERVATION_UNANCHORED_OR_PROMOTED"):
            self.run_build()

    def test_source_observation_ref_as_list_fails_with_catalog_error(self):
        self.manifest["source_observations"][0]["source_id"] = ["source:waraqat-w1"]
        with self.assertRaisesRegex(CatalogError, "SOURCE_OBSERVATION_UNANCHORED_OR_PROMOTED"):
            self.run_build()

    def test_query_id_as_list_fails_with_catalog_error(self):
        self.manifest["source_observations"][0]["query_id"] = ["pilot:amr-term"]
        with self.assertRaisesRegex(CatalogError, "SOURCE_OBSERVATION_UNANCHORED_OR_PROMOTED"):
            self.run_build()

    def test_definition_observation_ref_as_list_fails_with_catalog_error(self):
        self.manifest["definition_candidates"][0]["source_observation_id"] = [
            "observation:amr-term"]
        with self.assertRaisesRegex(CatalogError, "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_interpretation_concept_as_list_fails_with_catalog_error(self):
        self.manifest["interpretation_candidates"][0]["concept_id"] = [
            "concept:amr-term"]
        with self.assertRaisesRegex(CatalogError, "INTERPRETATION_UNANCHORED_OR_PROMOTED"):
            self.run_build()

    def test_comparison_concept_as_list_fails_with_catalog_error(self):
        self.manifest["definition_comparisons"][0]["concept_id"] = [
            "concept:amr-term"]
        with self.assertRaisesRegex(CatalogError, "DEFINITION_COMPARISON_UNATTESTED"):
            self.run_build()

    def test_duplicate_source_observation_id_refused(self):
        self.manifest["source_observations"][1]["id"] = (
            self.manifest["source_observations"][0]["id"])
        with self.assertRaisesRegex(CatalogError, "DEFINITION_DUPLICATE_ID"):
            self.run_build()

    def test_definition_wrong_concept_refused(self):
        self.manifest["definition_candidates"][0]["concept_id"] = "concept:wujub-candidate"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_definition_forged_author_refused(self):
        self.manifest["definition_candidates"][0]["claimed_author_id"] = "author:invented"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_definition_forged_verified_status_refused(self):
        self.manifest["definition_candidates"][0]["review_status"] = "VERIFIED"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_definition_prose_field_cannot_be_submitted(self):
        self.manifest["definition_candidates"][0]["definition"] = "This is an interpretation"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_CANDIDATE_FIELDS_INVALID"):
            self.run_build()

    def test_definition_duplicate_digest_not_independent_alternative(self):
        self.manifest["definition_candidates"][1]["definition_commitment_sha256"] = (
            self.manifest["definition_candidates"][0]["definition_commitment_sha256"])
        with self.assertRaisesRegex(CatalogError, "DEFINITION_DUPLICATE_DIGEST"):
            self.run_build()

    def test_unauthorized_interpretation_status_refused(self):
        self.manifest["interpretation_candidates"][0]["review_status"] = "APPROVED"
        with self.assertRaisesRegex(CatalogError, "INTERPRETATION_UNANCHORED_OR_PROMOTED"):
            self.run_build()

    def test_interpretation_cannot_use_other_concept_definitions(self):
        self.manifest["interpretation_candidates"][0]["concept_id"] = (
            "concept:wujub-candidate")
        with self.assertRaisesRegex(CatalogError, "INTERPRETATION_UNANCHORED_OR_PROMOTED"):
            self.run_build()

    def test_fake_juristic_disagreement_field_refused(self):
        self.manifest["definition_comparisons"][0]["scholarly_disagreement"] = True
        with self.assertRaisesRegex(CatalogError, "DEFINITION_COMPARISON_FIELDS_INVALID"):
            self.run_build()

    def test_duplicate_reversed_comparison_rejected(self):
        self.manifest["definition_comparisons"].append({
            **self.manifest["definition_comparisons"][0],
            "id": "comparison:reverse",
            "definition_candidate_ids": ["definition:amr-b", "definition:amr-a"],
        })
        with self.assertRaisesRegex(CatalogError, "DEFINITION_COMPARISON_DUPLICATE"):
            self.run_build()

    def test_comparison_must_use_two_different_definition_ids(self):
        self.manifest["definition_comparisons"][0]["definition_candidate_ids"] = [
            "definition:amr-a", "definition:amr-a"]
        with self.assertRaisesRegex(CatalogError, "DEFINITION_COMPARISON_UNATTESTED"):
            self.run_build()

    def test_initial_manifest_cannot_claim_parent(self):
        self.manifest["previous_manifest_sha256"] = "a"*64
        with self.assertRaisesRegex(CatalogError, "INITIAL_MANIFEST_PARENT_MUST_BE_NULL"):
            self.run_build()

    def test_append_only_version_adds_new_candidate(self):
        prior = copy.deepcopy(self.manifest)
        pin = sha(canonical(normalize_manifest(prior)))
        self.manifest["previous_manifest_sha256"] = pin
        self.manifest["definition_candidates"].append({
            **self.manifest["definition_candidates"][0],
            "id": "definition:amr-new",
            "version": "0.2.0",
            "definition_commitment_sha256": sha(b"synthetic-new"),
        })
        report = build_definitions(self.receipt, TRUSTED_RECEIPT_SHA,
                                   self.manifest, prior, pin)
        self.assertEqual(report["definition_candidate_count"], 3)
        self.assertEqual(report["previous_manifest_sha256"], pin)

    def test_append_only_forbids_mutating_existing_definition(self):
        prior = copy.deepcopy(self.manifest)
        pin = sha(canonical(normalize_manifest(prior)))
        self.manifest["previous_manifest_sha256"] = pin
        self.manifest["definition_candidates"][0]["definition_commitment_sha256"] = "f"*64
        with self.assertRaisesRegex(CatalogError, "APPEND_ONLY_RECORD_MUTATION_OR_DELETION"):
            build_definitions(self.receipt, TRUSTED_RECEIPT_SHA,
                              self.manifest, prior, pin)

    def test_append_only_forbids_deleting_old_source(self):
        prior = copy.deepcopy(self.manifest)
        pin = sha(canonical(normalize_manifest(prior)))
        self.manifest["previous_manifest_sha256"] = pin
        self.manifest["sources"].clear()
        with self.assertRaisesRegex(CatalogError, "APPEND_ONLY_RECORD_MUTATION_OR_DELETION"):
            build_definitions(self.receipt, TRUSTED_RECEIPT_SHA,
                              self.manifest, prior, pin)

    def test_append_only_requires_correct_independent_parent_pin(self):
        prior = copy.deepcopy(self.manifest)
        self.manifest["previous_manifest_sha256"] = "f"*64
        with self.assertRaisesRegex(CatalogError, "APPEND_ONLY_PARENT_PIN_MISMATCH"):
            build_definitions(self.receipt, TRUSTED_RECEIPT_SHA,
                              self.manifest, prior, "f"*64)

    def test_wrong_definition_version_refused(self):
        self.manifest["definition_candidates"][0]["version"] = "latest"
        with self.assertRaisesRegex(CatalogError, "DEFINITION_ATTRIBUTION_OR_STATUS_INVALID"):
            self.run_build()

    def test_cli_rejects_private_prose_and_uses_metadata_only_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            from engines.usul.concept_definitions import main
            from unittest.mock import patch
            import sys
            f = Path(tmp)
            p1, p2, out = (f / name for name in
                           ("receipt.json", "manifest.json", "out.json"))
            p1.write_text(json.dumps(self.receipt), encoding="utf-8")
            self.manifest["definition_candidates"][0]["text"] = "private"
            p2.write_text(json.dumps(self.manifest), encoding="utf-8")
            with patch.object(sys, "argv", ["app",
                    "--basis-receipt", str(p1),
                    "--trusted-basis-sha256", TRUSTED_RECEIPT_SHA,
                    "--manifest", str(p2), "--out", str(out)]):
                self.assertEqual(main(), 2)
            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertEqual(data["status"], "U02_DEFINITION_METADATA_REJECTED")
            self.assertNotIn("private", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
