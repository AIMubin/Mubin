"""U0.2 non-executable source-location docket; no juristic rule approval."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.usul.docket import assess_docket, validate_docket

ROOT = Path(__file__).resolve().parents[2]
INPUT = ROOT / "research/usul/u02-risala-source-candidates.json"

class SourceDocketTests(unittest.TestCase):
    def setUp(self):
        self.d = json.loads(INPUT.read_text(encoding="utf-8"))

    def invalid(self, d):
        errors = validate_docket(d)
        self.assertTrue(errors, "unsafe metadata was accepted")
        return errors

    def test_metadata_only_no_rule_promotion(self):
        r = assess_docket(self.d)
        self.assertTrue(r["valid_metadata"], r["errors"])
        self.assertEqual("source_candidate_metadata_only", r["scope"])
        self.assertEqual(4, r["candidate_count"])
        self.assertEqual(0, r["verified_rule_count"])
        for k in ("eligible_for_engine", "rights_verified", "edition_authenticated",
                  "source_bytes_available", "scholarly_authority_verified"):
            self.assertFalse(r[k], k)
        self.assertEqual(4, len(r["review_queue"]))
        self.assertEqual(64, len(r["docket_sha256"]))

    def test_locator_and_printed_page_are_distinct(self):
        expected = {146:53, 149:56, 157:64, 556:471}
        self.assertEqual(expected, {c["locator"]["route_id"]: c["locator"]["printed_page_on_site"]
                                   for c in self.d["candidates"]})
        d=copy.deepcopy(self.d)
        d["candidates"][0]["locator"]["printed_page_on_site"]=146
        self.assertEqual([], validate_docket(d))
        self.assertFalse(assess_docket(d)["edition_authenticated"])

    def test_exact_provider_and_book_identity(self):
        for change in ({"book_id":1681}, {"source_id":"shamela:book:999"},
                       {"book_url":"https://shamela.ws/book/7798"}):
            d=copy.deepcopy(self.d);d["book"].update(change)
            self.invalid(d)

    def test_exact_page_url_binding(self):
        for url in ("http://shamela.ws/book/8180/146", "https://shamela.ws/book/1681/146",
                    "https://shamela.ws/book/8180/149", "https://shamela.ws/book/8180/0146",
                    "https://shamela.ws/book/8180/146?x=1", "https://evil.example/8180/146"):
            with self.subTest(url=url):
                d=copy.deepcopy(self.d);d["candidates"][0]["locator"]["url"]=url
                self.invalid(d)

    def test_duplicates_and_empty_queue_rejected(self):
        d=copy.deepcopy(self.d);d["candidates"]=[]
        self.invalid(d)
        d=copy.deepcopy(self.d);d["candidates"][1]["candidate_id"]=d["candidates"][0]["candidate_id"]
        self.invalid(d)
        d=copy.deepcopy(self.d);d["candidates"][1]["locator"]["route_id"]=146
        d["candidates"][1]["locator"]["url"]="https://shamela.ws/book/8180/146"
        self.invalid(d)

    def test_reject_forged_reviews_text_and_ast(self):
        for name, value in (
            ("review_status", "approved"),("methodology_status","verified"),
            ("rule_status","executable"),("text","متن"),
            ("source_sha256","f"*64),("reviewers",[{"approved":True}]),
            ("rulebook",{"contract":"fake"}),("p1_receipt",{"valid":True})
        ):
            with self.subTest(name=name):
                d=copy.deepcopy(self.d);d["candidates"][0][name]=value
                self.invalid(d)

    def test_no_false_book_rights_or_provenance(self):
        for name,value in (("text_rights_status","cleared"),
                           ("source_bytes_status","pinned"),
                           ("edition_status","authenticated")):
            d=copy.deepcopy(self.d);d["book"][name]=value
            self.invalid(d)
        for name,value in (("automatic_promotion",True),("source_partition","h392_holdout"),
                           ("text_storage","full_book")):
            d=copy.deepcopy(self.d);d[name]=value
            self.invalid(d)

    def test_editorial_heading_not_laundered(self):
        x={c["topic_id"]:c for c in self.d["candidates"]}
        self.assertEqual("editor_added_heading_reported",x["ijma_chapter"]["heading_provenance"])
        self.assertIn("المحقق",x["ijma_chapter"]["editorial_warning"])
        self.assertTrue(all(c["heading_authorship"]=="not_verified_authorial"
                            for c in self.d["candidates"]))
        d=copy.deepcopy(self.d);d["candidates"][3]["heading_authorship"]="verified_authorial"
        self.invalid(d)

    def test_order_change_keeps_queue_but_changes_metadata_digest(self):
        d=copy.deepcopy(self.d);d["candidates"].reverse()
        orig=assess_docket(self.d);changed=assess_docket(d)
        self.assertEqual(orig["review_queue"],changed["review_queue"])
        self.assertNotEqual(orig["docket_sha256"],changed["docket_sha256"])

    def test_untrusted_extra_nested_structure_fails_early(self):
        d=copy.deepcopy(self.d);x=[]
        for _ in range(1400):x=[x]
        d["candidates"][0]["malicious"]=x
        self.invalid(d)

    def test_invalid_unicode_and_oversized_field(self):
        d=copy.deepcopy(self.d);d["book"]["work_title"]="\ud800"
        self.invalid(d)
        d=copy.deepcopy(self.d);d["candidates"][0]["research_question"]="A"*12000
        self.invalid(d)

    def test_hostile_container_subclasses_rejected(self):
        class ForgedDict(dict):
            def __eq__(self, _):return True
            def __ne__(self, _):return False
        d=ForgedDict(copy.deepcopy(self.d))
        self.invalid(d)
        d=copy.deepcopy(self.d)
        d["candidates"][0]=ForgedDict(d["candidates"][0])
        self.invalid(d)

    def test_candidate_identity_must_bind_topic_and_route(self):
        changed=copy.deepcopy(self.d)
        changed["candidates"][0]["candidate_id"],changed["candidates"][3]["candidate_id"] = (
            changed["candidates"][3]["candidate_id"],changed["candidates"][0]["candidate_id"]
        )
        self.invalid(changed)
        changed=copy.deepcopy(self.d)
        changed["candidates"][0]["topic_id"]=changed["candidates"][3]["topic_id"]
        self.invalid(changed)
        changed=copy.deepcopy(self.d)
        changed["candidates"][0]["locator"],changed["candidates"][1]["locator"]=(
            changed["candidates"][1]["locator"],changed["candidates"][0]["locator"]
        )
        self.invalid(changed)

    def test_fixed_four_book_chapters_cannot_silently_disappear(self):
        changed=copy.deepcopy(self.d)
        changed["candidates"]=changed["candidates"][:-1]
        self.invalid(changed)

    def test_cli_good(self):
        r=subprocess.run([sys.executable,"-m","core.usul.docket_cli",str(INPUT),"--json"],
                         cwd=ROOT,capture_output=True,text=True,timeout=15)
        self.assertEqual(0,r.returncode,r.stderr)
        output=json.loads(r.stdout)
        self.assertTrue(output["valid_metadata"])
        self.assertFalse(output["eligible_for_engine"])
        self.assertNotIn("fatwa",r.stdout.lower())

    def test_cli_duplicate_json_keys_and_nan(self):
        raw=INPUT.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/"bad.json"
            for sample in (raw.replace('"book_id": 8180','"book_id": 1, "book_id": 8180',1),
                           raw.replace('"book_id": 8180','"book_id": NaN',1)):
                p.write_text(sample,encoding="utf-8")
                r=subprocess.run([sys.executable,"-m","core.usul.docket_cli",str(p),"--json"],
                                 cwd=ROOT,capture_output=True,text=True,timeout=15)
                self.assertEqual(2,r.returncode,(r.stdout,r.stderr))
                self.assertFalse(json.loads(r.stdout)["valid_metadata"])

    def test_workflow_triggers_on_all_u02_changes(self):
        workflow=(ROOT/".github/workflows/mubin-usul-synthetic.yml").read_text(encoding="utf-8")
        for path in ('"core/tests/test_usul_u02.py"','"schemas/usul-u02-**"',
                     '"docs/research/USUL-U02-**"','"research/usul/**"'):
            self.assertGreaterEqual(workflow.count(path),2,path)
        self.assertIn("python -m core.usul.docket_cli",workflow)

if __name__=="__main__":
    unittest.main()
