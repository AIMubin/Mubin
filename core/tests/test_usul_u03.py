"""U0.3 research-question cards: unreviewed metadata, never an Usul rule."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.usul.claims import assess_cards, validate_cards
from core.usul.docket import assess_docket

ROOT = Path(__file__).resolve().parents[2]
PARENT = ROOT / "research/usul/u02-risala-source-candidates.json"
CARDS = ROOT / "research/usul/u03-risala-hypothesis-cards.json"
GATES = (
    "independent_edition_collation",
    "author_editor_attribution",
    "legal_use_basis_review",
    "methodology_and_disagreement_review",
    "conditions_exceptions_counterexamples",
    "two_independent_scholarly_reviews",
)

class ResearchCardsTests(unittest.TestCase):
    def setUp(self):
        self.parent = json.loads(PARENT.read_text(encoding="utf-8"))
        self.cards = json.loads(CARDS.read_text(encoding="utf-8"))

    def reject(self, cards=None, parent=None):
        problems = validate_cards(cards if cards is not None else self.cards,
                                  parent if parent is not None else self.parent)
        self.assertTrue(problems, "an unsafe research metadata change was accepted")
        return problems

    def test_parent_fingerprint_and_four_unreviewed_cards(self):
        result = assess_cards(self.cards, self.parent)
        self.assertTrue(result["valid_metadata"], result["errors"])
        self.assertTrue(result["source_docket_match"])
        self.assertEqual(assess_docket(self.parent)["docket_sha256"],
                         self.cards["source_docket_sha256"])
        self.assertEqual(4, result["hypothesis_count"])
        self.assertEqual(0, result["reviewed_rule_count"])
        self.assertEqual("research_questions_only", result["scope"])
        self.assertFalse(result["eligible_for_engine"])
        self.assertFalse(result["human_review_performed"])
        self.assertFalse(result["scholarly_authority_verified"])
        self.assertEqual(24, result["pending_evidence_gate_count"])
        self.assertEqual(64, len(result["card_set_sha256"]))

    def test_cards_bound_to_exact_parent_ids_and_topics(self):
        base = {x["candidate_id"]: x for x in self.parent["candidates"]}
        for c in self.cards["cards"]:
            p = base[c["candidate_id"]]
            self.assertEqual(p["topic_id"], c["topic_id"])
            self.assertEqual(p["locator"]["route_id"], c["source_route_id"])
            self.assertEqual(p["heading_provenance"], c["heading_provenance"])

    def test_all_evidence_gates_held_closed(self):
        for c in self.cards["cards"]:
            self.assertEqual(GATES, tuple(g["gate_id"] for g in c["evidence_gates"]))
            self.assertTrue(all(g["status"] == "not_completed" for g in c["evidence_gates"]))

    def test_swapped_card_ids_are_rejected(self):
        x = copy.deepcopy(self.cards)
        x["cards"][0]["card_id"], x["cards"][1]["card_id"] = (
            x["cards"][1]["card_id"], x["cards"][0]["card_id"])
        self.reject(x)

    def test_swapped_candidate_and_route_are_rejected(self):
        for field in ("candidate_id", "source_route_id", "topic_id", "heading_provenance"):
            with self.subTest(field=field):
                x = copy.deepcopy(self.cards)
                x["cards"][0][field], x["cards"][3][field] = (
                    x["cards"][3][field], x["cards"][0][field])
                self.reject(x)

    def test_dropping_or_duplicating_card_rejected(self):
        x = copy.deepcopy(self.cards)
        x["cards"].pop()
        self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"].append(copy.deepcopy(x["cards"][0]))
        self.reject(x)

    def test_mismatching_or_invalid_parent_rejected(self):
        x = copy.deepcopy(self.cards)
        x["source_docket_sha256"] = "0"*64
        self.reject(x)
        y = copy.deepcopy(self.parent)
        y["candidates"][3]["heading_provenance"] = "undetermined"
        self.reject(parent=y)

    def test_no_fake_rules_or_reviews_or_text(self):
        for field, val in (
            ("rule_ast", {"op":"fact"}), ("author_quote","invented"),
            ("p1_receipt", {"verified":True}), ("reviewers",[{"accepted":True}]),
            ("text","raw source"), ("eligible_for_engine",True),
        ):
            with self.subTest(field=field):
                x = copy.deepcopy(self.cards)
                x["cards"][0][field] = val
                self.reject(x)

    def test_no_review_gate_approval(self):
        for field, value in (
            ("review_status","approved"),("rule_status","executable"),
            ("formulation_provenance","author_quotation"),
        ):
            with self.subTest(field=field):
                x = copy.deepcopy(self.cards)
                x["cards"][0][field] = value
                self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"][0]["evidence_gates"][0]["status"] = "completed"
        self.reject(x)

    def test_evidence_axes_identity_and_order_are_frozen(self):
        x = copy.deepcopy(self.cards)
        x["cards"][0]["evidence_gates"].reverse()
        self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"][1]["evidence_gates"][1]["gate_id"] = GATES[0]
        self.reject(x)

    def test_cannot_swap_editorship_caveat_on_ijma(self):
        x = copy.deepcopy(self.cards)
        x["cards"][3]["heading_provenance"] = "printed_variant_reported"
        self.reject(x)

    def test_only_question_form_accepted_not_semantically_certified(self):
        x = copy.deepcopy(self.cards)
        x["cards"][0]["question_ar"] = "ثبت الحكم بإجماع العلماء."
        self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"][0]["question_ar"] = "هل يوجد دليل جديد؟"
        self.assertEqual([], validate_cards(x, self.parent))
        self.assertFalse(assess_cards(x, self.parent)["scholarly_authority_verified"])

    def test_order_stable_digest(self):
        a = assess_cards(self.cards, self.parent)
        x = copy.deepcopy(self.cards)
        x["cards"].reverse()
        b = assess_cards(x, self.parent)
        self.assertEqual(a["card_set_sha256"], b["card_set_sha256"])
        self.assertEqual(a["review_queue"], b["review_queue"])

    def test_programmatic_subclasses_aliases_and_cycles_rejected(self):
        class Lie(dict):
            def __eq__(self, other): return True
        x = Lie(copy.deepcopy(self.cards))
        self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"][0] = Lie(x["cards"][0])
        self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"][0]["conditions_to_check"] = x["cards"][1]["conditions_to_check"]
        self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"][0]["extra"] = []
        x["cards"][0]["extra"].append(x["cards"][0]["extra"])
        self.reject(x)

    def test_reject_budgets_and_bad_unicode(self):
        x = copy.deepcopy(self.cards)
        x["cards"][0]["question_ar"] = "A" * 100000
        self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"][0]["question_ar"] = "\\ud800"
        self.reject(x)
        x = copy.deepcopy(self.cards)
        x["cards"][0]["conditions_to_check"] = ["x"] * 2000
        self.reject(x)

    def test_cli_success_and_wrong_parent(self):
        cmd = [sys.executable, "-m", "core.usul.claims_cli", str(CARDS), str(PARENT), "--json"]
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=20)
        self.assertEqual(0, r.returncode, r.stderr)
        j = json.loads(r.stdout)
        self.assertTrue(j["valid_metadata"])
        self.assertFalse(j["eligible_for_engine"])
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bad.json"
            x = copy.deepcopy(self.cards)
            x["source_docket_sha256"] = "0"*64
            p.write_text(json.dumps(x, ensure_ascii=False), encoding="utf-8")
            r = subprocess.run([sys.executable,"-m","core.usul.claims_cli",
                                str(p),str(PARENT),"--json"],
                               cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(1,r.returncode,r.stderr)

    def test_cli_duplicate_json_and_nonfinite_rejected(self):
        raw = CARDS.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            p = Path(td)/"bad.json"
            for mutation in (
                raw.replace('"automatic_promotion": false',
                            '"automatic_promotion": true, "automatic_promotion": false',1),
                raw.replace('"automatic_promotion": false',
                            '"automatic_promotion": NaN',1),
            ):
                p.write_text(mutation,encoding="utf-8")
                r=subprocess.run([sys.executable,"-m","core.usul.claims_cli",
                                  str(p),str(PARENT),"--json"],
                                 cwd=ROOT,capture_output=True,text=True,timeout=20)
                self.assertEqual(2,r.returncode,(r.stdout,r.stderr))

    def test_workflow_covers_u03_files(self):
        wf=(ROOT/".github/workflows/mubin-usul-synthetic.yml").read_text(encoding="utf-8")
        for text in ('"core/tests/test_usul_u03.py"','"schemas/usul-u03-**"',
                     '"docs/research/USUL-U03-**"','"docs/reviews/USUL-U03-**"'):
            self.assertEqual(2,wf.count(text),text)
        self.assertIn("python -m core.usul.claims_cli",wf)

if __name__ == "__main__":
    unittest.main()
