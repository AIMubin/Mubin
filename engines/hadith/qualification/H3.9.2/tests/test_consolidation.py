from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmark_campaign import consolidation
from benchmark_campaign.core import canonical_json_bytes, load_json, load_jsonl, sha256_bytes, sha256_file
from benchmark_campaign.factory import _verifier_task_from_curator
from benchmark_campaign.source_cache import cache_filename, git_blob_sha
from benchmark_campaign.normalization import fingerprint_payload


TEST_SOURCE_TEXT = "anchor evidence"
TEST_BLOB_SHA = git_blob_sha(TEST_SOURCE_TEXT.encode("utf-8"))


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _task(slot_id: str, anchor: str = "s1") -> dict:
    row = {
        "task_id": slot_id,
        "slot_id": slot_id,
        "benchmark_id": "b1",
        "partition": "non_holdout",
        "visibility": "source_attributed",
        "risk_tier": 1,
        "auto_promotion": True,
        "anchor_source_id": anchor,
        "allowed_source_pool": ["s1"],
        "forbidden_source_pool": ["h1"],
        "allowed_labels": ["yes", "no"],
        "task_type": "classification",
        "retrieval_terms": ["evidence"],
        "retrieval_scope": {
            "access_mode": "full_partition_index",
            "partition": "non_holdout",
            "source_ids": ["s1"],
            "segments_sha256": "1" * 64,
            "index_manifest_sha256": "2" * 64,
        },
        "anchor_segment": {
            "source_id": anchor,
            "text": "anchor evidence",
            "locator": "test:anchor",
        },
        "instructions": {
            "contract": "agents/CURATOR_CONTRACT.md",
            "require_human_authored_support": True,
            "no_ai_opinion_as_gold": True,
            "return_no_candidate_when_unsupported": True,
        },
    }
    row["task_fingerprint"] = sha256_bytes(canonical_json_bytes(row))
    return row


def _stamped(task: dict, raw: dict, family: str) -> dict:
    row = dict(raw)
    row["task_fingerprint"] = task["task_fingerprint"]
    row["model_family"] = family
    row["model_ref"] = f"{family}-ref"
    row["execution_binding"] = {
        "protocol_version": 1,
        "config_sha256": "c" * 64,
        "batch_id": "a" * 24,
        "raw_response_sha256": sha256_bytes(canonical_json_bytes(raw)),
        "adapter_command_sha256": "d" * 64,
        "adapter_artifacts": [{
            "path": "adapters/chat_completions.py",
            "sha256": "e" * 64,
            "size_bytes": 1,
        }],
    }
    return row


def _plan(slot_ids: list[str]) -> dict:
    slots = [
        {
            "slot_id": slot_id,
            "benchmark_id": "b1",
            "partition": "non_holdout",
            "anchor_source_id": "s1",
        }
        for slot_id in slot_ids
    ]
    slots.extend(
        {
            "slot_id": f"{slot_id}:reserve:01",
            "benchmark_id": "b1",
            "partition": "non_holdout",
            "anchor_source_id": "s1",
            "candidate_slot_kind": "reserve",
            "replacement_for_slot_id": slot_id,
            "reserve_attempt": 1,
        }
        for slot_id in slot_ids
    )
    return {"slots": slots}


class ConsolidationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "root"
        self.root.mkdir()
        (self.root / "config").mkdir()
        _write_json(
            self.root / "config" / "factory-policy.json",
            {"factory_version": 1},
        )
        (self.root / "sources").mkdir()
        _write_json(
            self.root / "sources" / "source-registry.json",
            {
                "schema_version": 2,
                "sources": [{
                    "source_id": "s1",
                    "qualification_eligible": True,
                    "source_blob_sha": TEST_BLOB_SHA,
                    "source_repo": "test/repo",
                    "source_path": "s1.txt",
                    "repo_ref": "a" * 40,
                }],
            },
        )
        self.source_cache = Path(self.tmp.name) / "source-cache"
        self.source_cache.mkdir()
        (self.source_cache / cache_filename("s1")).write_text(
            TEST_SOURCE_TEXT, encoding="utf-8"
        )
        self.evidence_root = Path(self.tmp.name) / "evidence"
        self.evidence_root.mkdir()

    def tearDown(self):
        self.tmp.cleanup()

    def _evidence(
        self,
        name: str,
        tasks: list[dict],
        outcomes: dict[str, tuple[str, str | None]],
        *,
        curator_rejections: dict[str, str] | None = None,
        verifier_task_ids: set[str] | None = None,
        verifier_rejections: dict[str, str] | None = None,
        run_id: int = 1001,
        sha: str = "a" * 40,
        task_offset: int = 0,
        artifact_id: int | None = None,
    ) -> Path:
        curator_rejections = curator_rejections or {}
        verifier_task_ids = verifier_task_ids or set()
        verifier_rejections = verifier_rejections or {}
        evidence = self.evidence_root / name
        bundle = evidence / "source-bearing"
        bundle.mkdir(parents=True)

        _write_json(evidence / "ORIGIN.json", {
            "github_run_id": run_id,
            "github_run_attempt": 1,
            "conclusion": "success",
            "head_branch": "main",
            "head_sha": sha,
            "workflow_path": ".github/workflows/h392-curation-campaign.yml",
            "artifact_id": artifact_id if artifact_id is not None else run_id + 100,
            "artifact_name": f"h392-curation-chunk-{task_offset}-{len(tasks)}",
            "artifact_sha256": "b" * 64,
            "encrypted_bundle_sha256": "f" * 64,
        })

        _write_jsonl(bundle / "curator-tasks.jsonl", tasks)
        curator_responses = []
        for task in tasks:
            tid = task["task_id"]
            if tid in curator_rejections:
                continue
            outcome, _reason = outcomes[tid]
            if outcome == "skipped":
                raw = {
                    "task_id": tid,
                    "status": "no_candidate",
                    "reason": "unsupported",
                }
            else:
                candidate_input = (
                    {"text": f"candidate-{tid}"}
                    if tid in verifier_task_ids
                    else {"label": "yes"}
                )
                answer_provenance = {
                    "answer_origin": "human_authored_source",
                    "extraction_method": "ai",
                    "source_verified": True,
                    "human_reviewed": False,
                    "mode": (
                        "adjudication_required"
                        if _reason == "curator_requested_adjudication"
                        else "direct_extract"
                    ),
                    "supports": [{
                        "source_id": task["anchor_source_id"],
                        "support_text": "anchor evidence",
                    }],
                    "verbatim_answer": "anchor evidence",
                }
                raw = {
                    "task_id": tid,
                    "status": "candidate",
                    "candidate": {
                        "benchmark_id": task["benchmark_id"],
                        "case_id": f"case-{tid}",
                        "anchor_source_id": task["anchor_source_id"],
                        "family_id": f"family-{tid}",
                        "annotation": {
                            "reviewers": [],
                            "source_verified": True,
                            "adjudicated": False,
                            "adjudicator": None,
                        },
                        "curation_note": f"note-{tid}",
                        "family_id": f"family-{tid}",
                        "gold_status": "source_attributed",
                        "synthetic": False,
                        "source_refs": [{
                            "source_id": task["anchor_source_id"],
                            "locator": "gitblob:" + TEST_BLOB_SHA + "#char=0:15",
                            "excerpt": "anchor evidence",
                        }],
                        "answer_provenance": answer_provenance,
                        "annotation": {
                            "reviewers": [],
                            "source_verified": True,
                            "adjudicated": False,
                            "adjudicator": None,
                        },
                        "payload": {
                            "input": candidate_input,
                            "gold": {"label": "yes"},
                        },
                    },
                }
            curator_responses.append(_stamped(task, raw, "curator-family"))
        _write_jsonl(bundle / "curator-responses.jsonl", curator_responses)
        curator_rejection_rows = [
            {
                "task_id": tid,
                "task_fingerprint": next(
                    t["task_fingerprint"] for t in tasks if t["task_id"] == tid
                ),
                "error_code": code,
            }
            for tid, code in curator_rejections.items()
        ]
        _write_json(bundle / "curator-run.json", {
            "role": "curator",
            "partition": "non_holdout",
            "task_count": len(tasks),
            "attempted_task_count": len(curator_responses) + len(curator_rejection_rows),
            "completed_task_count": len(curator_responses),
            "rejected_task_count": len(curator_rejection_rows),
            "pending_task_count": 0,
            "tasks_sha256": sha256_file(bundle / "curator-tasks.jsonl"),
            "output_sha256": sha256_file(bundle / "curator-responses.jsonl"),
            "rejections": curator_rejection_rows,
        })

        curator_response_by_id = {
            str(row["task_id"]): row for row in curator_responses
        }
        verifier_tasks = []
        for tid in sorted(verifier_task_ids):
            task = next(task for task in tasks if task["task_id"] == tid)
            verifier_task, blind_error = _verifier_task_from_curator(
                task, curator_response_by_id[tid]
            )
            if blind_error is not None or verifier_task is None:
                raise AssertionError(
                    f"test fixture failed to project verifier task {tid}: {blind_error}"
                )
            verifier_tasks.append(verifier_task)
        _write_jsonl(bundle / "verifier-tasks.jsonl", verifier_tasks)
        verifier_responses = [
            _stamped(
                next(task for task in tasks if task["task_id"] == tid),
                {
                    "task_id": tid,
                    "status": "candidate",
                    "answer": {
                        "gold": {"label": "yes"},
                        "supports": [{
                            "source_id": next(
                                task for task in tasks if task["task_id"] == tid
                            )["anchor_source_id"],
                            "locator": "gitblob:" + TEST_BLOB_SHA + "#char=0:15",
                            "excerpt": "anchor evidence",
                            "support_text": "anchor evidence",
                        }],
                    },
                },
                "verifier-family",
            )
            for tid in sorted(verifier_task_ids)
            if tid not in verifier_rejections
        ]
        _write_jsonl(bundle / "verifier-responses.jsonl", verifier_responses)
        if verifier_task_ids:
            rejection_rows = [
                {
                    "task_id": tid,
                    "task_fingerprint": next(
                        task["task_fingerprint"] for task in tasks if task["task_id"] == tid
                    ),
                    "error_code": code,
                }
                for tid, code in verifier_rejections.items()
            ]
            _write_json(bundle / "verifier-run.json", {
                "role": "verifier",
                "partition": "non_holdout",
                "task_count": len(verifier_task_ids),
                "attempted_task_count": len(verifier_responses) + len(rejection_rows),
                "completed_task_count": len(verifier_responses),
                "rejected_task_count": len(rejection_rows),
                "pending_task_count": 0,
                "tasks_sha256": sha256_file(bundle / "verifier-tasks.jsonl"),
                "output_sha256": sha256_file(bundle / "verifier-responses.jsonl"),
                "rejections": rejection_rows,
            })

        curator_by_id = {str(row["task_id"]): row for row in curator_responses}
        verifier_by_id = {str(row["task_id"]): row for row in verifier_responses}

        ledger = []
        adjudication = []
        reviewed = []
        counts = {"promoted": 0, "adjudication": 0, "skipped": 0}
        for task in tasks:
            tid = task["task_id"]
            outcome, reason = outcomes[tid]
            counts[outcome] += 1
            case_id = f"case-{tid}" if outcome == "promoted" else None
            curator_response = curator_by_id.get(tid)
            verifier_response = verifier_by_id.get(tid)
            verifier_used = (
                None
                if outcome == "adjudication"
                and reason == "curator_requested_adjudication"
                else verifier_response
            )
            ledger.append({
                "task_id": tid,
                "task_fingerprint": task["task_fingerprint"],
                "benchmark_id": task["benchmark_id"],
                "partition": "non_holdout",
                "outcome": outcome,
                "reason": reason,
                "case_id": case_id,
                "curator_response_sha256": (
                    sha256_bytes(canonical_json_bytes(curator_response))
                    if curator_response is not None else None
                ),
                "verifier_response_sha256": (
                    sha256_bytes(canonical_json_bytes(verifier_used))
                    if verifier_used is not None else None
                ),
                "curator_model_family": (
                    curator_response.get("model_family")
                    if curator_response is not None else None
                ),
                "verifier_model_family": (
                    verifier_used.get("model_family")
                    if verifier_used is not None else None
                ),
            })
            if outcome == "adjudication":
                adjudication.append({"task_id": tid, "reason": reason})
            if outcome == "promoted":
                curator_response = curator_by_id[tid]
                verifier_response = verifier_by_id[tid]
                candidate = json.loads(json.dumps(
                    curator_response["candidate"], ensure_ascii=False
                ))
                candidate_refs = candidate["source_refs"]
                reviewed_refs = []
                for ref in candidate_refs:
                    excerpt = ref["excerpt"]
                    reviewed_ref = dict(ref)
                    reviewed_ref["source_blob_sha"] = TEST_BLOB_SHA
                    reviewed_ref["excerpt_sha256"] = sha256_bytes(
                        excerpt.encode("utf-8")
                    )
                    reviewed_refs.append(reviewed_ref)
                ap = dict(candidate["answer_provenance"])
                normalized_supports = []
                for support in ap["supports"]:
                    sid = support["source_id"]
                    support_text = support["support_text"]
                    ref = next(x for x in reviewed_refs if x["source_id"] == sid)
                    normalized_supports.append({
                        "source_id": sid,
                        "support_text": support_text,
                        "support_text_sha256": sha256_bytes(
                            support_text.encode("utf-8")
                        ),
                        "source_excerpt_sha256": ref["excerpt_sha256"],
                    })
                ap["supports"] = normalized_supports
                ap["gold_binding_sha256"] = sha256_bytes(canonical_json_bytes({
                    "gold": candidate["payload"]["gold"],
                    "supports": normalized_supports,
                    "mode": ap["mode"],
                }))
                reviewed_record = {
                    **candidate,
                    "source_ids": [ref["source_id"] for ref in reviewed_refs],
                    "source_refs": reviewed_refs,
                    "answer_provenance": ap,
                    "content_fingerprint": fingerprint_payload(
                        candidate["payload"]
                    ),
                    "factory_verification": {
                        "factory_version": 1,
                        "risk_tier": task["risk_tier"],
                        "slot_binding_sha256": sha256_bytes(
                            canonical_json_bytes(_plan([tid])["slots"][0])
                        ),
                        "curator_model_family": curator_response["model_family"],
                        "curator_model_ref": curator_response["model_ref"],
                        "verifier_model_family": verifier_response["model_family"],
                        "verifier_model_ref": verifier_response["model_ref"],
                        "curator_response_sha256": sha256_bytes(
                            canonical_json_bytes(curator_response)
                        ),
                        "verifier_response_sha256": sha256_bytes(
                            canonical_json_bytes(verifier_response)
                        ),
                        "curator_execution_binding": curator_response["execution_binding"],
                        "verifier_execution_binding": verifier_response["execution_binding"],
                        "verifier_supports": [{
                            "source_id": task["anchor_source_id"],
                            "locator": "gitblob:" + TEST_BLOB_SHA + "#char=0:15",
                            "excerpt_sha256": sha256_bytes(
                                "anchor evidence".encode("utf-8")
                            ),
                            "source_blob_sha": TEST_BLOB_SHA,
                            "char_start": 0,
                            "char_end": 15,
                            "support_text_sha256": sha256_bytes(
                                "anchor evidence".encode("utf-8")
                            ),
                        }],
                        "agreement": "exact_gold_match",
                        "task_fingerprint": task["task_fingerprint"],
                    },
                    "factory_task_id": tid,
                    "factory_slot_id": tid,
                    "factory_task_fingerprint": task["task_fingerprint"],
                }
                reviewed.append(reviewed_record)
        _write_jsonl(bundle / "CURATION_LEDGER.jsonl", ledger)
        _write_jsonl(bundle / "adjudication.jsonl", adjudication)
        if reviewed:
            _write_jsonl(bundle / "reviewed" / "b1" / "reviewed.jsonl", reviewed)

        summary = {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "non_holdout_curator_verifier_chunk",
            "github_sha": sha,
            "github_run_id": str(run_id),
            "task_offset": task_offset,
            "task_limit": len(tasks),
            "selected_task_count": len(tasks),
            "selected_tasks_sha256": sha256_file(bundle / "curator-tasks.jsonl"),
            "curator": {
                "output_sha256": sha256_file(bundle / "curator-responses.jsonl"),
            },
            "verifier_preparation": {
                "input_candidates": sum(
                    1 for row in curator_responses if row.get("status") == "candidate"
                ),
                "verifier_tasks": len(verifier_task_ids),
                "rejected_candidates": (
                    sum(1 for row in curator_responses if row.get("status") == "candidate")
                    - len(verifier_task_ids)
                ),
                "rejection_counts": (
                    {
                        "candidate_input_blindness": (
                            sum(1 for row in curator_responses if row.get("status") == "candidate")
                            - len(verifier_task_ids)
                        )
                    }
                    if (
                        sum(1 for row in curator_responses if row.get("status") == "candidate")
                        - len(verifier_task_ids)
                    )
                    else {}
                ),
                "tasks_sha256": sha256_file(bundle / "verifier-tasks.jsonl"),
            },
            "verifier": (
                {"output_sha256": sha256_file(bundle / "verifier-responses.jsonl")}
                if verifier_task_ids else
                {"not_run_reason": "no_curator_candidates"}
            ),
            "reconciliation": {
                "promoted_count": counts["promoted"],
                "adjudication_count": counts["adjudication"],
                "skipped_count": counts["skipped"],
            },
            "contains_source_text": False,
            "contains_gold_payloads": False,
            "source_bearing_bundle_encrypted": True,
        }
        _write_json(evidence / "CURATION_RUN_SUMMARY.json", summary)
        return evidence

    def test_consolidates_and_hash_binds_replacement_eligibility(self):
        tasks = [_task("p0"), _task("p1"), _task("p2")]
        self._evidence(
            "0-3",
            tasks,
            {
                "p0": ("promoted", None),
                "p1": ("adjudication", "missing_verifier_response"),
                "p2": ("skipped", "no_curator_candidate"),
            },
            verifier_task_ids={"p0"},
        )
        out = Path(self.tmp.name) / "out"
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"), patch.object(
            consolidation, "build_factory_plan", return_value=_plan(["p0", "p1", "p2"])
        ):
            summary = consolidation.consolidate_primary_evidence(
                self.root, self.evidence_root, out, expected_task_count=3,
                source_cache_dir=self.source_cache,
            )

        self.assertEqual(
            summary["outcomes"],
            {"adjudication": 1, "promoted": 1, "skipped": 1},
        )
        self.assertEqual(summary["replacement_eligible_primary_count"], 1)
        self.assertEqual(summary["pending_adjudication_count"], 1)
        self.assertEqual(
            summary["canonical_reason_counts"]["candidate_input_blindness"],
            1,
        )
        eligibility = load_json(out / "REPLACEMENT_ELIGIBILITY.json")
        self.assertFalse(eligibility["rules"]["pending_adjudication_is_replaceable"])
        self.assertFalse(eligibility["rules"]["reserve_reconciliation_enabled"])
        self.assertEqual(eligibility["eligible"][0]["primary_slot_id"], "p2")
        self.assertEqual(eligibility["eligible"][0]["reserve_slots"][0]["slot_id"], "p2:reserve:01")
        self.assertEqual(
            eligibility["eligible"][0]["cumulative_ledger_sha256"],
            sha256_file(out / "CUMULATIVE_LEDGER.jsonl"),
        )
        self.assertEqual(summary["input_run_ids"], [1001])
        self.assertEqual(summary["input_run_count"], 1)
        self.assertEqual(summary["input_artifact_count"], 1)

    def test_duplicate_primary_task_across_runs_fails_closed(self):
        task = _task("p0")
        self._evidence(
            "a", [task], {"p0": ("skipped", "no_curator_candidate")}, run_id=1
        )
        self._evidence(
            "b",
            [task],
            {"p0": ("skipped", "no_curator_candidate")},
            run_id=2,
            sha="c" * 40,
        )
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"), patch.object(
            consolidation, "build_factory_plan", return_value=_plan(["p0"])
        ):
            with self.assertRaisesRegex(ValueError, "duplicate primary task"):
                consolidation.consolidate_primary_evidence(
                    self.root, self.evidence_root, Path(self.tmp.name) / "out",
                    source_cache_dir=self.source_cache,
                )

    def test_collectable_curator_rejection_is_terminal_and_reserve_eligible(self):
        task = _task("p0")
        self._evidence(
            "reject",
            [task],
            {"p0": ("skipped", "no_curator_candidate")},
            curator_rejections={"p0": "adapter:contract_support_not_verbatim"},
        )
        out = Path(self.tmp.name) / "out"
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"), patch.object(
            consolidation, "build_factory_plan", return_value=_plan(["p0"])
        ):
            summary = consolidation.consolidate_primary_evidence(
                self.root, self.evidence_root, out, expected_task_count=1,
                source_cache_dir=self.source_cache,
            )
        self.assertEqual(summary["replacement_eligible_primary_count"], 1)
        row = load_jsonl(out / "CUMULATIVE_LEDGER.jsonl")[0]
        self.assertEqual(
            row["canonical_reason"],
            "curator_rejection:adapter:contract_support_not_verbatim",
        )

    def test_skipped_task_without_terminal_curator_evidence_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "bad",
            [task],
            {"p0": ("skipped", "no_curator_candidate")},
        )
        curator_responses = evidence / "source-bearing" / "curator-responses.jsonl"
        _write_jsonl(curator_responses, [])
        manifest_path = evidence / "source-bearing" / "curator-run.json"
        manifest = load_json(manifest_path)
        manifest["completed_task_count"] = 0
        manifest["attempted_task_count"] = 0
        manifest["output_sha256"] = sha256_file(curator_responses)
        _write_json(manifest_path, manifest)
        summary_path = evidence / "CURATION_RUN_SUMMARY.json"
        summary = load_json(summary_path)
        summary["curator"]["output_sha256"] = manifest["output_sha256"]
        _write_json(summary_path, summary)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(
                ValueError, "does not account for every selected task"
            ):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)


    def test_origin_rerun_attempt_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "rerun",
            [task],
            {"p0": ("skipped", "no_curator_candidate")},
        )
        origin_path = evidence / "ORIGIN.json"
        origin = load_json(origin_path)
        origin["github_run_attempt"] = 2
        _write_json(origin_path, origin)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(ValueError, "must be exactly 1"):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_rehashed_verifier_task_projection_tamper_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "verifier-tamper",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        bundle = evidence / "source-bearing"
        verifier_path = bundle / "verifier-tasks.jsonl"
        rows = load_jsonl(verifier_path)
        rows[0]["candidate_input"] = {"text": "substituted input"}
        unsigned = dict(rows[0])
        unsigned.pop("verifier_task_fingerprint", None)
        rows[0]["verifier_task_fingerprint"] = sha256_bytes(
            canonical_json_bytes(unsigned)
        )
        _write_jsonl(verifier_path, rows)

        verifier_manifest_path = bundle / "verifier-run.json"
        verifier_manifest = load_json(verifier_manifest_path)
        verifier_manifest["tasks_sha256"] = sha256_file(verifier_path)
        _write_json(verifier_manifest_path, verifier_manifest)

        summary_path = evidence / "CURATION_RUN_SUMMARY.json"
        summary = load_json(summary_path)
        summary["verifier_preparation"]["tasks_sha256"] = sha256_file(verifier_path)
        _write_json(summary_path, summary)

        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(ValueError, "exact blinded projection"):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_curator_requested_adjudication_preserves_short_circuit_ledger(self):
        task = _task("p0")
        evidence = self._evidence(
            "curator-adjudication",
            [task],
            {"p0": ("adjudication", "curator_requested_adjudication")},
            verifier_task_ids={"p0"},
        )
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            validated = consolidation.validate_primary_run_evidence(
                self.root, evidence
            )
        self.assertEqual(
            validated["ledger_rows"][0]["canonical_reason"],
            "curator_requested_adjudication",
        )
        ledger = load_jsonl(
            evidence / "source-bearing" / "CURATION_LEDGER.jsonl"
        )[0]
        self.assertIsNone(ledger["verifier_response_sha256"])
        self.assertIsNone(ledger["verifier_model_family"])

    def test_promoted_ledger_response_hash_tamper_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "ledger-hash",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        ledger_path = evidence / "source-bearing" / "CURATION_LEDGER.jsonl"
        rows = load_jsonl(ledger_path)
        rows[0]["verifier_response_sha256"] = "0" * 64
        _write_jsonl(ledger_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(ValueError, "Verifier response hash mismatch"):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_promoted_same_model_family_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "same-family",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        bundle = evidence / "source-bearing"
        verifier_path = bundle / "verifier-responses.jsonl"
        rows = load_jsonl(verifier_path)
        raw = {
            "task_id": rows[0]["task_id"],
            "status": rows[0]["status"],
            "answer": rows[0]["answer"],
        }
        rows[0] = _stamped(task, raw, "curator-family")
        _write_jsonl(verifier_path, rows)

        manifest_path = bundle / "verifier-run.json"
        manifest = load_json(manifest_path)
        manifest["output_sha256"] = sha256_file(verifier_path)
        _write_json(manifest_path, manifest)

        summary_path = evidence / "CURATION_RUN_SUMMARY.json"
        summary = load_json(summary_path)
        summary["verifier"]["output_sha256"] = sha256_file(verifier_path)
        _write_json(summary_path, summary)

        ledger_path = bundle / "CURATION_LEDGER.jsonl"
        ledger = load_jsonl(ledger_path)
        ledger[0]["verifier_response_sha256"] = sha256_bytes(
            canonical_json_bytes(rows[0])
        )
        ledger[0]["verifier_model_family"] = "curator-family"
        _write_jsonl(ledger_path, ledger)

        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(ValueError, "model_family_not_independent"):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_promoted_gold_disagreement_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "gold-disagreement",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        bundle = evidence / "source-bearing"
        verifier_path = bundle / "verifier-responses.jsonl"
        rows = load_jsonl(verifier_path)
        raw = {
            "task_id": rows[0]["task_id"],
            "status": "candidate",
            "answer": {
                **rows[0]["answer"],
                "gold": {"label": "no"},
            },
        }
        rows[0] = _stamped(task, raw, "verifier-family")
        _write_jsonl(verifier_path, rows)

        manifest_path = bundle / "verifier-run.json"
        manifest = load_json(manifest_path)
        manifest["output_sha256"] = sha256_file(verifier_path)
        _write_json(manifest_path, manifest)

        summary_path = evidence / "CURATION_RUN_SUMMARY.json"
        summary = load_json(summary_path)
        summary["verifier"]["output_sha256"] = sha256_file(verifier_path)
        _write_json(summary_path, summary)

        ledger_path = bundle / "CURATION_LEDGER.jsonl"
        ledger = load_jsonl(ledger_path)
        ledger[0]["verifier_response_sha256"] = sha256_bytes(
            canonical_json_bytes(rows[0])
        )
        _write_jsonl(ledger_path, ledger)

        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(ValueError, "gold_disagreement"):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_adjudication_reason_is_rederived_from_bound_responses(self):
        task = _task("p0")
        evidence = self._evidence(
            "false-gold-disagreement",
            [task],
            {"p0": ("adjudication", "gold_disagreement")},
            verifier_task_ids={"p0"},
        )
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(
                ValueError, "differs from deterministic reconciliation"
            ):
                consolidation.validate_primary_run_evidence(
                    self.root, evidence, self.source_cache
                )

    def test_real_gold_disagreement_matches_deterministic_reconciliation(self):
        task = _task("p0")
        evidence = self._evidence(
            "real-gold-disagreement",
            [task],
            {"p0": ("adjudication", "gold_disagreement")},
            verifier_task_ids={"p0"},
        )
        bundle = evidence / "source-bearing"
        verifier_path = bundle / "verifier-responses.jsonl"
        rows = load_jsonl(verifier_path)
        raw = {
            "task_id": rows[0]["task_id"],
            "status": "candidate",
            "answer": {
                **rows[0]["answer"],
                "gold": {"label": "no"},
            },
        }
        rows[0] = _stamped(task, raw, "verifier-family")
        _write_jsonl(verifier_path, rows)

        manifest_path = bundle / "verifier-run.json"
        manifest = load_json(manifest_path)
        manifest["output_sha256"] = sha256_file(verifier_path)
        _write_json(manifest_path, manifest)

        summary_path = evidence / "CURATION_RUN_SUMMARY.json"
        summary = load_json(summary_path)
        summary["verifier"]["output_sha256"] = sha256_file(verifier_path)
        _write_json(summary_path, summary)

        ledger_path = bundle / "CURATION_LEDGER.jsonl"
        ledger = load_jsonl(ledger_path)
        ledger[0]["verifier_response_sha256"] = sha256_bytes(
            canonical_json_bytes(rows[0])
        )
        ledger[0]["verifier_model_family"] = rows[0]["model_family"]
        _write_jsonl(ledger_path, ledger)

        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            validated = consolidation.validate_primary_run_evidence(
                self.root, evidence, self.source_cache
            )
        self.assertEqual(
            validated["ledger_rows"][0]["canonical_reason"],
            "gold_disagreement",
        )

    def test_post_verifier_adjudication_requires_verifier_binding(self):
        task = _task("p0")
        evidence = self._evidence(
            "post-verifier-binding",
            [task],
            {"p0": ("adjudication", "gold_disagreement")},
            verifier_task_ids={"p0"},
        )
        ledger_path = evidence / "source-bearing" / "CURATION_LEDGER.jsonl"
        rows = load_jsonl(ledger_path)
        rows[0]["verifier_response_sha256"] = None
        rows[0]["verifier_model_family"] = None
        _write_jsonl(ledger_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(ValueError, "post-Verifier ledger row lacks"):
                consolidation.validate_primary_run_evidence(
                    self.root, evidence, self.source_cache
                )

    def test_promoted_verifier_locator_must_resolve_against_pinned_source(self):
        task = _task("p0")
        evidence = self._evidence(
            "forged-locator",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        bundle = evidence / "source-bearing"
        verifier_path = bundle / "verifier-responses.jsonl"
        rows = load_jsonl(verifier_path)
        forged_raw = {
            "task_id": rows[0]["task_id"],
            "status": "candidate",
            "answer": {
                "gold": {"label": "yes"},
                "supports": [{
                    "source_id": "s1",
                    "locator": "gitblob:" + "2" * 40 + "#char=0:15",
                    "excerpt": TEST_SOURCE_TEXT,
                    "support_text": TEST_SOURCE_TEXT,
                }],
            },
        }
        rows[0] = _stamped(task, forged_raw, "verifier-family")
        _write_jsonl(verifier_path, rows)

        manifest_path = bundle / "verifier-run.json"
        manifest = load_json(manifest_path)
        manifest["output_sha256"] = sha256_file(verifier_path)
        _write_json(manifest_path, manifest)

        summary_path = evidence / "CURATION_RUN_SUMMARY.json"
        summary = load_json(summary_path)
        summary["verifier"]["output_sha256"] = sha256_file(verifier_path)
        _write_json(summary_path, summary)

        ledger_path = bundle / "CURATION_LEDGER.jsonl"
        ledger = load_jsonl(ledger_path)
        ledger[0]["verifier_response_sha256"] = sha256_bytes(
            canonical_json_bytes(rows[0])
        )
        _write_jsonl(ledger_path, ledger)

        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(ValueError, "verifier_support_invalid"):
                consolidation.validate_primary_run_evidence(
                    self.root, evidence, self.source_cache
                )

    def test_reviewed_preserved_candidate_field_tamper_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "reviewed-preserved-field",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        reviewed_path = (
            evidence / "source-bearing" / "reviewed" / "b1" / "reviewed.jsonl"
        )
        rows = load_jsonl(reviewed_path)
        rows[0]["curation_note"] = "tampered-note"
        _write_jsonl(reviewed_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(
                ValueError, "differs from Curator candidate curation_note"
            ):
                consolidation.validate_primary_run_evidence(
                    self.root, evidence, self.source_cache
                )

    def test_reviewed_verifier_support_binding_tamper_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "reviewed-support",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        reviewed_path = (
            evidence / "source-bearing" / "reviewed" / "b1" / "reviewed.jsonl"
        )
        rows = load_jsonl(reviewed_path)
        rows[0]["factory_verification"]["verifier_supports"][0][
            "support_text_sha256"
        ] = "0" * 64
        _write_jsonl(reviewed_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(
                ValueError, "Verifier supports differ from response"
            ):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_reviewed_source_blob_binding_tamper_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "reviewed-source-blob",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        reviewed_path = (
            evidence / "source-bearing" / "reviewed" / "b1" / "reviewed.jsonl"
        )
        rows = load_jsonl(reviewed_path)
        rows[0]["source_refs"][0]["source_blob_sha"] = "2" * 40
        _write_jsonl(reviewed_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(
                ValueError, "source blob binding mismatch"
            ):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_reviewed_content_fingerprint_tamper_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "reviewed-fingerprint",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        reviewed_path = (
            evidence / "source-bearing" / "reviewed" / "b1" / "reviewed.jsonl"
        )
        rows = load_jsonl(reviewed_path)
        rows[0]["content_fingerprint"] = "0" * 64
        _write_jsonl(reviewed_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(
                ValueError, "content fingerprint mismatch"
            ):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_reviewed_payload_tamper_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "reviewed-payload",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        reviewed_path = (
            evidence / "source-bearing" / "reviewed" / "b1" / "reviewed.jsonl"
        )
        rows = load_jsonl(reviewed_path)
        rows[0]["payload"]["gold"] = {"label": "no"}
        _write_jsonl(reviewed_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(
                ValueError, "differs from Curator candidate payload"
            ):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_reviewed_factory_response_binding_tamper_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "reviewed-factory",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        reviewed_path = (
            evidence / "source-bearing" / "reviewed" / "b1" / "reviewed.jsonl"
        )
        rows = load_jsonl(reviewed_path)
        rows[0]["factory_verification"]["verifier_response_sha256"] = "0" * 64
        _write_jsonl(reviewed_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(
                ValueError, "verifier_response_sha256 mismatch"
            ):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_reviewed_record_benchmark_mismatch_fails_closed(self):
        task = _task("p0")
        evidence = self._evidence(
            "reviewed-benchmark",
            [task],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        reviewed_path = (
            evidence / "source-bearing" / "reviewed" / "b1" / "reviewed.jsonl"
        )
        rows = load_jsonl(reviewed_path)
        rows[0]["benchmark_id"] = "wrong-benchmark"
        _write_jsonl(reviewed_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"):
            with self.assertRaisesRegex(ValueError, "reviewed record benchmark mismatch"):
                consolidation.validate_primary_run_evidence(self.root, evidence, self.source_cache)

    def test_multiple_artifacts_from_one_run_count_as_one_run(self):
        self._evidence(
            "first",
            [_task("p0")],
            {"p0": ("skipped", "no_curator_candidate")},
            run_id=77,
            task_offset=0,
            artifact_id=1001,
        )
        self._evidence(
            "second",
            [_task("p1")],
            {"p1": ("skipped", "no_curator_candidate")},
            run_id=77,
            task_offset=1,
            artifact_id=1002,
        )
        out = Path(self.tmp.name) / "out"
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"), patch.object(
            consolidation, "build_factory_plan", return_value=_plan(["p0", "p1"])
        ):
            summary = consolidation.consolidate_primary_evidence(
                self.root, self.evidence_root, out, expected_task_count=2,
                source_cache_dir=self.source_cache,
            )
        self.assertEqual(summary["input_run_ids"], [77])
        self.assertEqual(summary["input_run_count"], 1)
        self.assertEqual(summary["input_artifact_count"], 2)

    def test_reviewed_frozen_slot_binding_tamper_fails_closed(self):
        self._evidence(
            "slot-binding",
            [_task("p0")],
            {"p0": ("promoted", None)},
            verifier_task_ids={"p0"},
        )
        reviewed_path = (
            self.evidence_root / "slot-binding" / "source-bearing"
            / "reviewed" / "b1" / "reviewed.jsonl"
        )
        rows = load_jsonl(reviewed_path)
        rows[0]["factory_verification"]["slot_binding_sha256"] = "0" * 64
        _write_jsonl(reviewed_path, rows)
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"), patch.object(
            consolidation, "build_factory_plan", return_value=_plan(["p0"])
        ):
            with self.assertRaisesRegex(ValueError, "frozen slot binding mismatch"):
                consolidation.consolidate_primary_evidence(
                    self.root,
                    self.evidence_root,
                    Path(self.tmp.name) / "out",
                    expected_task_count=1,
                    source_cache_dir=self.source_cache,
                )

    def test_nonempty_output_directory_fails_closed(self):
        self._evidence(
            "stale-output",
            [_task("p0")],
            {"p0": ("skipped", "no_curator_candidate")},
        )
        out = Path(self.tmp.name) / "out"
        out.mkdir()
        (out / "stale.txt").write_text("stale", encoding="utf-8")
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"), patch.object(
            consolidation, "build_factory_plan", return_value=_plan(["p0"])
        ):
            with self.assertRaisesRegex(ValueError, "output directory must be empty"):
                consolidation.consolidate_primary_evidence(
                    self.root, self.evidence_root, out, expected_task_count=1
                )

    def test_artifact_task_range_must_match_summary_range(self):
        self._evidence(
            "swapped",
            [_task("p1")],
            {"p1": ("skipped", "no_curator_candidate")},
            task_offset=0,
        )
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"), patch.object(
            consolidation, "build_factory_plan", return_value=_plan(["p0", "p1"])
        ):
            with self.assertRaisesRegex(ValueError, "artifact task offsets differ"):
                consolidation.consolidate_primary_evidence(
                    self.root,
                    self.evidence_root,
                    Path(self.tmp.name) / "out",
                    expected_task_count=1,
                    source_cache_dir=self.source_cache,
                )

    def test_expected_count_requires_exact_zero_based_prefix(self):
        task = _task("p1")
        self._evidence(
            "gap",
            [task],
            {"p1": ("skipped", "no_curator_candidate")},
            task_offset=1,
        )
        with patch.object(consolidation, "_validate_tasks_against_frozen_plan"), patch.object(
            consolidation, "build_factory_plan", return_value=_plan(["p0", "p1"])
        ):
            with self.assertRaisesRegex(ValueError, "exact zero-based prefix"):
                consolidation.consolidate_primary_evidence(
                    self.root,
                    self.evidence_root,
                    Path(self.tmp.name) / "out",
                    expected_task_count=1,
                    source_cache_dir=self.source_cache,
                )


if __name__ == "__main__":
    unittest.main()
