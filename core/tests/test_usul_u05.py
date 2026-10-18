"""U0.5: unsubmitted review tasks are not scholarly reviewer decisions."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.usul.review_queue import (
    assess_review_queue, validate_review_queue, summarize_unverified_review_positions
)

ROOT = Path(__file__).resolve().parents[2]
QUEUE = ROOT / "research/usul/u05-risala-review-queue.json"
OBS = ROOT / "research/usul/u04-risala-text-observations.json"
CARDS = ROOT / "research/usul/u03-risala-hypothesis-cards.json"
DOCKET = ROOT / "research/usul/u02-risala-source-candidates.json"
AXES = (
    "independent_edition_collation", "author_editor_attribution",
    "legal_use_basis_review", "methodology_and_disagreement_review",
    "conditions_exceptions_counterexamples", "two_independent_scholarly_reviews",
)

class ReviewQueueTests(unittest.TestCase):
    def setUp(self):
        self.queue = json.loads(QUEUE.read_text(encoding="utf-8"))
        self.observations = json.loads(OBS.read_text(encoding="utf-8"))
        self.cards = json.loads(CARDS.read_text(encoding="utf-8"))
        self.docket = json.loads(DOCKET.read_text(encoding="utf-8"))

    def invalid(self, queue=None, observations=None, cards=None, docket=None):
        errors = validate_review_queue(
            self.queue if queue is None else queue,
            self.observations if observations is None else observations,
            self.cards if cards is None else cards,
            self.docket if docket is None else docket,
        )
        self.assertTrue(errors, "unexpectedly accepted untrusted review data")
        return errors

    def test_unsubmitted_four_claims_and_24_pending_tasks(self):
        x = assess_review_queue(self.queue,self.observations,self.cards,self.docket)
        self.assertTrue(x["valid_metadata"],x["errors"])
        self.assertEqual("unsubmitted_scholarly_review_queue_only",x["scope"])
        self.assertEqual(4,x["queued_claim_count"])
        self.assertEqual(24,x["open_evidence_task_count"])
        self.assertEqual(0,x["admitted_rule_count"])
        self.assertEqual(0,x["verified_human_review_count"])
        self.assertEqual(0,x["claimed_reviewer_count"])
        for k in ("eligible_for_engine","independent_human_review_verified",
                  "edition_authenticated","rights_verified","source_bytes_pinned"):
            self.assertFalse(x[k],k)
        self.assertTrue(x["parent_bindings_match"])
        self.assertEqual(64,len(x["queue_sha256"]))
        self.assertEqual(["u05_r001","u05_r002","u05_r003","u05_r004"],x["review_queue"])
        self.assertEqual([],self.queue["reviewer_submissions"])

    def test_four_to_four_parent_and_warning_binding(self):
        for i,item in enumerate(self.queue["reviews"],1):
            self.assertEqual(f"u05_r{i:03}",item["review_id"])
            self.assertEqual(f"u04_t{i:03}",item["observation_id"])
            self.assertEqual(f"u03_h{i:03}",item["card_id"])
            self.assertEqual(f"u02_c{i:03}",item["candidate_id"])
            self.assertEqual(self.cards["cards"][i-1]["question_ar"],item["research_question_ar"])
            self.assertEqual(self.observations["observations"][i-1]["source_route_id"],
                             item["source_route_id"])
        self.assertEqual("editor_added_heading_reported",
                         self.queue["reviews"][3]["heading_provenance"])
        self.assertIn("المحاور",self.queue["reviews"][3]["editorial_risk_ar"])

    def test_evidence_task_order_and_pending_states(self):
        for item in self.queue["reviews"]:
            self.assertEqual(AXES,tuple(t["axis_id"] for t in item["evidence_tasks"]))
            self.assertTrue(all(t["status"]=="pending" for t in item["evidence_tasks"]))
            self.assertTrue(all(t["evidence_refs"]==[] for t in item["evidence_tasks"]))

    def test_reorder_evidence_tasks_rejected(self):
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["evidence_tasks"].reverse()
        self.invalid(queue=x)

    def test_omit_or_duplicate_evidence_tasks_rejected(self):
        x=copy.deepcopy(self.queue);x["reviews"][0]["evidence_tasks"].pop()
        self.invalid(queue=x)
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["evidence_tasks"][1]["axis_id"]=AXES[0]
        self.invalid(queue=x)

    def test_swap_review_ids_rejected(self):
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["review_id"],x["reviews"][3]["review_id"]=(
            x["reviews"][3]["review_id"],x["reviews"][0]["review_id"])
        self.invalid(queue=x)

    def test_source_and_question_swaps_rejected(self):
        for field in ("observation_id","card_id","candidate_id","source_route_id",
                      "printed_page_on_site","heading_provenance","research_question_ar"):
            with self.subTest(field=field):
                x=copy.deepcopy(self.queue)
                x["reviews"][0][field],x["reviews"][3][field]=(
                    x["reviews"][3][field],x["reviews"][0][field])
                self.invalid(queue=x)

    def test_four_slots_complete_no_duplicate_or_missing(self):
        x=copy.deepcopy(self.queue);x["reviews"].pop()
        self.invalid(queue=x)
        x=copy.deepcopy(self.queue);x["reviews"].append(copy.deepcopy(x["reviews"][0]))
        self.invalid(queue=x)

    def test_parent_fingerprints_rejected_when_wrong(self):
        for field in ("observation_set_sha256","question_cards_sha256","source_docket_sha256"):
            x=copy.deepcopy(self.queue);x[field]="f"*64
            self.invalid(queue=x)
        x=copy.deepcopy(self.observations)
        x["observations"][3]["source_excerpts"][0]["voice_role"]="author_discussion"
        self.invalid(observations=x)
        x=copy.deepcopy(self.cards)
        x["cards"][0]["question_ar"]="ما الدليل الذي تغيّر؟"
        self.invalid(cards=x)
        x=copy.deepcopy(self.docket)
        x["candidates"][3]["heading_provenance"]="undetermined"
        self.invalid(docket=x)

    def test_review_states_and_reviewer_submissions_never_fake(self):
        for field,value in (
            ("review_status","approved"),("scholarly_status","verified"),
            ("admission_status","executable"),("evidence_refs",["sha256:abcdef"]),
            ("rule_ast",{"op":"fact"}),("reviewers",[{"accepted":True}]),
            ("source_text","copied corpus"),("p1_receipt",{"valid":True})
        ):
            with self.subTest(field=field):
                x=copy.deepcopy(self.queue);x["reviews"][0][field]=value
                self.invalid(queue=x)
        for field,value in (
            ("automatic_promotion",True),("reviewer_submissions",[{"decision":"accept"}]),
            ("verified_human_review_count",2),("rights_verified",True)
        ):
            x=copy.deepcopy(self.queue);x[field]=value
            self.invalid(queue=x)

    def test_approve_single_task_or_claim_rejected(self):
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["evidence_tasks"][0]["status"]="completed"
        self.invalid(queue=x)
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["evidence_tasks"][0]["evidence_refs"]=["sha256:"+"a"*64]
        self.invalid(queue=x)
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["decision"]="accept"
        self.invalid(queue=x)

    def test_interlocutor_editor_warning_cannot_disappear(self):
        x=copy.deepcopy(self.queue)
        x["reviews"][3]["editorial_risk_ar"]="المؤلف قرر الإجماع."
        self.invalid(queue=x)
        x=copy.deepcopy(self.queue)
        x["reviews"][3]["heading_provenance"]="printed_variant_reported"
        self.invalid(queue=x)

    def test_canonical_order_independent_queue_digest(self):
        r=assess_review_queue(self.queue,self.observations,self.cards,self.docket)
        x=copy.deepcopy(self.queue);x["reviews"].reverse()
        changed=assess_review_queue(x,self.observations,self.cards,self.docket)
        self.assertTrue(changed["valid_metadata"],changed["errors"])
        self.assertEqual(r["queue_sha256"],changed["queue_sha256"])
        self.assertEqual(r["review_queue"],changed["review_queue"])

    def test_parent_binding_report_not_confused_with_review_content_error(self):
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["evidence_tasks"][0]["status"]="completed"
        result=assess_review_queue(x,self.observations,self.cards,self.docket)
        self.assertFalse(result["valid_metadata"])
        self.assertTrue(result["parent_bindings_match"])
        x["observation_set_sha256"]="f"*64
        result=assess_review_queue(x,self.observations,self.cards,self.docket)
        self.assertFalse(result["parent_bindings_match"])

    def test_unverified_votes_never_open_authority(self):
        x=summarize_unverified_review_positions("accept","accept")
        self.assertEqual("unverified_concurrence",x["status"])
        self.assertFalse(x["independent_human_review_verified"])
        self.assertFalse(x["eligible_for_engine"])
        self.assertEqual(0,x["verified_human_review_count"])
        self.assertEqual("escalate_disagreement",
                         summarize_unverified_review_positions("accept","reject")["status"])
        self.assertEqual("requires_revision",
                         summarize_unverified_review_positions("accept","revise")["status"])
        self.assertEqual("unverified_abstention",
                         summarize_unverified_review_positions("accept","abstain")["status"])

    def test_unverified_votes_reject_invalid_types(self):
        for v in ("approved",None,True,{},["accept"],"ACCEPT"):
            with self.subTest(value=str(v)):
                with self.assertRaises(ValueError):
                    summarize_unverified_review_positions(v,"accept")

    def test_untrusted_containers_unicode_and_unknown_payloads(self):
        class Forged(dict):
            def __eq__(self,v):return True
            def __ne__(self,v):return False
        self.invalid(queue=Forged(copy.deepcopy(self.queue)))
        x=copy.deepcopy(self.queue);x["reviews"][0]=Forged(x["reviews"][0]);self.invalid(queue=x)
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["evidence_tasks"]=x["reviews"][1]["evidence_tasks"]
        self.invalid(queue=x)
        x=copy.deepcopy(self.queue)
        x["reviews"][0]["research_question_ar"]="\ud800"
        self.invalid(queue=x)
        x=copy.deepcopy(self.queue)
        bad=[];bad.append(bad)
        x["reviews"][0]["unexpected"]=bad
        self.invalid(queue=x)

    def test_reject_oversized_hidden_object_and_unicode(self):
        x=copy.deepcopy(self.queue);x["reviews"][0]["falsification_probe_ar"]="A"*30000
        self.invalid(queue=x)
        x=copy.deepcopy(self.queue);x["reviews"][0]["evidence_tasks"][0]["untrusted"]={"x":[[[]]]}
        self.invalid(queue=x)

    def test_cli_valid_unsubmitted_exit_zero(self):
        r=subprocess.run([sys.executable,"-m","core.usul.review_cli",str(QUEUE),
                          str(OBS),str(CARDS),str(DOCKET),"--json"],
                         cwd=ROOT,capture_output=True,text=True,timeout=20)
        self.assertEqual(0,r.returncode,(r.stdout,r.stderr))
        data=json.loads(r.stdout)
        self.assertTrue(data["valid_metadata"])
        self.assertEqual(24,data["open_evidence_task_count"])
        self.assertFalse(data["eligible_for_engine"])
        self.assertNotIn("source_excerpts",r.stdout)
        self.assertNotIn("research_question_ar",r.stdout)

    def test_cli_rejected_metadata_exit_one(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"queue.json"
            x=copy.deepcopy(self.queue);x["reviews"][0]["evidence_tasks"].reverse()
            p.write_text(json.dumps(x,ensure_ascii=False),encoding="utf-8")
            r=subprocess.run([sys.executable,"-m","core.usul.review_cli",
                              str(p),str(OBS),str(CARDS),str(DOCKET),"--json"],
                             cwd=ROOT,capture_output=True,text=True,timeout=20)
            self.assertEqual(1,r.returncode,(r.stdout,r.stderr))

    def test_cli_duplicate_keys_and_nan_exit_two(self):
        raw=QUEUE.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"queue.json"
            for mutation in (
                raw.replace('"automatic_promotion": false',
                            '"automatic_promotion": true, "automatic_promotion": false',1),
                raw.replace('"automatic_promotion": false',
                            '"automatic_promotion": NaN',1),
            ):
                p.write_text(mutation,encoding="utf-8")
                r=subprocess.run([sys.executable,"-m","core.usul.review_cli",
                                  str(p),str(OBS),str(CARDS),str(DOCKET),"--json"],
                                 cwd=ROOT,capture_output=True,text=True,timeout=20)
                self.assertEqual(2,r.returncode,(r.stdout,r.stderr))

    def test_workflow_covers_u05_tests_schema_docs_cli(self):
        wf=(ROOT/".github/workflows/mubin-usul-synthetic.yml").read_text(encoding="utf-8")
        for value in ('"core/tests/test_usul_u05.py"', '"schemas/usul-u05-**"',
                      '"docs/research/USUL-U05-**"', '"docs/reviews/USUL-U05-**"'):
            self.assertEqual(2,wf.count(value),value)
        self.assertIn("python -m core.usul.review_cli",wf)

if __name__ == "__main__":
    unittest.main()
