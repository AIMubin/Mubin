"""Tafsir T0.2.3 regression: synthetic passage provenance and abstention."""
from __future__ import annotations

from contextlib import closing, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from engines.tafsir.t01 import _lookup
from engines.tafsir.t02 import make_record, TafsirT02Error
from engines.tafsir.t023 import (
    build_relationships, identify_candidates, summarize_analysis,
    ATTRIB_NAMED_REPORT, ATTRIB_AUTHOR_OWN,
    ENDORSE_EXPLICIT, IDENTITY_UNKNOWN,
)
from engines.tafsir.t023_cli import main as cli_main

REPORTED = ("وقال مجاهد: معنى اصطناعي للاختبار وليس تفسيرًا حقيقيًا. "
            "وقيل: هذا قول تجريبي آخر للاختبار. "
            "والصواب عندنا قول اصطناعي ثالث للتدقيق.")
PLAIN = ("دلت هذه العبارة الاصطناعية على معنى مستعمل في الاختبار فقط. "
         "وليس ذلك رأيًا موثقًا لأحد من المفسرين.")
HTML = ("<b>وقال مجاهد:</b> مثال اصطناعي لا يمثل نص تفسير حقيقي. "
        "والصواب عندنا بيان اصطناعي آخر للاختبار.")


def passage(text=REPORTED, work="tafsir_tabari", ref="2:43", pad=""):
    raw = pad + text
    original_sha = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    sid = f"tafsir:{work}:{ref}:{original_sha}"
    return make_record(
        quran_reference=ref,
        work_id=work,
        author_id=None,
        source_record_id=sid,
        source_sha256=original_sha,
        original_text=raw,
        span=(len(pad),len(raw)),
    )


class T023Tests(unittest.TestCase):
    def test_named_report_is_a_candidate_not_an_author_opinion(self):
        c = identify_candidates(passage())
        report = [x for x in c if x["speaker_name"] == "مجاهد"]
        self.assertTrue(report)
        self.assertEqual(ATTRIB_NAMED_REPORT, report[0]["attribution_type"])
        self.assertFalse(report[0]["scholarly_verified"])
        self.assertNotEqual(ENDORSE_EXPLICIT, report[0]["author_endorsement"])

    def test_multiple_candidates_with_distinct_identifiers(self):
        c = identify_candidates(passage())
        self.assertGreaterEqual(len(c),3)
        self.assertEqual(len(c),len({x["candidate_id"] for x in c}))
        self.assertTrue(all(x["verification_status"] == "UNVERIFIED" for x in c))

    def test_explicit_first_person_cue_remains_unverified(self):
        own = [x for x in identify_candidates(passage())
               if x["attribution_type"] == ATTRIB_AUTHOR_OWN]
        self.assertTrue(own)
        self.assertIn("والصواب عندنا",own[0]["interpretation_statement"])
        self.assertEqual(ENDORSE_EXPLICIT,own[0]["author_endorsement"])
        self.assertEqual("UNVERIFIED",own[0]["verification_status"])

    def test_unqualified_no_cue_text_is_unclassified(self):
        c = identify_candidates(passage("البيان الاصطناعي هذا فقط من أجل تجربة التقطيع."))
        self.assertEqual("UNCLASSIFIED",c[0]["interpretation_type"])
        self.assertEqual("UNKNOWN",c[0]["attribution_type"])

    def test_untrusted_t02_passage_rejected(self):
        p=passage()
        p["source_sha256"]="f"*64
        with self.assertRaisesRegex(TafsirT02Error,"T023_SOURCE_RECORD_MISMATCH"):
            identify_candidates(p)
        p=passage()
        p["evidence_sha256"]="f"*64
        with self.assertRaisesRegex(TafsirT02Error,"T023_PASSAGE_EVIDENCE_MISMATCH"):
            identify_candidates(p)

    def test_forged_work_and_wrong_reference_refused(self):
        p=passage()
        p["work_id"]="tafsir_baghawi"
        with self.assertRaisesRegex(TafsirT02Error,"T023_SOURCE_RECORD_MISMATCH"):
            identify_candidates(p)
        p=passage()
        p["quran_reference"]="115:1"
        with self.assertRaisesRegex(TafsirT02Error,"T023_INVALID_REFERENCE"):
            identify_candidates(p)

    def test_literal_raw_source_offsets_account_for_html_and_padding(self):
        p=passage(HTML,pad="بداية ثابتة | ")
        c = identify_candidates(p)
        self.assertTrue(c)
        source = "بداية ثابتة | "+HTML
        for item in c:
            span=item["raw_source_span"]
            self.assertEqual(source[span[0]:span[1]],
                             item["interpretation_statement"])
            self.assertEqual(hashlib.sha256(
                item["interpretation_statement"].encode("utf-8")).hexdigest(),
                item["evidence_sha256"])

    def test_passing_data_not_grounded_is_not_accepted(self):
        p=passage()
        p["interpretation_statement"]=PLAIN
        with self.assertRaisesRegex(TafsirT02Error,"T023_INVALID_PASSAGE_SPAN"):
            identify_candidates(p)

    def test_quote_does_not_promote_author_preference(self):
        s="وقال مجاهد: «والصواب عندنا هذا القول الاصطناعي المنقول». "
        c=identify_candidates(passage(s))
        self.assertFalse(any(x["attribution_type"]==ATTRIB_AUTHOR_OWN for x in c))

    def test_relations_do_not_infer_agreement_disagreement_or_preference(self):
        c=identify_candidates(passage())
        r=build_relationships(c)
        self.assertTrue(r)
        self.assertTrue(all(x["relation_type"]=="UNDETERMINED" for x in r))
        self.assertTrue(all(not x["consensus_claimed"]
                            and not x["preference_by_system"] for x in r))

    def test_ghost_candidate_is_refused_even_with_a_fake_id(self):
        c=identify_candidates(passage())
        with self.assertRaisesRegex(TafsirT02Error,"T023_CANDIDATE_INVALID"):
            build_relationships(c+[{"candidate_id":"ghost",
                                    "passage_id":c[0]["passage_id"]}])

    def test_cross_source_relations_do_not_mix(self):
        a=identify_candidates(passage())
        b=identify_candidates(passage(work="tafsir_baghawi"))
        relations=build_relationships(a+b)
        self.assertFalse(any(x["from_candidate_id"] in {y["candidate_id"] for y in a}
                             and x["to_candidate_id"] in {y["candidate_id"] for y in b}
                             for x in relations))

    def test_tampered_candidate_raises_not_partial_relation(self):
        c=identify_candidates(passage())
        c[0]["work_id"]="tafsir_baghawi"
        with self.assertRaisesRegex(TafsirT02Error,"T023_CANDIDATE_SOURCE_INVALID"):
            build_relationships(c)

    def test_relation_refuses_overlapping_candidates(self):
        c=identify_candidates(passage())
        c[1]["statement_start"]=c[0]["statement_start"]
        with self.assertRaises(TafsirT02Error):
            build_relationships(c)

    def test_redacted_summary_is_explicitly_non_authoritative(self):
        p=passage()
        c=identify_candidates(p)
        r=build_relationships(c)
        summary=summarize_analysis([p],c,r)
        serialized=json.dumps(summary,ensure_ascii=False)
        self.assertNotIn("مجاهد",serialized)
        self.assertNotIn("الصواب",serialized)
        self.assertIn("NOT_EXEGETICAL_OPINIONS",summary["count_semantics"])
        self.assertEqual(len(c),summary["candidates_total"])
        self.assertEqual(len(r),summary["relations_undetermined"])
        self.assertFalse(summary["publication_allowed"])

    def test_unverified_flags_always_false(self):
        c=identify_candidates(passage())
        for item in c:
            for name in ("scholarly_verified","text_included","publication_allowed",
                         "juristic_inference_allowed","public_fatwa_authorized",
                         "p1_admitted"):
                self.assertIs(item[name],False,name)

    def test_duplicate_candidates_rejected(self):
        c=identify_candidates(passage())
        with self.assertRaisesRegex(TafsirT02Error,"T023_DUPLICATE_CANDIDATE_ID"):
            build_relationships(c+[c[0]])


class T023CLITests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"fixture.db"
        with closing(sqlite3.connect(self.db)) as conn, conn:
            conn.execute("CREATE TABLE verses(sura INTEGER,aya INTEGER,text TEXT)")
            conn.execute("CREATE TABLE tafsirs(source TEXT,sura INTEGER,aya INTEGER,text TEXT)")
            conn.execute("INSERT INTO verses VALUES (2,43,'NOT QURAN')")
            conn.execute("INSERT INTO tafsirs VALUES ('tabary',2,43,?)",(HTML,))
        h=hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.data=_lookup(self.db,"2:43",expected_sha256=h,
                          upstream_declared_sha256="a"*64,
                          include_private_text=True)

    def test_default_cli_does_not_print_sources(self):
        stream=io.StringIO()
        with patch("engines.tafsir.t023_cli.lookup_verse",return_value=self.data):
            with redirect_stdout(stream):
                code=cli_main(["2:43","--database",str(self.db)])
        self.assertEqual(0,code)
        data=json.loads(stream.getvalue())
        self.assertEqual("OK",data["status"])
        self.assertFalse(data["text_included"])
        self.assertNotIn("اصطناعي",stream.getvalue())

    def test_default_cli_reports_failure_without_private_paths(self):
        stream=io.StringIO()
        with redirect_stdout(stream):
            code=cli_main(["2:43","--database",str(self.db)])
        self.assertEqual(2,code)  # synthetic DB is not production-pinned
        self.assertNotIn(str(self.db),stream.getvalue())
        self.assertNotIn("اصطناعي",stream.getvalue())

if __name__ == "__main__":
    unittest.main()
