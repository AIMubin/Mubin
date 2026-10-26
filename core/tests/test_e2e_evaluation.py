"""E2E-01.4 evaluation framework tests. Synthetic only."""
from __future__ import annotations
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from engines.e2e.evaluation import run_full_evaluation
from engines.quran.research.private_adapters import PrivateResearchAdapters
from engines.quran.research.qualification import initialize_ledger
from qa import private_evidence_v01 as ev
from qa.corpus_ingest_v01 import load_manifest

HEAD = "d" * 64


class TestEvaluation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.corpus = self.vault / "mubin-private-corpus-v01.sqlite3"
        self.sidecar = self.root / "sidecar.db"
        self.registry = self.root / "registry.jsonl"
        self.anchor = self.root / "anchors"
        self.anchor.mkdir(parents=True, exist_ok=True)
        self.ekey = self.root / "evidence.key"
        self.ekey.write_bytes(b"x" * 48)
        self.qledger = self.root / "qual.jsonl"
        self.qanchor = self.root / "qanchors"
        self.qanchor.mkdir(parents=True, exist_ok=True)
        self.qkey = self.root / "qual.key"
        self.qkey.write_bytes(b"q" * 48)
        manifest = load_manifest()
        db = sqlite3.connect(self.corpus)
        db.executescript("""
            CREATE TABLE corpus_sources(source_id TEXT PRIMARY KEY, source_kind TEXT,
              version TEXT, raw_sha256 TEXT, rights_status TEXT,
              publication_enabled INTEGER, source_authenticated INTEGER, p1_admitted INTEGER);
            CREATE TABLE corpus_entries(source_id TEXT, sura INTEGER, aya INTEGER,
              source_kind TEXT, text TEXT, footnotes TEXT, PRIMARY KEY(source_id,sura,aya));
        """)
        for s in manifest["sources"]:
            db.execute("INSERT INTO corpus_sources VALUES(?,?,?,?,?,?,?,?)",
                (s["id"],s["kind"],s["version"],s["sha256"],
                 "legal_review_pending",0,0,0))
            db.execute("INSERT INTO corpus_entries VALUES(?,?,?,?,?,?)",
                (s["id"],2,1,s["kind"],"synthetic","fn"))
        db.commit(); db.close()
        conn = sqlite3.connect(self.sidecar)
        for tbl in ("tafsir_tabary","tafsir_katheer","tafsir_baghawy",
                    "tafsir_saadi","tafsir_moyassar"):
            conn.execute(f'CREATE TABLE "{tbl}" (sura INT,aya INT,tafsir TEXT)')
            conn.execute(f'INSERT INTO "{tbl}" VALUES (2,1,?)',("syn",))
        conn.execute('CREATE TABLE "QuranTafseer" (surahNo INT,ayahNo INT,Mukhtasarar TEXT)')
        conn.execute('INSERT INTO "QuranTafseer" VALUES (2,1,?)',("syn",))
        conn.commit(); conn.close()
        report = {"status": "EVIDENCE_REGISTRY_VERIFIED",
            "byte_integrity_verified": True, "head_entry_sha256": HEAD,
            "rights_status": "legal_review_pending",
            "source_authenticated": False, "scholarly_verified": False,
            "text_included": False}
        self.mock_ev = patch(
            "engines.quran.research.private_adapters.evidence.verify_evidence",
            return_value=report)
        self.mock_ev.start()
        self.addCleanup(self.mock_ev.stop)
        initialize_ledger(self.qledger, self.qanchor, self.qkey,
            vault=self.vault, evidence_registry=self.registry,
            evidence_anchor_dir=self.anchor, evidence_key=self.ekey,
            sidecar_db=self.sidecar, operator="lead-operator")

    def test_evaluation_runs_all_groups(self):
        from engines.quran.research.private_adapters import PrivateResearchAdapters as PRA
        adapters = PRA(vault=self.vault, corpus_db=self.corpus,
            sidecar_db=self.sidecar, registry=self.registry,
            anchor_dir=self.anchor, evidence_key=self.ekey)
        result = run_full_evaluation(adapters, self.corpus, self.vault, self.qledger,
            self.qanchor, self.qkey, ["2:1"], "دلالة صيغة الأمر والقرائن المؤثرة فيه")
        self.assertTrue(result["all_passed"])
        self.assertEqual(result["critical_failures"], 0)
        self.assertTrue(result["total"] > 0)

    def test_cannot_automate_reported(self):
        from engines.quran.research.private_adapters import PrivateResearchAdapters as PRA
        adapters = PRA(vault=self.vault, corpus_db=self.corpus,
            sidecar_db=self.sidecar, registry=self.registry,
            anchor_dir=self.anchor, evidence_key=self.ekey)
        result = run_full_evaluation(adapters, self.corpus, self.qledger,
            self.qanchor, self.qkey, ["2:1"], "دلالة صيغة الأمر والقرائن المؤثرة فيه")
        self.assertTrue(len(result.get("cannot_automate", [])) >= 5)


if __name__ == "__main__":
    unittest.main()
