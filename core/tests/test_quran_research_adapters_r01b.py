"""R0.1b private adapters: synthetic-only security and schema tests.

No actual Quran / Tafsir content, signing keys, or operator vault in CI.
The R0.1a validator itself is separately exercised by its own test suite;
here it is stubbed to exercise adapter behavior.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from hashlib import sha256
import hmac
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from qa import private_evidence_v01 as ev
from qa.corpus_ingest_v01 import load_manifest
from engines.quran.research.private_adapters import (
    PrivateResearchAdapters, ResearchAdapterError, PERMIT_CONTRACT,
    CONTRACT, SIDE_TABLES)

FIXTURE_QURAN = "invented-quran-coordinate-fixture—not-scripture"
FIXTURE_TAFSIR = "invented-tafsir-test-only-not-an-excerpt"
HEAD = "a" * 64


def _permit(path, key, *, source_ids=None, head=HEAD, duration=3600,
            allow=True, publication=False, purpose="restricted_internal_research"):
    payload = {
        "contract": PERMIT_CONTRACT,
        "evidence_head_sha256": head,
        "source_ids": list(source_ids or ["qe_ar_muyassar"]),
        "purpose": purpose,
        "expires_utc": (datetime.now(timezone.utc) +
                        timedelta(seconds=duration)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "authorization_id": "synthetic-review-0001",
        "text_access_allowed": allow,
        "publication_allowed": publication,
        "p1_admitted": False,
    }
    payload["mac"] = hmac.new(key, ev._canonical(payload), sha256).hexdigest()
    path.write_bytes(ev._canonical(payload))


class PrivateResearchAdaptersTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.corpus = self.vault / ev.CORPUS_DB_NAME
        self.sidecar = self.root / "original-sidecar.db"
        self.registry = self.root / "registry.jsonl"
        self.anchor = self.root / "anchors"
        self.evidence_key = self.root / "operator-evidence.key"
        self.permit = self.root / "signed-access.json"
        self.signing_key_path = self.root / "independent-approver.key"
        self.signing_key = b"test-only-secret-not-an-actual-operator-key-xyz"
        self.signing_key_path.write_bytes(self.signing_key)
        self.manifest = load_manifest()
        db = sqlite3.connect(self.corpus)
        try:
            db.executescript("""
                CREATE TABLE corpus_sources(
                  source_id TEXT PRIMARY KEY,source_kind TEXT,version TEXT,
                  raw_sha256 TEXT,rights_status TEXT,
                  publication_enabled INTEGER,source_authenticated INTEGER,p1_admitted INTEGER);
                CREATE TABLE corpus_entries(
                  source_id TEXT,sura INTEGER,aya INTEGER,source_kind TEXT,
                  text TEXT,footnotes TEXT,PRIMARY KEY(source_id,sura,aya));
            """)
            for source in self.manifest["sources"]:
                db.execute("INSERT INTO corpus_sources VALUES(?,?,?,?,?,?,?,?)",
                    (source["id"],source["kind"],source["version"],source["sha256"],
                     "legal_review_pending",0,0,0))
                db.execute("INSERT INTO corpus_entries VALUES(?,?,?,?,?,?)",
                    (source["id"],2,1,source["kind"],
                     FIXTURE_QURAN if source["kind"] == "quran" else FIXTURE_TAFSIR,
                     "synthetic-footnote-only"))
            db.commit()
        finally:
            db.close()
        conn = sqlite3.connect(self.sidecar)
        try:
            for table in SIDE_TABLES:
                if table == "QuranTafseer":
                    conn.execute('CREATE TABLE "QuranTafseer" (surahNo INTEGER,ayahNo INTEGER,Mukhtasarar TEXT)')
                    conn.execute('INSERT INTO "QuranTafseer" VALUES (2,1,?)',(FIXTURE_TAFSIR,))
                else:
                    conn.execute(f'CREATE TABLE "{table}" (sura INTEGER,aya INTEGER,tafsir TEXT)')
                    conn.execute(f'INSERT INTO "{table}" VALUES (2,1,?)',(FIXTURE_TAFSIR,))
            conn.commit()
        finally:
            conn.close()
        self.evidence_report = {
            "status": "EVIDENCE_REGISTRY_VERIFIED", "byte_integrity_verified": True,
            "head_entry_sha256": HEAD, "corpus_records": 31180,
            "source_authenticated": False, "rights_status": "legal_review_pending",
            "scholarly_verified": False, "text_included": False}
        p = patch("engines.quran.research.private_adapters.evidence.verify_evidence",
                  return_value=self.evidence_report)
        self.mock_evidence = p.start()
        self.addCleanup(p.stop)

    def adapters(self, **changes):
        args = dict(vault=self.vault, corpus_db=self.corpus,
                    sidecar_db=self.sidecar, registry=self.registry,
                    anchor_dir=self.anchor, evidence_key=self.evidence_key)
        args.update(changes)
        return PrivateResearchAdapters(**args)

    def test_five_corpus_sources_metadata_only(self):
        before = sha256(self.corpus.read_bytes()).hexdigest()
        sources=self.adapters().corpus_sources()
        self.assertEqual(5,len(sources))
        self.assertEqual({x["id"] for x in self.manifest["sources"]},
                         {x["source_id"] for x in sources})
        self.assertTrue(all(x["text_included"] is False for x in sources))
        self.assertTrue(all(x["publication_allowed"] is False for x in sources))
        self.assertNotIn(FIXTURE_TAFSIR,str(sources))
        self.assertEqual(before,sha256(self.corpus.read_bytes()).hexdigest())

    def test_six_allowlisted_sidecar_tables_metadata_only(self):
        data=self.adapters().sidecar_sources()
        self.assertEqual(6,len(data))
        self.assertEqual(set(SIDE_TABLES),{x["source_id"] for x in data})
        self.assertNotIn(FIXTURE_TAFSIR,str(data))

    def test_both_adapters_lookup_without_any_text(self):
        adapter=self.adapters()
        for kind,sid in (("corpus","qe_ar_muyassar"),
                         ("corpus","quran_tanzil_uthmani_hafs_20261018"),
                         ("sidecar","tafsir_tabary"),
                         ("sidecar","QuranTafseer")):
            with self.subTest(kind=kind,sid=sid):
                res=adapter.lookup("2:1",sid,adapter=kind)
                self.assertEqual(CONTRACT,res["contract"])
                self.assertTrue(res["coordinate_present"])
                self.assertFalse(res["text_included"])
                self.assertFalse(res["source_authenticated"])
                self.assertFalse(res["juristic_inference_allowed"])
                self.assertNotIn(FIXTURE_TAFSIR,str(res))
                self.assertNotIn(FIXTURE_QURAN,str(res))

    def test_absent_permit_denies_private_text_for_both_sources(self):
        adapter=self.adapters()
        for kind,sid in (("corpus","qe_ar_muyassar"),("sidecar","tafsir_tabary")):
            with self.subTest(kind=kind),self.assertRaisesRegex(
                    ResearchAdapterError,"LOCAL_TEXT_PERMIT_REQUIRED"):
                adapter.lookup("2:1",sid,adapter=kind,include_text=True)

    def test_signed_permit_limited_to_one_source_only(self):
        _permit(self.permit,self.signing_key)
        adapter=self.adapters(permit_path=self.permit,permit_key=self.signing_key_path)
        res=adapter.lookup("2:1","qe_ar_muyassar",include_text=True)
        self.assertEqual(FIXTURE_TAFSIR,res["text"])
        self.assertEqual("synthetic-footnote-only",res["footnotes"])
        self.assertTrue(res["text_included"])
        self.assertFalse(res["publication_allowed"])
        for kind,sid in (("corpus","qe_ar_nafahat"),("sidecar","tafsir_tabary")):
            with self.subTest(source=sid),self.assertRaisesRegex(
                    ResearchAdapterError,"LOCAL_TEXT_PERMIT_SCOPE_DENIED"):
                adapter.lookup("2:1",sid,adapter=kind,include_text=True)

    def test_sidecar_text_with_explicitly_signed_source_scope(self):
        _permit(self.permit,self.signing_key,source_ids=["tafsir_tabary"])
        adapter=self.adapters(permit_path=self.permit,permit_key=self.signing_key_path)
        result=adapter.lookup("2:1","tafsir_tabary",adapter="sidecar",include_text=True)
        self.assertEqual(FIXTURE_TAFSIR,result["text"])
        self.assertNotIn("footnotes",result)

    def test_corrupted_signature_denied(self):
        _permit(self.permit,self.signing_key)
        data=json.loads(self.permit.read_bytes())
        data["source_ids"].append("qe_ar_nafahat")
        self.permit.write_bytes(ev._canonical(data))
        with self.assertRaisesRegex(ResearchAdapterError,"LOCAL_TEXT_PERMIT_SIGNATURE_INVALID"):
            self.adapters(permit_path=self.permit,permit_key=self.signing_key_path).lookup(
                "2:1","qe_ar_muyassar",include_text=True)

    def test_expired_purpose_publication_and_wrong_head_denied(self):
        for change,reason in (
                ({"duration":-3},"LOCAL_TEXT_PERMIT_EXPIRED_OR_EXCESSIVE"),
                ({"purpose":"public_service"},"LOCAL_TEXT_PERMIT_SCOPE_DENIED"),
                ({"publication":True},"LOCAL_TEXT_PERMIT_SCOPE_DENIED"),
                ({"head":"b"*64},"LOCAL_TEXT_PERMIT_SCOPE_DENIED")):
            with self.subTest(change=change):
                _permit(self.permit,self.signing_key,**change)
                with self.assertRaisesRegex(ResearchAdapterError,reason):
                    self.adapters(permit_path=self.permit,permit_key=self.signing_key_path).lookup(
                        "2:1","qe_ar_muyassar",include_text=True)

    def test_denies_sql_injection_bad_coordinates_and_unknown_tables(self):
        ad=self.adapters()
        for ref in ("2:0","2:999","2:1 OR 1=1","1:8","0:1","2:001","2:1;DROP TABLE"):
            with self.subTest(ref=ref),self.assertRaisesRegex(ResearchAdapterError,"REFERENCE_INVALID"):
                ad.lookup(ref,"qe_ar_muyassar")
        for kind,sid in (("sidecar",'tafsir_tabary";DROP TABLE tafsir_tabary'),
                         ("corpus","other_source")):
            with self.subTest(sid=sid),self.assertRaisesRegex(ResearchAdapterError,"SOURCE_NOT_ALLOWLISTED"):
                ad.lookup("2:1",sid,adapter=kind)

    def test_reject_unsigned_evidence_or_wrong_vault_db_path(self):
        self.mock_evidence.return_value={**self.evidence_report,"source_authenticated":True}
        with self.assertRaisesRegex(ResearchAdapterError,"EVIDENCE_NOT_QUALIFIED"):
            self.adapters().corpus_sources()
        self.mock_evidence.return_value=self.evidence_report
        wrong=self.root/"different.sqlite3"
        with self.assertRaisesRegex(ResearchAdapterError,"CORPUS_PATH_NOT_ANCHORED"):
            self.adapters(corpus_db=wrong).corpus_sources()

    def test_reject_private_data_residing_in_public_checkout(self):
        from qa.corpus_ingest_v01 import REPO_ROOT
        with self.assertRaisesRegex(ResearchAdapterError,"PRIVATE_DATABASE_UNAVAILABLE"):
            from engines.quran.research.private_adapters import _db
            _db(REPO_ROOT/"unapproved.sqlite3")

    def test_local_signed_permit_must_be_outside_vault(self):
        _permit(self.permit,self.signing_key)
        inside=self.vault/"inside-permit.json"
        inside.write_bytes(self.permit.read_bytes())
        with self.assertRaisesRegex(ResearchAdapterError,"LOCAL_TEXT_PERMIT_INVALID"):
            self.adapters(permit_path=inside,permit_key=self.signing_key_path).lookup(
                "2:1","qe_ar_muyassar",include_text=True)


if __name__ == "__main__":
    unittest.main()
