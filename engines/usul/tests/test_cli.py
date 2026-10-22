import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class UsulCliTests(unittest.TestCase):
    def test_demo_cli_succeeds_without_claiming_juristic_validity(self):
        fixture = Path("engines/usul/examples/synthetic-demo.json")
        result = subprocess.run([sys.executable, "-m", "engines.usul.executor", str(fixture)],
                                capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertEqual(output["conclusions"]["demo:output"]["status"],
                         "CONDITIONALLY_SUPPORTED")
        self.assertFalse(output["public_fatwa_authorized"])
        self.assertFalse(output["input_evidence_ids_externally_verified"])

    def test_malformed_cli_returns_2_not_a_legal_outcome(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "invalid.json"
            p.write_text('{"schema_version":"0.1.0","methodology_id":"demo:profile"}',
                         encoding="utf-8")
            result = subprocess.run([sys.executable, "-m", "engines.usul.executor", str(p)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["scholarly_verified"])


if __name__ == "__main__":
    unittest.main()
