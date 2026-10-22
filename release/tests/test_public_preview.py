"""Public Mubin metadata-only preview: reproducibility and no-source-publication tests."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from release.public_preview import (
    PROJECT, OUT, QURAN, STAGE07, STAGE08,
    PreviewError, encode, public_manifest,
)


class PublicPreviewTests(unittest.TestCase):
    def setUp(self):
        self.root = PROJECT

    def test_committed_artifact_rebuilds_byte_identically(self):
        expected = encode(public_manifest(self.root))
        self.assertEqual((self.root / OUT).read_bytes(), expected)
        data = json.loads(expected.decode("utf-8"))
        self.assertEqual(data["system_version"], "0.1.0-alpha")
        self.assertEqual(data["preview_status"],
                         "STATIC_ARTIFACT_READY_NOT_HOSTING_CONFIRMED")

    def test_preview_contains_no_source_text_or_scholarly_publication(self):
        result = public_manifest(self.root)
        self.assertFalse(result["source_text_included"])
        self.assertFalse(result["rights_granted"])
        self.assertFalse(result["scholarly_verified"])
        self.assertFalse(result["public_fatwa_authorized"])
        self.assertEqual(result["publication_gates"]["canonical_quran_display"], "WITHHELD")
        self.assertEqual(result["publication_gates"]["source_verbatim_publication"], "WITHHELD")
        self.assertEqual(result["publication_gates"]["hadith_frozen_gold_mutation"], "PROHIBITED")
        self.assertEqual(len(result["research_example"]["query_counts"]), 6)
        self.assertEqual(sum(x["w1_exact"] + x["w2_exact"]
                             for x in result["research_example"]["query_counts"]), 12)
        serialized = encode(result).decode("utf-8")
        for field in ("excerpt", "section_text", "raw_html", "passage_text",
                      "full_verse_text", "tafsir_text", "p0_verified_evidence"):
            self.assertNotIn('"' + field + '"', serialized)

    def make_mutable_tree(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        for rel in (STAGE07, STAGE08, QURAN, "VERSION.yaml"):
            (root / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.root / rel, root / rel)
        return root

    def mutate(self, rel, mutate):
        root = self.make_mutable_tree()
        file = root / rel
        data = json.loads(file.read_text(encoding="utf-8"))
        mutate(data)
        file.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        with self.assertRaises(PreviewError):
            public_manifest(root)

    def test_changed_graph_counts_fail_closed(self):
        self.mutate(STAGE08, lambda data: data["graph_counts"].update(nodes_total=54))

    def test_changed_witness_source_pin_fail_closed(self):
        self.mutate(STAGE08, lambda data:
                    data["frozen_witness_pins"]["W2"].update(html="0"*64))

    def test_missing_real_replay_receipt_blocks_preview_artifact(self):
        self.mutate(STAGE07, lambda data:
                    data.update(campaign_decision="STAGE07_ENGINEERING_ONLY_PASS"))

    def test_quran_content_gates_must_stay_withheld(self):
        self.mutate(QURAN, lambda data:
                    data["independent_gates_unchanged"].update(canonical_quran_verified=True))

    def test_no_fatwas_or_rights_are_inferred_from_operator_receipts(self):
        self.mutate(STAGE08, lambda data:
                    data["limits"].update(redistribution_approved=True))

    def test_mutating_query_counts_requires_new_review(self):
        self.mutate(STAGE07, lambda data:
                    data["queries"][0]["W1"].update(strict=999))

    def test_release_cli_checks_artifact_without_running_unrelated_engines(self):
        command = [sys.executable, "-m", "release.public_preview", "--check"]
        p = subprocess.run(command, cwd=self.root,
                           capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        result = json.loads(p.stdout)
        self.assertEqual(result["status"], "PUBLIC_METADATA_PREVIEW_ARTIFACT_PASS")
        self.assertFalse(result["public_hosting_verified"])
        self.assertFalse(result["publication_rights_granted"])

    def test_preview_frontend_does_not_include_external_code_or_raw_content(self):
        index = (self.root / "docs/index.html").read_text(encoding="utf-8")
        js = (self.root / "docs/preview.js").read_text(encoding="utf-8")
        self.assertIn("Content-Security-Policy", index)
        self.assertIn("fetch(\"./preview-data.json\"", js)
        self.assertIn("textContent", js)
        self.assertNotIn("innerHTML", js)
        self.assertNotIn("eval(", js)
        self.assertNotIn("https://cdn.", index)
        self.assertNotIn("apiKey", js)


if __name__ == "__main__":
    unittest.main()
