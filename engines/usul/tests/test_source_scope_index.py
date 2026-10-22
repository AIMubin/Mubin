"""Pinned scope scanning is machine-executed, not a self-certified checked list."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.exception_evidence import ExceptionEvidenceError
from engines.usul.p0_bridge import build_and_run
from engines.usul.pilots.amr_default import example_bundle, example_spec, scenarios
from engines.usul.source_scope_index import INDEXES, FIXTURE_ROOT, examine, load_index


RULE = "pilot:rule-amr-default"
ATOM = "pilot:default-obligation-candidate"


def execute(index="absent", *, manual=None, strict=True, semantic=True, evidence=True,
            bundle=None, facts=None):
    b = example_bundle() if bundle is None else bundle
    return build_and_run(
        b, example_spec(b),
        scenarios()["indicator_unknown"] if facts is None else facts,
        require_semantic_binding=semantic,
        exception_assessments=manual,
        require_evidence_exceptions=evidence,
        pinned_scope_index=index,
        require_pinned_scope_index=strict,
    )


class PinnedIndexTests(unittest.TestCase):
    def test_both_frozen_manifest_sha_and_per_item_hashes(self):
        for kind in ("absent", "present"):
            index, observed = load_index(kind)
            self.assertEqual(observed, INDEXES[kind][1])
            self.assertEqual(len(index["items"]), 2)
            self.assertTrue(all(len(x["text_sha256"]) == 64 for x in index["items"]))
            self.assertEqual(index["index_kind"], "synthetic_fixture")

    def test_negative_found_by_full_scan_not_user_claim(self):
        out = execute("absent")
        self.assertIsNone(out["derivation_refused"])
        self.assertEqual(out["exception_assessment_trace"][0]["finding"],
                         "ABSENT_IN_DECLARED_SCOPE")
        self.assertEqual(out["usul_result"]["conclusions"][ATOM]["status"],
                         "CONDITIONALLY_SUPPORTED")
        proof = out["pinned_scope_index_proof"]
        self.assertTrue(proof["index_bytes_authenticated"])
        self.assertEqual(proof["enumerated_items"], proof["checked_items"])
        self.assertEqual(proof["matching_item_ids"], [])
        self.assertFalse(proof["scripture_coverage_verified"])
        self.assertFalse(proof["semantic_qarinah_detection_verified"])
        self.assertFalse(out["real_world_absence_verified"])
        self.assertFalse(out["scholarly_verified"])

    def test_positive_token_is_detected_in_pinned_second_document(self):
        out = execute("present")
        proof = out["pinned_scope_index_proof"]
        self.assertEqual(proof["matching_item_ids"], ["pilot:case-part2"])
        self.assertEqual(proof["checked_items"], 2)
        self.assertEqual(out["exception_assessment_trace"][0]["finding"], "PRESENT")
        self.assertEqual(out["usul_result"]["trace"][0]["status"],
                         "BLOCKED_BY_EXCEPTION")

    def test_not_checked_never_means_negative(self):
        out = execute("not_checked")
        self.assertIsNone(out["derivation_refused"])
        self.assertEqual(out["usul_result"]["trace"][0]["status"], "UNDETERMINED")
        self.assertEqual(out["pinned_scope_index_proof"]["checked_items"], 0)
        self.assertFalse(out["pinned_scope_index_proof"]["scan_performed"])

    def test_existing_sources_are_cited_without_excerpts(self):
        out = execute("absent")
        refs = out["rule_citations"][RULE]
        source_ids = {c["source_id"] for c in refs}
        self.assertEqual(source_ids, {"pilot:waraqat-digital", "pilot:synthetic-fixture"})
        self.assertTrue(all(c["source_excerpt_reproduced"] is False for c in refs))
        self.assertTrue(all(c["redistribution_permission_inferred"] is False for c in refs))

    def test_repeated_scan_is_identical_and_does_not_mutate_inputs(self):
        b = example_bundle()
        before = copy.deepcopy(b)
        first = execute("absent", bundle=b)
        self.assertEqual(b, before)
        self.assertEqual(first, execute("absent", bundle=b))

    def test_index_content_tampering_fails_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            source = FIXTURE_ROOT / "absent-index.json"
            altered = Path(tmp) / source.name
            altered.write_bytes(source.read_bytes().replace(b"CONTEXT_ONLY", b"[[QARINAH]]"))
            with self.assertRaisesRegex(ExceptionEvidenceError, "SHA-256 mismatch"):
                load_index("absent", root=tmp)

    def test_removed_fixture_is_not_substituted(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(FileNotFoundError):
                load_index("absent", root=tmp)

    def test_unrecognized_index_not_a_freeform_file_path(self):
        with self.assertRaises(ExceptionEvidenceError):
            load_index("../../etc/passwd")
        self.assertEqual(execute("unknown")["derivation_refused"]["code"],
                         "PINNED_SOURCE_INDEX_REJECTED")

    def test_manually_asserted_complete_scope_cannot_mix_with_pin(self):
        forged = [{
            "rule_id": RULE, "exception_atom": "pilot:diverting-indicator",
            "finding": "ABSENT_IN_DECLARED_SCOPE",
            "evidence_ids": ["pilot:ev-indicator"],
            "scope": {"id": "pilot:invented", "kind": "synthetic_fixture",
                      "declared_items": ["pilot:invented"],
                      "checked_items": ["pilot:invented"]},
        }]
        output = execute("present", manual=forged)
        self.assertEqual(output["derivation_refused"]["code"], "PINNED_INDEX_MODE_INCOMPLETE")
        self.assertIsNone(output["usul_result"])

    def test_strict_mode_requires_all_gates_and_source_index(self):
        for kwargs in ({"index": None},
                       {"semantic": False},
                       {"evidence": False},
                       {"strict": False}):
            with self.subTest(kwargs=kwargs):
                output = execute(**kwargs)
                self.assertEqual(output["derivation_refused"]["code"],
                                 "PINNED_INDEX_MODE_INCOMPLETE")

    def test_missing_p0_source_binding_rejected(self):
        modified = example_bundle()
        modified["sources"][1]["content_sha256"] = "0" * 64
        output = execute("absent", bundle=modified)
        self.assertEqual(output["derivation_refused"]["code"],
                         "PINNED_SOURCE_INDEX_REJECTED")

    def test_direct_exception_boolean_cannot_override_index(self):
        result = execute("absent", facts=scenarios()["fully_declared_no_indicator"])
        self.assertEqual(result["derivation_refused"]["code"], "UNSCOPED_EXCEPTION_FACT_REFUSED")

    def test_cli_requires_pin_and_prints_safe_ascii_json(self):
        repo = Path(__file__).resolve().parents[3]
        with tempfile.TemporaryDirectory() as temp:
            paths = [Path(temp) / name for name in ("bundle.json", "specs.json", "facts.json")]
            bundle = example_bundle()
            for p, data in zip(paths, (bundle, example_spec(bundle),
                                       scenarios()["indicator_unknown"])):
                p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
            cli = [sys.executable, "-m", "engines.usul.p0_bridge",
                   *(str(p) for p in paths),
                   "--require-semantic-binding", "--require-evidence-exceptions",
                   "--require-pinned-scope-index", "--pinned-scope-index", "absent"]
            proc = subprocess.run(cli, cwd=repo, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
            decision = json.loads(proc.stdout)
            self.assertEqual(decision["pinned_scope_index_proof"]["checked_items"], 2)
            self.assertEqual(decision["exception_assessment_trace"][0]["finding"],
                             "ABSENT_IN_DECLARED_SCOPE")
            # The console-independent bytes are ASCII even though citations
            # themselves preserve Arabic when decoded as JSON.
            self.assertTrue(proc.stdout.isascii())
            bad = subprocess.run(cli[:-2] + ["--pinned-scope-index", "absent"],
                                 cwd=repo, capture_output=True, text=True)
            self.assertEqual(bad.returncode, 0)  # same parameters, same result
            self.assertEqual(json.loads(bad.stdout), decision)


if __name__ == "__main__":
    unittest.main()
