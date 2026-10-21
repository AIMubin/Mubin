"""Pinned two-witness Stage07 wrapper: test refusal, local replay, privacy."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engines.usul.pilots import waraqat_stage07 as run
from engines.usul.arabic_evidence_retrieval import ArabicRetrievalError, FOLD_MARKS


def sha(b):
    return hashlib.sha256(b).hexdigest()


class WaraqatStage07Tests(unittest.TestCase):
    def test_pins_identical_to_published_stage06_record(self):
        base=Path(__file__).resolve().parents[3]
        review=json.loads((base/"corpus/reviews/u01-stage06-waraqat-dual-witness-alignment.json").read_text(encoding="utf-8"))
        self.assertEqual(run.W1_SECTION_SHA, review["witnesses"]["W1_primary"]["section_sha256"])
        self.assertEqual(run.W2_SECTION_SHA, review["witnesses"]["W2_comparator"]["section_sha256"])
        self.assertEqual(run.W1_RAW_SHA, review["witnesses"]["W1_primary"]["raw_html_sha256"])
        self.assertEqual(run.W2_RAW_SHA, review["witnesses"]["W2_comparator"]["raw_html_sha256"])
        self.assertEqual(run.W1_URL, review["witnesses"]["W1_primary"]["url"])
        self.assertEqual(run.W2_URL, review["witnesses"]["W2_comparator"]["url"])
        self.assertEqual(review["campaign_decision"],
                         "STAGE06_DUAL_SOURCE_EXTRACTION_REPLAY_PASS")

    def test_stage07_must_call_stage06_strictly_and_recheck_both_section_pins(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            first=root/"w1.txt"
            second=root/"w2.txt"
            first.write_bytes("الأمر فليس الندب\n".encode("utf-8"))
            second.write_bytes("الْأَمْر فليس الندب\n".encode("utf-8"))
            w1_pin=sha(first.read_bytes())
            w2_pin=sha(second.read_bytes())
            audit={
                "status":"STAGE06_DUAL_SOURCE_EXTRACTION_REPLAY_PASS",
                "primary_html_to_section_replay_verified":True,
                "secondary_html_to_section_replay_verified":True,
                "left":{"section_sha256":w1_pin},
                "right":{"section_sha256":w2_pin},
                "raw_html_witness1_sha256":run.W1_RAW_SHA,
                "raw_html_witness2_sha256":run.W2_RAW_SHA,
                "strict_change_count":4,
            }
            inputs=[root/"primary.html",root/"full.txt",root/"manifest.json",
                    first,root/"secondary.html",second]
            queries=[{"id":"pilot:amr","literal":"الأمر",
                      "candidate_profiles":[FOLD_MARKS]}]
            with patch.object(run,"W1_SECTION_SHA",w1_pin),\
                 patch.object(run,"W2_SECTION_SHA",w2_pin),\
                 patch.object(run,"compare_captured_witnesses",return_value=audit) as check:
                result=run.replay_and_search(*inputs, queries)
                check.assert_called_once_with(
                    *inputs, w2_pin, verify_secondary_extraction=True)
                self.assertEqual(result["status"],
                                 "STAGE07_DUAL_WITNESS_ARABIC_RETRIEVAL_PASS")
                self.assertTrue(result["stage06_strict_provenance"]["both_html_to_section_replays_verified"])
                self.assertFalse(result["query_cross_witness_semantic_agreement_verified"])
                self.assertEqual(result["witnesses"][0]["queries"][0]["strict_match_count"],1)
                self.assertEqual(result["witnesses"][1]["queries"][0]["strict_match_count"],0)
                self.assertEqual(result["witnesses"][1]["queries"][0]["candidate_profiles"][0]["match_count"],1)
                modified=copy.deepcopy(audit)
                modified["secondary_html_to_section_replay_verified"]=False
                check.return_value=modified
                with self.assertRaisesRegex(ArabicRetrievalError,"Stage06 strict"):
                    run.replay_and_search(*inputs,queries)
                check.return_value=audit
                second.write_bytes(second.read_bytes()+b"tampered")
                with self.assertRaisesRegex(ArabicRetrievalError,"digest"):
                    run.replay_and_search(*inputs,queries)

    def test_bad_witness_digest_in_gate_fails_before_indexing(self):
        with patch.object(run, "compare_captured_witnesses", return_value={
            "status":"STAGE06_TEXT_ALIGNMENT_PROVENANCE_PARTIAL",
            "primary_html_to_section_replay_verified":True,
            "secondary_html_to_section_replay_verified":False,
            "left":{"section_sha256":run.W1_SECTION_SHA},
            "right":{"section_sha256":run.W2_SECTION_SHA},
            "raw_html_witness1_sha256":run.W1_RAW_SHA,
            "raw_html_witness2_sha256":run.W2_RAW_SHA,
        }):
            with self.assertRaises(ArabicRetrievalError):
                run.replay_and_search("h1","txt","manifest","s1","h2","s2",[])

    def test_cli_missing_private_files_never_claims_replay(self):
        root=Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)
            queries=p/"q.json"
            report=p/"report.json"
            queries.write_text(json.dumps([{
                "id":"pilot:amr", "literal":"الأمر",
                "candidate_profiles":[FOLD_MARKS]}], ensure_ascii=False),encoding="utf-8")
            cmd=[sys.executable,"-m","engines.usul.pilots.waraqat_stage07",
                 "--primary-html",str(p/"h1.html"),
                 "--primary-export",str(p/"all.txt"),
                 "--primary-manifest",str(p/"manifest.json"),
                 "--primary-section",str(p/"s1.txt"),
                 "--secondary-html",str(p/"h2.html"),
                 "--secondary-section",str(p/"s2.txt"),
                 "--queries",str(queries),"--report",str(report)]
            result=subprocess.run(cmd,cwd=root,capture_output=True,text=True)
            self.assertEqual(result.returncode,3,result.stderr)
            self.assertTrue(result.stdout.isascii())
            self.assertEqual(json.loads(report.read_text(encoding="utf-8"))["status"],
                             "PENDING_PRIVATE_WITNESS_FILES")
            self.assertNotIn("PASS",result.stdout)


if __name__=="__main__":
    unittest.main()
