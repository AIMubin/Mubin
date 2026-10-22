import copy
import unittest

from engines.usul.executor import ContractError, evaluate


def scenario():
    # All atoms are synthetic: no Quran/hadith/legal claim is encoded.
    return {
        "schema_version": "0.1.0",
        "methodology_id": "demo:profile",
        "facts": [
            {"atom": "demo:premise", "truth": "true", "source_evidence_ids": ["demo:ev1"]},
            {"atom": "demo:exception", "truth": "false", "source_evidence_ids": ["demo:ev2"]},
        ],
        "rules": [{
            "id": "demo:rule",
            "methodology_id": "demo:profile",
            "rule_kind": "propositional_demo",
            "if_all": [{"atom": "demo:premise", "truth": "true"}],
            "unless_any": [{"atom": "demo:exception", "truth": "true"}],
            "then": {"atom": "demo:output", "truth": "true"},
            "source_evidence_ids": ["demo:ev3"],
        }],
        "objections": [],
    }


class UsulPrototypeTests(unittest.TestCase):
    def test_explicit_true_with_explicit_cleared_exception(self):
        result = evaluate(scenario())
        self.assertEqual(result["conclusions"]["demo:output"]["status"], "CONDITIONALLY_SUPPORTED")
        self.assertEqual(result["trace"][0]["status"], "CONDITIONALLY_SUPPORTED")
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["public_fatwa_authorized"])

    def test_missing_premise_is_unknown_not_false(self):
        case = scenario()
        case["facts"] = [case["facts"][1]]
        result = evaluate(case)
        self.assertEqual(result["trace"][0]["status"], "UNDETERMINED")

    def test_missing_exception_not_treated_as_cleared(self):
        case = scenario()
        case["facts"] = [case["facts"][0]]
        self.assertEqual(evaluate(case)["trace"][0]["status"], "UNDETERMINED")

    def test_triggered_exception_blocks(self):
        case = scenario()
        case["facts"][1]["truth"] = "true"
        self.assertEqual(evaluate(case)["trace"][0]["status"], "BLOCKED_BY_EXCEPTION")

    def test_explicit_negative_fact_not_closed_world_default(self):
        case = scenario()
        case["facts"][0]["truth"] = "false"
        self.assertEqual(evaluate(case)["trace"][0]["status"], "NOT_APPLICABLE")

    def test_open_objection_blocks(self):
        case = scenario()
        case["objections"] = [{"id": "demo:obj", "rule_id": "demo:rule", "status": "open",
                               "source_evidence_ids": ["demo:ev4"]}]
        self.assertEqual(evaluate(case)["trace"][0]["status"], "BLOCKED_BY_OBJECTION")
        case["objections"][0]["status"] = "answered"
        self.assertEqual(evaluate(case)["trace"][0]["status"], "CONDITIONALLY_SUPPORTED")

    def test_opposing_rules_are_contested_not_arbitrarily_chosen(self):
        case = scenario()
        opposing = copy.deepcopy(case["rules"][0])
        opposing["id"] = "demo:opposing"
        opposing["then"]["truth"] = "false"
        case["rules"].append(opposing)
        result = evaluate(case)
        self.assertEqual(result["conclusions"]["demo:output"]["status"], "CONTESTED")
        self.assertIsNone(result["conclusions"]["demo:output"]["supported_truth"])

    def test_rule_conclusion_conflicting_with_explicit_fact_is_contested(self):
        case = scenario()
        case["facts"].append({
            "atom": "demo:output", "truth": "false",
            "source_evidence_ids": ["demo:contradictory_fact"],
        })
        result = evaluate(case)
        self.assertEqual(result["conclusions"]["demo:output"]["status"], "CONTESTED")
        self.assertTrue(result["conclusions"]["demo:output"]["conflicts_with_explicit_input_fact"])
        self.assertIsNone(result["conclusions"]["demo:output"]["supported_truth"])

    def test_trace_preserves_evidence_identifiers_without_verifying_them(self):
        result = evaluate(scenario())
        self.assertEqual(result["trace"][0]["rule_source_evidence_ids"], ["demo:ev3"])
        self.assertEqual(result["trace"][0]["premise_source_evidence_ids"]["demo:premise"], ["demo:ev1"])
        self.assertFalse(result["input_evidence_ids_externally_verified"])

    def test_rule_chaining_does_not_occur(self):
        case = scenario()
        second = copy.deepcopy(case["rules"][0])
        second["id"] = "demo:second"
        second["if_all"] = [{"atom": "demo:output", "truth": "true"}]
        second["then"] = {"atom": "demo:next", "truth": "true"}
        second["unless_any"] = []
        case["rules"].append(second)
        result = evaluate(case)
        self.assertEqual(result["conclusions"]["demo:next"]["status"], "UNDETERMINED")

    def test_cross_methodology_or_qiyas_is_rejected(self):
        for key, value in (("methodology_id", "demo:other"), ("rule_kind", "qiyas")):
            case = scenario()
            case["rules"][0][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                evaluate(case)

    def test_duplicate_fact_and_unverified_source_ids_rejected(self):
        case = scenario()
        case["facts"].append(copy.deepcopy(case["facts"][0]))
        with self.assertRaises(ContractError):
            evaluate(case)
        case = scenario()
        case["rules"][0]["source_evidence_ids"] = []
        with self.assertRaises(ContractError):
            evaluate(case)

    def test_malformed_fields_and_boolean_laundering_rejected(self):
        for transform in (
            lambda x: x.update({"extra": True}),
            lambda x: x["rules"][0]["then"].update({"truth": True}),
            lambda x: x["facts"][0].update({"truth": "unknown"}),
        ):
            case = scenario()
            transform(case)
            with self.assertRaises(ContractError):
                evaluate(case)

    def test_same_conclusion_preserves_multiple_supports(self):
        case = scenario()
        second = copy.deepcopy(case["rules"][0])
        second["id"] = "demo:two"
        case["rules"].append(second)
        result = evaluate(case)
        self.assertEqual(result["conclusions"]["demo:output"]["status"], "CONDITIONALLY_SUPPORTED")
        self.assertEqual(len(result["conclusions"]["demo:output"]["supporting_rule_ids"]), 2)


if __name__ == "__main__":
    unittest.main()
