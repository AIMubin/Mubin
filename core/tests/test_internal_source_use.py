"""Synthetic negative and positive tests for Mubin's internal source gate."""
import copy
import unittest

from core.internal_source_use import assess_internal_source_use

PIN = "e" * 64


class InternalSourceGateTests(unittest.TestCase):
    def setUp(self):
        self.source = dict(
            source_id="source:example", source_kind="usul", work_id="work:example",
            edition_id="edition:local", source_sha256=PIN,
            verification_scope="PINNED_SOURCE_BYTES_MATCHED",
            redistribution_status="NOT_CLEARED")
        self.record = dict(work_type="usul", source_reference="source:example",
                           purpose_code="AI_ALGORITHM_DEVELOPMENT",
                           use_date="2026-10-22")
        self.attested = dict(
            basis="SA_2026_ART26_4_AI_DEVELOPMENT",
            lawfully_published=True, lawfully_acquired=True,
            purpose_bounded=True, private_local_storage=True,
            applicability_checked=True, contract_and_access_terms_checked=True,
            no_public_distribution=True, no_unnecessary_final_product_inclusion=True,
            normal_exploitation_respected=True, legitimate_interests_respected=True,
            independent_rights_respected=True, usage_register_retained=True,
            commercial_context="NONCOMMERCIAL", commercial_exception_checked=False,
            nonprofit_activity=True, author_and_source_attributed=True)

    def assess(self):
        return assess_internal_source_use(
            self.source, self.attested, independently_pinned_sha256=PIN,
            use_record=self.record)

    def test_development_does_not_wait_for_redistribution_clearance(self):
        for status in ("UNKNOWN", "NOT_CLEARED", "RESTRICTED", "REDISTRIBUTION_PERMITTED"):
            with self.subTest(rights=status):
                self.source["redistribution_status"] = status
                r = self.assess()
                self.assertTrue(r["internal_development_eligible"])
                for key in ("public_redistribution_authorized", "scholarly_verified",
                            "juristic_inference_allowed", "public_fatwa_authorized",
                            "operator_attestations_independently_verified"):
                    self.assertFalse(r[key])

    def test_all_five_engine_kinds_supported_without_public_licence(self):
        for kind in ("quran", "hadith", "tafsir", "usul", "fiqh"):
            with self.subTest(kind=kind):
                self.source["source_kind"] = kind
                self.record["work_type"] = kind
                self.assertTrue(self.assess()["internal_development_eligible"])

    def test_nonprofit_research_basis_supported_with_attribution(self):
        self.attested["basis"] = "SA_2026_ART26_2_NONPROFIT_RESEARCH"
        self.record["purpose_code"] = "NONPROFIT_RESEARCH"
        self.assertTrue(self.assess()["internal_development_eligible"])

    def test_nonprofit_without_attribution_denied(self):
        self.attested["basis"] = "SA_2026_ART26_2_NONPROFIT_RESEARCH"
        self.record["purpose_code"] = "NONPROFIT_RESEARCH"
        self.attested["author_and_source_attributed"] = False
        self.assertEqual(self.assess()["status"], "NONPROFIT_RESEARCH_SCOPE_INVALID")

    def test_nonprofit_commercial_denied(self):
        self.attested["basis"] = "SA_2026_ART26_2_NONPROFIT_RESEARCH"
        self.record["purpose_code"] = "NONPROFIT_RESEARCH"
        self.attested["commercial_context"] = "LIMITED_COMMERCIAL_EXCEPTION"
        self.attested["commercial_exception_checked"] = True
        self.assertEqual(self.assess()["status"], "NONPROFIT_RESEARCH_SCOPE_INVALID")

    def test_ai_purpose_mismatch_denied(self):
        self.record["purpose_code"] = "NONPROFIT_RESEARCH"
        self.assertEqual(self.assess()["status"], "AI_DEVELOPMENT_PURPOSE_INVALID")

    def test_unlawful_or_unknown_publication_holds_only_source(self):
        self.attested["lawfully_published"] = False
        self.assertFalse(self.assess()["internal_development_eligible"])

    def test_unlawful_or_unknown_acquisition_holds_only_source(self):
        self.attested["lawfully_acquired"] = False
        self.assertFalse(self.assess()["internal_development_eligible"])

    def test_unbounded_copying_not_accepted(self):
        self.attested["purpose_bounded"] = False
        self.assertEqual(self.assess()["status"], "PURPOSE_OR_STORAGE_OUT_OF_SCOPE")

    def test_public_storage_not_accepted(self):
        self.attested["private_local_storage"] = False
        self.assertFalse(self.assess()["internal_development_eligible"])

    def test_unreviewed_applicability_rejected(self):
        self.attested["applicability_checked"] = False
        self.assertFalse(self.assess()["internal_development_eligible"])

    def test_unreviewed_access_terms_rejected(self):
        self.attested["contract_and_access_terms_checked"] = False
        self.assertEqual(self.assess()["status"], "LEGAL_BASIS_OR_ACCESS_TERMS_UNCONFIRMED")

    def test_dissemination_and_harm_assessments_required(self):
        for key in ("no_public_distribution", "no_unnecessary_final_product_inclusion",
                    "normal_exploitation_respected", "legitimate_interests_respected",
                    "independent_rights_respected"):
            with self.subTest(key=key):
                self.attested[key] = False
                self.assertEqual(self.assess()["status"],
                                 "USE_IMPACT_OR_DISCLOSURE_RESTRICTIONS_UNCONFIRMED")
                self.attested[key] = True

    def test_usage_register_required(self):
        self.attested["usage_register_retained"] = False
        self.assertEqual(self.assess()["status"], "USAGE_REGISTER_REQUIRED")

    def test_usage_record_ref_and_work_type_must_match_source(self):
        self.record["source_reference"] = "source:forged"
        self.assertEqual(self.assess()["status"], "USAGE_RECORD_REFERENCE_OR_PURPOSE_INVALID")
        self.record["source_reference"] = "source:example"
        self.record["work_type"] = "hadith"
        self.assertEqual(self.assess()["status"], "USAGE_RECORD_REFERENCE_OR_PURPOSE_INVALID")

    def test_usage_record_must_not_contain_private_path(self):
        self.record["private_path"] = "/tmp/secret"
        self.assertEqual(self.assess()["status"], "INVALID_USAGE_RECORD_SCHEMA")

    def test_usage_date_must_be_real_and_canonical(self):
        for value in ("2026-13-22", "2026-02-30", "2026-2-2", "2026-10-22Z"):
            self.record["use_date"] = value
            self.assertEqual(self.assess()["status"], "USAGE_RECORD_DATE_INVALID")

    def test_unassessed_commercial_context_denied(self):
        self.attested["commercial_context"] = "UNASSESSED_COMMERCIAL"
        self.assertEqual(self.assess()["status"], "COMMERCIAL_CONTEXT_UNASSESSED")

    def test_limited_commercial_exception_requires_check(self):
        self.attested["commercial_context"] = "LIMITED_COMMERCIAL_EXCEPTION"
        self.assertEqual(self.assess()["status"], "COMMERCIAL_EXCEPTION_UNCONFIRMED")
        self.attested["commercial_exception_checked"] = True
        self.assertTrue(self.assess()["internal_development_eligible"])

    def test_source_not_verifiable_does_not_promote(self):
        self.source["verification_scope"] = "SCHOLARLY_VERIFIED"
        self.assertEqual(self.assess()["status"], "SOURCE_NOT_BYTE_VERIFIED")

    def test_self_asserted_hash_not_a_trusted_pin(self):
        r = assess_internal_source_use(
            self.source, self.attested, independently_pinned_sha256=None,
            use_record=self.record)
        self.assertEqual(r["status"], "INDEPENDENT_SOURCE_PIN_REQUIRED")

    def test_hash_mismatch_rejected(self):
        r = assess_internal_source_use(
            self.source, self.attested, independently_pinned_sha256="f" * 64,
            use_record=self.record)
        self.assertEqual(r["status"], "SOURCE_PIN_MISMATCH")

    def test_extra_private_text_field_rejected(self):
        self.source["copyrighted_text"] = "TEST-SECRET-VALUE"
        r = self.assess()
        self.assertEqual(r["status"], "INVALID_SOURCE_SCHEMA")
        self.assertNotIn("TEST-SECRET-VALUE", repr(r))

    def test_fake_permission_field_cannot_bypass_release_gate(self):
        self.attested["public_redistribution_authorized"] = True
        self.assertEqual(self.assess()["status"], "INVALID_ATTESTATION_SCHEMA")

    def test_nonboolean_attestations_fail_closed(self):
        self.attested["lawfully_acquired"] = 1
        self.assertEqual(self.assess()["status"], "INVALID_ATTESTATION_SCHEMA")

    def test_nonstring_unhashable_basis_fails_safely(self):
        self.attested["basis"] = ["SA_2026_ART26_4_AI_DEVELOPMENT"]
        self.assertEqual(self.assess()["status"], "UNSUPPORTED_USE_BASIS")

    def test_unknown_legal_basis_is_not_accepted(self):
        self.attested["basis"] = "ANY_AI_DEVELOPMENT_ALLOWED"
        self.assertEqual(self.assess()["status"], "UNSUPPORTED_USE_BASIS")

    def test_outputs_have_no_secret_or_path_fields(self):
        r = self.assess()
        self.assertNotIn("source_id", r)
        self.assertNotIn("private_path", r)
        self.assertFalse(r["operator_attestations_independently_verified"])

    def test_invalid_source_types_rejected(self):
        for bad in (None, [], {"source_id": ["source:example"]}):
            r = assess_internal_source_use(
                bad, self.attested, independently_pinned_sha256=PIN,
                use_record=self.record)
            self.assertFalse(r["internal_development_eligible"])

    def test_malformed_nested_records_do_not_crash(self):
        for bad in (None, ["any"], {"use_date": ["2026-10-22"]}):
            r = assess_internal_source_use(
                self.source, self.attested, independently_pinned_sha256=PIN,
                use_record=bad)
            self.assertFalse(r["internal_development_eligible"])


if __name__ == "__main__":
    unittest.main()
