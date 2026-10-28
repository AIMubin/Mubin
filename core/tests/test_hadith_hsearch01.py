"""H-Search-01 adversarial synthetic tests: source spans, abstention and privacy."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from engines.hadith.hsearch import sources as hs_sources
from engines.hadith.hsearch.contracts import (
    make_mention, make_witness, make_link)
from engines.hadith.hsearch.mention import detect_mentions
from engines.hadith.hsearch.matching import match_mentions
from engines.hadith.hsearch.commentary import find_commentary
from engines.hadith.hsearch.pipeline import run_hsearch
from engines.tafsir.t02 import make_record, _catalog_authors

PHRASE = ("قام النبي بالحديث عن معنى هذا الأمر في مجلس ضم عدة "
          "رجال من أصحاب العلم ثم تحدث عن المسألة")
TAFSIR_TEXT = "مقدمة اصطناعية لا حديث فيها. قال رسول الله: " + PHRASE + "."
SECOND = ("شاهد اصطناعي آخر غير مطابق، يحوي كلامًا مطولًا "
          "دون وجود الحديث المتطابق للاختبار.")


def _sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def passage(text=TAFSIR_TEXT, *, prefix=""):
    raw = prefix + text
    digest = _sha(raw)
    return make_record(
        quran_reference="2:43", work_id="tafsir_tabari",
        author_id=_catalog_authors()["tafsir_tabari"],
        source_record_id=f"tafsir:tafsir_tabari:2:43:{digest}",
        source_sha256=digest, original_text=raw,
        span=(len(prefix), len(raw)),
    )


def git_sha(s):
    return hs_sources.git_blob_sha(s.encode("utf-8"))


def synthetic_witness(source, start, end, *, sid="openiti:0279Tirmidhi.Sunan"):
    return make_witness(
        source_id=sid, work_id="0279Tirmidhi.Sunan",
        version_id="synthetic:1", source_blob_sha=git_sha(source),
        locator=f"L{start+1}", raw_text=source, span=(start, end))


class MentionTests(unittest.TestCase):
    def test_plain_prose_not_falsely_a_narration(self):
        self.assertEqual([],detect_mentions(passage(
            "نص اصطناعي ليس رواية ولا يحتوي علامة حديث أو أثر في هذه التجربة.")))

    def test_marker_cue_is_only_unverified(self):
        out = detect_mentions(passage())
        self.assertEqual(1,len(out))
        self.assertEqual("MARFU",out[0]["mention_type"])
        self.assertEqual("IMPLIED_BY_MARKER",out[0]["attribution_status"])
        self.assertFalse(out[0]["scholarly_verified"])

    def test_raw_offsets_use_original_source_not_passage_local(self):
        p = passage(prefix="<b>وسم أصلي</b> | ")
        m = detect_mentions(p)[0]
        a,b = m["raw_source_span"]
        raw="<b>وسم أصلي</b> | "+TAFSIR_TEXT
        self.assertEqual(raw[a:b],TAFSIR_TEXT[
            m["passage_relative_span"][0]:m["passage_relative_span"][1]])
        self.assertEqual(m["passage_id"],p["interpretation_id"])

    def test_tampered_parent_passage_refused(self):
        p = passage()
        p["evidence_sha256"]="f"*64
        with self.assertRaises(ValueError):
            detect_mentions(p)

    def test_mention_id_is_stable_and_bound_to_original_offset(self):
        a = detect_mentions(passage())[0]
        b = detect_mentions(passage())[0]
        c = detect_mentions(passage(prefix="مقدمة مختلفة | "))[0]
        self.assertEqual(a["mention_id"],b["mention_id"])
        self.assertNotEqual(a["mention_id"],c["mention_id"])

    def test_two_cues_distinct_and_no_prior_plain_prefix(self):
        p=passage("قال رسول الله حديث اصطناعي عن أمر محدد. "
                  "قال مجاهد: رواية أخرى في نفس السياق الاصطناعي.")
        m=detect_mentions(p)
        self.assertEqual(2,len(m))
        self.assertEqual(["MARFU","MAQTU"],[x["mention_type"] for x in m])
        self.assertNotEqual(m[0]["mention_id"],m[1]["mention_id"])

    def test_ibn_abbas_companion_cue_not_maqtuu(self):
        p=passage("قال ابن عباس: هذا مثال اصطناعي مطوّل لا يحمل معنى حقيقيًا.")
        m=detect_mentions(p)
        self.assertEqual("MAWQUF",m[0]["mention_type"])
        self.assertEqual("IMPLIED_BY_MARKER",m[0]["attribution_status"])


class WitnessAndMatchTests(unittest.TestCase):
    def setUp(self):
        self.m = detect_mentions(passage())[0]
        self.text = TAFSIR_TEXT[
            slice(*self.m["passage_relative_span"])]
        self.m["_mention_text"] = self.text

    def test_distinct_witness_ids_per_source_span(self):
        source = SECOND + "\n" + PHRASE + "\n" + SECOND
        a=synthetic_witness(source,0,len(SECOND))
        b=synthetic_witness(source,len(SECOND)+1,len(SECOND)+1+len(PHRASE))
        self.assertNotEqual(a["witness_id"],b["witness_id"])
        self.assertNotEqual(a["evidence_sha256"],b["evidence_sha256"])

    def test_match_locates_exact_witness_not_first_source_block(self):
        source = SECOND + "\n" + PHRASE
        first=synthetic_witness(source,0,len(SECOND))
        second=synthetic_witness(source,len(SECOND)+1,len(source))
        links=match_mentions([self.m],[first,second],source_texts={
            "openiti:0279Tirmidhi.Sunan":source})
        self.assertEqual(links[0]["match_status"],"CANDIDATE_MATCH")
        self.assertEqual(links[0]["witness_id"],second["witness_id"])
        self.assertFalse(links[0]["identity_of_narration_confirmed"])

    def test_phrase_in_entire_book_but_not_witness_is_no_match(self):
        source = SECOND + "\n" + PHRASE
        w=synthetic_witness(source,0,len(SECOND))
        result=match_mentions([self.m],[w],source_texts={
            "openiti:0279Tirmidhi.Sunan":source})
        self.assertEqual(result[0]["match_status"],"NO_MATCH")

    def test_witness_digest_tampering_fails_closed(self):
        source=PHRASE
        w=synthetic_witness(source,0,len(source))
        w["evidence_sha256"]="a"*64
        with self.assertRaisesRegex(ValueError,"HS_WITNESS_EVIDENCE_INVALID"):
            match_mentions([self.m],[w],source_texts={
                "openiti:0279Tirmidhi.Sunan":source})

    def test_mention_digest_tampering_fails_closed(self):
        source=PHRASE
        w=synthetic_witness(source,0,len(source))
        self.m["_mention_text"]="tampered text"
        with self.assertRaisesRegex(ValueError,"HS_MENTION_EVIDENCE_INVALID"):
            match_mentions([self.m],[w],source_texts={
                "openiti:0279Tirmidhi.Sunan":source})

    def test_13_char_overlap_is_not_a_hadith_identity(self):
        tiny="من صام رمضان"
        w=synthetic_witness(tiny+" هذا كلام مختلف في بقية العبارة",0,
            len(tiny+" هذا كلام مختلف في بقية العبارة"))
        m=dict(self.m,_mention_text=tiny)
        m["raw_source_span"]=[0,len(tiny)]
        m["evidence_sha256"]=_sha(tiny)
        result=match_mentions([m],[w],source_texts={
            "openiti:0279Tirmidhi.Sunan":tiny+" هذا كلام مختلف في بقية العبارة"})
        self.assertEqual(result[0]["match_status"],"NO_MATCH")

    def test_missing_source_binding_not_silently_accepted(self):
        w=synthetic_witness(PHRASE,0,len(PHRASE))
        with self.assertRaisesRegex(ValueError,"HS_MATCH_SOURCE_NOT_BOUND"):
            match_mentions([self.m],[w])

    def test_link_rejects_positive_without_witness(self):
        with self.assertRaises(ValueError):
            make_link(mention=self.m,witness=None,
                      match_status="CANDIDATE_MATCH",match_method="bad")


class SourceTests(unittest.TestCase):
    def test_holdout_source_is_not_authorized(self):
        self.assertNotIn("openiti:0385Daraqutni.Sunan",hs_sources.AUTHORIZED)
        self.assertNotIn("openiti:0852IbnHajarCasqalani.TalkhisHabir",
                         hs_sources.AUTHORIZED)

    def test_symlink_cache_entry_refused_before_read(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            target=root/"other.txt"
            target.write_bytes(b"forbidden")
            path=root/hs_sources.cache_filename("openiti:0279Tirmidhi.Sunan")
            try:
                path.symlink_to(target)
            except (OSError,NotImplementedError):
                self.skipTest("OS cannot create symlinks without privilege")
            with self.assertRaisesRegex(ValueError,"HS_CACHE_SYMLINK_FORBIDDEN"):
                hs_sources.acquire(root,allow_network=False)


class PipelineTests(unittest.TestCase):
    def test_missing_cache_yields_unavailable_not_no_match(self):
        with tempfile.TemporaryDirectory() as d:
            r=run_hsearch([passage()],Path(d),allow_network=False)
            self.assertEqual("OK",r["status"])
            self.assertTrue(r["sources_unavailable"])
            self.assertEqual({"SOURCE_UNAVAILABLE":1},r["links_by_status"])
            self.assertFalse(r["holdout_read"])

    def test_positive_synthetic_pipeline_only_candidate_not_verified(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            registry={}
            for sid in sorted(hs_sources.AUTHORIZED):
                text=(PHRASE+"\n") if sid=="openiti:0279Tirmidhi.Sunan" else (
                    SECOND+"\n")
                (root/hs_sources.cache_filename(sid)).write_bytes(
                    text.encode("utf-8"))
                registry[sid]={
                    "source_id":sid, "work_id":sid.split(":")[1],
                    "version_id":"synthetic:1",
                    "source_blob_sha":git_sha(text),
                }
            with patch("engines.hadith.hsearch.sources.authorized_sources",
                       return_value=registry):
                r=run_hsearch([passage()],root,allow_network=False)
            self.assertEqual("OK",r["status"])
            self.assertEqual({"CANDIDATE_MATCH":1},r["links_by_status"])
            self.assertNotEqual(r["links"][0]["witness_id"],None)
            self.assertEqual([],r["sources_unavailable"])
            self.assertFalse(r["scholarly_verified"])
            self.assertNotIn(PHRASE,json.dumps(r,ensure_ascii=False))

    def test_pin_mismatch_returns_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            sid="openiti:0279Tirmidhi.Sunan"
            (root/hs_sources.cache_filename(sid)).write_text(
                "wrong text",encoding="utf-8")
            r=run_hsearch([passage()],root,allow_network=False)
            self.assertEqual("REFUSED",r["status"])
            self.assertEqual("HS_ACQUIRE_OR_PIN_FAILED",r["code"])
            self.assertNotIn("wrong text",json.dumps(r))


class CommentaryTests(unittest.TestCase):
    def test_lexical_critique_is_not_a_scholar_judgment(self):
        r=find_commentary("في هذا السياق كلمة ضعيف.", "L2",
             source_id="s",work_id="w",version_id="v",blob_sha="a"*40)
        self.assertEqual("UNVERIFIED_CRITICAL_ATTRIBUTION",r["presence"])
        self.assertIsNone(r["speaker"])
        self.assertFalse(r["scholarly_verified"])
        self.assertFalse(r["text_included"])


if __name__=="__main__":
    unittest.main()
