"""R0.1c unified retrieval contract: synthetic-only contract and barrier tests.

No real vault, keys, or scripture content. Placeholder ASCII only.
"""
from __future__ import annotations

import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from qa import private_evidence_v01 as ev
from qa.corpus_ingest_v01 import load_manifest
from engines.quran.research.private_adapters import (
    PrivateResearchAdapters, ResearchAdapterError)
from engines.quran.research.unified import unified_lookup

FIXTURE_QURAN = "invented-quran-coordinate-fixture—not-scripture"
FIXTURE_TAFSIR = "invented-tafsir-test-only-not-an-excerpt"
HEAD = "b" * 64


class UnifiedRetrievalTests(unittest.TestCase):
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
        manifest = load_manifest()
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
            for source in manifest["sources"]:
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
            for table in ("tafsir_tabary","tafsir_katheer","tafsir_baghawy",
                          "tafsir_saadi","tafsir_moyassar"):
                conn.execute(f'CREATE TABLE "{table}" (sura INTEGER,aya INTEGER,tafsir TEXT)')
                conn.execute(f'INSERT INTO "{table}" VALUES (2,1,?)',(FIXTURE_TAFSIR,))
            conn.execute('CREATE TABLE "QuranTafseer" (surahNo INTEGER,ayahNo INTEGER,Mukhtasarar TEXT)')
            conn.execute('INSERT INTO "QuranTafseer" VALUES (2,1,?)',(FIXTURE_TAFSIR,))
            conn.commit()
        finally:
            conn.close()
        report = {"status": "EVIDENCE_REGISTRY_VERIFIED",
                  "byte_integrity_verified": True, "head_entry_sha256": HEAD,
                  "rights_status": "legal_review_pending",
                  "source_authenticated": False, "scholarly_verified": False,
                  "text_included": False}
        p = patch("engines.quran.research.private_adapters.evidence.verify_evidence",
                  return_value=report)
        self.mock_evidence = p.start()
        self.addCleanup(p.stop)
        self.adapters = PrivateResearchAdapters(
            vault=self.vault, corpus_db=self.corpus, sidecar_db=self.sidecar,
            registry=self.registry, anchor_dir=self.anchor,
            evidence_key=self.evidence_key)

    def lookup(self, **kwargs):
        return unified_lookup(self.adapters, "2:1", **kwargs)

    def test_metadata_contract_shape_and_nonpromotion(self):
        from engines.quran.research.unified import unified_lookup
        result = self.lookup()
        self.assertEqual(result["contract"], "mubin-private-retrieval-v0.1")
        self.assertEqual(result["reference"], "2:1")
        self.assertEqual(result["research_mode"], "metadata_only")
        self.assertEqual(len(result["sources"]), 11)
        for s in result["sources"]:
            self.assertTrue(s["coordinate_present"])
            self.assertFalse(s["text_included"])
            self.assertFalse(s["edition_verified"])
            self.assertEqual(s["rights_status"], "legal_review_pending")
            self.assertFalse(s["scholarly_verified"])
            self.assertFalse(s["p1_admitted"])
        self.assertEqual(result["evidence_head_sha256"], HEAD)
        self.assertFalse(result["text_included"])
        self.assertFalse(result["juristic_inference_allowed"])
        self.assertFalse(result["public_fatwa_authorized"])
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["source_authenticated"])

    def test_text_mode_denied_without_trusted_issuer(self):
        from engines.quran.research.unified import unified_lookup
        # Default upstream state: no trusted permit issuer is pinned, so the
        # R0.1b permit check must refuse before any private text is served.
        with self.assertRaises(ResearchAdapterError) as ctx:
            self.lookup(include_text=True)
        self.assertIn("PERMIT", ctx.exception.code)

    def test_text_mode_with_trusted_issuer_stays_restricted(self):
        import hashlib
        from engines.quran.research import private_adapters
        from engines.quran.research.unified import unified_lookup
        key = b"test-only-independent-approver-key-0001"
        signing = patch.object(private_adapters, "TRUSTED_PERMIT_SIGNER_SHA256",
                               hashlib.sha256(key).hexdigest())
        signing.start()
        self.addCleanup(signing.stop)
        from datetime import datetime, timedelta, timezone
        payload = {
            "contract": private_adapters.PERMIT_CONTRACT,
            "evidence_head_sha256": HEAD,
            "source_ids": [s["source_id"] for s in
                           self.adapters.corpus_sources() + self.adapters.sidecar_sources()],
            "purpose": "restricted_internal_research",
            "expires_utc": (datetime.now(timezone.utc) +
                            timedelta(seconds=600)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "authorization_id": "synthetic-review-0002",
            "text_access_allowed": True,
            "publication_allowed": False,
            "p1_admitted": False,
        }
        import hmac as hmac_mod
        payload["mac"] = hmac_mod.new(key, ev._canonical(payload),
                                      hashlib.sha256).hexdigest()
        permit = self.root / "signed-access.json"
        permit.write_bytes(ev._canonical(payload))
        permit_key = self.root / "signing-key.bin"
        permit_key.write_bytes(key)
        scoped = PrivateResearchAdapters(
            vault=self.vault, corpus_db=self.corpus, sidecar_db=self.sidecar,
            registry=self.registry, anchor_dir=self.anchor,
            evidence_key=self.evidence_key,
            permit_path=permit, permit_key=permit_key)
        result = unified_lookup(scoped, "2:1", include_text=True)
        self.assertEqual(result["research_mode"], "restricted_local_text")
        self.assertTrue(result["text_included"])
        for s in result["sources"]:
            self.assertTrue(s["text_included"])
            self.assertIn("text", s)
            self.assertTrue(s.get("restricted_local_use_only"))
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["juristic_inference_allowed"])

    def test_text_mode_permit_scope_excludes_source(self):
        import hashlib
        from engines.quran.research import private_adapters
        key = b"test-only-independent-approver-key-0002"
        signing = patch.object(private_adapters, "TRUSTED_PERMIT_SIGNER_SHA256",
                               hashlib.sha256(key).hexdigest())
        signing.start()
        self.addCleanup(signing.stop)
        from datetime import datetime, timedelta, timezone
        payload = {
            "contract": private_adapters.PERMIT_CONTRACT,
            "evidence_head_sha256": HEAD,
            "source_ids": ["qe_ar_muyassar"],
            "purpose": "restricted_internal_research",
            "expires_utc": (datetime.now(timezone.utc) +
                            timedelta(seconds=600)).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "authorization_id": "synthetic-review-0003",
            "text_access_allowed": True,
            "publication_allowed": False,
            "p1_admitted": False,
        }
        import hmac as hmac_mod
        payload["mac"] = hmac_mod.new(key, ev._canonical(payload),
                                      hashlib.sha256).hexdigest()
        permit = self.root / "signed-scoped.json"
        permit.write_bytes(ev._canonical(payload))
        permit_key = self.root / "signing-key2.bin"
        permit_key.write_bytes(key)
        scoped = PrivateResearchAdapters(
            vault=self.vault, corpus_db=self.corpus, sidecar_db=self.sidecar,
            registry=self.registry, anchor_dir=self.anchor,
            evidence_key=self.evidence_key,
            permit_path=permit, permit_key=permit_key)
        with self.assertRaises(ResearchAdapterError) as ctx:
            unified_lookup(scoped, "2:1", include_text=True)
        self.assertIn("SCOPE", ctx.exception.code)

    def test_invalid_reference_refused(self):
        for ref in ("2:0", "115:1", "abc", "2:999999"):
            with self.assertRaises(ResearchAdapterError):
                unified_lookup(self.adapters, ref)

    def test_adapter_filter_limits_sources(self):
        result = self.lookup(adapter_filter="corpus")
        self.assertEqual(len(result["sources"]), 5)
        result = self.lookup(adapter_filter="sidecar")
        self.assertEqual(len(result["sources"]), 6)

    def test_evidence_failure_passthrough(self):
        with patch("engines.quran.research.private_adapters.evidence.verify_evidence",
                   side_effect=ev.EvidenceError("HEAD_ANCHOR_MAC_INVALID")):
            with self.assertRaises(ResearchAdapterError) as ctx:
                self.lookup()
        self.assertEqual(ctx.exception.code, "EVIDENCE_VERIFICATION_FAILED")

    def test_evidence_head_changes_during_aggregation_refused(self):
        from engines.quran.research.unified import UnifiedRetrievalError
        with patch.object(self.adapters, "evidence_head",
                          side_effect=[HEAD, "c"*64]) as head:
            with self.assertRaisesRegex(
                    UnifiedRetrievalError, "EVIDENCE_HEAD_CHANGED_DURING_LOOKUP"):
                self.lookup()
            self.assertEqual(2,head.call_count)

    def test_unified_response_explicit_nonpromotion_flags(self):
        result=self.lookup()
        for obj in [result,*result["sources"]]:
            self.assertFalse(obj["source_authenticated"])
            self.assertFalse(obj["edition_verified"])
            self.assertFalse(obj["rights_verified"])
            self.assertFalse(obj["publication_allowed"])
            self.assertFalse(obj["redistribution_approved"])
            self.assertFalse(obj["p1_admitted"])
            self.assertFalse(obj["juristic_inference_allowed"])
            self.assertFalse(obj["public_fatwa_authorized"])
            self.assertEqual("legal_review_pending",obj["rights_status"])

    def test_cli_refusal_stable_json_with_no_text_or_traceback(self):
        import contextlib
        import io
        from engines.quran.research.unified import main
        out=io.StringIO()
        with patch("engines.quran.research.unified.unified_lookup",
                   side_effect=ResearchAdapterError("EVIDENCE_VERIFICATION_FAILED")):
            with contextlib.redirect_stdout(out):
                exit_code=main([
                    "lookup","--ref","2:1","--vault",str(self.vault),
                    "--corpus-db",str(self.corpus),"--sidecar-db",str(self.sidecar),
                    "--registry",str(self.registry),"--anchor-dir",str(self.anchor),
                    "--evidence-key",str(self.evidence_key)])
        self.assertEqual(1,exit_code)
        result=json.loads(out.getvalue())
        self.assertEqual("REFUSED",result["status"])
        self.assertEqual("EVIDENCE_VERIFICATION_FAILED",result["reason_code"])
        self.assertFalse(result["text_included"])
        self.assertNotIn(str(self.vault),out.getvalue())
        self.assertNotIn(FIXTURE_TAFSIR,out.getvalue())

    def test_deterministic_report_bytes(self):
        a = json.dumps(self.lookup(), ensure_ascii=False, sort_keys=True)
        b = json.dumps(self.lookup(), ensure_ascii=False, sort_keys=True)
        self.assertEqual(a, b)


from engines.quran.research.unified import unified_lookup

if __name__ == "__main__":
    unittest.main()
