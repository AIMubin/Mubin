import unittest
from corpus.registry import validate_registry, can_publish

def sample():
    return {"records": [
        {"id": "quran:h:release", "kind": "quran", "edition": "Synthetic fixture",
         "source_url": "https://example.org/source", "sha256": "a"*64,
         "verification": "staged", "rights": "unknown", "riwayah": "Hafs",
         "verse_numbering": "Kufi"},
        {"id": "mushaf:h:1", "kind": "mushaf", "edition": "Synthetic fixture",
         "source_url": "https://example.org/page", "sha256": "b"*64,
         "verification": "staged", "rights": "unknown", "riwayah": "Hafs",
         "page": 1, "quran_ref": "quran:h:release"},
        {"id": "tafsir:test:1", "kind": "tafsir", "edition": "Synthetic fixture",
         "source_url": "https://example.org/work", "sha256": "c"*64,
         "verification": "staged", "rights": "unknown", "work": "Sample work",
         "author": "Sample author", "ayat": ["1:1"], "quran_ref": "quran:h:release"}
    ]}

class RegistryTests(unittest.TestCase):
    def test_valid_fixture(self):
        self.assertEqual(validate_registry(sample()), [])
    def test_missing_reference(self):
        data = sample()
        data["records"][1]["quran_ref"] = "missing"
        self.assertTrue(validate_registry(data))
    def test_riwayah_mismatch(self):
        data = sample()
        data["records"][1]["riwayah"] = "Warsh"
        self.assertTrue(validate_registry(data))
    def test_duplicate(self):
        data = sample()
        data["records"].append(data["records"][0].copy())
        self.assertTrue(validate_registry(data))
    def test_no_publish_on_rights_unknown(self):
        self.assertFalse(can_publish(sample()["records"][0]))
    def test_no_publish_on_verification_only(self):
        record = sample()["records"][0]
        record["verification"] = "scholarly_verified"
        self.assertFalse(can_publish(record))
    def test_publish_gate_both_required(self):
        record = sample()["records"][0]
        record["verification"] = "scholarly_verified"
        record["rights"] = "redistribution_permitted"
        self.assertTrue(can_publish(record))

if __name__ == "__main__":
    unittest.main()
