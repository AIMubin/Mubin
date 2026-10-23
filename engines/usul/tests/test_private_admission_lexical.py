"""Adversarial PRIVATE intake -> Usul Stage04/05 contract tests; synthetic only."""
from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from corpus.internal_research_ingest import (
    ingest_internal_research, verify_usage_register,
)
from engines.usul.private_admission_lexical import (
    PrivateUsulRefusal, main, scan_admitted_section,
)
from engines.usul.source_snapshot_prepare import propose

TEXT = "تمهيد اصطناعي\nالأمر\nسطر تجريبي للأمر\nالنهي\n"
SOURCE_URL = "https://example.invalid/synthetic-private-witness"
META = {
    "source_id": "pilot:synthetic-snapshot",
    "work_title": "Synthetic work",
    "author": "Fixture author",
    "edition": "Synthetic descriptive edition",
    "source_url": SOURCE_URL,
    "locator": "test only",
    "transcription_provenance": "synthetic fixture",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def attestation():
    return {
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
        "nonprofit_activity": True,
        "author_and_source_attributed": True,
    }


def queries():
    return [
        {"id": "pilot:found", "literal": "الأمر", "profile": "literal_exact_v1"},
        {"id": "pilot:absent", "literal": "غير موجود",
         "profile": "literal_exact_v1"},
    ]


class PrivateAdmissionLexicalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.source = self.root / "original-synthetic.txt"
        self.source.write_bytes(TEXT.encode("utf-8"))
        self.digest = sha(self.source.read_bytes())
        self.vault = self.root / "vault"
        self.register = self.root / "register.jsonl"
        self.snapshot_manifest = self.root / "snapshot.json"
        proposed = propose(self.source, META, "pilot:section-amr", "الأمر", "النهي")
        self.snapshot_manifest.write_bytes(
            (json.dumps(proposed, ensure_ascii=False, sort_keys=True,
                        separators=(",", ":")) + "\n").encode("utf-8"))
        self.snapshot_pin = sha(self.snapshot_manifest.read_bytes())
        self.intake = self.vault / "manifests" / (
            "usul-fixture-w1-" + self.digest[:16] + ".json")
        self.query_file = self.root / "queries.json"
        self.query_file.write_text(json.dumps(queries(), ensure_ascii=False),
                                   encoding="utf-8")
        self.report = self.root / "metadata-report.json"

    def admit(self, kind="usul"):
        return ingest_internal_research(
            self.source, self.vault, self.register,
            source_meta={
                "source_id": "usul-fixture-w1", "source_kind": kind,
                "work_id": "synthetic-work", "edition_id": "synthetic-v1",
                "redistribution_status": "UNKNOWN",
                "source_url": SOURCE_URL,
                "acquisition_evidence": "test-fixture-pin-only",
            },
            attestation=attestation(),
            use_record={
                "work_type": kind, "source_reference": "usul-fixture-w1",
                "purpose_code": "NONPROFIT_RESEARCH",
                "use_date": "2026-10-22",
            },
            independently_pinned_sha256=self.digest)

    def scan(self, q=None, pin=None):
        return scan_admitted_section(
            self.intake, self.register, self.snapshot_manifest,
            self.snapshot_pin if pin is None else pin,
            "pilot:section-amr", queries() if q is None else q)

    def assert_refused(self, code):
        with self.assertRaises(PrivateUsulRefusal) as caught:
            self.scan()
        self.assertEqual(caught.exception.code, code)

    def test_admitted_lexical_link_is_reproducible_and_non_authoritative(self):
        self.admit()
        before = self.source.read_bytes()
        intake_before = self.intake.read_bytes()
        ledger_before = self.register.read_bytes()
        got = self.scan()
        self.assertEqual(got, self.scan())
        self.assertEqual(got["status"], "PRIVATE_ADMITTED_LEXICAL_REPLAY_PASS")
        self.assertEqual(got["source_sha256"], self.digest)
        self.assertEqual(got["snapshot_manifest_sha256"], self.snapshot_pin)
        self.assertEqual(got["admission_source_id"], "usul-fixture-w1")
        self.assertEqual(got["snapshot_source_id"], "pilot:synthetic-snapshot")
        self.assertFalse(got["source_id_equivalence_attested"])
        self.assertFalse(got["edition_equivalence_verified"])
        self.assertEqual(got["classification"], "EXACT_LITERAL_ONLY")
        self.assertEqual([x["match_count"] for x in got["queries"]], [2, 0])
        self.assertFalse(got["scholarly_verified"])
        self.assertFalse(got["redistribution_approved"])
        self.assertFalse(got["juristic_inference_allowed"])
        self.assertFalse(got["public_fatwa_authorized"])
        self.assertFalse(got["semantic_qarinah_detection_verified"])
        self.assertFalse(got["lawful_acquisition_independently_verified"])
        self.assertFalse(got["source_text_included"])
        self.assertFalse(got["query_text_included"])
        rendered = json.dumps(got, ensure_ascii=False)
        for sensitive in ("سطر تجريبي", "غير موجود", SOURCE_URL,
                          str(self.root), "Fixture author"):
            self.assertNotIn(sensitive, rendered)
        self.assertEqual(before, self.source.read_bytes())
        self.assertEqual(intake_before, self.intake.read_bytes())
        self.assertEqual(ledger_before, self.register.read_bytes())

    def test_no_admission_is_blocked(self):
        self.assert_refused("SOURCE_NOT_ADMITTED")

    def test_other_engine_kind_cannot_enter_usul_bridge(self):
        self.admit(kind="tafsir")
        self.assert_refused("USUL_SOURCE_KIND_REFUSED")

    def test_malformed_chain_blocks_even_if_old_manifest_is_still_present(self):
        self.admit()
        self.register.write_bytes(self.register.read_bytes() + b"{corrupt}\n")
        self.assertFalse(verify_usage_register(self.register)["chain_valid"])
        self.assert_refused("SOURCE_NOT_ADMITTED")

    def test_changed_content_object_is_refused(self):
        self.admit()
        obj = self.vault / "objects" / self.digest[:2] / self.digest
        obj.write_bytes(b"malicious substitution")
        self.assert_refused("SOURCE_NOT_ADMITTED")

    def test_untrusted_or_changed_snapshot_manifest_pin_is_refused(self):
        self.admit()
        self.snapshot_manifest.write_bytes(self.snapshot_manifest.read_bytes() + b" ")
        self.assert_refused("SNAPSHOT_MANIFEST_PIN_MISMATCH")

    def test_different_admitted_source_identity_is_refused_even_with_new_pin(self):
        self.admit()
        snapshot = json.loads(self.snapshot_manifest.read_text(encoding="utf-8"))
        for field, wrong in (
            ("source_sha256", "0" * 64),
            ("source_url", "https://other.invalid/different-capture"),
        ):
            new = dict(snapshot)
            new[field] = wrong
            self.snapshot_manifest.write_text(json.dumps(new), encoding="utf-8")
            self.snapshot_pin = sha(self.snapshot_manifest.read_bytes())
            with self.subTest(field=field):
                self.assert_refused("SNAPSHOT_SOURCE_MISMATCH")
        # Restore verified synthetic pin for later tests if needed.

    def test_mutated_section_with_fresh_manifest_pin_still_fails(self):
        self.admit()
        snapshot = json.loads(self.snapshot_manifest.read_text(encoding="utf-8"))
        snapshot["sections"][0]["section_sha256"] = "a" * 64
        self.snapshot_manifest.write_text(json.dumps(snapshot), encoding="utf-8")
        self.snapshot_pin = sha(self.snapshot_manifest.read_bytes())
        self.assert_refused("STAGE05_LEXICAL_REPLAY_REFUSED")

    def test_bad_queries_fail_with_non_disclosing_code(self):
        self.admit()
        with self.assertRaises(PrivateUsulRefusal) as caught:
            self.scan(q=[{"id": "pilot:secret", "literal": "PRIVATE\nPATH",
                          "profile": "literal_exact_v1"}])
        self.assertEqual(caught.exception.code, "STAGE05_LEXICAL_REPLAY_REFUSED")
        self.assertNotIn("PRIVATE", str(caught.exception))

    def test_unadmitted_manifest_is_not_rehabilitated_by_stage04(self):
        self.admit()
        data = json.loads(self.intake.read_text(encoding="utf-8"))
        data["admission_status"] = "UNASSESSED"
        self.intake.write_text(json.dumps(data), encoding="utf-8")
        self.assert_refused("SOURCE_NOT_ADMITTED")

    def cli_args(self):
        return [
            "--admission-manifest", str(self.intake),
            "--usage-register", str(self.register),
            "--snapshot-manifest", str(self.snapshot_manifest),
            "--trusted-snapshot-manifest-sha256", self.snapshot_pin,
            "--section-id", "pilot:section-amr",
            "--queries", str(self.query_file),
            "--report", str(self.report),
        ]

    def test_cli_emits_private_metadata_only_and_stable_exit(self):
        self.admit()
        self.assertEqual(main(self.cli_args()), 0)
        output = self.report.read_text(encoding="utf-8")
        self.assertEqual(json.loads(output)["status"],
                         "PRIVATE_ADMITTED_LEXICAL_REPLAY_PASS")
        self.assertNotIn("سطر تجريبي", output)
        self.assertNotIn(SOURCE_URL, output)
        self.assertNotIn(str(self.root), output)
        self.register.write_bytes(b"{invalid json}\n")
        self.assertEqual(main(self.cli_args()), 1)
        # A previously written success report must not falsely survive a
        # subsequent refusal as a newly accepted run.
        self.assertFalse(json.loads(self.report.read_text(encoding="utf-8"))
                         .get("scholarly_verified", False))

    def test_cli_private_report_cannot_be_written_inside_git(self):
        self.admit()
        git = self.root / "repo"
        (git / ".git").mkdir(parents=True)
        args = self.cli_args()
        args[-1] = str(git / "report.json")
        self.assertEqual(main(args), 1)
        self.assertFalse((git / "report.json").exists())


if __name__ == "__main__":
    unittest.main()
