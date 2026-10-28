"""H-Search-01 acceptance tests (synthetic CI data only)."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from engines.hadith.hsearch.contracts import (
    make_mention, make_witness, make_link)
from engines.hadith.hsearch.mention import detect_mentions
from engines.hadith.hsearch.matching import match_mentions
from engines.hadith.hsearch.commentary import find_commentary
from engines.hadith.hsearch.pipeline import run_hsearch

PASSAGE = ("عن رسول الله أنه أمر بالصلاة، وفي لفظ أخرى ذكر المسألة. "
           "وقال مجاهد: المراد الأداء في وقتها.")


def passage(text=PASSAGE):
    return {"quran_reference": "2:43", "work_id": "tafsir_tabari",
            "source_record_id": "tafsir:tafsir_tabari:2:43:" + "a" * 64,
            "evidence_span": [0, len(text)],
            "interpretation_statement": text}


class ContractsTests(unittest.TestCase):
    def test_mention_stable_id_and_digest(self):
        a = make_mention(meta={"quran_reference": "2:43",
            "tafsir_work_id": "w", "tafsir_source_record_id": "r"},
            raw_text=PASSAGE, span=(0, 30), mention_type="MARFU",
            attribution_status="EXPLICIT_IN_TEXT")
        b = make_mention(meta={"quran_reference": "2:43",
            "tafsir_work_id": "w", "tafsir_source_record_id": "r"},
            raw_text=PASSAGE, span=(0, 30), mention_type="MARFU",
            attribution_status="EXPLICIT_IN_TEXT")
        self.assertEqual(a["mention_id"], b["mention_id"])
        self.assertTrue(a["mention_id"].startswith("hm:"))
        snippet = PASSAGE[0:30]
        self.assertEqual(a["evidence_sha256"],
                         hashlib.sha256(snippet.encode()).hexdigest())

    def test_witness_requires_valid_blob(self):
        with self.assertRaises(Exception):
            make_witness(source_id="s", work_id="w", version_id="v",
                         source_blob_sha="nothex", locator="L1",
                         raw_text="نص", span=(0, 2))

    def test_link_requires_witness_for_match(self):
        m = make_mention(meta={"quran_reference": "2:43",
            "tafsir_work_id": "w", "tafsir_source_record_id": "r"},
            raw_text=PASSAGE, span=(0, 30), mention_type="MARFU",
            attribution_status="EXPLICIT_IN_TEXT")
        with self.assertRaises(Exception):
            make_link(mention=m, witness=None,
                      match_status="CANDIDATE_MATCH", match_method="x")

    def test_no_canonical_hadith_numbers(self):
        m = make_mention(meta={"quran_reference": "2:43",
            "tafsir_work_id": "w", "tafsir_source_record_id": "r"},
            raw_text=PASSAGE, span=(0, 30), mention_type="MARFU",
            attribution_status="EXPLICIT_IN_TEXT")
        raw = json.dumps(m, ensure_ascii=False)
        self.assertNotIn("hadith_number", raw)


class MentionTests(unittest.TestCase):
    def test_marfu_detected_with_span(self):
        out = detect_mentions(passage())
        self.assertTrue(out)
        marfu = [m for m in out if m["mention_type"] == "MARFU"]
        self.assertTrue(marfu)
        s0, s1 = marfu[0]["raw_source_span"]
        self.assertEqual(PASSAGE[s0:s1], PASSAGE[s0:s1])
        self.assertIn("عن رسول الله", PASSAGE[s0:s1])

    def test_mawquf_stays_distinct(self):
        out = detect_mentions(passage())
        types = {m["mention_type"] for m in out}
        self.assertIn("MAWQUF", types)
        self.assertNotEqual(types, {"MARFU"})

    def test_all_unverified_flags_false(self):
        out = detect_mentions(passage())
        for m in out:
            for flag in ("scholarly_verified", "text_included",
                         "publication_allowed", "juristic_inference_allowed",
                         "public_fatwa_authorized", "p1_admitted"):
                self.assertFalse(m[flag], flag)


class MatchingTests(unittest.TestCase):
    def test_no_match_when_no_witnesses(self):
        m = make_mention(meta={"quran_reference": "2:43",
            "tafsir_work_id": "w", "tafsir_source_record_id": "r"},
            raw_text=PASSAGE, span=(0, 30), mention_type="MARFU",
            attribution_status="EXPLICIT_IN_TEXT")
        links = match_mentions([m], [])
        self.assertEqual(links[0]["match_status"], "SOURCE_UNAVAILABLE")

    def test_similar_wording_never_upgrades_without_verified_substring(self):
        raw = "عن رسول الله أنه أمر بالصلاة على طريق أخرى مختلفة في اللفظ كليا"
        digest = hashlib.sha256(raw.encode()).hexdigest()
        w = make_witness(source_id="openiti:0279Tirmidhi.Sunan",
                         work_id="0279Tirmidhi.Sunan",
                         version_id="v1",
                         source_blob_sha="a" * 40, locator="L1",
                         raw_text=raw, span=(0, len(raw)))
        m = make_mention(meta={"quran_reference": "2:43",
            "tafsir_work_id": "w", "tafsir_source_record_id": "r"},
            raw_text=PASSAGE, span=(0, 30), mention_type="MARFU",
            attribution_status="EXPLICIT_IN_TEXT")
        links = match_mentions([m], [w])
        # Completely different wording: no shared distinctive n-gram,
        # so the honest status is NO_MATCH — similarity is never enough.
        self.assertEqual(links[0]["match_status"], "NO_MATCH")


class CommentaryTests(unittest.TestCase):
    def test_no_judgment_reported_when_absent(self):
        r = find_commentary("نص بلا أي أحكام", "L1", source_id="s",
                            work_id="w", version_id="v", blob_sha="a" * 40)
        self.assertEqual(r["presence"], "NO_CRITICAL_JUDGMENT_FOUND")

    def test_judgment_never_generalized(self):
        r = find_commentary("في هذا الحكم: ضعيف.", "L2", source_id="s",
                            work_id="w", version_id="v", blob_sha="a" * 40)
        self.assertIn(r["presence"],
                      ("SOURCE_REPORTED_JUDGMENT",
                       "UNVERIFIED_CRITICAL_ATTRIBUTION"))
        self.assertFalse(r["scholarly_verified"])
        self.assertIn("never generalized", r["scope_note"])


class PipelineTests(unittest.TestCase):
    def test_source_unavailable_distinct_from_no_match(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        r = run_hsearch([passage()], Path(tmp.name), allow_network=False)
        self.assertEqual(r["status"], "OK")
        self.assertTrue(r["sources_unavailable"])
        for l in r["links"]:
            self.assertEqual(l["match_status"], "SOURCE_UNAVAILABLE")

    def test_holdout_never_read(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        r = run_hsearch([passage()], Path(tmp.name), allow_network=False)
        self.assertFalse(r["holdout_read"])


if __name__ == "__main__":
    unittest.main()
