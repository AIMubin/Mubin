from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from benchmark_campaign.core import canonical_json_bytes, dump_jsonl, load_json, load_jsonl, sha256_bytes, write_json
from benchmark_campaign.factory import (
    build_factory_plan,
    build_factory_tasks,
    build_source_index,
    enforce_partition_boundary,
    prepare_verifier_tasks,
    reconcile_factory,
    _gold_contract_error,
)
from benchmark_campaign.source_cache import cache_filename, git_blob_sha
from benchmark_campaign.validate import (_validate_factory_slot_binding, _validate_factory_verification, _validate_factory_risk_policy)


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
        write_json(root / "config" / "benchmark-spec.json", {
            "campaign_id": "fixture",
            "benchmarks": [{
                "id": "b1",
                "evaluation": {
                    "task_type": "classification",
                    "labels": ["yes", "no"],
                },
            }],
        })
        write_json(root / "config" / "curation-quotas.json", {
            "total_target": 2,
            "benchmarks": [{
                "benchmark_id": "b1",
                "non_holdout": {
                    "anchor_quotas": [{"anchor_source_id": "s1", "target_cases": 1}],
                },
                "holdout": {
                    "anchor_quotas": [{"anchor_source_id": "s2", "target_cases": 1}],
                },
            }],
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

    def _build_one_task(self, root: Path, risk_tier: int = 1, auto_promotion: bool = True):
        cache, _ = self._fixture(root)
        policy_path = root / "config" / "factory-policy.json"
        policy = load_json(policy_path)
        policy["benchmarks"]["b1"]["risk_tier"] = risk_tier
        policy["benchmarks"]["b1"]["auto_promotion"] = auto_promotion
        write_json(policy_path, policy)
        index = root / "factory-work" / "index"
        build_source_index(root, cache, index, "non_holdout", False, 512, 64)
        plan = root / "factory-work" / "plan.json"
        build_factory_plan(root, plan)
        tasks = root / "factory-work" / "tasks.jsonl"
        report = build_factory_tasks(root, plan, index, tasks, "non_holdout", False)
        self.assertEqual(report["task_count"], 1)
        task = load_jsonl(tasks)[0]
        self.assertEqual(task["allowed_source_pool"], ["s1"])
        self.assertEqual(task["forbidden_source_pool"], ["s2"])
        self.assertEqual(task["retrieval_scope"]["source_ids"], ["s1"])
        self.assertEqual(task["retrieval_scope"]["partition"], "non_holdout")
        self.assertEqual(task["retrieval_scope"]["access_mode"], "full_partition_index")
        self.assertRegex(task["retrieval_scope"]["segments_sha256"], r"^[a-f0-9]{64}$")
        self.assertRegex(task["retrieval_scope"]["index_manifest_sha256"], r"^[a-f0-9]{64}$")
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
            prepare_verifier_tasks(root, tasks, curator, out)
            row = load_jsonl(out)[0]
            self.assertEqual(row["candidate_input"], {"pair": ["A", "B"]})
            self.assertEqual(row["retrieval_scope"], task["retrieval_scope"])
            self.assertRegex(row["verifier_task_fingerprint"], r"^[a-f0-9]{64}$")
            unsigned = dict(row)
            unsigned.pop("verifier_task_fingerprint")
            self.assertEqual(
                row["verifier_task_fingerprint"],
                hashlib.sha256(
                    json.dumps(
                        unsigned, sort_keys=True, separators=(",", ":"), ensure_ascii=False
                    ).encode("utf-8")
                ).hexdigest(),
            )
            self.assertNotIn("candidate", row)
            self.assertNotIn("source_refs", row)
            self.assertNotIn("answer_provenance", row)

    def test_verifier_task_rejects_answer_bearing_input_key(self):
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
                    "payload": {
                        "input": {"pair": ["A", "B"], "gold_label": "yes"},
                        "gold": {"label": "yes"}
                    }
                },
            }])
            with self.assertRaisesRegex(ValueError, "violates verifier blindness"):
                prepare_verifier_tasks(
                    root, tasks, curator, root / "factory-work" / "verifier.jsonl"
                )

    def test_verifier_task_rejects_explicit_label_value_in_input(self):
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
                    "payload": {
                        "input": {"pair": ["A", "B"], "hint": "yes"},
                        "gold": {"label": "yes"}
                    }
                },
            }])
            with self.assertRaisesRegex(ValueError, "explicit benchmark label value"):
                prepare_verifier_tasks(
                    root, tasks, curator, root / "factory-work" / "verifier.jsonl"
                )

    def test_model_family_independence_normalizes_case_and_whitespace(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(
                task, excerpt, verifier_family="  FAMILY-A  "
            )
            report, _, adjudication, _ = self._reconcile(
                root, task, cache, curator, verifier
            )
            self.assertEqual(report["promoted_count"], 0)
            self.assertEqual(
                load_jsonl(adjudication)[0]["reason"],
                "model_family_not_independent",
            )

    def _factory_locator(self, task: dict, excerpt: str) -> str:
        blob = task["anchor_segment"]["source_blob_sha"]
        return f"gitblob:{blob}#char=0:{len(excerpt)}"

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
                "locator": self._factory_locator(task, excerpt),
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
        def stamp(raw: dict, family: str, model_ref: str, seed: str):
            row = dict(raw)
            row["task_fingerprint"] = task["task_fingerprint"]
            row["model_family"] = family
            row["model_ref"] = model_ref
            row["execution_binding"] = {
                "protocol_version": 1,
                "config_sha256": seed * 64,
                "batch_id": seed * 24,
                "raw_response_sha256": sha256_bytes(canonical_json_bytes(raw)),
                "adapter_command_sha256": seed * 64,
                "adapter_artifacts": [{
                    "path": "adapters/test.py",
                    "sha256": seed * 64,
                    "size_bytes": 123,
                }],
            }
            return row
        curator = stamp({
            "task_id": task["task_id"],
            "status": "candidate",
            "candidate": self._candidate(task, excerpt),
        }, "family-a", "a@1", "a")
        verifier = stamp({
            "task_id": task["task_id"],
            "status": "candidate",
            "answer": {
                "gold": {"label": verifier_gold},
                "supports": [{
                    "source_id": "s1",
                    "locator": self._factory_locator(task, excerpt),
                    "excerpt": excerpt,
                    "support_text": "سمع من شيخه",
                }],
            },
        }, verifier_family, "b@1", "b")
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

    def test_reconcile_rejects_tampered_raw_response_binding(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            curator["candidate"]["payload"]["input"]["question"] = "tampered"
            with self.assertRaisesRegex(ValueError, "raw response hash mismatch"):
                self._reconcile(root, task, cache, curator, verifier)

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
            self.assertEqual(rows[0]["factory_verification"]["risk_tier"], 1)
            self.assertEqual(rows[0]["factory_verification"]["factory_version"], 1)
            self.assertEqual(rows[0]["factory_slot_id"], task["slot_id"])
            self.assertEqual(rows[0]["factory_task_id"], task["slot_id"])
            self.assertRegex(
                rows[0]["factory_verification"]["slot_binding_sha256"],
                r"^[a-f0-9]{64}$",
            )
            self.assertRegex(rows[0]["factory_verification"]["curator_response_sha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(rows[0]["factory_verification"]["verifier_response_sha256"], r"^[a-f0-9]{64}$")
            self.assertNotEqual(
                rows[0]["factory_verification"]["curator_model_family"],
                rows[0]["factory_verification"]["verifier_model_family"],
            )
            self.assertEqual(load_jsonl(adjudication), [])
            ledger_rows = load_jsonl(ledger)
            self.assertEqual(ledger_rows[0]["outcome"], "promoted")
            self.assertNotIn('"label": "yes"', ledger.read_text(encoding="utf-8"))

    def test_invalid_curator_locator_routes_to_adjudication(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            blob = task["anchor_segment"]["source_blob_sha"]
            curator["candidate"]["source_refs"][0]["locator"] = (
                f"gitblob:{blob}#char=1:{len(excerpt) + 1}"
            )
            report, _, adjudication, _ = self._reconcile(
                root, task, cache, curator, verifier
            )
            self.assertEqual(report["promoted_count"], 0)
            self.assertEqual(
                load_jsonl(adjudication)[0]["reason"],
                "curator_locator_invalid",
            )

    def test_slot_binding_tamper_fails_validator(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            report, reviewed, _, _ = self._reconcile(
                root, task, cache, curator, verifier
            )
            self.assertEqual(report["promoted_count"], 1)
            row = load_jsonl(reviewed / "b1" / "reviewed.jsonl")[0]
            row["split"] = "development"
            self.assertEqual(_validate_factory_slot_binding(root, row, "b1"), [])
            row["factory_verification"]["slot_binding_sha256"] = "0" * 64
            codes = {
                v.code for v in _validate_factory_slot_binding(root, row, "b1")
            }
            self.assertIn("qualification.factory_slot_binding", codes)

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

    def test_holdout_source_index_rejects_internal_cache_even_with_external_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _ = self._fixture(root)
            external_out = Path(d) / "custodian" / "index"
            with self.assertRaisesRegex(ValueError, "outside"):
                build_source_index(root, cache, external_out, "holdout", True, 512, 64)

    def test_holdout_verifier_preparation_requires_external_inputs_and_output(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            tasks = root / "holdout-tasks.jsonl"
            curator = root / "holdout-curator.jsonl"
            out = Path(d) / "custodian" / "verifier.jsonl"
            dump_jsonl(tasks, [{
                "task_id": "h1",
                "task_fingerprint": "a" * 64,
                "partition": "holdout",
            }])
            dump_jsonl(curator, [])
            with self.assertRaisesRegex(ValueError, "outside"):
                prepare_verifier_tasks(
                    root, tasks, curator, out,
                    partition="holdout", custodian_mode=True
                )

    def test_duplicate_factory_task_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            tasks = root / "tasks.jsonl"
            curator = root / "curator.jsonl"
            out = root / "verifier.jsonl"
            row = {
                "task_id": "dup",
                "task_fingerprint": "a" * 64,
                "partition": "non_holdout",
            }
            dump_jsonl(tasks, [row, row])
            dump_jsonl(curator, [])
            with self.assertRaisesRegex(ValueError, "duplicate factory task IDs"):
                prepare_verifier_tasks(root, tasks, curator, out)

    def test_task_fingerprint_tamper_is_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, tasks, task = self._build_one_task(root)
            rows = load_jsonl(tasks)
            rows[0]["risk_tier"] = 3
            dump_jsonl(tasks, rows)
            curator = root / "factory-work" / "curator.jsonl"
            dump_jsonl(curator, [])
            with self.assertRaisesRegex(ValueError, "task fingerprint mismatch"):
                prepare_verifier_tasks(root, tasks, curator, root / "factory-work" / "v.jsonl")

    def test_rehashed_task_policy_tamper_is_still_rejected_against_frozen_plan(self):
        from benchmark_campaign.core import canonical_json_bytes, sha256_bytes
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, tasks, _ = self._build_one_task(root)
            rows = load_jsonl(tasks)
            rows[0]["risk_tier"] = 3
            unsigned = dict(rows[0])
            unsigned.pop("task_fingerprint", None)
            rows[0]["task_fingerprint"] = sha256_bytes(canonical_json_bytes(unsigned))
            dump_jsonl(tasks, rows)
            curator = root / "factory-work" / "curator.jsonl"
            dump_jsonl(curator, [])
            with self.assertRaisesRegex(ValueError, "differs from frozen slot"):
                prepare_verifier_tasks(root, tasks, curator, root / "factory-work" / "v.jsonl")

    def test_factory_plan_tamper_is_rejected_before_task_generation(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            work = Path(d)
            plan_path = work / "plan.json"
            plan = build_factory_plan(project, plan_path)
            plan["slots"][0]["auto_promotion"] = not plan["slots"][0]["auto_promotion"]
            write_json(plan_path, plan)
            index = work / "index"
            index.mkdir()
            dump_jsonl(index / "segments.jsonl", [])
            write_json(index / "INDEX_MANIFEST.json", {
                "partition": "non_holdout",
                "segments_sha256": hashlib.sha256((index / "segments.jsonl").read_bytes()).hexdigest(),
            })
            with self.assertRaisesRegex(ValueError, "factory plan does not match"):
                build_factory_tasks(project, plan_path, index, work / "tasks.jsonl", "non_holdout")

    def test_source_index_hash_tamper_is_rejected_before_task_generation(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _ = self._fixture(root)
            index = root / "factory-work" / "index"
            build_source_index(root, cache, index, "non_holdout", False, 512, 64)
            plan = root / "factory-work" / "plan.json"
            # Use a fixture-local plan that is intentionally not used here; index validation
            # is exercised after replacing build_factory_plan inputs below.
            build_factory_plan(root, plan)
            with (index / "segments.jsonl").open("a", encoding="utf-8") as fh:
                fh.write("{}\n")
            with self.assertRaisesRegex(ValueError, "source index segments hash mismatch"):
                build_factory_tasks(root, plan, index, root / "factory-work" / "tasks.jsonl", "non_holdout")

    def test_gold_contract_rejects_out_of_contract_labels(self):
        task = {"task_type": "classification", "allowed_labels": ["yes", "no"]}
        self.assertIsNone(_gold_contract_error({"label": "yes"}, task))
        self.assertEqual(
            _gold_contract_error({"label": "maybe"}, task),
            "classification_label_outside_contract",
        )
        multi = {"task_type": "multilabel", "allowed_labels": ["a", "b"]}
        self.assertEqual(
            _gold_contract_error({"labels": ["a", "c"]}, multi),
            "multilabel_label_outside_contract",
        )

    def test_out_of_contract_gold_routes_to_adjudication(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            curator["candidate"]["payload"]["gold"] = {"label": "outside"}
            verifier["answer"]["gold"] = {"label": "outside"}
            report, _, adjudication, _ = self._reconcile(root, task, cache, curator, verifier)
            self.assertEqual(report["promoted_count"], 0)
            self.assertTrue(
                load_jsonl(adjudication)[0]["reason"].startswith("curator_gold_contract_invalid:")
            )

    def test_unreviewed_ai_source_attributed_requires_factory_verification(self):
        record = {
            "case_id": "x",
            "gold_status": "source_attributed",
            "source_ids": ["s1"],
            "answer_provenance": {
                "extraction_method": "ai",
                "human_reviewed": False,
            },
        }
        codes = {v.code for v in _validate_factory_verification(record, "b1")}
        self.assertIn("qualification.factory_verification_missing", codes)

    def test_risk_tier_three_blocks_unreviewed_ai_even_with_factory_metadata(self):
        record = {
            "case_id": "x",
            "gold_status": "source_attributed",
            "answer_provenance": {
                "extraction_method": "ai",
                "human_reviewed": False,
            },
        }
        codes = {v.code for v in _validate_factory_risk_policy(record, "b1", {"risk_tier": 3})}
        self.assertIn("qualification.risk_tier_human_gate", codes)
        record["answer_provenance"]["human_reviewed"] = True
        self.assertEqual(_validate_factory_risk_policy(record, "b1", {"risk_tier": 3}), [])

    def test_risk_policy_can_force_human_or_authority_gate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root, risk_tier=3, auto_promotion=False)
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
