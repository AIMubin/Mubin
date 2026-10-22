"""Synthetic tests for the private operator U0.2 receipt generator.

The historical private W1/W2 texts are never read by CI. A stub gateway
is injected after fixture construction; the production CLI cannot inject it.
"""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from engines.usul.concept_rule_catalog import CatalogError, sha
from engines.usul.pilots import waraqat_u02_private_acceptance as acceptance


class PrivateAcceptanceTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        d = Path(temp.name)
        self.payloads = (
            b"<html>synthetic W1 source</html>",
            b"synthetic export",
            b'{"synthetic":true}',
            "الأمر الأمر\nالقرينة الوجوب\n".encode("utf-8"),
            b"<html>synthetic W2 source</html>",
            b"synthetic W2 section",
        )
        self.paths = tuple(d / ("fixture-%d.bin" % i) for i in range(6))
        for p, raw in zip(self.paths, self.payloads):
            p.write_bytes(raw)
        self.queries = [
            {"id": "query:amr", "literal": "الأمر"},
            {"id": "query:qarinah", "literal": "القرينة"},
            {"id": "query:wujub", "literal": "الوجوب"},
        ]
        self.catalog = {}
        self.lexical = {}
        self.pointers = []
        self.report = {
            "status": "U02_WARAQAT_PINNED_CATALOG_PASS",
            "u02_real_replay_report_sha256": sha(b"mock-bridge"),
            "stage08_graph_sha256": sha(b"mock-graph"),
            "catalog_sha256": sha(b"mock-catalog"),
            "stage08_node_count": 53,
            "stage08_edge_count": 87,
            "catalog_concept_count": 3,
            "catalog_rule_candidates": 1,
            "lexical_bindings": [
                {"concept_id": "concept:amr-term", "query_id": "query:amr",
                 "source_id": "pilot:waraqat-primary",
                 "section_sha256": sha(self.payloads[3]),
                 "classification": "EXACT_LITERAL_ONLY",
                 "unique_occurrence_count": 2,
                 "occurrence_ids": ["occ:1", "occ:2"]},
                {"concept_id": "concept:qarinah", "query_id": "query:qarinah",
                 "source_id": "pilot:waraqat-primary",
                 "section_sha256": sha(self.payloads[3]),
                 "classification": "EXACT_LITERAL_ONLY",
                 "unique_occurrence_count": 1,
                 "occurrence_ids": ["occ:3"]},
                {"concept_id": "concept:wujub", "query_id": "query:wujub",
                 "source_id": "pilot:waraqat-primary",
                 "section_sha256": sha(self.payloads[3]),
                 "classification": "EXACT_LITERAL_ONLY",
                 "unique_occurrence_count": 1,
                 "occurrence_ids": ["occ:4"]},
            ],
        }

    def pinned(self):
        return (
            patch.object(acceptance, "EXPECTED_FILE_PINS",
                         tuple(sha(x) for x in self.payloads)),
            patch.object(acceptance, "W1_RAW_SHA", sha(self.payloads[0])),
            patch.object(acceptance, "W1_EXPORT_SHA", sha(self.payloads[1])),
            patch.object(acceptance, "W1_MANIFEST_SHA", sha(self.payloads[2])),
            patch.object(acceptance, "W1_SECTION_SHA", sha(self.payloads[3])),
            patch.object(acceptance, "W2_RAW_SHA", sha(self.payloads[4])),
            patch.object(acceptance, "W2_SECTION_SHA", sha(self.payloads[5])),
        )

    def strict_stub(self, paths, *metadata):
        if (Path(paths[0]).read_bytes() != self.payloads[0] or
                Path(paths[4]).read_bytes() != self.payloads[4]):
            raise CatalogError("MOCK_MUTATION_REJECTED")
        return copy.deepcopy(self.report)

    def run_attestor(self, replay=None):
        from contextlib import ExitStack
        with ExitStack() as stack:
            for context in self.pinned():
                stack.enter_context(context)
            return acceptance.attest_private_sources(
                self.paths, self.queries, self.pointers, self.catalog,
                self.lexical, commit_sha="a"*40,
                replay=self.strict_stub if replay is None else replay)

    def test_operator_receipt_determinism_privacy_and_negative_gates(self):
        first, second = self.run_attestor(), self.run_attestor()
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "U02_REAL_WARAQAT_PRIVATE_REPLAY_ACCEPTED")
        self.assertTrue(first["identical_two_source_replays"])
        self.assertTrue(first["w1_mutated_html_rejected"])
        self.assertTrue(first["w2_mutated_html_rejected"])
        self.assertEqual(
            [x["independent_exact_count"]
             for x in first["independent_original_byte_literal_counts"]],
            [2, 1, 1])
        self.assertEqual(len(first["acceptance_receipt_sha256"]), 64)
        for field in ("source_text_included", "private_paths_included",
                      "scholarly_verified", "redistribution_approved",
                      "semantic_equivalence_verified", "rule_execution_performed",
                      "public_fatwa_authorized", "source_support_attested",
                      "source_edition_authenticated"):
            self.assertFalse(first[field])
        self.assertNotIn("الأمر الأمر", json.dumps(first, ensure_ascii=False))
        self.assertNotIn(str(self.paths[0]), json.dumps(first))

    def test_input_source_digest_mutation_is_denied(self):
        self.paths[3].write_bytes(b"mutated")
        with self.assertRaisesRegex(CatalogError, "FROZEN_PRIVATE_INPUT_DIGEST_MISMATCH"):
            self.run_attestor()

    def test_independent_byte_count_detects_forged_link(self):
        self.report["lexical_bindings"][0]["unique_occurrence_count"] = 3
        self.report["lexical_bindings"][0]["occurrence_ids"].append("occ:5")
        with self.assertRaisesRegex(CatalogError, "INDEPENDENT_W1_LITERAL_COUNT_MISMATCH"):
            self.run_attestor()

    def test_negative_replay_must_actually_refuse_modified_html(self):
        def permissive(paths, *args):
            return copy.deepcopy(self.report)
        with self.assertRaisesRegex(CatalogError, "HOSTILE_PRIVATE_HTML_REPLAY_NOT_REFUSED"):
            self.run_attestor(permissive)

    def test_two_replays_must_be_identical(self):
        counter = [0]
        def nondeterministic(paths, *args):
            self.strict_stub(paths, *args)
            counter[0] += 1
            payload = copy.deepcopy(self.report)
            payload["u02_real_replay_report_sha256"] = sha(
                ("mock-%d" % counter[0]).encode("ascii"))
            return payload
        with self.assertRaisesRegex(CatalogError, "PRIVATE_REPLAY_NONDETERMINISTIC_OR_FAILED"):
            self.run_attestor(nondeterministic)

    def test_unknown_query_cannot_be_used_to_fake_occurrences(self):
        self.report["lexical_bindings"][1]["query_id"] = "query:unknown"
        with self.assertRaisesRegex(CatalogError, "LEXICAL_LINK_SOURCE_MISMATCH"):
            self.run_attestor()

    def test_invalid_commit_sha_refused(self):
        with self.assertRaisesRegex(CatalogError, "AUDITED_COMMIT_SHA_INVALID"):
            acceptance.attest_private_sources(
                self.paths, self.queries, self.pointers, self.catalog,
                self.lexical, commit_sha="not-a-sha", replay=self.strict_stub)

    def test_absent_private_inputs_yield_pending_not_pass(self):
        output = self.paths[0].parent / "result.json"
        args = []
        for name in ("primary-html", "primary-export", "primary-manifest",
                     "primary-section", "secondary-html", "secondary-section"):
            args.extend(["--"+name, str(output.parent / (name+".missing"))])
        p = subprocess.run(
            [sys.executable, "-m",
             "engines.usul.pilots.waraqat_u02_private_acceptance",
             *args, "--commit-sha", "a"*40, "--out", str(output)],
            capture_output=True, text=True,
            cwd=Path(__file__).resolve().parents[3])
        self.assertEqual(p.returncode, 3, p.stderr)
        data = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(data["status"], "PENDING_PRIVATE_WITNESS_FILES")
        self.assertFalse(data["source_text_included"])


if __name__ == "__main__":
    unittest.main()
