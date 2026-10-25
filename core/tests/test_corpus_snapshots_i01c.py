"""I0.1c evidence snapshots: immutability, pinning and no-mixing tests."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch
import sqlite3
import tempfile
import unittest

from qa.corpus_snapshot_v01 import (
    SnapshotError, publish_snapshot, resolve_current_snapshot,
)
from qa import private_evidence_v01 as ev


def _sha(data: bytes) -> str:
    import hashlib
    return hashlib.sha256(data).hexdigest()


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.vault = self.root / "vault"
        self.vault.mkdir()
        self.sidecar_bytes = b"SQLite format 3\x00" + b"s" * 512
        self.sidecar_sha = _sha(self.sidecar_bytes)
        self.corpus = self.root / "corpus.sqlite3"
        self.corpus.write_bytes(b"corpus-A-bytes")
        self.sidecar = self.root / "sidecar.db"
        self.sidecar.write_bytes(self.sidecar_bytes)
        self.receipt = _sha(b"campaign-A")
        # Synthetic sidecar: patch the frozen production pin for these tests
        # (the real 223 MB pin stays untouched in production).
        import qa.tafsircenter_sidecar_v01 as sidecar_mod
        pin_patch = patch.object(sidecar_mod, "EXPECTED_SHA256",
                                 self.sidecar_sha)
        pin_patch.start()
        self.addCleanup(pin_patch.stop)

    def publish(self, corpus_bytes=None):
        if corpus_bytes is not None:
            self.corpus.write_bytes(corpus_bytes)
        return publish_snapshot(self.vault, self.corpus, self.sidecar,
                                campaign_receipt_sha256=self.receipt)

    def test_publish_creates_immutable_revision_and_latest(self):
        report = self.publish()
        resolved = resolve_current_snapshot(self.vault)
        self.assertEqual(resolved["revision_id"], report["revision_id"])
        self.assertTrue(resolved["immutable"])
        # no-replace: publishing the SAME files again under a new revision id
        # is allowed (content-addressed), but the old revision dir is intact
        first = self.vault / "snapshots" / report["revision_id"]
        self.assertTrue((first / "corpus.sqlite3").is_file())
        self.assertTrue((first / "sidecar.db").is_file())

    def test_sidecar_pin_mismatch_refused(self):
        self.sidecar.write_bytes(b"SQLite format 3\x00" + b"X" * 512)
        with self.assertRaisesRegex(SnapshotError,
                                    "SNAPSHOT_SIDECAR_PIN_MISMATCH"):
            self.publish()

    def test_mutating_original_after_publish_cannot_change_revision(self):
        report = self.publish()
        revision = self.vault / "snapshots" / report["revision_id"]
        frozen_corpus = (revision / "corpus.sqlite3").read_bytes()
        frozen_sidecar = (revision / "sidecar.db").read_bytes()
        self.corpus.write_bytes(b"corpus-original-changed-after-publish")
        self.sidecar.write_bytes(b"sidecar-original-changed-after-publish")
        self.assertEqual((revision / "corpus.sqlite3").read_bytes(),
                         frozen_corpus)
        self.assertEqual((revision / "sidecar.db").read_bytes(),
                         frozen_sidecar)
        self.assertNotEqual(self.corpus.stat().st_ino,
                            (revision / "corpus.sqlite3").stat().st_ino)
        self.assertEqual(resolve_current_snapshot(self.vault)["revision_id"],
                         report["revision_id"])

    def test_revision_manifest_digest_is_bound_to_latest(self):
        report = self.publish()
        manifest = self.vault / "snapshots" / report["revision_id"] / "revision.json"
        doc = json.loads(manifest.read_text(encoding="utf-8"))
        doc["publication_allowed"] = True
        manifest.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaisesRegex(
                SnapshotError, "SNAPSHOT_MANIFEST_DIGEST_MISMATCH"):
            resolve_current_snapshot(self.vault)

    def test_old_hardlink_revision_is_refused_not_labeled_immutable(self):
        report = self.publish()
        revision = self.vault / "snapshots" / report["revision_id"]
        original = revision / "corpus.sqlite3"
        original.chmod(0o600)  # Windows denies unlink of a read-only file
        original.unlink()
        import os
        os.link(self.corpus, original)
        with self.assertRaisesRegex(
                SnapshotError, "SNAPSHOT_SHARED_INODE_REFUSED"):
            resolve_current_snapshot(self.vault)

    def test_revision_b_published_session_on_a_is_unaffected(self):
        """A session pinned to Revision A completes on A even after B."""
        self.publish()
        resolved_a = resolve_current_snapshot(self.vault)
        corpus_a = resolved_a["corpus_db"].read_bytes()
        # publish Revision B with different corpus bytes (new revision id)
        new_corpus = self.root / "corpus-B.sqlite3"
        new_corpus.write_bytes(b"corpus-B-bytes")
        self.sidecar.write_bytes(self.sidecar_bytes)
        publish_snapshot(self.vault, new_corpus, self.sidecar,
                         campaign_receipt_sha256=self.receipt)
        # session A still reads ITS pinned immutable files, byte-exact,
        # and its revision differs from the newly published latest (B).
        self.assertEqual(resolved_a["corpus_db"].read_bytes(), corpus_a)
        latest = json.loads((self.vault / "LATEST.json").read_text(encoding="utf-8"))
        self.assertNotEqual(resolved_a["revision_id"], latest["revision_id"])

    def test_mixed_revisions_refused(self):
        self.publish()
        resolved = resolve_current_snapshot(self.vault)
        # simulate mixing: corrupt the revision manifest of the pinned rev
        manifest = resolved["vault"] / "snapshots" / resolved["revision_id"] / "revision.json"
        body = json.loads(manifest.read_text(encoding="utf-8"))
        body["corpus_sha256"] = "f" * 64
        manifest.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaisesRegex(SnapshotError,
                                    "SNAPSHOT_CORPUS_DIGEST_MISMATCH|SNAPSHOT_MANIFEST_MISMATCH|SNAPSHOT_MANIFEST_DIGEST_MISMATCH"):
            resolve_current_snapshot(self.vault)


def resolve_latest_revision_before_b(vault):
    import json as jsonlib
    latest = jsonlib.loads((Path(vault) / "LATEST.json").read_text(encoding="utf-8"))
    return latest["revision_id"]


if __name__ == "__main__":
    unittest.main()
