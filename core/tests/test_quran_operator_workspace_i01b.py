"""I0.1b operator workspace: synthetic security and contract tests.

Loopback-only HTTP tests over a synthetic vault. No real vault, keys,
permits or scripture content. ASCII placeholders only.
"""
from __future__ import annotations

import hashlib
from http import client as httpclient
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch
import urllib.request

from engines.quran.research.workspace import build_workspace_server
from engines.quran.research import qualification as qual
from engines.quran.research import private_adapters
from qa import private_evidence_v01 as ev
from qa.corpus_ingest_v01 import load_manifest

PLACEHOLDER = "synthetic-placeholder-not-scripture"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class WorkspaceTests(unittest.TestCase):
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
        self.qual_ledger = self.root / "qualification-ledger.jsonl"
        self.qual_anchor = self.root / "qualification-anchors"
        self.qual_key = self.root / "operator-qualification.key"
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
                    (source["id"],2,1,source["kind"],PLACEHOLDER,
                     "synthetic-footnote-only"))
            db.commit()
        finally:
            db.close()
        conn = sqlite3.connect(self.sidecar)
        try:
            for table in ("tafsir_tabary","tafsir_katheer","tafsir_baghawy",
                          "tafsir_saadi","tafsir_moyassar"):
                conn.execute(f'CREATE TABLE "{table}" (sura INTEGER,aya INTEGER,tafsir TEXT)')
                conn.execute(f'INSERT INTO "{table}" VALUES (2,1,?)',(PLACEHOLDER,))
            conn.execute('CREATE TABLE "QuranTafseer" (surahNo INTEGER,ayahNo INTEGER,Mukhtasarar TEXT)')
            conn.execute('INSERT INTO "QuranTafseer" VALUES (2,1,?)',(PLACEHOLDER,))
            conn.commit()
        finally:
            conn.close()
        report = {"status": "EVIDENCE_REGISTRY_VERIFIED",
                  "byte_integrity_verified": True, "head_entry_sha256": "b" * 64,
                  "rights_status": "legal_review_pending",
                  "source_authenticated": False, "scholarly_verified": False,
                  "text_included": False}
        p = patch("engines.quran.research.private_adapters.evidence.verify_evidence",
                  return_value=report)
        self.mock_evidence = p.start()
        self.addCleanup(p.stop)
        self.server = build_workspace_server(
            vault=self.vault, corpus_db=self.corpus, sidecar_db=self.sidecar,
            registry=self.registry, anchor_dir=self.anchor,
            evidence_key=self.evidence_key,
            qualification_ledger=self.qual_ledger,
            qualification_anchor_dir=self.qual_anchor,
            qualification_key=self.qual_key, port=0)
        self.host, self.port = self.server.server_address[:2]
        self.base = f"http://127.0.0.1:{self.port}"
        thread = __import__("threading").Thread(
            target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.shutdown)
        self.addCleanup(self.server.server_close)

    def _get(self, path, *, host=None, origin=None, fetch_site=None):
        conn = httpclient.HTTPConnection("127.0.0.1", self.port, timeout=10)
        headers = {}
        if host is not None:
            headers["Host"] = host
        if origin is not None:
            headers["Origin"] = origin
        if fetch_site is not None:
            headers["Sec-Fetch-Site"] = fetch_site
        conn.request("GET", path, headers=headers)
        response = conn.getresponse()
        body = response.read()
        conn.close()
        return response.status, dict(response.getheaders()), body

    def test_workspace_page_is_rtl_metadata_only_with_security_headers(self):
        status, headers, body = self._get("/")
        self.assertEqual(status, 200)
        text = body.decode("utf-8")
        self.assertIn('dir="rtl"', text)
        self.assertIn('lang="ar"', text)
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
        # no operator key or vault path ever appears
        self.assertNotIn(str(self.evidence_key), text)
        self.assertNotIn(str(self.vault), text)
        self.assertNotIn(str(self.qual_key), text)

    def test_states_endpoint_lists_pending_states_without_text(self):
        status, _, body = self._get("/api/states")
        self.assertEqual(status, 200)
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(payload["contract"], "mubin-operator-workspace-v0.1")
        ids = {s["source_id"] for s in payload["sources"]}
        self.assertIn("qe_ar_muyassar", ids)
        self.assertIn("tafsir_tabary", ids)
        for s in payload["sources"]:
            self.assertEqual(s["rights_decision_state"], "legal_review_pending")
        self.assertFalse(payload["text_included"])
        self.assertFalse(payload["publication_allowed"])
        self.assertFalse(payload["juristic_inference_allowed"])
        self.assertFalse(payload["public_fatwa_authorized"])

    def test_lookup_metadata_only_lists_all_sources(self):
        self.qual_initialize()
        status, _, body = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 200)
        payload = json.loads(body.decode("utf-8"))
        # /api/lookup serves the I0.1a operator contract on this workspace
        self.assertEqual(payload["contract"],
                         "mubin-operator-qualified-retrieval-v0.1")
        self.assertEqual(payload["research_mode"], "metadata_only")
        self.assertEqual(len(payload["sources"]), 11)
        for s in payload["sources"]:
            self.assertTrue(s["coordinate_present"])
            self.assertFalse(s["text_included"])
        raw = body.decode("utf-8")
        self.assertNotIn(PLACEHOLDER, raw)

    def qual_initialize(self):
        from engines.quran.research.qualification import initialize_ledger
        initialize_ledger(
            self.qual_ledger, self.qual_anchor, self.qual_key,
            vault=self.vault,
            evidence_registry=self.registry,
            evidence_anchor_dir=self.anchor,
            evidence_key=self.evidence_key,
            sidecar_db=self.sidecar, operator="lead-operator")

    def _record(self, decision_type, *, axis="scholarly", scope=None):
        from datetime import datetime, timezone
        scope = scope if scope is not None else {"full_source": True}
        record = {
            "decision_id": "synthetic-" + decision_type.lower().replace("_", "-"),
            "axis": axis, "source_id": "qe_ar_muyassar",
            "scope": scope, "decision": decision_type,
            "reviewer": "independent-human-reviewer",
            "reviewed_at_utc": datetime.now(timezone.utc).strftime(
                "%Y-%m-%dT%H:%M:%SZ"),
            "evidence_head_sha256": self.mock_evidence.return_value[
                "head_entry_sha256"],
            "notes": "synthetic-only local fixture",
        }
        qual.append_decision(
            self.qual_ledger, self.qual_anchor, self.qual_key,
            record, "lead-operator", evidence_registry=self.registry,
            evidence_anchor_dir=self.anchor,
            evidence_key=self.evidence_key, vault=self.vault,
            sidecar_db=self.sidecar)

    def _state(self, source_id="qe_ar_muyassar"):
        status, _, body = self._get("/api/states")
        result = json.loads(body)
        return status, result, next((
            row for row in result.get("sources", [])
            if row["source_id"] == source_id), None)

    def test_never_treat_unpaired_initialized_ledger_as_uninitialized(self):
        self.qual_initialize()
        self.qual_ledger.write_bytes(b"")  # continuity exists; no decision file pair
        for path in ("/", "/api/states"):
            status, _, body = self._get(path)
            self.assertEqual(status, 409)
            self.assertIn(b"LEDGER_UNPAIRED_OR_EMPTY", body)
            self.assertNotIn(str(self.qual_ledger).encode(), body)

    def test_stale_positive_status_never_promotes(self):
        self.qual_initialize()
        self._record("SOURCE_TEXT_INTEGRITY_REVIEWED")
        status, payload, row = self._state()
        self.assertEqual(status, 200)
        self.assertEqual(row["scholarly_decision_state"],
                         "SOURCE_TEXT_INTEGRITY_REVIEWED")
        self.assertEqual(row["matching_evidence_decisions"], 1)
        self.mock_evidence.return_value["head_entry_sha256"] = "c" * 64
        status, payload, row = self._state()
        self.assertEqual(status, 200)
        self.assertEqual(row["scholarly_decision_state"], "UNREVIEWED")
        self.assertEqual(row["matching_evidence_decisions"], 0)
        self.assertTrue(row["historical_evidence_decisions_present"])
        self.assertFalse(payload["scholarly_verified"])
        self.assertFalse(payload["publication_allowed"])

    def test_historical_rejection_is_sticky_and_quarantines_stay_scoped(self):
        self.qual_initialize()
        self._record("SOURCE_REJECTED")
        self.mock_evidence.return_value["head_entry_sha256"] = "c" * 64
        status, _, row = self._state()
        self.assertEqual(status, 200)
        self.assertEqual(row["scholarly_decision_state"], "SOURCE_REJECTED")
        self.assertTrue(row["historical_evidence_decisions_present"])

    def test_record_quarantine_not_misrepresented_as_source_wide(self):
        self.qual_initialize()
        self._record("RECORD_QUARANTINED",
                     scope={"record_coordinates": ["2:1"]})
        status, _, row = self._state()
        self.assertEqual(status, 200)
        self.assertEqual(row["scholarly_decision_state"], "UNREVIEWED")
        self.assertTrue(row["record_quarantines_present"])
        status, _, body = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 200)
        source = next(s for s in json.loads(body)["sources"]
                      if s["source_id"] == "qe_ar_muyassar")
        self.assertEqual(source["scholarly_decision_state"], "RECORD_QUARANTINED")

    def test_evidence_head_changed_during_state_snapshot_refused(self):
        before = dict(self.mock_evidence.return_value)
        after = dict(before, head_entry_sha256="c" * 64)
        self.mock_evidence.side_effect = [before, after]
        status, _, body = self._get("/api/states")
        self.assertEqual(status, 409)
        self.assertIn(b"evidence_head_changed_during_lookup", body)

    def test_query_not_accepted_on_static_routes(self):
        for path in ("/?unexpected=1", "/api/states?ref=2:1"):
            status, _, body = self._get(path)
            self.assertEqual(status, 400)
            self.assertIn(b"invalid_query", body)

    def test_invalid_host_refused(self):
        status, _, body = self._get("/", host="evil.example.com:1")
        self.assertEqual(status, 403)
        self.assertIn(b"invalid_host", body)

    def test_cross_origin_refused(self):
        status, _, body = self._get("/api/states",
                                    origin="http://evil.example.com")
        self.assertEqual(status, 403)
        self.assertIn(b"cross_origin_rejected", body)

    def test_cross_site_fetch_refused(self):
        status, _, body = self._get("/api/states", fetch_site="cross-site")
        self.assertEqual(status, 403)
        self.assertIn(b"cross_site_rejected", body)

    def test_xss_reference_not_reflected(self):
        self.qual_initialize()
        status, _, body = self._get(
            "/api/lookup?ref=2:1%3Cscript%3Ealert(1)%3C/script%3E")
        # The payload must be refused (400 invalid query or 409 invalid
        # reference) and never reflected into the response body.
        self.assertIn(status, (400, 409))
        self.assertNotIn(b"<script>", body)

    def test_unknown_route_not_found(self):
        status, _, body = self._get("/api/private-text")
        self.assertEqual(status, 404)
        self.assertIn(b"route_not_found", body)

    def test_post_not_supported(self):
        conn = httpclient.HTTPConnection("127.0.0.1", self.port, timeout=10)
        conn.request("POST", "/api/states", body=b"{}")
        response = conn.getresponse()
        response.read()
        conn.close()
        self.assertNotEqual(response.status, 200)
        self.assertIn(response.status, (404, 405, 501))


from engines.quran.research.workspace import build_workspace_server

if __name__ == "__main__":
    unittest.main()
