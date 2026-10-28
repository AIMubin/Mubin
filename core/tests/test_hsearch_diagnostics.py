"""Synthetic proof that each H-Search exclusion stage is independently visible."""
from __future__ import annotations

import hashlib
import json
import unittest

from engines.hadith.hsearch.diagnostics import diagnose_coverage

SOURCE_ID = "openiti:0458Bayhaqi.SunanKubra"
PHRASE = "قال حدثنا رجل عن قوم في مجلس علم قديم قبل"
SID = "tafsir:tafsir_tabari:1:7:synthetic"
WORK = "tafsir_tabari"
PREFIX = "مقدمة اصطناعية ليس بها أي رواية مستقلة. "
SUFFIX = " خاتمة اصطناعية لا توثيق لها."


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def fixture(*, included_in_passage=True, included_in_mention=True,
            included_in_block=True, corrupted_source=False):
    tafsir = PREFIX + PHRASE + SUFFIX
    pos = tafsir.index(PHRASE)
    rows = [{
        "work_id": WORK, "source_record_id": SID,
        "source_sha256": sha(tafsir) if not corrupted_source else "0"*64,
        "raw_text": tafsir,
    }]
    passages = [{
        "source_record_id": SID,
        "interpretation_id": "interp:synthetic",
        "evidence_span": ([0,len(tafsir)] if included_in_passage
                          else [0,len(PREFIX)-1]),
    }]
    mentions = [{
        "tafsir_source_record_id": SID,
        "mention_id": "hm:synthetic",
        "raw_source_span": ([pos,pos+len(PHRASE)] if included_in_mention
                            else [0,len(PREFIX)-1]),
    }]
    source = "بداية مختلفة " + PHRASE + " تتمة أصلية"
    cross = source.index(" مجلس")
    blocks = ([(0,len(source),"L1")] if included_in_block
              else [(0,cross,"L1"),(cross,len(source),"L2")])
    return dict(rows=rows, passages=passages, mentions=mentions,
                sources={SOURCE_ID:source},
                source_blocks={SOURCE_ID:blocks})


class GapDiagnosticsTests(unittest.TestCase):
    def test_passage_exclusion_is_visible(self):
        result=diagnose_coverage(**fixture(included_in_passage=False))
        self.assertGreater(result["stage_counts"].get("OUTSIDE_T02_PASSAGE",0),0)
        self.assertEqual(0,result["stage_counts"].get(
            "INSIDE_ALL_PIPELINE_WINDOWS",0))

    def test_narration_window_exclusion_is_visible(self):
        result=diagnose_coverage(**fixture(included_in_mention=False))
        self.assertGreater(result["stage_counts"].get(
            "OUTSIDE_NARRATION_WINDOW",0),0)

    def test_cross_source_block_exclusion_is_visible(self):
        result=diagnose_coverage(**fixture(included_in_block=False))
        self.assertGreater(result["stage_counts"].get(
            "CROSSES_OR_OUTSIDE_SOURCE_BLOCK",0),0)

    def test_valid_case_reaches_pipeline_scope_but_no_hadith_authentication(self):
        result=diagnose_coverage(**fixture())
        self.assertGreater(result["stage_counts"].get(
            "INSIDE_ALL_PIPELINE_WINDOWS",0),0)
        self.assertIs(result["narration_identity_proven"],False)
        self.assertIs(result["scientific_gate_passed"],False)
        sample=result["samples"][0]
        self.assertEqual(10,sample["folded_word_count"])
        self.assertEqual(sha(PHRASE),sample["tafsir_raw_sha256"])
        self.assertEqual(sha(PHRASE),sample["hadith_raw_sha256"])

    def test_nonmatching_origins_return_no_synthetic_positive(self):
        inputs=fixture()
        inputs["sources"]={SOURCE_ID:"كلام تجريبي يختلف تماماً عن العبارة"}
        inputs["source_blocks"]={SOURCE_ID:[(0,len(
            inputs["sources"][SOURCE_ID]),"L1")]}
        result=diagnose_coverage(**inputs)
        self.assertEqual(0,result["matched_full_source_10gram_occurrences"])

    def test_tampered_original_tafsir_sha_refused(self):
        with self.assertRaisesRegex(ValueError,"HS_DIAG_TAFSIR_RAW_SHA_INVALID"):
            diagnose_coverage(**fixture(corrupted_source=True))

    def test_holdout_source_rejected(self):
        inputs=fixture()
        original=inputs["sources"][SOURCE_ID]
        held="openiti:0385Daraqutni.Sunan"
        inputs["sources"]={held:original}
        inputs["source_blocks"]={held: [(0,len(original),"L1")]}
        with self.assertRaisesRegex(ValueError,"HS_DIAG_UNAUTHORIZED_SOURCE"):
            diagnose_coverage(**inputs)

    def test_receipt_excludes_private_phrases(self):
        result=diagnose_coverage(**fixture())
        dump=json.dumps(result,ensure_ascii=False)
        self.assertNotIn(PHRASE,dump)
        self.assertNotIn(PREFIX,dump)
        self.assertNotIn("raw_text",dump)
        self.assertIs(result["text_included"],False)
        self.assertEqual(64,len(result["evidence_payload_sha256"]))

    def test_repeated_run_has_identical_fingerprint(self):
        a=diagnose_coverage(**fixture())
        b=diagnose_coverage(**fixture())
        self.assertEqual(a["evidence_payload_sha256"],b["evidence_payload_sha256"])


if __name__ == "__main__":
    unittest.main()
