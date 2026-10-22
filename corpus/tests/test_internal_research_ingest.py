"""Negative and positive tests for the internal-research ingestion bridge.

All fixtures are synthetic; no real witness bytes are used here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from corpus.internal_research_ingest import (
    InternalSourceRefusal, ingest_internal_research, is_admitted,
    verify_usage_register,
)


def _attestation(**overrides):
    base = {
        "basis": "SA_2026_ART26_2_NONPROFIT_RESEARCH",
        "lawfully_published": True, "lawfully_acquired": True,
        "purpose_bounded": True, "private_local_storage": True,
        "applicability_checked": True,
        "contract_and_access_terms_checked": True,
        "no_public_distribution": True,
        "no_unnecessary_final_product_inclusion": True,
        "normal_exploitation_respected": True,
        "legitimate_interests_respected": True,
        "independent_rights_respected": True,
        "usage_register_retained": True,
        "commercial_context": "NONCOMMERCIAL",
        "commercial_exception_checked": False,
        "nonprofit_activity": True, "author_and_source_attributed": True,
    }
    base.update(overrides)
    return base


def _use_record(**overrides):
    base = {"work_type": "usul", "source_reference": "usul-waraqat-w1",
            "purpose_code": "NONPROFIT_RESEARCH", "use_date": "2026-10-22"}
    base.update(overrides)
    return base


def _meta(**overrides):
    base = {
        "source_id": "usul-waraqat-w1", "source_kind": "usul",
        "work_id": "usul-al-waraqat", "edition_id": "digital-witness-unverified",
        "redistribution_status": "UNKNOWN", "source_url": "https://example.test/src",
        "acquisition_evidence": "pin-ledger:9ce9de30",
    }
    base.update(overrides)
    return base


class InternalResearchIngestTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.base = Path(self._tmp.name)
        self.corpus_root = self.base / "corpus-data-private"
        self.register = self.base / "usage-register.jsonl"
        self.source = self.base / "src" / "w1-export.txt"
        self.source.parent.mkdir(parents=True, exist_ok=True)
        payload = ("باب الأمر\n\n" + "نص تركيبي للاختبار فقط\n" * 20).encode("utf-8")
        self.source.write_bytes(payload)
        self.pin = hashlib.sha256(payload).hexdigest()

    def tearDown(self):
        self._tmp.cleanup()

    def admit(self):
        return ingest_internal_research(
            self.source, self.corpus_root, self.register,
            source_meta=_meta(), attestation=_attestation(),
            use_record=_use_record(),
            independently_pinned_sha256=self.pin)

    def test_positive_admission_is_complete_and_chained(self):
        out = self.admit()
        self.assertEqual(out["status"], "INTERNAL_DEVELOPMENT_RESEARCH_ELIGIBLE")
        manifest = self.corpus_root / "manifests" / (
            "usul-waraqat-w1-" + out["object_sha256"][:16] + ".json")
        record = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(record["visibility"], "internal_only")
        self.assertEqual(record["admission_status"],
                         "INTERNAL_DEVELOPMENT_RESEARCH_ELIGIBLE")
        self.assertTrue(is_admitted(manifest, self.register))
        reg = verify_usage_register(self.register)
        self.assertTrue(reg["chain_valid"])
        self.assertEqual(reg["entries"], 1)

    def test_pin_mismatch_refused_and_nothing_written(self):
        with self.assertRaises(InternalSourceRefusal) as ctx:
            ingest_internal_research(
                self.source, self.corpus_root, self.register,
                source_meta=_meta(), attestation=_attestation(),
                use_record=_use_record(),
                independently_pinned_sha256="f" * 64)
        self.assertEqual(ctx.exception.code, "SOURCE_PIN_MISMATCH")
        self.assertFalse(self.corpus_root.exists(),
                         "corpus root must not be created on refusal")
        self.assertFalse(self.register.exists(),
                         "usage register must not be created on refusal")

    def test_missing_file_refused(self):
        with self.assertRaises(InternalSourceRefusal) as ctx:
            ingest_internal_research(
                self.base / "src" / "missing.txt", self.corpus_root,
                self.register, source_meta=_meta(), attestation=_attestation(),
                use_record=_use_record(), independently_pinned_sha256=self.pin)
        self.assertEqual(ctx.exception.code, "SOURCE_PATH_MISSING")

    def test_symlink_source_refused(self):
        link = self.base / "src" / "link.txt"
        try:
            link.symlink_to(self.source)
        except OSError:
            self.skipTest("symlinks unavailable")
        with self.assertRaises(InternalSourceRefusal) as ctx:
            ingest_internal_research(
                link, self.corpus_root, self.register, source_meta=_meta(),
                attestation=_attestation(), use_record=_use_record(),
                independently_pinned_sha256=self.pin)
        self.assertEqual(ctx.exception.code, "SOURCE_IS_SYMLINK")

    def test_unproven_acquisition_refused(self):
        with self.assertRaises(InternalSourceRefusal) as ctx:
            ingest_internal_research(
                self.source, self.corpus_root, self.register,
                source_meta=_meta(), attestation=_attestation(lawfully_acquired=False),
                use_record=_use_record(), independently_pinned_sha256=self.pin)
        self.assertEqual(ctx.exception.code,
                         "LAWFUL_PUBLICATION_OR_ACQUISITION_UNCONFIRMED")
        self.assertFalse(self.register.exists())

    def test_purpose_basis_mismatch_refused(self):
        with self.assertRaises(InternalSourceRefusal) as ctx:
            ingest_internal_research(
                self.source, self.corpus_root, self.register,
                source_meta=_meta(),
                attestation=_attestation(basis="SA_2026_ART26_4_AI_DEVELOPMENT"),
                use_record=_use_record(purpose_code="NONPROFIT_RESEARCH"),
                independently_pinned_sha256=self.pin)
        self.assertEqual(ctx.exception.code, "AI_DEVELOPMENT_PURPOSE_INVALID")
        self.assertFalse(self.register.exists())

    def test_incomplete_use_record_refused(self):
        broken = _use_record()
        del broken["use_date"]
        with self.assertRaises(InternalSourceRefusal) as ctx:
            ingest_internal_research(
                self.source, self.corpus_root, self.register,
                source_meta=_meta(), attestation=_attestation(),
                use_record=broken, independently_pinned_sha256=self.pin)
        self.assertEqual(ctx.exception.code, "INVALID_USAGE_RECORD_SCHEMA")

    def test_no_automatic_redistribution_upgrade(self):
        out = self.admit()
        manifest = self.corpus_root / "manifests" / (
            "usul-waraqat-w1-" + out["object_sha256"][:16] + ".json")
        record = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(record["rights_statement"], "UNKNOWN",
                         "no automatic redistribution upgrade")
        self.assertEqual(record["visibility"], "internal_only")

    def test_use_before_admission_refused(self):
        self.assertFalse(is_admitted(
            self.corpus_root / "manifests" / "absent.json", self.register))

    def test_register_tamper_detected(self):
        self.admit()
        lines = self.register.read_text(encoding="utf-8").splitlines()
        body = json.loads(lines[0])
        body["payload"]["source_sha256"] = "e" * 64
        lines[0] = json.dumps(body, ensure_ascii=False, sort_keys=True,
                              separators=(",", ":"))
        self.register.write_text("\n".join(lines) + "\n", encoding="utf-8")
        report = verify_usage_register(self.register)
        self.assertFalse(report["chain_valid"])

    def test_tampered_usage_register_prevents_admission_and_new_append(self):
        original = self.admit()
        manifest_path = self.corpus_root / "manifests" / (
            "usul-waraqat-w1-" + original["object_sha256"][:16] + ".json")
        rows = self.register.read_text(encoding="utf-8").splitlines()
        entry = json.loads(rows[0])
        entry["payload"]["source_sha256"] = "f" * 64
        self.register.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        self.assertFalse(verify_usage_register(self.register)["chain_valid"])
        self.assertFalse(is_admitted(manifest_path, self.register))
        from corpus.internal_research_ingest import append_usage_register
        with self.assertRaisesRegex(
                InternalSourceRefusal, "USAGE_REGISTER_CHAIN_INVALID"):
            append_usage_register(self.register, {"example": "candidate"})
        self.assertEqual(len(self.register.read_text(encoding="utf-8").splitlines()), 1)

    def test_structurally_forged_sequence_fails_even_with_rehashed_entry(self):
        from corpus.internal_research_ingest import _canonical
        self.admit()
        entry = json.loads(self.register.read_text(encoding="utf-8"))
        entry["seq"] = 99
        entry["entry_sha256"] = hashlib.sha256(_canonical({
            k: v for k, v in entry.items() if k != "entry_sha256"
        })).hexdigest()
        self.register.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        self.assertFalse(verify_usage_register(self.register)["chain_valid"])

    def test_missing_metadata_key_is_stable_refusal_not_keyerror(self):
        meta = _meta()
        del meta["source_url"]
        with self.assertRaisesRegex(InternalSourceRefusal, "INVALID_SOURCE_META_SCHEMA"):
            ingest_internal_research(
                self.source, self.corpus_root, self.register,
                source_meta=meta, attestation=_attestation(),
                use_record=_use_record(), independently_pinned_sha256=self.pin)
        self.assertFalse(self.corpus_root.exists())

    def test_raw_source_prose_field_is_rejected(self):
        meta = _meta()
        meta["raw_source_excerpt"] = "private-synthetic"
        with self.assertRaisesRegex(InternalSourceRefusal, "INVALID_SOURCE_META_SCHEMA"):
            ingest_internal_research(
                self.source, self.corpus_root, self.register,
                source_meta=meta, attestation=_attestation(),
                use_record=_use_record(), independently_pinned_sha256=self.pin)

    def test_private_usage_register_cannot_be_inside_git_repository(self):
        git = self.base / "repo"
        (git / ".git").mkdir(parents=True)
        register = git / "sensitive-register.jsonl"
        with self.assertRaisesRegex(InternalSourceRefusal, "PRIVATE_STORAGE_INSIDE_GIT_REFUSED"):
            ingest_internal_research(
                self.source, self.corpus_root, register,
                source_meta=_meta(), attestation=_attestation(),
                use_record=_use_record(), independently_pinned_sha256=self.pin)
        self.assertFalse(register.exists())

    def test_private_corpus_root_cannot_be_git_repository_root(self):
        git = self.base / "repo"
        (git / ".git").mkdir(parents=True)
        with self.assertRaisesRegex(InternalSourceRefusal, "PRIVATE_STORAGE_INSIDE_GIT_REFUSED"):
            ingest_internal_research(
                self.source, git, self.register,
                source_meta=_meta(), attestation=_attestation(),
                use_record=_use_record(), independently_pinned_sha256=self.pin)
        self.assertFalse(self.register.exists())

    def test_mutating_content_addressed_object_revokes_admission(self):
        out = self.admit()
        manifest_path = self.corpus_root / "manifests" / (
            "usul-waraqat-w1-" + out["object_sha256"][:16] + ".json")
        self.assertTrue(is_admitted(manifest_path, self.register))
        object_path = (self.corpus_root / "objects" / out["object_sha256"][:2] /
                       out["object_sha256"])
        object_path.write_bytes(b"tampered-local-data")
        self.assertFalse(is_admitted(manifest_path, self.register))

    def test_malformed_register_is_not_admitted(self):
        out = self.admit()
        manifest_path = self.corpus_root / "manifests" / (
            "usul-waraqat-w1-" + out["object_sha256"][:16] + ".json")
        self.register.write_text("{not-json\n", encoding="utf-8")
        self.assertFalse(verify_usage_register(self.register)["chain_valid"])
        self.assertFalse(is_admitted(manifest_path, self.register))

    def test_private_original_cannot_be_in_git_tree(self):
        repo = self.base / "repo"
        (repo / ".git").mkdir(parents=True)
        original = repo / "source.txt"
        original.write_bytes(self.source.read_bytes())
        with self.assertRaisesRegex(
                InternalSourceRefusal, "PRIVATE_STORAGE_INSIDE_GIT_REFUSED"):
            ingest_internal_research(
                original, self.corpus_root, self.register,
                source_meta=_meta(), attestation=_attestation(),
                use_record=_use_record(), independently_pinned_sha256=self.pin)
        self.assertFalse(self.register.exists())

    def test_importer_cannot_change_bytes_after_hash_preflight(self):
        from unittest.mock import patch
        from corpus.import_local import ingest as real_ingest

        def mutate_source_and_ingest(*args, **kwargs):
            self.source.write_bytes(b"malicious source swapped after hash check")
            return real_ingest(*args, **kwargs)

        with patch("corpus.internal_research_ingest.ingest",
                   side_effect=mutate_source_and_ingest):
            with self.assertRaisesRegex(
                    InternalSourceRefusal, "SOURCE_CHANGED_DURING_IMPORT"):
                self.admit()
        self.assertFalse(self.register.exists())

    def test_duplicate_source_same_content_two_manifests(self):
        first = self.admit()
        second = self.admit()
        self.assertEqual(first["object_sha256"], second["object_sha256"])
        self.assertNotEqual(first["manifest_sha256"], second["manifest_sha256"])


if __name__ == "__main__":
    unittest.main()
