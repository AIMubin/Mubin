"""End-to-end code-pinned index experiment (all items are synthetic)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

from engines.usul.pilots.indexed_amr_pilot import run
from engines.usul.pilots.amr_default import SOURCE_EXCERPT
from engines.usul.source_scope_index import INDEXES


class IndexedWaraqatPilotTests(unittest.TestCase):
    def test_complete_truth_table_has_pinned_proofs_and_source_traces(self):
        result = run()
        self.assertEqual(result, run())
        expected = {
            "pinned_absent_in_synthetic_index": "CONDITIONALLY_SUPPORTED",
            "pinned_positive_marker": "BLOCKED_BY_EXCEPTION",
            "index_search_not_performed": "UNDETERMINED",
            "synthetic_command_premise_missing": "UNDETERMINED",
        }
        self.assertEqual(
            {k: value["rule_status"] for k, value in result["scenarios"].items()},
            expected,
        )
        first = result["scenarios"]["pinned_absent_in_synthetic_index"]
        proof = first["machine_index_proof"]
        self.assertEqual(proof["index_sha256"], INDEXES["absent"][1])
        self.assertEqual(proof["enumerated_items"], 2)
        self.assertEqual(proof["checked_items"], 2)
        self.assertTrue(proof["index_bytes_authenticated"])
        self.assertFalse(first["real_world_absence_verified"])
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["public_fatwa_authorized"])

    def test_positive_and_not_checked_cannot_be_negative(self):
        data = run()["scenarios"]
        positive = data["pinned_positive_marker"]["machine_index_proof"]
        self.assertEqual(positive["index_sha256"], INDEXES["present"][1])
        self.assertEqual(positive["matching_item_ids"], ["pilot:case-part2"])
        unknown = data["index_search_not_performed"]["machine_index_proof"]
        self.assertFalse(unknown["scan_performed"])
        self.assertEqual(unknown["checked_items"], 0)
        self.assertEqual(data["index_search_not_performed"]["exception_finding"],
                         "NOT_CHECKED")

    def test_real_book_citations_distinct_from_fixture_source(self):
        data = run()["scenarios"]["pinned_absent_in_synthetic_index"]
        source_ids = {item["source_id"] for item in data["rule_source_citations"]}
        self.assertEqual(source_ids, {"pilot:waraqat-digital", "pilot:synthetic-fixture"})
        self.assertTrue(all(item["source_excerpt_reproduced"] is False
                            for item in data["rule_source_citations"]))

    def test_windows_compatible_cli_and_no_original_excerpt_redistribution(self):
        root = Path(__file__).resolve().parents[3]
        process = subprocess.run(
            [sys.executable, "-m", "engines.usul.pilots.indexed_amr_pilot"],
            cwd=root, capture_output=True, text=True, check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertTrue(process.stdout.isascii())
        output = json.loads(process.stdout)
        self.assertEqual(output["campaign"], "U0.1-source-index-stage03")
        self.assertNotIn(SOURCE_EXCERPT, process.stdout)
        self.assertFalse(output["real_source_corpus_exhaustiveness_verified"])


if __name__ == "__main__":
    unittest.main()
