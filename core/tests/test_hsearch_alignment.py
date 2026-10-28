"""H-Search-01.1 adversarial Unicode folded→raw alignment fixtures (synthetic).

No protected Tafsir or Hadith corpus is bundled. Tested numeric spans are
Unicode codepoint offsets into literal source text, never normalized text.
"""
from __future__ import annotations

import hashlib
import io
import json
from contextlib import redirect_stdout
from pathlib import Path
import unittest
from unittest.mock import patch

from engines.hadith.hsearch.alignment import (
    fold_with_raw_map, align_shared_tokens)
from engines.hadith.hsearch.contracts import make_witness
from engines.hadith.hsearch.matching import match_mentions
from engines.hadith.hsearch.sources import git_blob_sha
from engines.hadith.hsearch.replay import replay, main as replay_main

WORDS = "قال حدثنا رجل عن قوم في مجلس علم قديم قبل عصر الناس"
# Ten tokens: قال/حدثنا/رجل/عن/قوم/في/مجلس/علم/قديم/قبل
PHRASE = "قال حدثنا رجل عن قوم في مجلس علم قديم قبل"


def _sha(t):
    return hashlib.sha256(t.encode("utf-8")).hexdigest()


def _mention(raw, start=0):
    return {
        "mention_id":"hm:synthetic", "evidence_sha256":_sha(raw),
        "raw_source_span":[start, start+len(raw)],
        "_mention_text":raw,
    }


def _witness(raw):
    return make_witness(
        source_id="openiti:0279Tirmidhi.Sunan",
        work_id="0279Tirmidhi.Sunan",
        version_id="synthetic-test", source_blob_sha=git_blob_sha(
            raw.encode("utf-8")),
        locator="synthetic-L1", raw_text=raw, span=(0,len(raw)),
    )


class FoldingTests(unittest.TestCase):
    def test_normalization_matches_prior_hsearch_rules(self):
        raw="أَإِآٰ بــَى  ة\nوتشكيل"
        fold,_=fold_with_raw_map(raw)
        self.assertEqual("ااا بي ه وتشكيل",fold)

    def test_each_folded_char_points_to_original_codepoints(self):
        raw="سَلامٌ \n عِلْم"
        fold,mapping=fold_with_raw_map(raw)
        self.assertEqual(len(fold),len(mapping))
        self.assertEqual("سلام علم",fold)
        self.assertEqual("سَ",raw[slice(*mapping[0])])
        self.assertEqual(" \n ",raw[slice(*mapping[4])])

    def test_empty_and_removed_marks(self):
        self.assertEqual(("",[]),fold_with_raw_map(""))
        self.assertEqual(("",[]),fold_with_raw_map("\u064e\u064b"))
        self.assertEqual((" ",[(0,3)]),fold_with_raw_map(" \n\t"))

    def test_invalid_unicode_inputs_rejected(self):
        with self.assertRaisesRegex(ValueError,"HS_ALIGNMENT_RAW_TEXT_INVALID"):
            fold_with_raw_map(None)
        with self.assertRaisesRegex(ValueError,"HS_ALIGNMENT_INPUT_INVALID"):
            align_shared_tokens("",None)

    def test_harakat_and_aleph_variants_recover_two_distinct_raw_hashes(self):
        left="PREFIX: قَالَ حَدَّثَنَا رَجُلٌ عَنْ قَوْمٍ فِي مَجْلِسِ عِلْمٍ قَدِيمٍ قَبْلَ عصر"
        right="كتاب: قال حدثنا رجل عن قوم في مجلس علم قديم قبل سياق آخر"
        hit=align_shared_tokens(left,right)
        self.assertIsNotNone(hit)
        a,b=hit["tafsir_relative_span"]
        c,d=hit["hadith_relative_span"]
        self.assertEqual("قال حدثنا رجل عن قوم في مجلس علم قديم قبل",
                         " ".join(fold_with_raw_map(left[a:b])[0].split()))
        self.assertEqual("قال حدثنا رجل عن قوم في مجلس علم قديم قبل",
                         " ".join(fold_with_raw_map(right[c:d])[0].split()))
        self.assertEqual(_sha(left[a:b]),hit["tafsir_raw_phrase_sha256"])
        self.assertEqual(_sha(right[c:d]),hit["hadith_raw_phrase_sha256"])
        self.assertNotEqual(hit["tafsir_raw_phrase_sha256"],
                            hit["hadith_raw_phrase_sha256"])

    def test_extra_whitespace_and_newlines_roundtrip(self):
        left="قال  حدثنا رجل عن قوم في مجلس\nعلم قديم قبل"
        right="قال حدثنا رجل عن قوم في مجلس علم قديم قبل"
        found=align_shared_tokens(left,right)
        self.assertIsNotNone(found)
        a,b=found["tafsir_relative_span"]
        self.assertEqual(left[a:b],left)
        self.assertEqual(10,found["folded_word_count"])

    def test_partial_word_match_is_rejected(self):
        left=PHRASE
        right="مقال حدثنا رجل عن قوم في مجلس علم قديم قبل"
        self.assertIsNone(align_shared_tokens(left,right))

    def test_13_character_seed_fails_ten_word_gate(self):
        left="من صام رمضان"
        right="من صام رمضان والنص التالي مختلف كلية"
        self.assertIsNone(align_shared_tokens(left,right))

    def test_repeated_hits_deterministically_choose_first(self):
        text="start "+PHRASE+" -- "+PHRASE+" end"
        x=align_shared_tokens(PHRASE,text)
        y=align_shared_tokens(PHRASE,text)
        self.assertEqual(x,y)
        a,b=x["hadith_relative_span"]
        self.assertEqual(text[a:b],PHRASE)

    def test_no_empty_spans(self):
        self.assertIsNone(align_shared_tokens("",PHRASE))
        self.assertIsNone(align_shared_tokens(PHRASE,""))


class EndToEndMatchTests(unittest.TestCase):
    def test_metadata_contains_real_source_spans_not_folded_positions(self):
        left="مقدمة: قَالَ حَدَّثَنَا رَجُلٌ عَنْ قَوْمٍ فِي مَجْلِسِ عِلْمٍ قَدِيمٍ قَبْلَ"
        right="تنويه: "+PHRASE+" تعليق لاحق"
        m=_mention(left,start=217)
        w=_witness(right)
        links=match_mentions([m],[w],source_texts={w["source_id"]:right})
        self.assertEqual("CANDIDATE_MATCH",links[0]["match_status"])
        self.assertFalse(links[0]["identity_of_narration_confirmed"])
        a,b=links[0]["tafsir_shared_raw_span"]
        c,d=links[0]["hadith_shared_raw_span"]
        raw_left=left[a-217:b-217]
        raw_right=right[c:d]
        self.assertEqual(_sha(raw_left),links[0]["tafsir_shared_raw_sha256"])
        self.assertEqual(_sha(raw_right),links[0]["hadith_shared_raw_sha256"])
        self.assertGreater(a,217)
        self.assertTrue(raw_right.startswith("قال"))
        self.assertEqual(10,links[0]["folded_word_count"])
        self.assertFalse(links[0]["scholarly_verified"])
        self.assertFalse(links[0]["text_included"])

    def test_a_replaced_source_file_cannot_be_used_as_witness(self):
        right=PHRASE
        w=_witness(right)
        with self.assertRaisesRegex(ValueError,"HS_MATCH_SOURCE_BLOB_MISMATCH"):
            match_mentions([_mention(right)],[w],
                           source_texts={w["source_id"]:right+"tampered"})

    def test_witness_digest_mismatch_fails_even_if_full_blob_good(self):
        raw=PHRASE
        w=_witness(raw)
        w["evidence_sha256"]="f"*64
        with self.assertRaisesRegex(ValueError,"HS_WITNESS_EVIDENCE_INVALID"):
            match_mentions([_mention(raw)],[w],
                           source_texts={w["source_id"]:raw})

    def test_source_phrase_not_in_cited_block_returns_no_match(self):
        source="فاصل: "+PHRASE+"\nشاهد آخر مستقل ليس له الصلة المطلوبة"
        part=source.index("\n")+1
        w=make_witness(
            source_id="openiti:0279Tirmidhi.Sunan",work_id="0279Tirmidhi.Sunan",
            version_id="v", source_blob_sha=git_blob_sha(source.encode()),
            locator="L2",raw_text=source,span=(part,len(source)))
        r=match_mentions([_mention(PHRASE)],[w],
                         source_texts={w["source_id"]:source})
        self.assertEqual("NO_MATCH",r[0]["match_status"])

    def test_no_auto_textually_supported_even_for_identical_ten_words(self):
        m=_mention(PHRASE)
        w=_witness(PHRASE)
        r=match_mentions([m],[w],source_texts={w["source_id"]:PHRASE})
        self.assertEqual("CANDIDATE_MATCH",r[0]["match_status"])
        self.assertTrue(r[0]["textually_grounded_lexical_overlap"])
        self.assertFalse(r[0]["identity_of_narration_confirmed"])



class PrivateOperatorReplayTests(unittest.TestCase):
    def test_redacted_receipt_reports_only_lexical_candidate(self):
        dummy_link = {
            "link_id": "hl:test", "match_status": "CANDIDATE_MATCH",
            "textually_grounded_lexical_overlap": True,
            "identity_of_narration_confirmed": False,
            "folded_word_count": 10,
            "tafsir_shared_raw_span": [44, 92],
            "hadith_shared_raw_span": [100, 148],
            "tafsir_shared_raw_sha256": "a"*64,
            "hadith_shared_raw_sha256": "b"*64,
            "text_included": False,
        }
        fake = {
            "status": "OK", "passages_processed": 1,
            "mentions_total": 1, "witnesses_total": 2,
            "links_total": 1, "links_by_status": {"CANDIDATE_MATCH": 1},
            "sources_unavailable": [], "links": [dummy_link],
        }
        with patch("engines.hadith.hsearch.replay.lookup_verse",
                   return_value={"quran_reference": "2:185"}), \
             patch("engines.hadith.hsearch.replay.extract_local_verse",
                   return_value=[{"not":"private source bytes"}]), \
             patch("engines.hadith.hsearch.replay.run_hsearch",
                   return_value=fake):
            result = replay("2:185", Path("private.db"), Path("private_cache"))
        self.assertEqual("OK",result["status"])
        self.assertEqual(1,result["aligned_candidate_count"])
        self.assertFalse(result["narration_identity_established"])
        self.assertFalse(result["scientific_gate_passed"])
        self.assertFalse(result["text_included"])
        self.assertNotIn("private source bytes",
                         json.dumps(result,ensure_ascii=False))

    def test_replay_fails_without_leaking_private_error(self):
        stream = io.StringIO()
        with patch("engines.hadith.hsearch.replay.replay",
                   side_effect=RuntimeError("private source content")):
            with redirect_stdout(stream):
                code=replay_main([
                    "2:185", "--database", "private.db",
                    "--hadith-cache", "private_cache",
                ])
        self.assertEqual(2,code)
        result=json.loads(stream.getvalue())
        self.assertEqual("REFUSED",result["status"])
        self.assertFalse(result["text_included"])
        self.assertNotIn("private source content",stream.getvalue())


if __name__ == "__main__":
    unittest.main()
