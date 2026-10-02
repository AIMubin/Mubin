from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from benchmark_campaign.core import dump_jsonl, load_jsonl, write_json
from benchmark_campaign.factory import (
    build_factory_plan,
    build_factory_tasks,
    build_source_index,
    enforce_partition_boundary,
    prepare_verifier_tasks,
    reconcile_factory,
)
from benchmark_campaign.source_cache import cache_filename, git_blob_sha


class FactoryTests(unittest.TestCase):
    def test_real_factory_plan_expands_exactly_1280_slots(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.json"
            plan = build_factory_plan(project, out)
            self.assertEqual(plan["slot_count"], 1280)
            self.assertEqual(plan["target_total"], 1280)
            self.assertEqual(plan["holdout_slots"], 384)
            self.assertEqual(plan["non_holdout_slots"], 896)
            risk3 = [s for s in plan["slots"] if s["risk_tier"] == 3]
            self.assertTrue(risk3)
            self.assertTrue(all(s["auto_promotion"] is False for s in risk3))

    def test_holdout_output_requires_custodian_and_external_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            with self.assertRaisesRegex(ValueError, "custodian_mode"):
                enforce_partition_boundary(root, "holdout", root / "x", False)
            with self.assertRaisesRegex(ValueError, "outside"):
                enforce_partition_boundary(root, "holdout", root / "x", True)
            external = Path(d) / "custodian" / "x"
            enforce_partition_boundary(root, "holdout", external, True)

    def _fixture(self, root: Path):
        (root / "config").mkdir(parents=True)
        (root / "sources").mkdir()
        cache = root / "source-cache"
        cache.mkdir()
        text1 = ("قال الإمام سمع من شيخه وهذا نص ثابت\n" * 40)
        text2 = ("مصدر حجز نهائي لا يستخدم في التطوير\n" * 40)
        b1 = text1.encode("utf-8")
        b2 = text2.encode("utf-8")
        write_json(root / "sources" / "source-registry.json", {
            "schema_version": 2,
            "sources": [
                {
                    "source_id": "s1", "work_id": "w1", "qualification_eligible": True,
                    "provider": "test", "source_repo": "test/repo", "source_path": "s1.txt",
                    "source_blob_sha": git_blob_sha(b1), "version_id": "v1", "repo_ref": "a" * 40,
                },
                {
                    "source_id": "s2", "work_id": "w2", "qualification_eligible": True,
                    "provider": "test", "source_repo": "test/repo", "source_path": "s2.txt",
                    "source_blob_sha": git_blob_sha(b2), "version_id": "v1", "repo_ref": "b" * 40,
                },
            ],
        })
        (cache / cache_filename("s1")).write_bytes(b1)
        write_json(root / "config" / "curation-plan.json", {
            "global_source_partition": {"holdout": ["s2"], "non_holdout": ["s1"]},
            "benchmarks": {
                "b1": {
                    "holdout_source_pool": ["s2"],
                    "non_holdout_source_pool": ["s1"],
                    "target_holdout": 1,
                    "target_non_holdout": 1,
                }
            },
        })
        write_json(root / "config" / "factory-policy.json", {
            "factory_version": 1,
            "benchmarks": {
                "b1": {
                    "risk_tier": 1,
                    "auto_promotion": True,
                    "candidate_keywords": ["سمع من"],
                }
            },
        })
        return cache, text1

    def test_source_index_verifies_pinned_bytes_and_builds_segments(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _ = self._fixture(root)
            out = root / "factory-work" / "index"
            report = build_source_index(root, cache, out, "non_holdout", False, 512, 64)
            self.assertEqual(report["source_count"], 1)
            self.assertGreater(report["segment_count"], 1)
            rows = load_jsonl(out / "segments.jsonl")
            self.assertTrue(rows)
            self.assertEqual({r["source_id"] for r in rows}, {"s1"})
            self.assertTrue(all(r["locator"].startswith("gitblob:") for r in rows))

    def _build_one_task(self, root: Path):
        cache, _ = self._fixture(root)
        index = root / "factory-work" / "index"
        build_source_index(root, cache, index, "non_holdout", False, 512, 64)
        plan = root / "factory-work" / "plan.json"
        write_json(plan, {
            "slots": [{
                "slot_id": "b1:non_holdout:s1:0001",
                "benchmark_id": "b1",
                "partition": "non_holdout",
                "anchor_source_id": "s1",
                "ordinal": 1,
                "task_type": "classification",
                "allowed_labels": ["yes", "no"],
                "auto_promotion": True,
                "risk_tier": 1,
                "visibility": "development_safe",
            }]
        })
        tasks = root / "factory-work" / "tasks.jsonl"
        report = build_factory_tasks(root, plan, index, tasks, "non_holdout", False)
        self.assertEqual(report["task_count"], 1)
        task = load_jsonl(tasks)[0]
        self.assertEqual(task["allowed_source_pool"], ["s1"])
        self.assertEqual(task["forbidden_source_pool"], ["s2"])
        return cache, tasks, task

    def test_verifier_task_is_blind_to_curator_gold_and_supports(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, tasks, task = self._build_one_task(root)
            curator = root / "factory-work" / "curator.jsonl"
            dump_jsonl(curator, [{
                "task_id": task["task_id"],
                "task_fingerprint": task["task_fingerprint"],
                "model_family": "family-a",
                "model_ref": "a@1",
                "status": "candidate",
                "candidate": {
                    "payload": {"input": {"pair": ["A", "B"]}, "gold": {"label": "yes"}},
                    "source_refs": [{"source_id": "s1", "excerpt": "secret-support"}],
                    "answer_provenance": {"supports": [{"support_text": "secret-support"}]},
                },
            }])
            out = root / "factory-work" / "verifier.jsonl"
            prepare_verifier_tasks(tasks, curator, out)
            row = load_jsonl(out)[0]
            self.assertEqual(row["candidate_input"], {"pair": ["A", "B"]})
            self.assertNotIn("candidate", row)
            self.assertNotIn("source_refs", row)
            self.assertNotIn("answer_provenance", row)

    def _candidate(self, task: dict, excerpt: str):
        return {
            "benchmark_id": task["benchmark_id"],
            "case_id": "case-1",
            "anchor_source_id": "s1",
            "family_id": "family-1",
            "gold_status": "source_attributed",
            "synthetic": False,
            "source_refs": [{
                "source_id": "s1",
                "locator": "test:s1:1",
                "excerpt": excerpt,
            }],
            "answer_provenance": {
                "answer_origin": "human_authored_source",
                "extraction_method": "ai",
                "human_reviewed": False,
                "source_verified": True,
                "mode": "direct_extract",
                "verbatim_answer": "سمع من شيخه",
                "supports": [{
                    "source_id": "s1",
                    "support_text": "سمع من شيخه",
                }],
            },
            "annotation": {
                "reviewers": [],
                "source_verified": True,
                "adjudicated": False,
                "adjudicator": None,
            },
            "payload": {
                "input": {"question": "هل ثبت السماع؟"},
                "gold": {"label": "yes"},
            },
        }

    def _responses(self, task: dict, excerpt: str, verifier_family: str = "family-b",
                   verifier_gold: str = "yes"):
        curator = {
            "task_id": task["task_id"],
            "task_fingerprint": task["task_fingerprint"],
            "model_family": "family-a",
            "model_ref": "a@1",
            "status": "candidate",
            "candidate": self._candidate(task, excerpt),
        }
        verifier = {
            "task_id": task["task_id"],
            "task_fingerprint": task["task_fingerprint"],
            "model_family": verifier_family,
            "model_ref": "b@1",
            "status": "candidate",
            "answer": {
                "gold": {"label": verifier_gold},
                "supports": [{
                    "source_id": "s1",
                    "locator": "test:s1:1",
                    "excerpt": excerpt,
                    "support_text": "سمع من شيخه",
                }],
            },
        }
        return curator, verifier

    def _reconcile(self, root: Path, task: dict, cache: Path, curator: dict, verifier: dict):
        tasks = root / "factory-work" / "tasks-reconcile.jsonl"
        cr = root / "factory-work" / "curator-reconcile.jsonl"
        vr = root / "factory-work" / "verifier-reconcile.jsonl"
        dump_jsonl(tasks, [task])
        dump_jsonl(cr, [curator])
        dump_jsonl(vr, [verifier])
        reviewed = root / "staging"
        adjudication = root / "factory-work" / "adjudication.jsonl"
        ledger = root / "factory-work" / "CURATION_LEDGER.jsonl"
        report = reconcile_factory(
            root, tasks, cr, vr, cache, reviewed, adjudication, ledger, False
        )
        return report, reviewed, adjudication, ledger

    def test_independent_exact_agreement_promotes_source_attributed_case(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, tasks, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            report, reviewed, adjudication, ledger = self._reconcile(
                root, task, cache, curator, verifier
            )
            self.assertEqual(report["promoted_count"], 1)
            self.assertEqual(report["adjudication_count"], 0)
            rows = load_jsonl(reviewed / "b1" / "reviewed.jsonl")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["factory_verification"]["agreement"], "exact_gold_match")
            self.assertEqual(load_jsonl(adjudication), [])
            ledger_rows = load_jsonl(ledger)
            self.assertEqual(ledger_rows[0]["outcome"], "promoted")
            self.assertNotIn('"label": "yes"', ledger.read_text(encoding="utf-8"))

    def test_same_model_family_routes_to_adjudication(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt, verifier_family="family-a")
            report, _, adjudication, _ = self._reconcile(root, task, cache, curator, verifier)
            self.assertEqual(report["promoted_count"], 0)
            self.assertEqual(load_jsonl(adjudication)[0]["reason"], "model_family_not_independent")

    def test_gold_disagreement_routes_to_adjudication(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt, verifier_gold="no")
            report, _, adjudication, _ = self._reconcile(root, task, cache, curator, verifier)
            self.assertEqual(report["promoted_count"], 0)
            self.assertEqual(load_jsonl(adjudication)[0]["reason"], "gold_disagreement")

    def test_risk_policy_can_force_human_or_authority_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            task["auto_promotion"] = False
            task["risk_tier"] = 3
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            report, _, adjudication, _ = self._reconcile(root, task, cache, curator, verifier)
            self.assertEqual(report["promoted_count"], 0)
            self.assertEqual(
                load_jsonl(adjudication)[0]["reason"],
                "policy_requires_human_or_authority_gate",
            )


if __name__ == "__main__":
    unittest.main()
