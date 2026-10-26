"""E2E-01.1 integrated research slice tests. Synthetic only."""
from __future__ import annotations
import hashlib, json
from pathlib import Path
import sqlite3, tempfile, unittest
from unittest.mock import patch
from engines.e2e.research_slice import research_slice
from engines.quran.research.private_adapters import PrivateResearchAdapters
from engines.quran.research.qualification import initialize_ledger
from engines.quran.research.unified import CONTRACT as RC
from qa import private_evidence_v01 as ev
from qa.corpus_ingest_v01 import load_manifest

HEAD = "d" * 64
PH = "synthetic-placeholder"

class T(unittest.TestCase):
    def setUp(s):
        s.tmp = tempfile.TemporaryDirectory(); s.addCleanup(s.tmp.cleanup)
        s.root = Path(s.tmp.name)
        s.vault = s.root / "vault"; s.vault.mkdir()
        s.corpus = s.vault / "mubin-private-corpus-v01.sqlite3"
        s.sidecar = s.root / "sidecar.db"
        s.registry = s.root / "registry.jsonl"
        s.anchor = s.root / "anchors"; s.anchor.mkdir(parents=True, exist_ok=True)
        s.ekey = s.root / "evidence.key"; s.ekey.write_bytes(b"x" * 48)
        s.qledger = s.root / "qual.jsonl"
        s.qanchor = s.root / "qanchors"; s.qanchor.mkdir(parents=True, exist_ok=True)
        s.qkey = s.root / "qual.key"; s.qkey.write_bytes(b"q" * 48)
        manifest = load_manifest()
        db = sqlite3.connect(s.corpus)
        db.executescript("CREATE TABLE corpus_sources(source_id TEXT PRIMARY KEY,source_kind TEXT,version TEXT,raw_sha256 TEXT,rights_status TEXT,publication_enabled INT,source_authenticated INT,p1_admitted INT);CREATE TABLE corpus_entries(source_id TEXT,sura INT,aya INT,source_kind TEXT,text TEXT,footnotes TEXT,PRIMARY KEY(source_id,sura,aya));")
        for src in manifest["sources"]:
            db.execute("INSERT INTO corpus_sources VALUES(?,?,?,?,?,?,?,?)",(src["id"],src["kind"],src["version"],src["sha256"],"legal_review_pending",0,0,0))
            db.execute("INSERT INTO corpus_entries VALUES(?,?,?,?,?,?)",(src["id"],2,1,src["kind"],PH,"fn"))
        db.commit(); db.close()
        conn = sqlite3.connect(s.sidecar)
        for tbl in ("tafsir_tabary","tafsir_katheer","tafsir_baghawy","tafsir_saadi","tafsir_moyassar"):
            conn.execute(f'CREATE TABLE "{tbl}" (sura INT,aya INT,tafsir TEXT)')
            conn.execute(f'INSERT INTO "{tbl}" VALUES (2,1,?)',("syn",))
        conn.execute('CREATE TABLE "QuranTafseer" (surahNo INT,ayahNo INT,Mukhtasarar TEXT)')
        conn.execute('INSERT INTO "QuranTafseer" VALUES (2,1,?)',("syn",))
        conn.commit(); conn.close()
        report = {"status":"EVIDENCE_REGISTRY_VERIFIED","byte_integrity_verified":True,"head_entry_sha256":HEAD,"rights_status":"legal_review_pending","source_authenticated":False,"scholarly_verified":False,"text_included":False}
        s.mock_ev = patch("engines.quran.research.private_adapters.evidence.verify_evidence",return_value=report)
        s.mock_ev.start(); s.addCleanup(s.mock_ev.stop)
        s.mock_head = patch.object(PrivateResearchAdapters,"evidence_head",return_value=HEAD)
        s.mock_head.start(); s.addCleanup(s.mock_head.stop)
        initialize_ledger(s.qledger,s.qanchor,s.qkey,vault=s.vault,evidence_registry=s.registry,evidence_anchor_dir=s.anchor,evidence_key=s.ekey,sidecar_db=s.sidecar,operator="lead-operator")
        retrieval = {"contract":RC,"reference":"2:1","research_mode":"metadata_only","evidence_head_sha256":HEAD,"text_included":False,"source_authenticated":False,"scholarly_verified":False,"rights_status":"legal_review_pending","sources":[{"source_id":src["id"],"source_kind":src["kind"],"adapter":"quranenc_corpus","coordinate_present":True,"text_included":False,"edition_verified":False,"rights_status":"legal_review_pending","scholarly_verified":False,"p1_admitted":False} for src in manifest["sources"]]}
        s.mock_ret = patch("engines.quran.research.unified.unified_lookup",return_value=retrieval)
        s.mock_ret.start(); s.addCleanup(s.mock_ret.stop)

    def test_result(self):
        adapters = PrivateResearchAdapters(vault=self.vault,corpus_db=self.corpus,sidecar_db=self.sidecar,registry=self.registry,anchor_dir=self.anchor,evidence_key=self.ekey)
        result = research_slice(adapters,"2:1","دلالة الأمر",ledger=self.qledger,qualification_anchor_dir=self.qanchor,qualification_key=self.qkey,vault=self.vault)
        self.assertEqual(result["contract"],"mubin-e2e-research-v0.1")
        for key in ("quran_retrieval","usul_analysis","qualification_states","gaps","undetermined","limits"): self.assertIn(key,result)
        for k,v in result["limits"].items(): self.assertFalse(v)

    def test_deterministic(self):
        a = json.dumps(self.test_result and self.test_result(),sort_keys=True,ensure_ascii=False) if False else ""
        adapters = PrivateResearchAdapters(vault=self.vault,corpus_db=self.corpus,sidecar_db=self.sidecar,registry=self.registry,anchor_dir=self.anchor,evidence_key=self.ekey)
        a = json.dumps(research_slice(adapters,"2:1","دلالة الأمر",ledger=self.qledger,qualification_anchor_dir=self.qanchor,qualification_key=self.qkey,vault=self.vault),sort_keys=True,ensure_ascii=False)
        b = json.dumps(research_slice(adapters,"2:1","دلالة الأمر",ledger=self.qledger,qualification_anchor_dir=self.qanchor,qualification_key=self.qkey,vault=self.vault),sort_keys=True,ensure_ascii=False)
        self.assertEqual(a,b)

    def test_no_text_leak(self):
        adapters = PrivateResearchAdapters(vault=self.vault,corpus_db=self.corpus,sidecar_db=self.sidecar,registry=self.registry,anchor_dir=self.anchor,evidence_key=self.ekey)
        result = research_slice(adapters,"2:1","دلالة الأمر",ledger=self.qledger,qualification_anchor_dir=self.qanchor,qualification_key=self.qkey,vault=self.vault)
        raw = json.dumps(result,ensure_ascii=False)
        self.assertNotIn(PH,raw)

def research_slice_helper(*args,**kw): pass
PH = "synthetic-placeholder"

if __name__ == "__main__": unittest.main()
