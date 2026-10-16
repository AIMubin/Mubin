"""S0.1 Shamela feasibility: metadata-only, adversarial, offline tests.

No Shamela book text, page contents, downloadable corpus, or H3.9.2 holdouts.
"""
from __future__ import annotations

import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.source_catalog.shamela import validate_shamela_catalog

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / "research" / "shamela" / "pilot-catalog.json"


class TestShamelaBibliographicPilot(unittest.TestCase):
    def setUp(self):
        self.catalog = json.loads(CATALOG.read_text(encoding="utf-8"))

    def assert_rejected(self, catalog, key):
        problems = validate_shamela_catalog(catalog)
        self.assertTrue(problems, "invalid source metadata accepted")
        self.assertTrue(any(key in p for p in problems), problems)

    def test_three_distinct_books_metadata_only(self):
        self.assertEqual([], validate_shamela_catalog(self.catalog))
        self.assertEqual(3, len(self.catalog["entries"]))
        entries = {e["book_id"]: e for e in self.catalog["entries"]}
        self.assertEqual({1681, 7798, 8180}, set(entries))
        self.assertEqual(
            {1681: "hadith", 7798: "tafsir", 8180: "usul"},
            {i: e["discipline"] for i, e in entries.items()},
        )
        for item in entries.values():
            self.assertEqual("unverified", item["rights_status"])
            self.assertEqual("not_acquired", item["text_acquisition_status"])
            self.assertEqual("bibliographic_claim_only", item["edition_verification"])
            self.assertEqual(f"https://shamela.ws/book/{item['book_id']}", item["book_url"])
            self.assertEqual(f"shamela:book:{item['book_id']}", item["source_id"])
            self.assertTrue(item["sample_page_url"].startswith(item["book_url"] + "/"))
            self.assertNotIn("text", item)
            self.assertNotIn("text_sha256", item)
            self.assertNotIn("license_verified", item)
        self.assertFalse(self.catalog["acquisition"]["database_inspected"])
        self.assertFalse(self.catalog["acquisition"]["text_acquired"])
        self.assertFalse(self.catalog["acquisition"]["rights_verified"])

    def test_duplicate_book_id_rejected(self):
        self.catalog["entries"].append(copy.deepcopy(self.catalog["entries"][0]))
        self.assert_rejected(self.catalog, "duplicate")

    def test_book_url_and_id_must_match_exactly(self):
        e = self.catalog["entries"][0]
        for url in [
            "http://shamela.ws/book/1681",
            "https://evil.example/book/1681",
            "https://shamela.ws/book/7798",
            "https://shamela.ws/book/1681?download=true",
            "https://shamela.ws/book/1681#fragment",
            "https://shamela.ws/book/1681/1",
        ]:
            with self.subTest(url=url):
                changed = copy.deepcopy(self.catalog)
                changed["entries"][0]["book_url"] = url
                self.assert_rejected(changed, "book_url")

    def test_sample_page_url_must_belong_to_exact_book(self):
        for url in [
            "https://shamela.ws/book/7798/1",
            "https://shamela.ws/book/1681",
            "https://shamela.ws/book/1681/0",
            "https://shamela.ws/book/1681/1?view=raw",
            "https://shamela.ws/book/1681/-3",
            "https://shamela.ws/book/1681/01",
        ]:
            with self.subTest(url=url):
                changed = copy.deepcopy(self.catalog)
                changed["entries"][0]["sample_page_url"] = url
                self.assert_rejected(changed, "sample_page_url")

    def test_rights_cannot_be_auto_cleared(self):
        for value in ["operator_cleared", "licensed", "public_domain", True]:
            with self.subTest(value=value):
                changed = copy.deepcopy(self.catalog)
                changed["entries"][0]["rights_status"] = value
                self.assert_rejected(changed, "rights_status")

    def test_no_raw_text_hashes_spans_or_eligibility(self):
        for key, value in [
            ("text", "نص كتاب حقيقي"),
            ("excerpt", "مقتطف"),
            ("text_sha256", "a" * 64),
            ("spans", [{"start_byte": 0, "end_byte": 1}]),
            ("qualification_eligible", True),
            ("download_url", "https://shamela.ws/download/raw"),
            ("content_sha256", "b" * 64),
        ]:
            with self.subTest(key=key):
                changed = copy.deepcopy(self.catalog)
                changed["entries"][0][key] = value
                self.assert_rejected(changed, key)

    def test_no_acquisition_or_edition_authentication_claims(self):
        for field in ["text_acquired", "rights_verified", "database_inspected"]:
            changed = copy.deepcopy(self.catalog)
            changed["acquisition"][field] = True
            self.assert_rejected(changed, field)
        changed = copy.deepcopy(self.catalog)
        changed["entries"][1]["edition_verification"] = "authenticated"
        self.assert_rejected(changed, "edition_verification")

    def test_duplicate_work_title_allowed_as_editions_not_same_identity(self):
        copy_a = copy.deepcopy(self.catalog)
        copy_a["entries"][1]["work_title"] = copy_a["entries"][0]["work_title"]
        self.assertEqual([], validate_shamela_catalog(copy_a))

    def test_id_collisions_and_boolean_book_id_rejected(self):
        changed = copy.deepcopy(self.catalog)
        changed["entries"][0]["source_id"] = changed["entries"][1]["source_id"]
        self.assert_rejected(changed, "source_id")
        changed = copy.deepcopy(self.catalog)
        changed["entries"][0]["book_id"] = True
        self.assert_rejected(changed, "book_id")

    def test_bad_pagination_and_edition_label_rejected(self):
        for label in ["", "  ", "\ud800"]:
            changed = copy.deepcopy(self.catalog)
            changed["entries"][0]["edition_display"] = label
            self.assert_rejected(changed, "edition" if label != "\ud800" else "UTF-8")
        changed = copy.deepcopy(self.catalog)
        changed["entries"][2]["pagination_status"] = "exact_verified_byte_offsets"
        self.assert_rejected(changed, "pagination_status")

    def test_unknown_bibliography_keys_rejected(self):
        changed = copy.deepcopy(self.catalog)
        changed["entries"][1]["author_id_authenticated"] = True
        self.assert_rejected(changed, "author_id_authenticated")

    def test_capped_count_before_schema_diagnostics(self):
        changed = copy.deepcopy(self.catalog)
        changed["entries"] = [copy.deepcopy(self.catalog["entries"][0]) for _ in range(257)]
        self.assert_rejected(changed, "256")

    def test_metadata_size_limit_rejected(self):
        changed = copy.deepcopy(self.catalog)
        changed["entries"][0]["notes"] = "A" * (1024 * 1024 + 100)
        self.assert_rejected(changed, "size")

    def test_nested_programmatic_input_does_not_crash(self):
        changed = copy.deepcopy(self.catalog)
        changed["entries"][0]["notes"] = []
        for _ in range(1300):
            changed["entries"][0]["notes"] = [changed["entries"][0]["notes"]]
        self.assert_rejected(changed, "JSON")

    def test_overlong_metadata_rejected_before_strip_allocation(self):
        class LongText(str):
            def strip(self, *args, **kwargs):
                raise AssertionError("cannot strip oversized untrusted text")

        changed = copy.deepcopy(self.catalog)
        changed["entries"][0]["notes"] = LongText("x" * 4097)
        problems = validate_shamela_catalog(changed)
        self.assertTrue(any("notes" in p for p in problems), problems)

    def test_unknown_nested_field_rejected_before_serialization(self):
        changed = copy.deepcopy(self.catalog)
        value = []
        for _ in range(1500):
            value = [value]
        changed["entries"][0]["text_payload"] = value
        self.assert_rejected(changed, "unknown")

    def test_lone_surrogate_in_url_does_not_crash(self):
        changed = copy.deepcopy(self.catalog)
        changed["entries"][0]["book_url"] = "https://shamela.ws/book/1681\ud800"
        self.assert_rejected(changed, "UTF-8")

    def test_cli_accepts_metadata_and_rejects_unsafe_inputs(self):
        ok = subprocess.run(
            [sys.executable, "-m", "core.source_catalog", str(CATALOG), "--json"],
            cwd=ROOT, text=True, capture_output=True, check=False,
        )
        self.assertEqual(0, ok.returncode, ok.stderr)
        report = json.loads(ok.stdout)
        self.assertTrue(report["valid"], report)
        self.assertEqual(3, report["entry_count"])
        self.assertNotIn("source_text", ok.stdout)
        with tempfile.TemporaryDirectory() as directory:
            badfile = Path(directory) / "invalid.json"
            badfile.write_text("{", encoding="utf-8")
            rejected = subprocess.run(
                [sys.executable, "-m", "core.source_catalog", str(badfile), "--json"],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(2, rejected.returncode)
            badfile.write_text(json.dumps({**self.catalog, "scope": "full_text_ingested"}), encoding="utf-8")
            rejected = subprocess.run(
                [sys.executable, "-m", "core.source_catalog", str(badfile), "--json"],
                cwd=ROOT, text=True, capture_output=True, check=False,
            )
            self.assertEqual(1, rejected.returncode)


if __name__ == "__main__":
    unittest.main()
