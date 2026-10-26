"""E2E-01.3: synthetic end-to-end HTTP/RTL tests for existing workspace.

Only local SQLite placeholders and HMAC test fixtures; no real verse text or
operator vault is used. The exercise goes through actual workspace routing,
operator_lookup, qualification signatures and the al-Waraqat pilot.
"""
from __future__ import annotations

import gc
import json
from pathlib import Path
import sqlite3
import threading
import unittest
from unittest.mock import patch

from core.tests import test_e2e_research_slice as e2e_fixtures
from core.tests import test_semantic_linkage as linkage_fixtures
from core.tests import test_quran_operator_workspace_i01b as workspace_fixture
from core.tests import test_quran_pinned_workspace_i01c1 as pinned_fixtures
from engines.quran.research.workspace import (
    build_workspace_server, load_research_observation, WorkspaceError,
)
from qa import private_evidence_v01 as ev


class ResearchWorkspaceTests(unittest.TestCase):
    _get = workspace_fixture.WorkspaceTests._get

    def setUp(self):
        e2e_fixtures.E2EResearchSliceTests.setUp(self)
        # On Windows SQLite URI=immutable read handles referenced by exception
        # traceback cycles from intentionally refused HTTP requests may survive
        # until GC. Collect AFTER all server cleanups and BEFORE tmp cleanup.
        self.addCleanup(gc.collect)
        # The baseline E2E fixture already shuts down its unused HTTP server.
        with sqlite3.connect(self.corpus) as db:
            db.execute("""INSERT INTO corpus_entries
                SELECT source_id, 2, 43, source_kind, text, footnotes
                FROM corpus_entries WHERE sura=2 AND aya=1""")
        with sqlite3.connect(self.sidecar) as db:
            for table in ("tafsir_tabary", "tafsir_katheer",
                          "tafsir_baghawy", "tafsir_saadi", "tafsir_moyassar"):
                db.execute(f'INSERT INTO "{table}" SELECT 2,43,tafsir '
                           f'FROM "{table}" WHERE sura=2 AND aya=1')
            db.execute('INSERT INTO "QuranTafseer" '
                       'SELECT 2,43,Mukhtasarar FROM "QuranTafseer" '
                       'WHERE surahNo=2 AND ayahNo=1')
        self._start_server(None)

    def _start_server(self, observation):
        if getattr(self, "_research_server_running", False):
            self.server.shutdown()
            self.server.server_close()
        self.server = build_workspace_server(
            vault=self.vault, corpus_db=self.corpus, sidecar_db=self.sidecar,
            registry=self.registry, anchor_dir=self.anchor,
            evidence_key=self.evidence_key,
            qualification_ledger=self.qual_ledger,
            qualification_anchor_dir=self.qual_anchor,
            qualification_key=self.qual_key,
            linkage_observation=observation, port=0)
        self.host, self.port = self.server.server_address[:2]
        # ThreadingHTTPServer defaults to daemon worker threads; on Windows
        # an in-flight immutable SQLite connection can outlive tempfile
        # cleanup. Track non-daemon request threads so server_close joins them
        # BEFORE the temporary databases are removed.
        self.server.daemon_threads = False
        # Each _start_server creates distinct cleanup closures: leaving the
        # prior server closed is harmless (shutdown is idempotent).
        srv = self.server
        self.addCleanup(srv.server_close)
        self.addCleanup(srv.shutdown)
        t = threading.Thread(target=srv.serve_forever, daemon=True)
        t.start()
        self._research_server_running = True

    def test_complete_arabic_research_html_real_synthetic_adapters(self):
        status, headers, html = self._get("/research?ref=2:43")
        self.assertEqual(status, 200)
        self.assertEqual(headers["Cache-Control"], "no-store")
        self.assertIn(b'text/html', headers["Content-Type"].encode())
        text = html.decode("utf-8")
        self.assertIn('dir="rtl"', text)
        self.assertIn("UNASSESSED", text)
        self.assertIn("باب الأمر", text)
        self.assertIn("مصادر القرآن والتفسير", text)
        self.assertNotIn(workspace_fixture.PLACEHOLDER, text)
        self.assertNotIn("synthetic-footnote-only", text)
        self.assertNotIn(str(self.evidence_key), text)

    def test_existing_home_has_same_workspace_research_link(self):
        status, _, raw = self._get("/")
        self.assertEqual(status, 200)
        self.assertIn(b"/research?ref=2:43", raw)
        self.assertIn(b"dir=\"rtl\"", raw)

    def test_read_only_research_json_exposes_scientific_limits(self):
        status, headers, raw = self._get("/api/research?ref=2:43")
        self.assertEqual(status, 200)
        obj = json.loads(raw)
        self.assertEqual(obj["contract"], "mubin-e2e-research-v0.1")
        self.assertEqual(len(obj["quran_retrieval"]["sources"]), 11)
        self.assertEqual(len(obj["usul_analysis"]["cases"]), 4)
        self.assertEqual(obj["research_linkage"]["status"], "UNASSESSED")
        self.assertFalse(obj["limits"]["text_included"])
        self.assertFalse(obj["limits"]["publication_allowed"])
        self.assertFalse(obj["limits"]["juristic_inference_allowed"])
        self.assertFalse(obj["limits"]["public_fatwa_authorized"])
        self.assertNotIn(workspace_fixture.PLACEHOLDER.encode(), raw)

    def test_proposed_observation_rendered_but_never_certified(self):
        obs = linkage_fixtures.example()
        self._start_server(obs)
        status, _, raw = self._get("/api/research?ref=2:43")
        self.assertEqual(status, 200)
        obj = json.loads(raw)
        self.assertEqual(obj["research_linkage"]["status"], "PROPOSED_NOT_CERTIFIED")
        self.assertTrue(obj["research_linkage"]["evidence_head_bound_to_qualified_retrieval"])
        self.assertFalse(obj["research_linkage"]["verse_text_byte_match_independently_verified"])
        status, _, html = self._get("/research?ref=2:43")
        self.assertEqual(status, 200)
        rendered = html.decode("utf-8")
        self.assertIn("أَقِيمُوا", rendered)
        self.assertIn("PROPOSED_NOT_CERTIFIED", rendered)
        self.assertIn("عدم رصد القرينة", rendered)

    def test_operator_supplied_markup_is_escaped(self):
        obs = linkage_fixtures.example(
            imperative_position='<img src=x onerror=alert(1)>')
        self._start_server(obs)
        status, _, body = self._get("/research?ref=2:43")
        self.assertEqual(status, 200)
        html = body.decode("utf-8")
        self.assertIn("&lt;img src=x onerror=alert(1)&gt;", html)
        self.assertNotIn('<img src=x onerror=alert(1)>', html)
        self.assertIn("default-src 'none'",
                      self._get("/research?ref=2:43")[1]["Content-Security-Policy"])

    def test_unrelated_reference_does_not_receive_falsely_bound_proposal(self):
        self._start_server(linkage_fixtures.example())
        status, _, raw = self._get("/api/research?ref=2:1")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(raw)["research_linkage"]["status"],
                         "UNASSESSED")

    def test_invalid_and_duplicate_queries_refused_without_echoing(self):
        for q in ("ref=2:999", "ref=2:43&ref=2:1", "ref=2:43&bad=1"):
            with self.subTest(q=q):
                status, _, raw = self._get("/api/research?" + q)
                self.assertIn(status, (400, 409))
                self.assertNotIn(workspace_fixture.PLACEHOLDER.encode(), raw)

    def test_cross_origin_and_outside_route_rejected(self):
        status, _, _ = self._get(
            "/api/research?ref=2:43", origin="http://evil.example")
        self.assertEqual(status, 403)
        status, _, _ = self._get("/api/private-text")
        self.assertEqual(status, 404)

    def test_damaged_qualification_ledger_refuses_both_surfaces(self):
        self.qual_ledger.write_bytes(b"unsigned-attack")
        for path in ("/research?ref=2:43", "/api/research?ref=2:43"):
            status, _, data = self._get(path)
            self.assertEqual(status, 409)
            self.assertNotIn(workspace_fixture.PLACEHOLDER.encode(), data)

    def test_operator_observation_file_bounded_and_local(self):
        path = self.root / "operator-observation.json"
        path.write_text(json.dumps(linkage_fixtures.example(),
                                   ensure_ascii=False), encoding="utf-8")
        loaded = load_research_observation(path, vault=self.vault)
        self.assertEqual(loaded["verse_ref"], "2:43")
        path.write_bytes(b"{" + b"x" * 8193)
        with self.assertRaisesRegex(
                WorkspaceError, "RESEARCH_OBSERVATION_FILE_REFUSED"):
            load_research_observation(path, vault=self.vault)
        path.write_text(json.dumps({"invalid": True}), encoding="utf-8")
        with self.assertRaisesRegex(
                WorkspaceError, "RESEARCH_OBSERVATION_FILE_REFUSED"):
            load_research_observation(path, vault=self.vault)


class PinnedResearchRouteTests(unittest.TestCase):
    _get = pinned_fixtures.PinnedWorkspaceTests._get
    qual_initialize = workspace_fixture.WorkspaceTests.qual_initialize

    def setUp(self):
        pinned_fixtures.PinnedWorkspaceTests.setUp(self)

    def test_pinned_research_keeps_no_bulk_hash_per_request(self):
        self.qual_initialize()
        with patch.object(ev, "_sha_file", side_effect=AssertionError("hash")):
            status, _, body = self._get("/api/research?ref=2:1")
        self.assertEqual(status, 200)
        data = json.loads(body)
        self.assertEqual(data["research_linkage"]["status"], "UNASSESSED")
        self.assertFalse(data["limits"]["public_fatwa_authorized"])


if __name__ == "__main__":
    unittest.main()
