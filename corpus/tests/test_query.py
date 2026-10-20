import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from corpus.query import get_ayah
from corpus.verify_quran import EXPECTED_COUNTS


class QueryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.db = Path(self.directory.name) / "sample.db"
        connection = sqlite3.connect(self.db)
        try:
            connection.execute("CREATE TABLE verses(sura INTEGER,aya INTEGER,text TEXT)")
            connection.execute("CREATE TABLE tafsirs(source TEXT,sura INTEGER,aya INTEGER,text TEXT)")
            connection.execute("INSERT INTO verses VALUES (1,1,'SYNTHETIC NOT QURAN')")
            connection.execute("INSERT INTO verses VALUES (2,1,'SYNTHETIC NOT QURAN')")
            connection.executemany("INSERT INTO tafsirs VALUES (?,?,?,?)", [
                ('tabary', 1, 1, '<br>'), ('baghawy', 1, 1, 'س'*32767)])
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.directory.cleanup()

    def test_provenance_flags(self):
        response = get_ayah(self.db, 1, 1)
        self.assertFalse(response["scholarly_verification"])
        self.assertEqual(response["text_classification"], "REFERENCE_REQUIRED_NO_QURAN_TEXT")
        self.assertIsNone(response["text"])
        tafsirs = {x['source_id']:x for x in response['tafsirs']}
        self.assertFalse(tafsirs['tabary']['displayable'])
        self.assertIsNone(tafsirs['tabary']['text'])
        self.assertIn('POSSIBLE_TRUNCATION_32767', tafsirs['baghawy']['quality_flags'])

    def test_suspect_baghawy_fails_closed_for_every_review_case(self):
        from corpus.query import BAGHAWY_Q03_REVIEW_HOLD
        connection = sqlite3.connect(self.db)
        try:
            for sura, aya in sorted(BAGHAWY_Q03_REVIEW_HOLD):
                connection.execute("INSERT INTO verses VALUES (?,?,?)",
                                   (sura, aya, "SYNTHETIC NOT QURAN"))
                connection.execute("INSERT INTO tafsirs VALUES (?,?,?,?)",
                                   ("baghawy", sura, aya, "SYNTHETIC NOT A REAL TAFSIR"))
            connection.execute("INSERT INTO tafsirs VALUES (?,?,?,?)",
                               ("tabary", 4, 43, "SYNTHETIC COMPARISON"))
            connection.commit()
        finally:
            connection.close()
        for sura, aya in sorted(BAGHAWY_Q03_REVIEW_HOLD):
            value = {row["source_id"]: row for row in get_ayah(self.db, sura, aya)["tafsirs"]}["baghawy"]
            self.assertFalse(value["displayable"])
            self.assertIsNone(value["text"])
            self.assertIsNone(value["display_text"])
            self.assertEqual(value["display_status"], "WITHHELD_PENDING_EDITORIAL_VERIFICATION")
            self.assertIn("EDITORIAL_HOLD_SUSPECTED_INCOMPLETE_UPSTREAM_TEXT", value["quality_flags"])
            self.assertFalse(value["diagnostic_override_active"])
            reviewer_value = {row["source_id"]: row for row in get_ayah(
                self.db, sura, aya, allow_flagged_tafsir_text=True)["tafsirs"]}["baghawy"]
            self.assertTrue(reviewer_value["displayable"])
            self.assertTrue(reviewer_value["diagnostic_override_active"])
            self.assertEqual(reviewer_value["display_status"], "DIAGNOSTIC_UNVERIFIED_SOURCE_TEXT")
            self.assertFalse(reviewer_value["scholarly_verification"])
        tabary = {row["source_id"]: row for row in get_ayah(self.db, 4, 43)["tafsirs"]}["tabary"]
        self.assertTrue(tabary["displayable"])
        self.assertFalse(tabary["editorial_review_required"])

    def test_32767_baghawy_unlisted_verse_is_also_withheld(self):
        # A new upstream ceiling-bound record must not leak just because the
        # four original issue IDs were the only known cases at review time.
        b = {row["source_id"]: row for row in get_ayah(self.db, 1, 1)["tafsirs"]}["baghawy"]
        self.assertFalse(b["displayable"])
        self.assertIsNone(b["text"])
        self.assertEqual(b["display_status"], "WITHHELD_PENDING_EDITORIAL_VERIFICATION")

    def test_source_citation_provenance_preserved_when_text_withheld(self):
        response = get_ayah(self.db, 1, 1)
        tafsirs = {item["source_id"]: item for item in response["tafsirs"]}
        flagged = tafsirs["baghawy"]
        citation = flagged["source_citation"]
        self.assertEqual(citation["work_label"], "معالم التنزيل (البغوي)")
        self.assertEqual(citation["source_dataset"], "tafsircenter/tafsir-mcp-data")
        self.assertEqual(citation["verse_locator"], "1:1")
        self.assertEqual(citation["edition_identity"], "NOT_YET_VERIFIED")
        self.assertEqual(citation["rights"], "UNKNOWN_UNLESS_SEPARATELY_ESTABLISHED")
        self.assertFalse(citation["content_displayed"])
        self.assertEqual(citation["imported_text_sha256"],
                         hashlib.sha256(("س" * 32767).encode("utf-8")).hexdigest())
        self.assertIsNone(flagged["display_text"])
        diagnostic = {x["source_id"]: x for x in get_ayah(
            self.db, 1, 1, allow_flagged_tafsir_text=True)["tafsirs"]}["baghawy"]
        self.assertEqual(diagnostic["source_citation"]["imported_text_sha256"],
                         citation["imported_text_sha256"])
        self.assertTrue(diagnostic["source_citation"]["content_displayed"])

    def test_reject_invalid_verse(self):
        with self.assertRaises(ValueError):
            get_ayah(self.db, 1, 8)

    def test_reference_override_requires_pinned_and_complete_witness(self):
        p = Path(self.directory.name)/'ref.txt'
        p.write_text(''.join(f'{s}|{a}|VERBATIM SYNTHETIC\n'
                             for s,n in enumerate(EXPECTED_COUNTS,1) for a in range(1,n+1)), encoding='utf-8')
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        self.assertEqual(get_ayah(self.db,1,1,p,h)['text'], 'VERBATIM SYNTHETIC')
        self.assertIn('tanzil.net',get_ayah(self.db,1,1,p,h)['quran_text_attribution'])
        self.assertFalse(get_ayah(self.db,1,1,p,h)['scholarly_verification'])
        with self.assertRaises(ValueError): get_ayah(self.db,1,1,p,'a'*64)
        opening = 'بِسْمِ ٱللَّهِ ٱلرَّحْمَٰنِ ٱلرَّحِيمِ'
        other = Path(self.directory.name)/'reference_with_basmala.txt'
        def synthetic_verse(s, a):
            if (s, a) == (1, 1):
                return opening  # The segmentation baseline must be an actual basmala.
            if (s, a) == (2, 1):
                return opening + " VERBATIM SYNTHETIC"
            return "VERBATIM SYNTHETIC"

        other.write_text(''.join(
            f"{s}|{a}|{synthetic_verse(s, a)}\n"
            for s,n in enumerate(EXPECTED_COUNTS,1) for a in range(1,n+1)
        ), encoding='utf-8')
        h2=hashlib.sha256(other.read_bytes()).hexdigest()
        segmented=get_ayah(self.db,2,1,other,h2)
        self.assertEqual(segmented['text'], 'VERBATIM SYNTHETIC')
        self.assertEqual(segmented['opening_basmala'], opening)
        self.assertIn('VERSE_SEGMENT', segmented['text_classification'])
        self.assertFalse(segmented['scholarly_verification'])



if __name__ == '__main__': unittest.main()
