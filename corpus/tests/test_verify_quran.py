import hashlib
import tempfile
import unittest
from pathlib import Path
from corpus.verify_quran import EXPECTED_COUNTS, verify

class QuranStructuralTests(unittest.TestCase):
    def test_reference_counts(self):
        self.assertEqual(len(EXPECTED_COUNTS), 114)
        self.assertEqual(sum(EXPECTED_COUNTS), 6236)

    def test_mock_fixture_valid_structure_not_authenticity(self):
        # Deliberately synthetic. Passing MUST NOT imply authentic Quran text.
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "synthetic.txt"
            content = "".join(f"{s}|{a}|TEST ONLY\\n" for s,n in enumerate(EXPECTED_COUNTS,1) for a in range(1,n+1))
            p.write_bytes(content.encode())
            sha = hashlib.sha256(p.read_bytes()).hexdigest()
            result = verify(p, sha)
            self.assertTrue(result["passed"])
            self.assertFalse(result["canonical_authentication"])

    def test_missing_digest_fails_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "empty.txt"
            p.write_bytes(b"")
            self.assertFalse(verify(p)["passed"])

    def test_wrong_order_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "bad.txt"
            p.write_text("1|2|TEST ONLY\n1|1|TEST ONLY\n", encoding="utf-8")
            self.assertFalse(verify(p, hashlib.sha256(p.read_bytes()).hexdigest())["passed"])

if __name__ == "__main__":
    unittest.main()
