"""B02-B metadata gate negative regressions; no private corpus, no network."""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from qa.check_b02b_handoff import FILE_NAMES, HandoffError, validate


class HandoffVerifierTests(unittest.TestCase):
    def test_missing_package_fails_closed(self):
        with tempfile.TemporaryDirectory() as base:
            with self.assertRaisesRegex(HandoffError, "B02B_PACKAGE_MISSING"):
                validate(Path(base))

    def test_partial_package_fails_closed(self):
        with tempfile.TemporaryDirectory() as base:
            folder = Path(base) / "research/b02b"
            folder.mkdir(parents=True)
            (folder / "task.yaml").write_text("preserved_candidate:\n", encoding="utf-8")
            with self.assertRaisesRegex(HandoffError, "B02B_FILES_INCOMPLETE"):
                validate(Path(base))

    def test_false_selected_case_rejected_before_json_parsing(self):
        with tempfile.TemporaryDirectory() as base:
            folder = Path(base) / "research/b02b"
            folder.mkdir(parents=True)
            for name in FILE_NAMES:
                (folder / name).write_text("{}", encoding="utf-8")
            (folder / "task.yaml").write_text(
                "preserved_candidate:\nselected_case:\n"
                "status: REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR\n", encoding="utf-8")
            with self.assertRaisesRegex(HandoffError, "B02B_TASK_FALSE_SELECTED_CASE"):
                validate(Path(base))

    def test_selection_rejection_required(self):
        with tempfile.TemporaryDirectory() as base:
            folder = Path(base) / "research/b02b"
            folder.mkdir(parents=True)
            for name in FILE_NAMES:
                (folder / name).write_text("{}", encoding="utf-8")
            (folder / "task.yaml").write_text("preserved_candidate:\n", encoding="utf-8")
            with self.assertRaisesRegex(HandoffError, "B02B_TASK_SELECTION_VERDICT_MISSING"):
                validate(Path(base))

if __name__ == "__main__":
    unittest.main()
