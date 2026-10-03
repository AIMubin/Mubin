from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from benchmark_campaign.core import dump_jsonl, load_json, load_jsonl, sha256_file, write_json
from benchmark_campaign.execution import (_validate_raw_adapter_rows, load_agent_execution_config, run_agent_execution)
from benchmark_campaign.factory import (
    build_factory_plan,
    build_factory_tasks,
    build_source_index,
    prepare_verifier_tasks,
)
from benchmark_campaign.freeze import _frozen_protocol_files
from benchmark_campaign.source_cache import cache_filename, git_blob_sha


ADAPTER = r"""
import json
import os
import sys

input_path = sys.argv[1]
output_path = sys.argv[2]
mode = sys.argv[3]
role = os.environ["MUBIN_AGENT_ROLE"]

rows = []
with open(input_path, encoding="utf-8") as fh:
    for line in fh:
        if not line.strip():
            continue
        task = json.loads(line)
        if role == "curator":
            row = {
                "task_id": task["task_id"],
                "status": "candidate",
                "candidate": {
                    "payload": {
                        "input": {"question": "هل ثبت السماع؟"},
                        "gold": {"label": "yes"}
                    }
                }
            }
        else:
            row = {
                "task_id": task["task_id"],
                "status": "candidate",
                "answer": {
                    "gold": {"label": "yes"},
                    "supports": []
                }
            }
        if mode == "spoof":
            row["model_family"] = "forged-family"
        rows.append(row)

with open(output_path, "w", encoding="utf-8", newline="\n") as fh:
    for row in rows:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
"""


class AgentExecutionTests(unittest.TestCase):
    def _fixture(self, root: Path):
        (root / "config").mkdir(parents=True)
        (root / "sources").mkdir()
        (root / "agents").mkdir()
        (root / "agents" / "CURATOR_CONTRACT.md").write_text("curator contract\n", encoding="utf-8")
        (root / "agents" / "VERIFIER_CONTRACT.md").write_text("verifier contract\n", encoding="utf-8")
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
                "evaluation": {"task_type": "classification", "labels": ["yes", "no"]},
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
        index = root / "factory-work" / "index"
        build_source_index(root, cache, index, "non_holdout", False, 512, 64)
        plan = root / "factory-work" / "plan.json"
        build_factory_plan(root, plan)
        tasks = root / "factory-work" / "tasks.jsonl"
        build_factory_tasks(root, plan, index, tasks, "non_holdout", False)

        adapter = root / "adapter.py"
        adapter.write_text(ADAPTER, encoding="utf-8")
        return cache, index, tasks, adapter

    def _config(self, root: Path, adapter: Path, role: str, family: str, mode: str = "ok"):
        path = root / f"{role}-{family}.json"
        write_json(path, {
            "schema_version": 1,
            "role": role,
            "model_family": family,
            "model_ref": f"{family}@test-revision",
            "adapter": {
                "command": [
                    sys.executable,
                    str(adapter),
                    "{input}",
                    "{output}",
                    mode,
                ],
                "env_allowlist": [],
                "artifacts": [adapter.relative_to(root).as_posix()],
            },
            "batch_size": 1,
            "timeout_seconds": 30,
            "max_attempts": 1,
        })
        return path

    def _run_curator(self, root: Path, index: Path, tasks: Path, adapter: Path,
                     family: str = "family-a"):
        config = self._config(root, adapter, "curator", family)
        out = root / "factory-work" / "curator-responses.jsonl"
        manifest = root / "factory-work" / "curator-run.json"
        report = run_agent_execution(
            root, "curator", tasks, index, config, out, manifest
        )
        return report, out, manifest

    def test_adapter_response_order_is_normalized_to_batch_order(self):
        batch = [
            {"task_id": "t1"},
            {"task_id": "t2"},
        ]
        rows = [
            {"task_id": "t2", "status": "no_candidate", "reason": "none"},
            {"task_id": "t1", "status": "no_candidate", "reason": "none"},
        ]
        checked = _validate_raw_adapter_rows(rows, batch, "curator")
        self.assertEqual([r["task_id"] for r in checked], ["t1", "t2"])

    def test_execution_protocol_is_part_of_freeze_surface(self):
        project = Path(__file__).resolve().parents[1]
        frozen = {p.name for p in _frozen_protocol_files(project)}
        self.assertIn("execution.py", frozen)
        self.assertIn("AGENT_EXECUTION.md", frozen)

    def test_curator_executor_stamps_identity_and_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            report, out, _ = self._run_curator(root, index, tasks, adapter)
            self.assertEqual(report["completed_task_count"], 1)
            row = load_jsonl(out)[0]
            task = load_jsonl(tasks)[0]
            self.assertEqual(row["task_fingerprint"], task["task_fingerprint"])
            self.assertEqual(row["model_family"], "family-a")
            self.assertEqual(row["model_ref"], "family-a@test-revision")
            self.assertRegex(row["execution_binding"]["config_sha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(row["execution_binding"]["raw_response_sha256"], r"^[a-f0-9]{64}$")
            self.assertRegex(row["execution_binding"]["adapter_command_sha256"], r"^[a-f0-9]{64}$")
            self.assertEqual(len(row["execution_binding"]["adapter_artifacts"]), 1)
            self.assertEqual(
                row["execution_binding"]["adapter_artifacts"][0]["sha256"],
                sha256_file(adapter),
            )

    def test_resume_rejects_changed_adapter_artifact_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            config = self._config(root, adapter, "curator", "family-a")
            out = root / "factory-work" / "responses.jsonl"
            manifest = root / "factory-work" / "run.json"
            run_agent_execution(root, "curator", tasks, index, config, out, manifest)
            adapter.write_text(ADAPTER + "\n# changed bytes\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "execution binding mismatch|manifest identity mismatch"):
                run_agent_execution(
                    root, "curator", tasks, index, config, out, manifest, resume=True
                )

    def test_resume_rejects_tampered_adapter_binding_in_existing_response(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            config = self._config(root, adapter, "curator", "family-a")
            out = root / "factory-work" / "responses.jsonl"
            manifest = root / "factory-work" / "run.json"
            run_agent_execution(root, "curator", tasks, index, config, out, manifest)
            row = load_jsonl(out)[0]
            row["execution_binding"]["adapter_artifacts"][0]["sha256"] = "0" * 64
            dump_jsonl(out, [row])
            with self.assertRaisesRegex(ValueError, "adapter artifact binding mismatch"):
                run_agent_execution(
                    root, "curator", tasks, index, config, out, manifest, resume=True
                )

    def test_execution_config_rejects_absolute_adapter_artifact_path(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            adapter = root / "adapter.py"
            adapter.write_text("print('x')\n", encoding="utf-8")
            cfg = root / "bad-absolute.json"
            write_json(cfg, {
                "schema_version": 1,
                "role": "curator",
                "model_family": "family-a",
                "model_ref": "family-a@test",
                "adapter": {
                    "command": ["python", str(adapter), "{input}", "{output}"],
                    "env_allowlist": [],
                    "artifacts": [str(adapter)],
                },
                "batch_size": 1,
                "timeout_seconds": 30,
                "max_attempts": 1,
            })
            with self.assertRaisesRegex(ValueError, "campaign-root-relative"):
                load_agent_execution_config(cfg, "curator")

    def test_adapter_cannot_spoof_model_identity(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            config = self._config(root, adapter, "curator", "family-a", "spoof")
            with self.assertRaisesRegex(RuntimeError, "executor-reserved fields"):
                run_agent_execution(
                    root, "curator", tasks, index, config,
                    root / "factory-work" / "responses.jsonl",
                    root / "factory-work" / "run.json",
                )

    def test_resume_is_idempotent_and_does_not_duplicate_responses(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            config = self._config(root, adapter, "curator", "family-a")
            out = root / "factory-work" / "responses.jsonl"
            manifest = root / "factory-work" / "run.json"
            run_agent_execution(root, "curator", tasks, index, config, out, manifest)
            report = run_agent_execution(
                root, "curator", tasks, index, config, out, manifest, resume=True
            )
            self.assertEqual(len(load_jsonl(out)), 1)
            self.assertEqual(report["completed_task_count"], 1)
            self.assertEqual(report["pending_task_count"], 0)

    def test_resume_rejects_changed_execution_config(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            config = self._config(root, adapter, "curator", "family-a")
            out = root / "factory-work" / "responses.jsonl"
            manifest = root / "factory-work" / "run.json"
            run_agent_execution(root, "curator", tasks, index, config, out, manifest)
            changed = self._config(root, adapter, "curator", "family-b")
            with self.assertRaisesRegex(ValueError, "model identity differs"):
                run_agent_execution(
                    root, "curator", tasks, index, changed, out, manifest, resume=True
                )

    def test_resume_rejects_tampered_existing_response_payload(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            config = self._config(root, adapter, "curator", "family-a")
            out = root / "factory-work" / "responses.jsonl"
            manifest = root / "factory-work" / "run.json"
            run_agent_execution(root, "curator", tasks, index, config, out, manifest)
            row = load_jsonl(out)[0]
            row["candidate"]["payload"]["input"]["question"] = "tampered after execution"
            dump_jsonl(out, [row])
            with self.assertRaisesRegex(ValueError, "raw payload hash mismatch"):
                run_agent_execution(
                    root, "curator", tasks, index, config, out, manifest, resume=True
                )

    def test_verifier_rejects_non_curator_independence_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            _, curator_out, curator_manifest = self._run_curator(
                root, index, tasks, adapter, "family-a"
            )
            verifier_tasks = root / "factory-work" / "verifier-tasks.jsonl"
            prepare_verifier_tasks(root, tasks, curator_out, verifier_tasks)
            fake = load_json(curator_manifest)
            fake["role"] = "verifier"
            fake_path = root / "factory-work" / "fake-prior.json"
            write_json(fake_path, fake)
            verifier_config = self._config(root, adapter, "verifier", "family-b")
            with self.assertRaisesRegex(ValueError, "must be a Curator execution manifest"):
                run_agent_execution(
                    root, "verifier", verifier_tasks, index, verifier_config,
                    root / "factory-work" / "verifier-responses.jsonl",
                    root / "factory-work" / "verifier-run.json",
                    independent_from_manifest=fake_path,
                )

    def test_execution_config_rejects_common_inline_secret_flags(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cfg = root / "bad.json"
            write_json(cfg, {
                "schema_version": 1,
                "role": "curator",
                "model_family": "family-a",
                "model_ref": "family-a@test",
                "adapter": {
                    "command": [
                        "adapter",
                        "--api-key=literal-secret",
                        "{input}",
                        "{output}",
                    ],
                    "env_allowlist": [],
                    "artifacts": ["adapter.py"],
                },
                "batch_size": 1,
                "timeout_seconds": 30,
                "max_attempts": 1,
            })
            with self.assertRaisesRegex(ValueError, "secret-bearing"):
                load_agent_execution_config(cfg, "curator")

    def test_verifier_rejects_same_model_family_before_adapter_call(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            _, curator_out, curator_manifest = self._run_curator(
                root, index, tasks, adapter, "family-a"
            )
            verifier_tasks = root / "factory-work" / "verifier-tasks.jsonl"
            prepare_verifier_tasks(root, tasks, curator_out, verifier_tasks)
            verifier_config = self._config(root, adapter, "verifier", "  FAMILY-A  ")
            with self.assertRaisesRegex(ValueError, "must differ"):
                run_agent_execution(
                    root, "verifier", verifier_tasks, index, verifier_config,
                    root / "factory-work" / "verifier-responses.jsonl",
                    root / "factory-work" / "verifier-run.json",
                    independent_from_manifest=curator_manifest,
                )

    def test_verifier_task_tamper_fails_self_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            _, curator_out, curator_manifest = self._run_curator(
                root, index, tasks, adapter, "family-a"
            )
            verifier_tasks = root / "factory-work" / "verifier-tasks.jsonl"
            prepare_verifier_tasks(root, tasks, curator_out, verifier_tasks)
            row = load_jsonl(verifier_tasks)[0]
            row["candidate_input"]["question"] = "tampered"
            dump_jsonl(verifier_tasks, [row])
            verifier_config = self._config(root, adapter, "verifier", "family-b")
            with self.assertRaisesRegex(ValueError, "verifier task fingerprint mismatch"):
                run_agent_execution(
                    root, "verifier", verifier_tasks, index, verifier_config,
                    root / "factory-work" / "verifier-responses.jsonl",
                    root / "factory-work" / "verifier-run.json",
                    independent_from_manifest=curator_manifest,
                )

    def test_verifier_executor_uses_distinct_family_and_stamps_original_fingerprint(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "campaign"
            root.mkdir()
            _, index, tasks, adapter = self._fixture(root)
            _, curator_out, curator_manifest = self._run_curator(
                root, index, tasks, adapter, "family-a"
            )
            verifier_tasks = root / "factory-work" / "verifier-tasks.jsonl"
            prepare_verifier_tasks(root, tasks, curator_out, verifier_tasks)
            verifier_config = self._config(root, adapter, "verifier", "family-b")
            out = root / "factory-work" / "verifier-responses.jsonl"
            manifest = root / "factory-work" / "verifier-run.json"
            report = run_agent_execution(
                root, "verifier", verifier_tasks, index, verifier_config, out, manifest,
                independent_from_manifest=curator_manifest,
            )
            self.assertEqual(report["completed_task_count"], 1)
            response = load_jsonl(out)[0]
            original = load_jsonl(tasks)[0]
            self.assertEqual(response["task_fingerprint"], original["task_fingerprint"])
            self.assertEqual(response["model_family"], "family-b")
            self.assertEqual(
                report["independent_curator_manifest_sha256"],
                sha256_file(curator_manifest),
            )
            self.assertEqual(
                report["independent_curator_model_family"],
                "family-a",
            )
            self.assertEqual(
                report["independent_curator_config_sha256"],
                load_json(curator_manifest)["config_sha256"],
            )


if __name__ == "__main__":
    unittest.main()
