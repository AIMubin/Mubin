import tempfile
import unittest
from pathlib import Path

from corpus.attest_tafsir_print_pdf import capture, sha256_file


class PrintAttestationTests(unittest.TestCase):
    def setUp(self):
        try:
            import fitz
        except ImportError:
            self.skipTest("PyMuPDF optional runtime not installed")
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.pdf = self.root / "synthetic-test-only.pdf"
        document = fitz.open()
        for number in (1, 2, 3):
            page = document.new_page()
            page.insert_text((72, 72), f"SYNTHETIC PAGE {number}: NOT A REAL EDITION")
        document.save(self.pdf)
        document.close()
        self.metadata = {"work": "معالم التنزيل", "publisher": "دار طيبة",
                         "publication_year": "1409 H", "edition": "synthetic edition candidate",
                         "scan_url": "https://example.org/synthetic-fixture"}

    def tearDown(self):
        if hasattr(self, "directory"):
            self.directory.cleanup()

    def test_capture_and_fail_closed_flags(self):
        out = self.root / "out"
        report = capture(self.pdf, "4:43", 2, [1, 3], out, self.metadata)
        self.assertEqual(len(report["pages"]), 2)
        self.assertEqual(report["pdf_file_sha256"], sha256_file(self.pdf))
        self.assertFalse(report["printed_pagination_verified"])
        self.assertFalse(report["scholarly_verified"])
        for page in report["pages"]:
            self.assertTrue((out / page["image_local_path"]).is_file())
            self.assertEqual(page["page_image_sha256"], sha256_file(out / page["image_local_path"]))
            self.assertTrue(page["searchable_text_detected"])
        with self.assertRaises(FileExistsError):
            capture(self.pdf, "4:43", 2, [1], out, self.metadata)

    def test_reject_wrong_volume_and_page(self):
        with tempfile.TemporaryDirectory() as tmp:
            # Set up explicit test PDF even if the test fixture is unavailable.
            if not hasattr(self, "pdf"):
                self.skipTest("PyMuPDF unavailable")
            with self.assertRaises(ValueError):
                capture(self.pdf, "17:4", 2, [1], self.root / "bad", self.metadata)
            with self.assertRaises(ValueError):
                capture(self.pdf, "4:43", 2, [9], self.root / "bad", self.metadata)
            with self.assertRaises(ValueError):
                capture(self.pdf, "4:43", 2, [1, 1], self.root / "bad", self.metadata)


if __name__ == "__main__":
    unittest.main()
