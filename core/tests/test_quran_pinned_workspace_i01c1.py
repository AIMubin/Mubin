"""I0.1c.1 synthetic-only HTTP integration/security tests for pinned sessions.

Exercises the real Snapshot resolver and SQLite adapters while stubbing ONLY
the expensive original-vault verifier. A real hash-chain and HMAC evidence
anchor are created in the isolated temp folder. No private Quran/tafsir data.
"""
from __future__ import annotations

import hashlib
import hmac
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

from core.tests import test_quran_operator_workspace_i01b as workspace_fixtures
from engines.quran.research.workspace import build_workspace_server
from qa import private_evidence_v01 as ev
from qa import tafsircenter_sidecar_v01 as sidecar_mod
from qa.corpus_snapshot_v01 import publish_snapshot, resolve_current_snapshot


def _digest(data: bytes):
    return hashlib.sha256(data).hexdigest()


class PinnedWorkspaceTests(unittest.TestCase):
    _get = workspace_fixtures.WorkspaceTests._get
    qual_initialize = workspace_fixtures.WorkspaceTests.qual_initialize

    def setUp(self):
        # Reuse the canonical synthetic metadata-schema fixture without
        # subclassing/rerunning I0.1b's separate behavioral test suite.
        workspace_fixtures.WorkspaceTests.setUp(self)
        self.server.shutdown()
        self.server.server_close()
        receipt = self.vault / ev.RECEIPT_NAME
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_bytes(b"synthetic-evidence-campaign-receipt")
        sidecar_sha = _digest(self.sidecar.read_bytes())
        pin = patch.object(sidecar_mod, "EXPECTED_SHA256", sidecar_sha)
        pin.start()
        self.addCleanup(pin.stop)
        published = publish_snapshot(
            self.vault, self.corpus, self.sidecar,
            campaign_receipt_sha256=_digest(receipt.read_bytes()))
        self.initial_revision = published["revision_id"]

        payload = {
            "corpus_database_sha256": _digest(self.corpus.read_bytes()),
            "sidecar_source_sha256": sidecar_sha,
            "campaign_receipt_sha256": _digest(receipt.read_bytes()),
            "source_authenticated": False, "rights_status": "legal_review_pending",
            "rights_verified": False, "scholarly_verified": False,
            "p1_admitted": False, "juristic_inference_allowed": False,
            "public_fatwa_authorized": False, "text_included": False,
        }
        raw = {
            "seq": 1, "prev_entry_sha256": "0" * 64,
            "operator": "synthetic-operator",
            "recorded_at_utc": "2026-10-26T00:00:00+00:00",
            "payload": payload,
        }
        head = _digest(ev._canonical(raw))
        self.registry.write_bytes(ev._canonical(
            {**raw, "entry_sha256": head}) + b"\n")
        self.anchor.mkdir(parents=True, exist_ok=True)
        self.evidence_key.write_bytes(b"test-only-evidence-hmac-key-not-real-0123456789")
        anchor = {"registry": self.registry.name,
                  "head_entry_sha256": head, "sequence": 1}
        anchor["head_hmac"] = hmac.new(
            self.evidence_key.read_bytes(), ev._canonical(anchor),
            hashlib.sha256).hexdigest()
        (self.anchor / (self.registry.stem + "." + ev.ANCHOR_NAME)).write_bytes(
            ev._canonical(anchor) + b"\n")
        self.mock_evidence.return_value["head_entry_sha256"] = head

        self.server = build_workspace_server(
            vault=self.vault, corpus_db=self.corpus, sidecar_db=self.sidecar,
            registry=self.registry, anchor_dir=self.anchor,
            evidence_key=self.evidence_key,
            qualification_ledger=self.qual_ledger,
            qualification_anchor_dir=self.qual_anchor,
            qualification_key=self.qual_key,
            pinned_snapshot=True, port=0)
        self.host, self.port = self.server.server_address[:2]
        self.base = f"http://127.0.0.1:{self.port}"
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def test_true_loopback_http_lookup_uses_snapshot_without_rehash(self):
        self.qual_initialize()
        self.mock_evidence.reset_mock()
        # Neither full original-vault verifier nor either bulk SHA routine may
        # be invoked on ANY of the steady-state HTTP lookup calls.
        with patch.object(ev, "_sha_file", side_effect=AssertionError("full hash")), \
             patch("qa.corpus_snapshot_v01._sha_file",
                   side_effect=AssertionError("snapshot rehash")):
            for _ in range(5):
                status, headers, raw = self._get("/api/lookup?ref=2:1")
                self.assertEqual(status, 200)
                self.assertIn("no-store", headers["Cache-Control"])
                payload = json.loads(raw)
                self.assertEqual(len(payload["sources"]), 11)
                self.assertFalse(payload["text_included"])
                self.assertFalse(payload["publication_allowed"])
                self.assertFalse(payload["public_fatwa_authorized"])
                self.assertNotIn(workspace_fixtures.PLACEHOLDER, raw.decode("utf-8"))
        self.mock_evidence.assert_not_called()

    def test_signed_states_endpoint_still_works_without_rehash(self):
        self.qual_initialize()
        with patch.object(ev, "_sha_file", side_effect=AssertionError("hash")):
            status, _, raw = self._get("/api/states")
        self.assertEqual(status, 200)
        payload = json.loads(raw)
        self.assertEqual(payload["ledger_state"], "initialized")
        self.assertEqual(payload["qualification_decisions"], 0)
        self.assertFalse(payload["juristic_inference_allowed"])

    def test_p2_snapshot_modified_after_full_hash_before_session_pin_refused(self):
        # Codex P2 reproduction: publish/resolve already checked SHA-256,
        # then mutate the snapshot BEFORE the session records its baseline.
        from engines.quran.research.pinned_session import (
            PinnedSnapshotSession, PinnedSessionError)
        real_resolve = resolve_current_snapshot

        def mutate_after_resolver(vault):
            checked = real_resolve(vault)
            path = checked["corpus_db"]
            path.chmod(0o600)
            with path.open("ab") as stream:
                stream.write(b"undetected-under-old-post-verification-baseline")
            return checked

        with patch(
            "engines.quran.research.pinned_session.resolve_current_snapshot",
            side_effect=mutate_after_resolver):
            with self.assertRaisesRegex(
                    PinnedSessionError, "PINNED_FILES_CHANGED_DURING_STARTUP"):
                PinnedSnapshotSession(
                    vault=self.vault, corpus_db=self.corpus,
                    sidecar_db=self.sidecar, registry=self.registry,
                    anchor_dir=self.anchor, evidence_key=self.evidence_key)

    def test_original_changed_after_full_verification_before_pin_refused(self):
        # A legitimate snapshot still exists; the original sidecar bytes
        # changed between its full original verification and the session pin.
        from engines.quran.research.pinned_session import (
            PinnedSnapshotSession, PinnedSessionError)
        real_resolve = resolve_current_snapshot

        def mutate_original_after_verification(vault):
            checked = real_resolve(vault)
            with self.sidecar.open("ab") as stream:
                stream.write(b"changed-after-original-verification")
            return checked

        with patch(
            "engines.quran.research.pinned_session.resolve_current_snapshot",
            side_effect=mutate_original_after_verification):
            with self.assertRaisesRegex(
                    PinnedSessionError, "PINNED_FILES_CHANGED_DURING_STARTUP"):
                PinnedSnapshotSession(
                    vault=self.vault, corpus_db=self.corpus,
                    sidecar_db=self.sidecar, registry=self.registry,
                    anchor_dir=self.anchor, evidence_key=self.evidence_key)

    def test_latest_pointer_moves_during_initialization_refused(self):
        # Switching LATEST after startup is allowed; moving it DURING the
        # verification that establishes the first trusted pin is not.
        from engines.quran.research.pinned_session import (
            PinnedSnapshotSession, PinnedSessionError)
        real_resolve = resolve_current_snapshot

        def publish_b_after_verification(vault):
            checked = real_resolve(vault)
            other = self.root / "other-corpus.sqlite3"
            other.write_bytes(b"synthetic-new-revision-B")
            publish_snapshot(
                self.vault, other, self.sidecar,
                campaign_receipt_sha256=_digest(
                    (self.vault / ev.RECEIPT_NAME).read_bytes()))
            return checked

        with patch(
            "engines.quran.research.pinned_session.resolve_current_snapshot",
            side_effect=publish_b_after_verification):
            with self.assertRaisesRegex(
                    PinnedSessionError, "PINNED_FILES_CHANGED_DURING_STARTUP"):
                PinnedSnapshotSession(
                    vault=self.vault, corpus_db=self.corpus,
                    sidecar_db=self.sidecar, registry=self.registry,
                    anchor_dir=self.anchor, evidence_key=self.evidence_key)

    def test_wrong_campaign_receipt_manifest_refused_at_startup(self):
        # Both snapshot SQLite digests still match signed evidence, but the
        # publisher has supplied an unrelated campaign receipt hash.
        from engines.quran.research.pinned_session import (
            PinnedSnapshotSession, PinnedSessionError)
        publish_snapshot(
            self.vault, self.corpus, self.sidecar,
            campaign_receipt_sha256=_digest(b"unrelated-campaign"))
        with self.assertRaisesRegex(
                PinnedSessionError, "PINNED_EVIDENCE_DIGEST_CHANGED"):
            PinnedSnapshotSession(
                vault=self.vault, corpus_db=self.corpus,
                sidecar_db=self.sidecar, registry=self.registry,
                anchor_dir=self.anchor, evidence_key=self.evidence_key)

    def test_synthetic_full_http_benchmark_emits_p50_p95(self):
        import contextlib
        import io
        from qa.benchmark_pinned_workspace_i01c1 import main as benchmark
        self.qual_initialize()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = benchmark([
                "--origin", self.base,
                "--ref", "2:1", "--warmup", "2", "--samples", "15"])
        self.assertEqual(code, 0)
        data = json.loads(output.getvalue())
        self.assertEqual(data["status"], "HTTP_LOOKUP_BENCHMARK_OK")
        self.assertEqual(data["samples"], 15)
        self.assertLessEqual(data["p50_ms"], data["p95_ms"])
        self.assertLessEqual(data["p95_ms"], data["max_ms"])
        self.assertFalse(data["source_authenticated"])
        self.assertFalse(data["publication_allowed"])
        print("SYNTHETIC_LOOPBACK_HTTP_BENCHMARK " + json.dumps({
            "samples": 15, "p50_ms": data["p50_ms"],
            "p95_ms": data["p95_ms"]}, sort_keys=True))

    def test_original_sidecar_change_fails_closed(self):
        self.qual_initialize()
        with self.sidecar.open("ab") as stream:
            stream.write(b"changed-after-pin")
        status, _, raw = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 409)
        self.assertIn(b"PINNED_FILES_CHANGED", raw)
        self.assertNotIn(workspace_fixtures.PLACEHOLDER.encode(), raw)

    def test_snapshot_byte_mutation_fails_closed(self):
        self.qual_initialize()
        path = resolve_current_snapshot(self.vault)["corpus_db"]
        path.chmod(0o600)
        with path.open("ab") as stream:
            stream.write(b"changed-after-pin")
        status, _, raw = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 409)
        self.assertIn(b"PINNED_FILES_CHANGED", raw)

    def test_forged_evidence_payload_old_head_fails_closed(self):
        self.qual_initialize()
        document = json.loads(self.registry.read_text(encoding="utf-8"))
        document["payload"]["corpus_database_sha256"] = "a" * 64
        self.registry.write_bytes(ev._canonical(document) + b"\n")
        status, _, raw = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 409)
        self.assertIn(b"PINNED_SESSION_VERIFICATION_FAILED", raw)

    def test_new_latest_does_not_silently_repoint_old_session(self):
        self.qual_initialize()
        new = self.root / "corpus-B.sqlite3"
        new.write_bytes(b"synthetic-B-only-not-scripture")
        publish_snapshot(
            self.vault, new, self.sidecar,
            campaign_receipt_sha256=_digest(
                (self.vault / ev.RECEIPT_NAME).read_bytes()))
        current = resolve_current_snapshot(self.vault)
        self.assertNotEqual(current["revision_id"], self.initial_revision)
        # The original attested evidence and pinned A files are unmodified.
        status, _, raw = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 200)
        self.assertEqual(len(json.loads(raw)["sources"]), 11)

    def test_authenticated_new_evidence_head_requires_repin(self):
        self.qual_initialize()
        first = json.loads(self.registry.read_text(encoding="utf-8"))
        next_entry = {
            "seq": 2, "prev_entry_sha256": first["entry_sha256"],
            "operator": "synthetic-operator-2",
            "recorded_at_utc": "2026-10-26T01:00:00+00:00",
            "payload": first["payload"],
        }
        next_head = _digest(ev._canonical(next_entry))
        self.registry.write_bytes(
            ev._canonical(first) + b"\n" +
            ev._canonical({**next_entry, "entry_sha256": next_head}) + b"\n")
        anchor = {"registry": self.registry.name,
                  "head_entry_sha256": next_head, "sequence": 2}
        anchor["head_hmac"] = hmac.new(
            self.evidence_key.read_bytes(), ev._canonical(anchor),
            hashlib.sha256).hexdigest()
        (self.anchor / (self.registry.stem + "." + ev.ANCHOR_NAME)).write_bytes(
            ev._canonical(anchor) + b"\n")
        status, _, raw = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 409)
        self.assertIn(b"PINNED_EVIDENCE_HEAD_CHANGED", raw)

    def test_hmac_anchor_corruption_fails_closed(self):
        self.qual_initialize()
        anchor = self.anchor / (self.registry.stem + "." + ev.ANCHOR_NAME)
        anchor.write_bytes(b'{"tampered":"without-the-hmac-key"}')
        status, _, raw = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 409)
        self.assertIn(b"PINNED_SESSION_VERIFICATION_FAILED", raw)

    def test_qualification_corruption_still_refused(self):
        self.qual_initialize()
        self.qual_ledger.write_bytes(b"")
        status, _, raw = self._get("/api/lookup?ref=2:1")
        self.assertEqual(status, 409)
        self.assertIn(b"LEDGER_UNPAIRED_OR_EMPTY", raw)

    def test_cross_origin_and_private_text_routes_rejected(self):
        self.qual_initialize()
        status, _, _ = self._get("/api/lookup?ref=2:1",
                                 origin="http://evil.example")
        self.assertEqual(status, 403)
        status, _, _ = self._get("/api/private-text")
        self.assertEqual(status, 404)


if __name__ == "__main__":
    unittest.main()
