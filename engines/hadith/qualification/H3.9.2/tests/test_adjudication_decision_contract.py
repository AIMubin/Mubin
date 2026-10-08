from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


class Schema31DecisionContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(__file__).resolve().parents[1]
        cls.contract_path = cls.root / "config" / "adjudication-decision-contract.json"
        cls.schema_path = cls.root / "schemas" / "adjudication-decision.schema.json"
        cls.reviewer_schema_path = cls.root / "schemas" / "adjudication-reviewer-registry.schema.json"
        cls.status_path = cls.root / "artifacts" / "H3.9.2-STATUS.json"
        cls.contract = json.loads(cls.contract_path.read_text(encoding="utf-8"))
        cls.schema = json.loads(cls.schema_path.read_text(encoding="utf-8"))
        cls.reviewer_schema = json.loads(cls.reviewer_schema_path.read_text(encoding="utf-8"))
        cls.status = json.loads(cls.status_path.read_text(encoding="utf-8"))

    def test_contract_is_bound_to_exact_schema30_packet(self):
        self.assertEqual(self.contract["protocol_freeze_schema"], 31)
        scope = self.contract["scope"]
        self.assertEqual(scope["packet_workflow_run_id"], 37722153068)
        self.assertEqual(scope["packet_artifact_id"], 11526263194)
        self.assertEqual(scope["case_count"], 158)
        self.assertEqual(
            scope["layer_counts"],
            {"primary": 129, "reserve01": 24, "reserve02": 5},
        )
        self.assertEqual(
            scope["benchmark_counts"],
            {"external-critical-commentary": 158},
        )

    def test_ai_cannot_be_decision_authority(self):
        authority = self.contract["authority_model"]
        self.assertTrue(authority["terminal_decisions_are_human_actions"])
        self.assertFalse(authority["ai_may_fill_reviewer_identity_or_attestation"])
        self.assertFalse(authority["ai_may_cast_or_self_authorize_decision"])
        self.assertTrue(authority["model_agreement_is_never_authority"])
        self.assertTrue(
            authority["pinned_human_authored_authority_statement_may_be_evidence"]
        )
        self.assertTrue(
            authority["authority_evidence_does_not_replace_human_signoff"]
        )
        self.assertEqual(
            authority["canonical_terminal_decision_path"], "terminal_signoff.decision"
        )
        self.assertTrue(authority["terminal_signoff_must_be_human_attested"])
        self.assertTrue(authority["unattested_top_level_terminal_decision_forbidden"])

    def test_terminal_quorum_requires_independent_source_verification(self):
        q = self.contract["terminal_quorum"]
        for terminal in ("accepted", "rejected"):
            self.assertEqual(q[terminal]["minimum_qualified_reviewers"], 1)
            self.assertTrue(q[terminal]["independent_source_verifier_required"])
            self.assertTrue(q[terminal]["nonempty_rationale_required"])
            self.assertTrue(q[terminal]["adjudicator_required_on_material_disagreement"])
        self.assertTrue(q["accepted"]["source_verified_must_be_true"])
        self.assertTrue(q["accepted"]["accepted_candidate_binding_required"])
        self.assertTrue(q["rejected"]["rejection_reason_required"])

    def test_expert_gold_escalation_preserves_stronger_curation_rule(self):
        policy = self.contract["gold_status_escalation_policy"]
        self.assertEqual(policy["expert_gold_minimum_distinct_reviewers"], 2)
        self.assertTrue(policy["expert_gold_independent_adjudicator_required"])
        self.assertTrue(policy["expert_gold_source_verifier_required"])
        self.assertTrue(policy["expert_gold_rule_overrides_lower_risk_tier_quorum"])
        self.assertTrue(
            policy[
                "derived_adjudicative_judgment_must_not_be_downgraded_to_source_attributed_to_avoid_expert_review"
            ]
        )

    def test_deferred_remains_pending_and_nonreplaceable(self):
        q = self.contract["terminal_quorum"]["deferred"]
        self.assertTrue(q["remains_pending"])
        self.assertFalse(q["replacement_eligible"])
        self.assertFalse(q["independent_source_verifier_required"])
        self.assertTrue(self.contract["deferred_record_policy"]["remains_pending"])
        self.assertFalse(
            self.contract["deferred_record_policy"]["replacement_eligible"]
        )

    def test_independence_and_conflict_rules_are_frozen(self):
        policy = self.contract["independence_and_conflict_policy"]
        self.assertTrue(policy["reviewer_and_source_verifier_must_be_distinct"])
        self.assertTrue(
            policy["adjudicator_must_be_distinct_from_all_case_reviewers_and_source_verifier"]
        )
        self.assertTrue(policy["human_case_curator_may_not_be_terminal_reviewer_of_same_case"])
        self.assertTrue(policy["undisclosed_material_conflict_invalidates_signoff"])
        self.assertTrue(policy["recused_reviewer_may_not_contribute_to_quorum"])
        self.assertTrue(policy["ai_systems_may_not_occupy_human_roles"])
        self.assertTrue(policy["distinct_person_checks_use_person_binding_sha256"])
        self.assertTrue(policy["per_case_conflict_declaration_required_for_every_signing_role"])
        self.assertTrue(policy["per_case_recusal_must_be_false_for_every_counted_signoff"])

    def test_schema31_authorizes_review_after_template_execution_freeze(self):
        gates = self.contract["execution_gates"]
        self.assertTrue(gates["human_review_may_begin_under_this_contract"])
        self.assertNotIn("human_review_blocked_reason", gates)
        self.assertEqual(
            gates["human_review_authorization_basis"]["workflow_run_id"],
            37781676566,
        )
        migration = self.contract["template_migration_policy"]
        self.assertTrue(migration["required_before_human_review"])
        self.assertTrue(migration["requirement_satisfied"])
        self.assertTrue(migration["execution_frozen"])
        self.assertEqual(
            migration["execution_evidence_path"],
            "artifacts/SCHEMA31_DECISION_TEMPLATE_EVIDENCE_158.json",
        )
        self.assertFalse(migration["legacy_template_authorized_for_review"])
        self.assertTrue(migration["schema31_template_must_remove_unattested_top_level_decision"])
        self.assertTrue(migration["schema31_template_execution_evidence_must_be_frozen_before_review"])
        self.assertFalse(gates["repository_decision_ingestion_authorized"])
        self.assertFalse(gates["automatic_decision_application_authorized"])
        self.assertFalse(gates["automatic_reserve3_authorized"])
        self.assertFalse(gates["benchmark_population_mutation_authorized"])
        policy = self.contract["decision_record_policy"]
        self.assertTrue(policy["ingestion_must_validate_unique_reviewer_ids"])
        self.assertTrue(policy["ingestion_must_validate_cross_identity_independence"])
        self.assertTrue(policy["ingestion_must_validate_terminal_quorum"])
        self.assertTrue(policy["ingestion_must_validate_expert_gold_escalation"])
        self.assertTrue(policy["terminal_signoff_required"])
        self.assertEqual(policy["canonical_terminal_decision_path"], "terminal_signoff.decision")
        self.assertTrue(policy["ingestion_must_validate_terminal_signoff_coherence"])
        self.assertTrue(policy["ingestion_must_validate_case_conflict_and_recusal"])
        self.assertTrue(policy["ingestion_must_validate_unique_person_bindings"])
        self.assertTrue(policy["ingestion_must_validate_material_disagreement_truthfulness"])

    def test_repository_status_binds_exact_contract_bytes(self):
        self.assertEqual(self.status["freeze_schema_version"], 31)
        decision = self.status["adjudication_decision_contract"]
        self.assertEqual(
            decision["path"],
            "config/adjudication-decision-contract.json",
        )
        self.assertEqual(
            decision["schema_path"],
            "schemas/adjudication-decision.schema.json",
        )
        self.assertEqual(
            decision["contract_sha256"],
            hashlib.sha256(self.contract_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            decision["decision_schema_sha256"],
            hashlib.sha256(self.schema_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            decision["reviewer_registry_schema_path"],
            "schemas/adjudication-reviewer-registry.schema.json",
        )
        self.assertEqual(
            decision["reviewer_registry_schema_sha256"],
            hashlib.sha256(self.reviewer_schema_path.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            self.contract["reviewer_registry"]["schema_path"],
            "schemas/adjudication-reviewer-registry.schema.json",
        )
        self.assertTrue(self.contract["reviewer_registry"]["unique_reviewer_id_required"])
        self.assertTrue(self.contract["reviewer_registry"]["unique_person_binding_required"])
        self.assertTrue(self.contract["reviewer_registry"]["one_registry_entry_per_human"])
        self.assertEqual(
            self.contract["reviewer_registry"]["person_binding_method"],
            "hmac-sha256-custodian-secret-v1",
        )
        self.assertTrue(
            self.contract["reviewer_registry"]["person_binding_secret_must_remain_external"]
        )
        self.assertTrue(decision["human_review_authorized"])
        self.assertTrue(decision["template_migration_required_before_review"])
        self.assertTrue(decision["template_migration_requirement_satisfied"])
        self.assertTrue(decision["template_execution_frozen"])
        self.assertEqual(
            decision["template_execution_evidence_path"],
            "artifacts/SCHEMA31_DECISION_TEMPLATE_EVIDENCE_158.json",
        )
        self.assertFalse(decision["legacy_schema30_decision_template_authorized"])
        self.assertFalse(decision["decision_ingestion_authorized"])
        self.assertFalse(decision["automatic_reserve3_authorized"])

    def test_reviewer_registry_schema_requires_human_attested_roles(self):
        self.assertFalse(self.reviewer_schema["additionalProperties"])
        reviewer = self.reviewer_schema["properties"]["reviewers"]["items"]
        self.assertTrue(reviewer["properties"]["human"]["const"])
        self.assertEqual(
            set(reviewer["properties"]["roles"]["items"]["enum"]),
            {"qualified_reviewer", "source_verifier", "adjudicator"},
        )
        self.assertEqual(
            self.reviewer_schema["properties"]["person_binding_method"]["const"],
            "hmac-sha256-custodian-secret-v1",
        )
        self.assertEqual(
            reviewer["properties"]["person_binding_sha256"]["pattern"],
            "^[a-f0-9]{64}$",
        )
        self.assertTrue(reviewer["properties"]["identity_binding_attestation"]["const"])
        self.assertEqual(
            reviewer["properties"]["scope"]["items"]["enum"],
            ["external-critical-commentary"],
        )

    def test_decision_schema_is_narrow_and_human_attested(self):
        self.assertFalse(self.schema["additionalProperties"])
        self.assertEqual(
            self.schema["properties"]["benchmark_id"]["const"],
            "external-critical-commentary",
        )
        self.assertNotIn("decision", self.schema["properties"])
        terminal = self.schema["properties"]["terminal_signoff"]
        self.assertTrue(terminal["properties"]["human_attestation"]["const"])
        self.assertEqual(
            set(terminal["properties"]["signer_role"]["enum"]),
            {"qualified_reviewer", "adjudicator"},
        )
        self.assertEqual(terminal["properties"]["conflict_of_interest"]["const"], "none")
        self.assertFalse(terminal["properties"]["recused"]["const"])
        review = self.schema["properties"]["reviews"]["items"]
        self.assertEqual(
            review["properties"]["reviewer_role"]["const"],
            "qualified_reviewer",
        )
        self.assertTrue(
            review["properties"]["human_attestation"]["const"]
        )
        self.assertFalse(review["properties"]["recused"]["const"])
        source = self.schema["properties"]["source_verification"]["oneOf"][1]
        self.assertEqual(source["properties"]["conflict_of_interest"]["const"], "none")
        self.assertFalse(source["properties"]["recused"]["const"])
        adjudicator = self.schema["properties"]["adjudication"]["oneOf"][1]
        self.assertEqual(adjudicator["properties"]["conflict_of_interest"]["const"], "none")
        self.assertFalse(adjudicator["properties"]["recused"]["const"])
        self.assertEqual(
            self.schema["properties"]["reviewer_registry_snapshot_sha256"]["pattern"],
            "^[a-f0-9]{64}$",
        )


if __name__ == "__main__":
    unittest.main()
