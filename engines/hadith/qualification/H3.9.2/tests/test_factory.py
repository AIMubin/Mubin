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
    def test_real_factory_plan_preserves_1280_primary_slots_and_adds_reserves(self):
        project = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "plan.json"
            plan = build_factory_plan(project, out)
            self.assertEqual(plan["target_total"], 1280)
            self.assertEqual(plan["primary_slot_count"], 1280)
            self.assertEqual(plan["reserve_slots_per_primary"], 1)
            self.assertEqual(plan["reserve_slot_count"], 1280)
            self.assertEqual(plan["slot_count"], 2560)
            self.assertEqual(plan["holdout_slots"], 384)
            self.assertEqual(plan["non_holdout_slots"], 896)
            self.assertEqual(plan["candidate_holdout_slots"], 768)
            self.assertEqual(plan["candidate_non_holdout_slots"], 1792)

            primary = plan["slots"][:1280]
            self.assertTrue(all("candidate_slot_kind" not in x for x in primary))
            non_holdout_primary = [
                x for x in primary if x["partition"] == "non_holdout"
            ]
            self.assertEqual(len(non_holdout_primary), 896)
            self.assertEqual(
                non_holdout_primary[0]["slot_id"],
                "external-critical-commentary:non_holdout:openiti:0279Tirmidhi.Sunan:0001",
            )

            reserves = plan["slots"][1280:]
            self.assertTrue(reserves)
            self.assertTrue(
                all(x.get("candidate_slot_kind") == "reserve" for x in reserves)
            )
            self.assertTrue(
                all(
                    isinstance(x.get("replacement_for_slot_id"), str)
                    and x["replacement_for_slot_id"]
                    for x in reserves
                )
            )
            self.assertTrue(
                all(x.get("reserve_attempt") == 1 for x in reserves)
            )

            risk3 = [x for x in plan["slots"] if x["risk_tier"] == 3]
            self.assertTrue(risk3)
            self.assertTrue(all(x["auto_promotion"] is False for x in risk3))

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

    def test_real_primary_non_holdout_prefix_remains_legacy_offset_stable(self):
        project = Path(__file__).resolve().parents[1]
        plan = build_factory_plan(project)
        quotas = load_json(project / "config" / "curation-quotas.json")
        expected_ids = []
        for q in quotas["benchmarks"]:
            bid = q["benchmark_id"]
            for anchor in q["non_holdout"]["anchor_quotas"]:
                sid = anchor["anchor_source_id"]
                for ordinal in range(1, int(anchor["target_cases"]) + 1):
                    expected_ids.append(
                        f"{bid}:non_holdout:{sid}:{ordinal:04d}"
                    )
        actual_ids = [
            slot["slot_id"]
            for slot in plan["slots"]
            if slot["partition"] == "non_holdout"
        ][:896]
        self.assertEqual(actual_ids, expected_ids)
        self.assertTrue(all(":reserve:" not in x for x in actual_ids))

    def test_enabling_reserve_capacity_does_not_change_primary_task_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _ = self._fixture(root)
            quotas_path = root / "config" / "curation-quotas.json"
            quotas = load_json(quotas_path)
            quotas["candidate_reserve_policy"] = {
                "reserve_slots_per_primary": 0,
                "rule": "no reserve",
                "primary_slot_prefix_preserved": True,
            }
            quotas["total_candidate_slots"] = 2
            write_json(quotas_path, quotas)

            index = root / "factory-work" / "index"
            build_source_index(root, cache, index, "non_holdout", False, 512, 64)

            legacy_plan = root / "factory-work" / "legacy-plan.json"
            legacy_tasks = root / "factory-work" / "legacy-tasks.jsonl"
            build_factory_plan(root, legacy_plan)
            build_factory_tasks(
                root, legacy_plan, index, legacy_tasks, "non_holdout", False
            )
            legacy_primary = load_jsonl(legacy_tasks)[0]

            quotas["candidate_reserve_policy"]["reserve_slots_per_primary"] = 1
            quotas["candidate_reserve_policy"]["rule"] = "one reserve"
            quotas["total_candidate_slots"] = 4
            write_json(quotas_path, quotas)

            reserve_plan = root / "factory-work" / "reserve-plan.json"
            reserve_tasks = root / "factory-work" / "reserve-tasks.jsonl"
            build_factory_plan(root, reserve_plan)
            build_factory_tasks(
                root, reserve_plan, index, reserve_tasks, "non_holdout", False
            )
            reserve_primary = load_jsonl(reserve_tasks)[0]
            self.assertEqual(reserve_primary, legacy_primary)
            self.assertEqual(
                reserve_primary["task_fingerprint"],
                legacy_primary["task_fingerprint"],
            )

    def test_reserve_task_carries_explicit_replacement_binding(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _ = self._fixture(root)
            quotas_path = root / "config" / "curation-quotas.json"
            quotas = load_json(quotas_path)
            quotas["candidate_reserve_policy"] = {
                "reserve_slots_per_primary": 1,
                "rule": "test reserve",
                "primary_slot_prefix_preserved": True,
            }
            quotas["total_candidate_slots"] = 4
            write_json(quotas_path, quotas)

            index = root / "factory-work" / "index"
            build_source_index(root, cache, index, "non_holdout", False, 512, 64)
            plan_path = root / "factory-work" / "plan.json"
            plan = build_factory_plan(root, plan_path)
            self.assertEqual(plan["primary_slot_count"], 2)
            self.assertEqual(plan["reserve_slot_count"], 2)

            tasks_path = root / "factory-work" / "tasks.jsonl"
            report = build_factory_tasks(
                root, plan_path, index, tasks_path, "non_holdout", False
            )
            self.assertEqual(report["task_count"], 2)
            tasks = load_jsonl(tasks_path)
            primary, reserve = tasks
            self.assertNotIn("candidate_slot_kind", primary)
            self.assertEqual(reserve["candidate_slot_kind"], "reserve")
            self.assertEqual(reserve["replacement_for_slot_id"], primary["slot_id"])
            self.assertEqual(reserve["reserve_attempt"], 1)
            self.assertNotEqual(
                reserve["anchor_segment"]["segment_id"],
                primary["anchor_segment"]["segment_id"],
            )

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

    def _build_one_multilabel_task(self, root: Path):
        cache, _ = self._fixture(root)
        spec_path = root / "config" / "benchmark-spec.json"
        spec = load_json(spec_path)
        spec["benchmarks"][0]["evaluation"] = {
            "task_type": "multilabel",
            "labels": ["a", "b"],
        }
        write_json(spec_path, spec)
        index = root / "factory-work" / "index"
        build_source_index(root, cache, index, "non_holdout", False, 512, 64)
        plan = root / "factory-work" / "plan.json"
        build_factory_plan(root, plan)
        tasks = root / "factory-work" / "tasks.jsonl"
        report = build_factory_tasks(
            root, plan, index, tasks, "non_holdout", False
        )
        self.assertEqual(report["task_count"], 1)
        task = load_jsonl(tasks)[0]
        self.assertEqual(task["task_type"], "multilabel")
        self.assertEqual(task["allowed_labels"], ["a", "b"])
        return cache, tasks, task

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

    def test_verifier_task_allows_exact_public_allowed_labels_metadata(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, tasks, task = self._build_one_task(root)
            curator = root / "factory-work" / "curator.jsonl"
            candidate_input = {
                "question": "هل ثبت السماع؟",
                "allowed_labels": task["allowed_labels"],
            }
            dump_jsonl(curator, [{
                "task_id": task["task_id"],
                "task_fingerprint": task["task_fingerprint"],
                "model_family": "family-a",
                "model_ref": "a@1",
                "status": "candidate",
                "candidate": {
                    "payload": {
                        "input": candidate_input,
                        "gold": {"label": "yes"}
                    }
                },
            }])
            out = root / "factory-work" / "verifier.jsonl"
            report = prepare_verifier_tasks(root, tasks, curator, out)
            self.assertEqual(report["input_candidates"], 1)
            self.assertEqual(report["verifier_tasks"], 1)
            self.assertEqual(report["rejected_candidates"], 0)
            self.assertEqual(load_jsonl(out)[0]["candidate_input"], candidate_input)

    def test_verifier_task_records_answer_bearing_input_key_as_local_rejection(self):
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
            out = root / "factory-work" / "verifier.jsonl"
            report = prepare_verifier_tasks(root, tasks, curator, out)
            self.assertEqual(report["input_candidates"], 1)
            self.assertEqual(report["verifier_tasks"], 0)
            self.assertEqual(report["rejected_candidates"], 1)
            self.assertEqual(
                report["rejection_counts"],
                {"candidate_input_blindness": 1},
            )
            self.assertEqual(load_jsonl(out), [])

    def test_verifier_task_records_explicit_label_value_as_local_rejection(self):
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
            out = root / "factory-work" / "verifier.jsonl"
            report = prepare_verifier_tasks(root, tasks, curator, out)
            self.assertEqual(report["verifier_tasks"], 0)
            self.assertEqual(report["rejected_candidates"], 1)

    def test_verifier_task_rejects_modified_allowed_labels_as_local_rejection(self):
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
                        "input": {"allowed_labels": [task["allowed_labels"][0]]},
                        "gold": {"label": "yes"}
                    }
                },
            }])
            out = root / "factory-work" / "verifier.jsonl"
            report = prepare_verifier_tasks(root, tasks, curator, out)
            self.assertEqual(report["verifier_tasks"], 0)
            self.assertEqual(report["rejected_candidates"], 1)

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

    def _refresh_raw_response_hash(self, response: dict) -> None:
        raw = dict(response)
        raw.pop("task_fingerprint", None)
        raw.pop("model_family", None)
        raw.pop("model_ref", None)
        raw.pop("execution_binding", None)
        response["execution_binding"]["raw_response_sha256"] = sha256_bytes(
            canonical_json_bytes(raw)
        )

    def _reconcile(
        self, root: Path, task: dict, cache: Path,
        curator: dict, verifier: dict | None,
    ):
        tasks = root / "factory-work" / "tasks-reconcile.jsonl"
        cr = root / "factory-work" / "curator-reconcile.jsonl"
        vr = root / "factory-work" / "verifier-reconcile.jsonl"
        dump_jsonl(tasks, [task])
        dump_jsonl(cr, [curator])
        dump_jsonl(vr, [verifier] if verifier is not None else [])
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
            self.assertEqual(report["adjudication_reason_counts"], {})
            self.assertEqual(
                report["outcome_by_benchmark"],
                {"b1": {"promoted": 1}},
            )
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

    def test_multilabel_label_order_does_not_create_false_disagreement(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_multilabel_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            curator["candidate"]["payload"]["gold"] = {"labels": ["a", "b"]}
            verifier["answer"]["gold"] = {"labels": ["b", "a"]}
            self._refresh_raw_response_hash(curator)
            self._refresh_raw_response_hash(verifier)

            report, reviewed, adjudication, _ = self._reconcile(
                root, task, cache, curator, verifier
            )
            self.assertEqual(report["promoted_count"], 1)
            self.assertEqual(report["adjudication_count"], 0)
            self.assertEqual(load_jsonl(adjudication), [])
            row = load_jsonl(reviewed / "b1" / "reviewed.jsonl")[0]
            self.assertEqual(row["payload"]["gold"], {"labels": ["a", "b"]})
            self.assertEqual(
                row["factory_verification"]["agreement"],
                "exact_gold_match",
            )

    def test_curator_requested_adjudication_never_reaches_final_seal(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            curator["candidate"]["answer_provenance"]["mode"] = "adjudication_required"
            curator["candidate"]["answer_provenance"].pop("verbatim_answer", None)
            self._refresh_raw_response_hash(curator)

            report, reviewed, adjudication, _ = self._reconcile(
                root, task, cache, curator, verifier
            )
            self.assertEqual(report["promoted_count"], 0)
            self.assertEqual(report["adjudication_count"], 1)
            self.assertFalse((reviewed / "b1" / "reviewed.jsonl").exists())
            self.assertEqual(
                load_jsonl(adjudication)[0]["reason"],
                "curator_requested_adjudication",
            )
            self.assertEqual(
                report["adjudication_reason_counts"],
                {"curator_requested_adjudication": 1},
            )

    def test_curator_requested_adjudication_precedes_missing_verifier(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, _ = self._responses(task, excerpt)
            curator["candidate"]["answer_provenance"]["mode"] = "adjudication_required"
            curator["candidate"]["answer_provenance"].pop("verbatim_answer", None)
            self._refresh_raw_response_hash(curator)

            report, _, adjudication, _ = self._reconcile(
                root, task, cache, curator, None
            )
            self.assertEqual(report["promoted_count"], 0)
            self.assertEqual(report["adjudication_count"], 1)
            self.assertEqual(
                load_jsonl(adjudication)[0]["reason"],
                "curator_requested_adjudication",
            )
            self.assertEqual(
                report["adjudication_reason_counts"],
                {"curator_requested_adjudication": 1},
            )

    def test_same_source_multiple_supports_can_promote(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            cache, _, task = self._build_one_task(root)
            excerpt = "قال الإمام سمع من شيخه وهذا نص ثابت"
            curator, verifier = self._responses(task, excerpt)
            curator["candidate"]["answer_provenance"]["supports"].append({
                "source_id": "s1",
                "support_text": "قال الإمام",
            })
            verifier["answer"]["supports"].append({
                "source_id": "s1",
                "locator": self._factory_locator(task, excerpt),
                "excerpt": excerpt,
                "support_text": "قال الإمام",
            })
            self._refresh_raw_response_hash(curator)
            self._refresh_raw_response_hash(verifier)
            report, reviewed, adjudication, _ = self._reconcile(
                root, task, cache, curator, verifier
            )
            self.assertEqual(report["promoted_count"], 1)
            self.assertEqual(load_jsonl(adjudication), [])
            row = load_jsonl(reviewed / "b1" / "reviewed.jsonl")[0]
            self.assertEqual(len(row["source_refs"]), 1)
            self.assertEqual(len(row["answer_provenance"]["supports"]), 2)
            self.assertEqual(len(row["factory_verification"]["verifier_supports"]), 2)

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
            self._refresh_raw_response_hash(curator)
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
            self.assertEqual(
                report["adjudication_reason_counts"],
                {"model_family_not_independent": 1},
            )
            self.assertEqual(
                report["adjudication_reason_counts_by_benchmark"],
                {"b1": {"model_family_not_independent": 1}},
            )
            self.assertEqual(
                report["outcome_by_benchmark"],
                {"b1": {"adjudication": 1}},
            )

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
            self.assertEqual(
                report["adjudication_reason_counts"],
                {"gold_disagreement": 1},
            )

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
        self.assertEqual(
            _gold_contract_error({"labels": [1]}, multi),
            "multilabel_labels_must_be_strings",
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
            self._refresh_raw_response_hash(curator)
            self._refresh_raw_response_hash(verifier)
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
            curator["candidate"]["answer_provenance"]["mode"] = "adjudication_required"
            curator["candidate"]["answer_provenance"].pop("verbatim_answer", None)
            self._refresh_raw_response_hash(curator)
            report, _, adjudication, _ = self._reconcile(root, task, cache, curator, verifier)
            self.assertEqual(report["promoted_count"], 0)
            self.assertEqual(
                load_jsonl(adjudication)[0]["reason"],
                "policy_requires_human_or_authority_gate",
            )


if __name__ == "__main__":
    unittest.main()
