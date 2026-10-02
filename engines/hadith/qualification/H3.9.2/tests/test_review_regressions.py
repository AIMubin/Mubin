from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from benchmark_campaign.audit import _read_architecture_gate
from benchmark_campaign.core import dump_jsonl, load_json, write_json
from benchmark_campaign.curation import curate_reviewed_file
from benchmark_campaign.evaluate import _label_coverage_checks, _threshold_pass
from benchmark_campaign.holdout_seal import decrypt_gold_map, seal_holdout_rows
from benchmark_campaign.normalization import fingerprint_payload
from benchmark_campaign.source_cache import cache_filename, git_blob_sha
from benchmark_campaign.validate import _validate_annotation, validate_campaign


class ReviewRegressionTests(unittest.TestCase):
    def test_safety_metric_cannot_pass_with_zero_denominator(self):
        passed, checks = _threshold_pass(
            {"unsafe_merge_rate": 0.0},
            {"unsafe_merge_rate": {"max": 0.0}},
            {"unsafe_merge": 0},
            {"unsafe_merge": 1},
        )
        self.assertFalse(passed)
        self.assertTrue(any(x["metric"] == "unsafe_merge_denominator" and not x["passed"] for x in checks))

    def test_missing_gold_label_fails_coverage_gate(self):
        contract = {
            "labels": ["a", "b", "c"],
            "minimum_label_counts": {"a": 1, "b": 1, "c": 1},
        }
        passed, checks = _label_coverage_checks(contract, ["a", "b", "a"], "classification")
        self.assertFalse(passed)
        self.assertTrue(any(x["metric"] == "gold_label_count:c" and not x["passed"] for x in checks))

    def test_example_architecture_audit_never_qualifies(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = root / "architecture.json"
            write_json(p, {
                "schema_version": 1,
                "audit_kind": "example_only",
                "audit_id": "example-not-qualifying",
                "candidate_commit": "b" * 40,
                "frozen": False,
                "architecture_gate_passed": True,
                "evidence": [],
            })
            ok, evidence = _read_architecture_gate(root, p, "b" * 40)
            self.assertFalse(ok)
            self.assertFalse(evidence["verified"])

    def test_source_attributed_ai_extraction_does_not_require_fake_human_review(self):
        record = {
            "case_id": "x",
            "gold_status": "source_attributed",
            "answer_provenance": {
                "answer_origin": "human_authored_source",
                "extraction_method": "ai",
                "human_reviewed": False,
                "source_verified": True,
                "mode": "direct_extract",
            },
            "annotation": {
                "reviewers": [],
                "source_verified": True,
                "adjudicated": False,
                "adjudicator": None,
            },
        }
        self.assertEqual(_validate_annotation(record, "b"), [])

    def test_sealed_holdout_binds_answer_provenance(self):
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        from benchmark_campaign.core import canonical_json_bytes, sha256_bytes
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            excerpt = "قال أبو عيسى هذا حديث حسن صحيح"
            support_text = "هذا حديث حسن صحيح"
            excerpt_sha = hashlib.sha256(excerpt.encode()).hexdigest()
            support = {
                "source_id": "s1",
                "support_text": support_text,
                "support_text_sha256": hashlib.sha256(support_text.encode()).hexdigest(),
                "source_excerpt_sha256": excerpt_sha,
            }
            gold = {"label": "hasan_sahih"}
            ap = {
                "answer_origin": "human_authored_source",
                "extraction_method": "ai",
                "human_reviewed": False,
                "source_verified": True,
                "mode": "direct_extract",
                "verbatim_answer": "حسن صحيح",
                "supports": [support],
            }
            ap["gold_binding_sha256"] = sha256_bytes(canonical_json_bytes({
                "gold": gold, "supports": [support], "mode": "direct_extract"
            }))
            record = {
                "case_id": "c1",
                "content_fingerprint": "a" * 64,
                "source_ids": ["s1"],
                "family_id": "f1",
                "gold_status": "source_attributed",
                "answer_provenance": ap,
                "payload": {"input": {"q": "x"}, "gold": gold},
            }
            key = AESGCM.generate_key(bit_length=256)
            sealed = seal_holdout_rows(root, "campaign", "b1", [record], key)
            public_rows = sealed["public_rows"]
            self.assertEqual(decrypt_gold_map(root, "campaign", "b1", public_rows, key)["c1"], gold)
            public_rows[0]["answer_provenance"]["verbatim_answer"] = "تم العبث"
            with self.assertRaisesRegex(ValueError, "bind"):
                decrypt_gold_map(root, "campaign", "b1", public_rows, key)

    def test_tampered_source_cache_is_rejected_inside_curation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "sources").mkdir()
            cache = root / "source-cache"
            cache.mkdir()
            source_id = "s1"
            original = b"ORIGINAL SOURCE"
            write_json(root / "sources" / "source-registry.json", {
                "schema_version": 2,
                "sources": [{
                    "source_id": source_id,
                    "work_id": "w1",
                    "qualification_eligible": True,
                    "provider": "test",
                    "source_repo": "test/repo",
                    "source_path": "s1.txt",
                    "source_blob_sha": git_blob_sha(original),
                    "version_id": "v1",
                    "repo_ref": "a" * 40,
                }],
            })
            # The attacker places a different byte stream containing the desired fabricated excerpt.
            (cache / cache_filename(source_id)).write_bytes(b"FABRICATED EXCERPT")
            inp = root / "input.jsonl"
            dump_jsonl(inp, [{
                "case_id": "c1",
                "family_id": "f1",
                "gold_status": "source_attributed",
                "synthetic": False,
                "anchor_source_id": source_id,
                "source_refs": [{"source_id": source_id, "locator": "loc", "excerpt": "FABRICATED EXCERPT"}],
                "answer_provenance": {
                    "answer_origin": "human_authored_source",
                    "extraction_method": "ai",
                    "human_reviewed": False,
                    "source_verified": True,
                    "mode": "direct_extract",
                },
                "annotation": {"reviewers": [], "source_verified": True, "adjudicated": False, "adjudicator": None},
                "payload": {"input": {"q": "x"}, "gold": {"label": "yes"}},
            }])
            with self.assertRaisesRegex(ValueError, "pinned source cache hash mismatch"):
                curate_reviewed_file(root, "b1", inp, root / "out.jsonl", cache)

    def _minimal_partition_fixture(self, root: Path):
        (root / "config").mkdir()
        (root / "sources").mkdir()
        (root / "benchmarks" / "b1").mkdir(parents=True)
        spec = {
            "campaign_id": "x",
            "qualification": {
                "allowed_gold_status": ["reference_pilot"],
                "require_frozen_curation_plan": True,
                "require_frozen_curation_quotas": False,
            },
            "benchmarks": [{
                "id": "b1",
                "target_total": 2,
                "target_development": 1,
                "target_validation": 0,
                "target_holdout": 1,
                "min_unique_sources": 2,
                "min_holdout_sources": 1,
                "min_unique_families": 2,
                "min_holdout_families": 1,
            }],
        }
        write_json(root / "sources" / "source-registry.json", {
            "schema_version": 2,
            "sources": [
                {"source_id":"s-ho","work_id":"h","qualification_eligible":True,"provider":"t","source_repo":"r","source_path":"h","source_blob_sha":"1"*40,"version_id":"v","repo_ref":"a"*40},
                {"source_id":"s-dev","work_id":"d","qualification_eligible":True,"provider":"t","source_repo":"r","source_path":"d","source_blob_sha":"2"*40,"version_id":"v","repo_ref":"a"*40},
            ],
        })
        write_json(root / "config" / "curation-plan.json", {
            "campaign_id": "x",
            "global_source_partition": {"holdout":["s-ho"],"non_holdout":["s-dev"]},
            "benchmarks": {"b1": {
                "holdout_source_pool":["s-ho"],
                "non_holdout_source_pool":["s-dev"],
                "target_holdout":1,
                "target_non_holdout":1,
            }},
        })

        def rec(cid, split, source, family):
            excerpt = f"excerpt-{cid}"
            payload = {"input":{"text":cid},"gold":{"label":"yes"}}
            return {
                "benchmark_id":"b1","case_id":cid,"split":split,
                "source_ids":[source],"anchor_source_id":source,"family_id":family,
                "content_fingerprint":fingerprint_payload(payload),
                "gold_status":"reference_pilot","synthetic":False,
                "source_refs":[{"source_id":source,"locator":"loc","source_blob_sha":"1"*40 if source=="s-ho" else "2"*40,"excerpt":excerpt,"excerpt_sha256":hashlib.sha256(excerpt.encode()).hexdigest()}],
                "annotation":{"reviewers":["r"],"source_verified":True,"adjudicated":False,"adjudicator":None},
                "payload":payload,
            }
        return spec, rec

    def test_validator_rejects_swapped_preregistered_source_partition(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec, rec = self._minimal_partition_fixture(root)
            # Globally disjoint, but deliberately reversed relative to preregistration.
            dump_jsonl(root / "benchmarks" / "b1" / "records.jsonl", [
                rec("d","development","s-ho","fd"),
                rec("h","holdout","s-dev","fh"),
            ])
            report = validate_campaign(root, spec)
            codes = {x["code"] for x in report["campaign_violations"]}
            self.assertIn("curation_plan.record_partition_mismatch", codes)
            self.assertFalse(report["all_benchmarks_qualified"])


if __name__ == "__main__":
    unittest.main()
