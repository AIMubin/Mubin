"""Synthetic, source-specific heritage rights-routing contract tests.

These do not establish legal rights to any real text or edition.
"""
from dataclasses import replace
import unittest

from core.source_policy import SourceUseRecord, assess_source_use


class HeritageSourceRightsTests(unittest.TestCase):
    def setUp(self):
        self.base = SourceUseRecord("synthetic:book:one", "classical_base_text")
        self.pd = replace(
            self.base, basis="public_domain", evidence_ref="review:synthetic:one",
            lawful_copy_provenance=True, independent_transcription=True,
            exact_layer_separated=True, source_attribution=True,
        )
        self.statutory = replace(
            self.base, basis="statutory_exception",
            evidence_ref="review:synthetic:two", lawful_original_publication=True,
            lawful_copy_provenance=True, exact_layer_separated=True,
            proportional_copy=True, source_attribution=True,
            noncommercial_research=True, no_unreasonable_rights_harm=True,
            short_quote_only=True,
        )

    def route(self, record, purpose):
        return assess_source_use(record, purpose).decision

    def test_unverified_readonly_bibliography_not_text_permission(self):
        self.assertEqual("proceed", self.route(self.base, "metadata_reference"))
        self.assertEqual("restricted", self.route(self.base, "ai_development_copy"))
        self.assertEqual("restricted", self.route(self.base, "full_text_publication"))

    def test_classical_original_distinct_from_edition(self):
        self.assertEqual("proceed", self.route(self.pd, "local_research"))
        self.assertEqual("proceed", self.route(self.pd, "ai_development_copy"))
        for layer in ("modern_edition_or_annotation", "publisher_database", "personal_annotation"):
            with self.subTest(layer=layer):
                self.assertEqual("restricted", self.route(replace(self.pd, asset_layer=layer), "ai_development_copy"))

    def test_public_domain_requires_specific_claim_and_transcription(self):
        for change in (
            {"evidence_ref": ""}, {"lawful_copy_provenance": False},
            {"independent_transcription": False}, {"exact_layer_separated": False},
            {"source_attribution": False},
        ):
            with self.subTest(change=change):
                self.assertEqual("restricted", self.route(replace(self.pd, **change), "local_research"))

    def test_stated_statutory_research_purpose_bounded(self):
        self.assertEqual("proceed", self.route(self.statutory, "local_research"))
        self.assertEqual("proceed", self.route(self.statutory, "ai_development_copy"))
        self.assertEqual("proceed", self.route(self.statutory, "short_public_quote"))
        self.assertEqual("restricted", self.route(self.statutory, "full_text_publication"))
        self.assertEqual("restricted", self.route(self.statutory, "dataset_redistribution"))

    def test_stated_statutory_facts_are_each_required(self):
        for key in ("lawful_original_publication", "lawful_copy_provenance",
                    "exact_layer_separated", "proportional_copy",
                    "no_unreasonable_rights_harm", "noncommercial_research"):
            with self.subTest(key=key):
                self.assertEqual("restricted", self.route(replace(self.statutory, **{key: False}), "ai_development_copy"))

    def test_database_not_granted_generic_statutory_exception(self):
        self.assertEqual("restricted", self.route(replace(self.statutory, asset_layer="publisher_database"), "ai_development_copy"))

    def test_license_scoped_to_named_actions(self):
        r = replace(
            self.base, basis="explicit_license", evidence_ref="license:synthetic",
            lawful_copy_provenance=True, exact_layer_separated=True,
            source_attribution=True, permitted_scopes=("local_research",),
        )
        self.assertEqual("proceed", self.route(r, "local_research"))
        self.assertEqual("restricted", self.route(r, "ai_development_copy"))
        self.assertEqual("restricted", self.route(replace(r, source_attribution=False), "local_research"))

    def test_claim_is_local_not_global(self):
        held = replace(self.pd, claim_status="pending_review")
        other = replace(self.pd, source_id="synthetic:other")
        self.assertEqual("source_hold", self.route(held, "metadata_reference"))
        self.assertEqual("source_hold", self.route(replace(held, claim_status="substantiated"), "ai_development_copy"))
        self.assertEqual("proceed", self.route(other, "ai_development_copy"))

    def test_private_user_notes_never_metadata_public(self):
        self.assertEqual("restricted", self.route(replace(self.base, asset_layer="personal_annotation"), "metadata_reference"))

    def test_invalid_untrusted_fields_fail_closed(self):
        for change in (
            {"basis": []}, {"claim_status": []}, {"asset_layer": {}},
            {"lawful_copy_provenance": 1},
            {"permitted_scopes": (["local_research"],)},
            {"source_id": " "},
        ):
            with self.subTest(change=change):
                self.assertEqual("invalid", self.route(replace(self.base, **change), "local_research"))
        self.assertEqual("invalid", self.route(self.pd, "undefined_use"))

    def test_unicode_directional_spoofing_rejected(self):
        # A displayed evidence ref must not conceal altered source identity.
        for field, value in (
            ("source_id", "synthetic:book:\u202Eevil"),
            ("evidence_ref", "rights:review:\u2066hidden"),
            ("source_id", "synthetic:book:\u007Fhidden"),
        ):
            with self.subTest(field=field):
                self.assertEqual(
                    "invalid", self.route(replace(self.pd, **{field: value}), "local_research")
                )

    def test_policy_documents_and_complaint_template_trigger_ci(self):
        from pathlib import Path
        root = Path(__file__).resolve().parents[2]
        workflow = (root / ".github/workflows/mubin-inference-foundation.yml").read_text(
            encoding="utf-8"
        )
        for path in ('"RIGHTS_NOTICE.md"', '"docs/governance/**"',
                     '".github/ISSUE_TEMPLATE/**"'):
            with self.subTest(path=path):
                # Both pull-request and main push event filters must include path.
                self.assertGreaterEqual(workflow.count(path), 2)

    def test_no_false_rights_certification_in_response(self):
        result = assess_source_use(self.statutory, "ai_development_copy")
        self.assertEqual("operator_declarations_only", result.assurance)
        self.assertNotIn("rights_verified", result.__dict__)
