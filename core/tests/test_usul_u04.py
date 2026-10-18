"""U0.4 source-display observations: research-only, no scholarly admissions."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.usul.observations import assess_observations, validate_observations

ROOT = Path(__file__).resolve().parents[2]
OBS = ROOT/"research/usul/u04-risala-text-observations.json"
CARDS = ROOT/"research/usul/u03-risala-hypothesis-cards.json"
DOCKET = ROOT/"research/usul/u02-risala-source-candidates.json"

class TextObservationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(OBS.read_text(encoding="utf-8"))
        self.cards = json.loads(CARDS.read_text(encoding="utf-8"))
        self.docket = json.loads(DOCKET.read_text(encoding="utf-8"))

    def reject(self, data=None, cards=None, docket=None):
        failures = validate_observations(
            self.data if data is None else data,
            self.cards if cards is None else cards,
            self.docket if docket is None else docket)
        self.assertTrue(failures, "unsafe observation accepted")
        return failures

    def test_four_observations_eight_tiny_excerpts(self):
        report = assess_observations(self.data, self.cards, self.docket)
        self.assertTrue(report["valid_metadata"], report["errors"])
        self.assertEqual("unverified_site_display_observations_only", report["scope"])
        self.assertEqual(4,report["observation_count"])
        self.assertEqual(8,report["excerpt_count"])
        self.assertEqual(0,report["approved_rule_count"])
        self.assertTrue(report["parent_bindings_match"])
        for k in ("eligible_for_engine","human_review_performed","edition_authenticated",
                  "source_bytes_pinned","legal_rights_verified","author_attribution_verified"):
            self.assertFalse(report[k],k)
        self.assertEqual(64,len(report["observation_set_sha256"]))
        self.assertNotIn("source_excerpts",report)
        self.assertNotIn("فما حجتك",json.dumps(report,ensure_ascii=False))

    def test_each_route_budget_25_whitespace_words(self):
        for o in self.data["observations"]:
            self.assertEqual(2,len(o["source_excerpts"]))
            self.assertLessEqual(sum(len(s["text_ar"].split()) for s in o["source_excerpts"]),25)
        x=copy.deepcopy(self.data)
        x["observations"][0]["source_excerpts"][0]["text_ar"]=" ".join(["كلمة"]*26)
        self.reject(x)

    def test_all_exact_parent_links(self):
        self.assertEqual([146,149,157,556],[o["source_route_id"] for o in self.data["observations"]])
        self.assertEqual([53,56,64,471],[o["printed_page_on_site"] for o in self.data["observations"]])
        self.assertEqual(["u03_h001","u03_h002","u03_h003","u03_h004"],
                         [o["card_id"] for o in self.data["observations"]])

    def test_parent_digests_and_schema_state_hold(self):
        x=copy.deepcopy(self.data)
        x["question_cards_sha256"]="f"*64
        self.reject(x)
        x=copy.deepcopy(self.cards)
        x["cards"][1]["question_ar"]="ما سبب تعديل السؤال؟"
        self.reject(cards=x)
        x=copy.deepcopy(self.docket)
        x["candidates"][3]["heading_provenance"]="undetermined"
        self.reject(docket=x)

    def test_swapped_observation_card_identity_rejected(self):
        x=copy.deepcopy(self.data)
        x["observations"][0]["observation_id"],x["observations"][1]["observation_id"]=(
            x["observations"][1]["observation_id"],x["observations"][0]["observation_id"])
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][0]["card_id"],x["observations"][1]["card_id"]=(
            x["observations"][1]["card_id"],x["observations"][0]["card_id"])
        self.reject(x)

    def test_changed_print_page_or_heading_provenance_rejected(self):
        x=copy.deepcopy(self.data)
        x["observations"][0]["printed_page_on_site"]=146
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][3]["heading_provenance"]="printed_variant_reported"
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][3]["source_route_id"]=149
        self.reject(x)

    def test_editor_note_and_interlocutor_cannot_be_reclassified(self):
        for i,ex_idx,new_role in ((3,0,"author_discussion"),(3,1,"author_discussion"),
                                  (2,0,"author_discussion"),(1,1,"author_discussion")):
            with self.subTest(index=i,excerpt=ex_idx):
                x=copy.deepcopy(self.data)
                x["observations"][i]["source_excerpts"][ex_idx]["voice_role"]=new_role
                self.reject(x)

    def test_exact_excerpt_mutation_rejected(self):
        for i in range(4):
            for j in range(2):
                with self.subTest(record=i,snippet=j):
                    x=copy.deepcopy(self.data)
                    x["observations"][i]["source_excerpts"][j]["text_ar"] += " محرفة"
                    self.reject(x)

    def test_missing_reordered_duplicate_excerpts_rejected(self):
        x=copy.deepcopy(self.data)
        x["observations"][0]["source_excerpts"].pop()
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][0]["source_excerpts"].reverse()
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][0]["source_excerpts"][1]["excerpt_id"] = (
            x["observations"][0]["source_excerpts"][0]["excerpt_id"])
        self.reject(x)

    def test_no_fake_authority_or_source_custody(self):
        changes=[("approved",True),("author_quote","نص"),("rule_ast",{"op":"fact"}),
                 ("reviewers",[{"approved":True}]),("p1_receipt",{"valid":True}),
                 ("licensed_source_bytes",True)]
        for k,value in changes:
            with self.subTest(field=k):
                x=copy.deepcopy(self.data)
                x["observations"][0][k]=value
                self.reject(x)
        for k,value in (("eligible_for_engine",True),("licensed_corpus",True),
                        ("automatic_promotion",True),("text_storage","full_book")):
            x=copy.deepcopy(self.data)
            x[k]=value
            self.reject(x)

    def test_unsupported_personal_review_flags_rejected(self):
        for k,value in (("rule_formalization_status","approved"),
                        ("human_review_status","complete"),
                        ("author_attribution_status","verified")):
            x=copy.deepcopy(self.data)
            x["observations"][0][k]=value
            self.reject(x)

    def test_programmatic_hostile_containers_and_cycles_rejected(self):
        class Forged(dict):
            def __eq__(self,other): return True
            def __ne__(self,other): return False
        self.reject(data=Forged(copy.deepcopy(self.data)))
        x=copy.deepcopy(self.data)
        x["observations"][0] = Forged(x["observations"][0])
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][0]["analyst_note_ar"] = "\ud800"
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][0]["unexpected"]=[]
        x["observations"][0]["unexpected"].append(x["observations"][0]["unexpected"])
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][0]["source_excerpts"]=x["observations"][1]["source_excerpts"]
        self.reject(x)

    def test_bounded_research_description_and_unknown_extras(self):
        x=copy.deepcopy(self.data)
        x["observations"][0]["analyst_note_ar"]="ا"*20000
        self.reject(x)
        x=copy.deepcopy(self.data)
        x["observations"][0]["source_excerpts"][0]["unknown"]={"large":[[[[]]]]}
        self.reject(x)

    def test_cli_valid_but_no_promotion(self):
        cmd=[sys.executable,"-m","core.usul.observations_cli",str(OBS),
             str(CARDS),str(DOCKET),"--json"]
        r=subprocess.run(cmd,cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(0,r.returncode,(r.stdout,r.stderr))
        report=json.loads(r.stdout)
        self.assertTrue(report["valid_metadata"])
        self.assertFalse(report["eligible_for_engine"])
        self.assertNotIn("text_ar",r.stdout)

    def test_cli_invalid_schema_exit_1(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"bad.json"
            x=copy.deepcopy(self.data)
            x["observations"][3]["heading_provenance"]="printed_variant_reported"
            p.write_text(json.dumps(x,ensure_ascii=False),encoding="utf-8")
            r=subprocess.run([sys.executable,"-m","core.usul.observations_cli",
                              str(p),str(CARDS),str(DOCKET),"--json"],
                             cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(1,r.returncode,(r.stdout,r.stderr))

    def test_cli_duplicate_members_and_nan_exit_2(self):
        raw=OBS.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"bad.json"
            for sample in (
                raw.replace('"automatic_promotion": false',
                            '"automatic_promotion": true, "automatic_promotion": false',1),
                raw.replace('"automatic_promotion": false',
                            '"automatic_promotion": NaN',1)
            ):
                p.write_text(sample,encoding="utf-8")
                r=subprocess.run([sys.executable,"-m","core.usul.observations_cli",
                                  str(p),str(CARDS),str(DOCKET),"--json"],
                                 cwd=ROOT,capture_output=True,text=True,timeout=20)
                self.assertEqual(2,r.returncode,(r.stdout,r.stderr))

    def test_workflow_path_filters_and_cli(self):
        wf=(ROOT/".github/workflows/mubin-usul-synthetic.yml").read_text(encoding="utf-8")
        for needle in ('"core/tests/test_usul_u04.py"','"schemas/usul-u04-**"',
                       '"docs/research/USUL-U04-**"','"docs/reviews/USUL-U04-**"'):
            self.assertEqual(2,wf.count(needle),needle)
        self.assertIn("python -m core.usul.observations_cli",wf)

if __name__=="__main__":
    unittest.main()
