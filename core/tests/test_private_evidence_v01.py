"""Synthetic adversarial tests for the R0.1a private evidence registry.

CI-safe: builds throwaway sqlite fixtures in temp dirs. The real operator
vault is NEVER touched here. Text fixtures use ASCII placeholders, never
Quranic or tafsir content.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

import qa.private_evidence_v01 as ev


SOURCES = 2
VERSES = 3
ENTRIES = SOURCES * VERSES


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":")).encode("utf-8")


def build_vault(base: Path, *, sources=SOURCES, verses=VERSES):
    """Create a synthetic vault: receipt + corpus sqlite + sidecar db."""
    vault = base / "vault"
    vault.mkdir(parents=True, exist_ok=True)
    (vault / "receipts").mkdir(exist_ok=True)

    # corpus db (content is placeholder ASCII, never scripture)
    db = vault / ev.CORPUS_DB_NAME
    con = sqlite3.connect(db)
    con.executescript("""
      CREATE TABLE corpus_sources(source_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL,
        raw_sha256 TEXT NOT NULL);
      CREATE TABLE corpus_entries(source_id TEXT NOT NULL, sura INTEGER NOT NULL,
        aya INTEGER NOT NULL, source_kind TEXT NOT NULL, text TEXT NOT NULL,
        footnotes TEXT NOT NULL, PRIMARY KEY(source_id,sura,aya));
    """)
    per_source = {}
    for i in range(1, sources + 1):
        sid = f"synthetic-source-{i}"
        rows = []
        for a in range(1, verses + 1):
            rows.append((sid, 1, a, "quran" if i == 1 else "tafsir",
                         f"placeholder-{i}-{a}", ""))
        per_source[sid] = {"kind": rows[0][3], "records": verses,
                           "sha256": _sha(f"source-{i}-rows".encode("utf-8"))}
        con.executemany("INSERT INTO corpus_entries VALUES(?,?,?,?,?,?)", rows)
    for i in range(1, sources + 1):
        sid = f"synthetic-source-{i}"
        con.execute("INSERT INTO corpus_sources VALUES(?,?,?)",
                    (sid, "quran" if i == 1 else "tafsir",
                     _sha(f"source-{i}-rows".encode("utf-8"))))
    con.commit()
    con.close()

    receipt = {
        "campaign": "operator-local-private-corpus-import-v01",
        "steps": [{"step": "permanent_private_corpus_import",
                   "records": sources * verses,
                   "sources": [{"id": f"synthetic-source-{i}",
                                "sha256": _sha(f"source-{i}-rows".encode("utf-8")),
                                "verses": verses}
                               for i in range(1, sources + 1)]}],
        "limits": {"scholarly_verified": False},
    }
    (vault / "receipts" / "operator-import-campaign-v01.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    # sidecar db (minimal file; the verifier is patched in these tests)
    sidecar = vault / ev.SIDECAR_DB_NAME
    sidecar.write_bytes(b"SQLite format 3\x00" + b"x" * 512)
    return vault, per_source


class EvidenceRegistryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.vault, self.per_source = build_vault(self.base)
        self.registry = self.base / "registry.jsonl"
        self.anchor_dir = self.base / "anchors"
        self.key_file = self.base / "operator.key"
        self.pins = patch.object(ev, "SIDECAR_PIN", _sha(self.vault.joinpath(ev.SIDECAR_DB_NAME).read_bytes()))
        self.pins.start()
        self.addCleanup(self.pins.stop)
        # The sidecar module has its own dedicated tests; here it is stubbed
        # so the registry/chain/HMAC logic is what is under test.
        stub_report = {"table_counts": {"synthetic_tafsir": VERSES},
                       "tafsir_sources": ["synthetic_tafsir"]}
        self.sidecar_stub = patch.object(ev, "_verify_tafsircenter",
                                         lambda p, deep=True: stub_report)
        self.sidecar_stub.start()
        self.addCleanup(self.sidecar_stub.stop)
        # Scale the record-count expectations to the small synthetic corpus.
        for name, value in (("CORPUS_SOURCES", SOURCES),
                            ("CORPUS_ENTRIES", ENTRIES),
                            ("CORPUS_VERSES_PER_SOURCE", VERSES)):
            p = patch.object(ev, name, value)
            p.start()
            self.addCleanup(p.stop)

    def tearDown(self):
        self._tmp.cleanup()

    @property
    def sidecar(self) -> Path:
        return self.vault / ev.SIDECAR_DB_NAME

    def append(self, *, operator="op1"):
        return ev.append_evidence(self.registry, self.anchor_dir, self.key_file,
                                  self.vault, self.sidecar,
                                  "operator-local-private-corpus-import-v01",
                                  operator)

    def verify(self):
        return ev.verify_evidence(self.registry, self.anchor_dir, self.key_file,
                                  self.vault, self.sidecar)

    def test_binary_key_with_whitespace_end_bytes_remains_verbatim(self):
        import secrets
        binary_key=bytes([10])+b"K"*46+bytes([9])
        with patch.object(secrets, "token_bytes", return_value=binary_key):
            self.append()
        self.assertEqual(binary_key, self.key_file.read_bytes())
        self.append()
        self.assertEqual("EVIDENCE_REGISTRY_VERIFIED", self.verify()["status"])

    def test_append_then_verify_is_clean_and_metadata_only(self):
        out = self.append()
        self.assertEqual(out["status"], "REGISTRY_ENTRY_APPENDED")
        report = self.verify()
        self.assertEqual(report["status"], "EVIDENCE_REGISTRY_VERIFIED")
        self.assertEqual(report["entries"], 1)
        self.assertTrue(report["byte_integrity_verified"])
        self.assertFalse(report["source_authenticated"])
        self.assertEqual(report["rights_status"], "legal_review_pending")
        # metadata-only: no verse-like placeholder text anywhere in registry
        raw = self.registry.read_text(encoding="utf-8")
        self.assertNotIn("placeholder-1-1", raw)

    def test_single_byte_db_tamper_refused(self):
        self.append()
        raw = bytearray(self.vault.joinpath(ev.CORPUS_DB_NAME).read_bytes())
        raw[-3] ^= 0x01
        self.vault.joinpath(ev.CORPUS_DB_NAME).write_bytes(bytes(raw))
        with patch.object(ev, "SIDECAR_PIN",
                          _sha(self.vault.joinpath(ev.SIDECAR_DB_NAME).read_bytes())):
            with self.assertRaisesRegex(ev.EvidenceError, "CORPUS_"):
                self.verify()

    def test_receipt_tamper_refused(self):
        self.append()
        receipt = self.vault / "receipts" / "operator-import-campaign-v01.json"
        body = json.loads(receipt.read_text(encoding="utf-8"))
        body["steps"][0]["records"] = 999
        receipt.write_text(json.dumps(body), encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError, "CAMPAIGN_RECEIPT_INVALID"):
            self.verify()

    def test_registry_midchain_tamper_detected(self):
        self.append()
        self.append()
        lines = self.registry.read_text(encoding="utf-8").splitlines()
        body = json.loads(lines[0])
        body["payload"]["corpus_records"] = 1
        lines[0] = json.dumps(body, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
        self.registry.write_text("\n".join(lines) + "\n", encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError, "REGISTRY_CHAIN_INVALID"):
            self.verify()

    def test_recomputed_chain_cannot_forge_head_anchor(self):
        """The whole chain is recomputed by an attacker WITH the old head:
        the out-of-vault HMAC anchor still refuses the forged head."""
        self.append()
        lines = self.registry.read_text(encoding="utf-8").splitlines()
        body = json.loads(lines[0])
        body["payload"]["corpus_records"] = 42
        payload = {k: v for k, v in body.items() if k != "entry_sha256"}
        forged_sha = _sha(_canonical(payload))
        body["entry_sha256"] = forged_sha
        lines[0] = json.dumps(body, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
        self.registry.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # attacker also rewrites the anchor file body (but lacks the key)
        anchor = self.anchor_dir / (self.registry.stem + "." + ev.ANCHOR_NAME)
        anchor_body = json.loads(anchor.read_text(encoding="utf-8"))
        anchor_body["head_entry_sha256"] = forged_sha
        anchor.write_text(json.dumps(anchor_body, ensure_ascii=False,
                                     sort_keys=True), encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError,
                                    "HEAD_ANCHOR_(MAC_INVALID|HEAD_MISMATCH)"):
            self.verify()

    def test_rehashed_history_refused_on_new_append_before_reanchoring(self):
        """Recomputing a fully consistent chain cannot get a new valid MAC."""
        self.append()
        original_registry = self.registry.read_bytes()
        original_anchor = (self.anchor_dir /
            (self.registry.stem + "." + ev.ANCHOR_NAME)).read_bytes()
        body = json.loads(original_registry.decode("utf-8"))
        body["payload"]["corpus_records"] = 42
        body["entry_sha256"] = _sha(_canonical({
            k:v for k,v in body.items() if k!="entry_sha256"}))
        forged = _canonical(body) + bytes([10])
        self.registry.write_bytes(forged)
        with self.assertRaisesRegex(ev.EvidenceError, "HEAD_ANCHOR_HEAD_MISMATCH"):
            self.append()
        self.assertEqual(forged, self.registry.read_bytes())
        self.assertEqual(original_anchor, (self.anchor_dir /
            (self.registry.stem + "." + ev.ANCHOR_NAME)).read_bytes())
        self.assertNotEqual(original_registry, self.registry.read_bytes())

    def test_receipt_same_meaning_new_bytes_refused(self):
        self.append()
        path=self.vault/"receipts"/"operator-import-campaign-v01.json"
        body=json.loads(path.read_text(encoding="utf-8"))
        path.write_text(json.dumps(body, separators=(",",":")),
                        encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError, "VAULT_CHANGED_SINCE_LAST_ENTRY"):
            self.verify()

    def test_missing_key_check_does_not_create_new_key(self):
        self.append()
        self.key_file.unlink()
        with self.assertRaisesRegex(ev.EvidenceError, "OPERATOR_KEY_MISSING"):
            self.verify()
        self.assertFalse(self.key_file.exists())

    def test_secret_key_and_anchor_nested_beneath_vault_refused(self):
        nested=self.vault/"private"/"anchors"
        with self.assertRaisesRegex(
                ev.EvidenceError, "SECRET_OR_ANCHOR_INSIDE_VAULT_REFUSED"):
            ev.append_evidence(self.registry,nested,self.key_file,
                               self.vault,self.sidecar,"test","op")
        self.assertFalse(nested.exists())
        secret=self.vault/"private"/"operator.key"
        with self.assertRaisesRegex(
                ev.EvidenceError, "SECRET_OR_ANCHOR_INSIDE_VAULT_REFUSED"):
            ev.append_evidence(self.registry,self.anchor_dir,secret,
                               self.vault,self.sidecar,"test","op")
        self.assertFalse(secret.exists())

    def test_initial_check_requires_existing_anchored_registry(self):
        ev.load_operator_key(self.key_file)
        with self.assertRaisesRegex(
                ev.EvidenceError, "REGISTRY_EMPTY|REGISTRY_MISSING"):
            self.verify()

    def test_stale_lock_never_unlinks_busy_operator_lock(self):
        import os
        import time
        lock=self.registry.parent/ev.LOCK_NAME
        holder=ev._VaultLock(lock,"operator")
        with holder:
            old=time.time()-ev._VaultLock.STALE_SECONDS-50
            os.utime(lock,(old,old))
            with self.assertRaisesRegex(
                    ev.EvidenceError,"REGISTRY_BUSY_ANOTHER_OPERATOR"):
                with ev._VaultLock(lock,"second"):
                    pass
            self.assertTrue(lock.is_file())

    def test_malformed_receipt_refuses_without_traceback(self):
        receipt=self.vault/"receipts"/"operator-import-campaign-v01.json"
        body=json.loads(receipt.read_text(encoding="utf-8"))
        body["steps"]=[None]
        receipt.write_text(json.dumps(body),encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError,"CAMPAIGN_RECEIPT_INVALID"):
            self.append()

    def test_registry_wrong_json_type_refused(self):
        self.append()
        self.registry.write_text('[]'+chr(10),encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError,"REGISTRY_CHAIN_INVALID"):
            self.verify()

    def test_head_anchor_wrong_json_type_refused(self):
        self.append()
        anchor=self.anchor_dir/(self.registry.stem+"."+ev.ANCHOR_NAME)
        anchor.write_text('[]',encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError,"HEAD_ANCHOR_FORMAT_INVALID"):
            self.verify()

    def test_head_anchor_signed_sequence_must_match_registry(self):
        import hmac
        self.append()
        anchor=self.anchor_dir/(self.registry.stem+"."+ev.ANCHOR_NAME)
        body=json.loads(anchor.read_text(encoding="utf-8"))
        body["sequence"]=99
        auth={k:v for k,v in body.items() if k!="head_hmac"}
        body["head_hmac"]=hmac.new(self.key_file.read_bytes(),
                                  _canonical(auth),hashlib.sha256).hexdigest()
        anchor.write_text(json.dumps(body,sort_keys=True),encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError,"HEAD_ANCHOR_HEAD_MISMATCH"):
            self.verify()

    def test_append_refuses_semantically_same_rewritten_receipt(self):
        """Codex P1: changed current vault evidence must not gain a new MAC."""
        self.append()
        before=self.registry.read_bytes()
        anchor=self.anchor_dir/(self.registry.stem+"."+ev.ANCHOR_NAME)
        anchor_before=anchor.read_bytes()
        receipt=self.vault/"receipts"/"operator-import-campaign-v01.json"
        body=json.loads(receipt.read_text(encoding="utf-8"))
        receipt.write_text(json.dumps(body,separators=(",",":")),encoding="utf-8")
        with self.assertRaisesRegex(ev.EvidenceError,"VAULT_CHANGED_SINCE_LAST_ENTRY"):
            self.append()
        self.assertEqual(before,self.registry.read_bytes())
        self.assertEqual(anchor_before,anchor.read_bytes())

    def test_append_refuses_modified_sqlite_with_same_record_counts(self):
        self.append()
        db=self.vault/ev.CORPUS_DB_NAME
        con=sqlite3.connect(db)
        try:
            con.execute("UPDATE corpus_entries SET text='changed-synthetic' "
                        "WHERE source_id='synthetic-source-1' AND sura=1 AND aya=1")
            con.commit()
            self.assertEqual("ok",con.execute("PRAGMA quick_check").fetchone()[0])
        finally:
            con.close()
        with self.assertRaisesRegex(ev.EvidenceError,"VAULT_CHANGED_SINCE_LAST_ENTRY"):
            self.append()

    def test_append_rejects_unterminated_jsonl_without_corrupting_anchor(self):
        """Codex P2: missing final LF may not yield concatenated JSON objects."""
        self.append()
        anchor=self.anchor_dir/(self.registry.stem+"."+ev.ANCHOR_NAME)
        signed=anchor.read_bytes()
        self.registry.write_bytes(self.registry.read_bytes().rstrip(bytes([10])))
        before=self.registry.read_bytes()
        with self.assertRaisesRegex(ev.EvidenceError,"REGISTRY_NONCANONICAL_BYTES"):
            self.append()
        self.assertEqual(before,self.registry.read_bytes())
        self.assertEqual(signed,anchor.read_bytes())

    def test_anchor_inside_vault_refused(self):
        with self.assertRaisesRegex(ev.EvidenceError, "ANCHOR_INSIDE_VAULT_REFUSED"):
            ev.append_evidence(self.registry, self.vault, self.key_file,
                               self.vault, self.sidecar,
                               "operator-local-private-corpus-import-v01", "op")

    def test_concurrent_append_serialized_by_lock(self):
        lock = ev._VaultLock(self.registry.parent / ev.LOCK_NAME, "holder")
        with lock:
            with self.assertRaisesRegex(ev.EvidenceError,
                                        "REGISTRY_BUSY_ANOTHER_OPERATOR"):
                self.append()
        # after release the same append succeeds
        self.append()

    def test_vault_changed_since_last_entry_detected(self):
        self.append()
        db = self.vault / ev.CORPUS_DB_NAME
        raw = bytearray(db.read_bytes())
        raw[-3] ^= 0x01
        db.write_bytes(bytes(raw))
        with patch.object(ev, "SIDECAR_PIN",
                          _sha(self.vault.joinpath(ev.SIDECAR_DB_NAME).read_bytes())):
            with self.assertRaisesRegex(ev.EvidenceError,
                                        "VAULT_CHANGED_SINCE_LAST_ENTRY|CORPUS_"):
                self.verify()


if __name__ == "__main__":
    unittest.main()
