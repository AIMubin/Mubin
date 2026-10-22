import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from engines.usul.source_snapshot_prepare import propose
from engines.usul.source_snapshot_coverage import audit, SnapshotContractError

META = {
 "source_id":"pilot:snapshot","work_title":"Synthetic test text",
 "author":"Mubin","edition":"synthetic","source_url":"https://example.invalid",
 "locator":"test chapter","transcription_provenance":"generated test bytes"
}

class PrepareTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  self.source=Path(self.temp.name)/"source.txt"
  self.source.write_bytes("عنوان\nالأمر\nسطر تجريبي\nالنهي\n".encode("utf-8"))

 def test_prepare_draft_metadata_only(self):
  m=propose(self.source,META,"pilot:amr","الأمر","النهي")
  self.assertEqual(m["sections"][0]["expected_line_count"],2)
  self.assertNotIn("سطر تجريبي",json.dumps(m,ensure_ascii=False))

 def test_independently_supplied_digest_checks_bytes_not_authority(self):
  m=propose(self.source,META,"pilot:amr","الأمر","النهي")
  path=Path(self.temp.name)/"metadata.json"
  path.write_text(json.dumps(m,ensure_ascii=False),encoding="utf-8")
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  result=audit(self.source,path,trusted_manifest_sha256=digest)
  self.assertEqual(result["status"],"SNAPSHOT_COVERAGE_PASS")
  self.assertFalse(result["scholarly_verified"])
  self.assertFalse(result["external_original_html_or_print_equivalence_verified"])

 def test_missing_boundary_rejected(self):
  with self.assertRaises(SnapshotContractError):
   propose(self.source,META,"pilot:amr","missing","النهي")

if __name__=="__main__":
 unittest.main()
