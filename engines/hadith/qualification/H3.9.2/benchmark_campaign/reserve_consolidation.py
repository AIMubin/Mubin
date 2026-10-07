from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .consolidation import validate_reserve_run_evidence
from .core import (
    canonical_json_bytes,
    dump_jsonl,
    load_json,
    sha256_bytes,
    sha256_file,
    write_json,
)
from .factory import build_factory_plan
from .freeze import FREEZE_SCHEMA_VERSION
from .post_consolidation import validate_reserve_activation


RESERVE_CONSOLIDATION_SCHEMA_VERSION = 1


def _compress_offsets(offsets: list[int]) -> list[dict[str, int]]:
    if not offsets:
        return []
    out: list[dict[str, int]] = []
    start = previous = offsets[0]
    for value in offsets[1:]:
        if value == previous + 1:
            previous = value
            continue
        out.append({"start": start, "end": previous + 1})
        start = previous = value
    out.append({"start": start, "end": previous + 1})
    return out


def _load_repository_target(root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
    target = status.get("reserve_consolidation_target")
    if not isinstance(target, dict):
        raise ValueError("reserve consolidation target missing from repository status")
    if target.get("ready") is not True or target.get("completed") is not False:
        raise ValueError("reserve consolidation target is not open")
    if target.get("workflow") != ".github/workflows/h392-reserve-consolidation.yml":
        raise ValueError("reserve consolidation target workflow mismatch")
    if int(status.get("freeze_schema_version", 0)) != FREEZE_SCHEMA_VERSION:
        raise ValueError("reserve consolidation freeze schema mismatch")
    if int(target.get("protocol_freeze_schema", 0)) != FREEZE_SCHEMA_VERSION:
        raise ValueError("reserve consolidation target protocol schema mismatch")

    execution = status.get("reserve_execution_target")
    if not isinstance(execution, dict):
        raise ValueError("reserve execution target missing from repository status")
    if execution.get("completed") is not False:
        raise ValueError("reserve execution target must remain uncommitted until consolidation")
    if int(execution.get("expected_task_count", -1)) != int(target.get("expected_task_count", -2)):
        raise ValueError("reserve execution/consolidation task counts differ")
    if execution.get("activation_manifest_sha256") != target.get("activation_manifest_sha256"):
        raise ValueError("reserve execution/consolidation activation bindings differ")
    return status, target


def consolidate_reserve_evidence(
    root: Path,
    evidence_root: Path,
    out_dir: Path,
    *,
    source_cache_dir: Path,
    activation_path: Path,
) -> dict[str, Any]:
    """Consolidate the exact repository-approved reserve execution evidence."""

    status, target = _load_repository_target(root)
    activation = validate_reserve_activation(root, activation_path, [])
    activation_sha = sha256_file(activation_path)
    if target.get("activation_manifest_sha256") != activation_sha:
        raise ValueError("reserve consolidation activation SHA-256 mismatch")
    if activation.get("cumulative_ledger_sha256") != target.get("cumulative_ledger_sha256"):
        raise ValueError("reserve consolidation cumulative-ledger binding mismatch")
    if activation.get("replacement_eligibility_sha256") != target.get(
        "replacement_eligibility_sha256"
    ):
        raise ValueError("reserve consolidation eligibility binding mismatch")

    plan = build_factory_plan(root)
    plan_sha = sha256_bytes(canonical_json_bytes(plan))
    if activation.get("factory_plan_sha256") != plan_sha:
        raise ValueError("reserve consolidation factory-plan binding mismatch")
    slots = {str(row["slot_id"]): row for row in plan.get("slots", [])}

    activated_rows = activation.get("activated")
    if not isinstance(activated_rows, list):
        raise ValueError("reserve activation rows missing")
    activated_by_id = {
        str(row.get("reserve_slot_id", "")): row
        for row in activated_rows
        if isinstance(row, dict)
    }
    if len(activated_by_id) != len(activated_rows) or "" in activated_by_id:
        raise ValueError("reserve activation contains duplicate/empty reserve IDs")
    activated_ids = sorted(activated_by_id)
    expected_task_count = int(target.get("expected_task_count", -1))
    if expected_task_count != len(activated_ids):
        raise ValueError("reserve consolidation target count differs from activation")
    offset_by_slot = {slot_id: i for i, slot_id in enumerate(activated_ids)}

    expected_artifacts_raw = target.get("source_artifacts")
    if not isinstance(expected_artifacts_raw, list) or not expected_artifacts_raw:
        raise ValueError("reserve consolidation source artifact target missing")
    expected_artifacts: dict[int, dict[str, Any]] = {}
    for row in expected_artifacts_raw:
        if not isinstance(row, dict):
            raise ValueError("reserve consolidation source artifact target must be objects")
        artifact_id = row.get("artifact_id")
        if (
            not isinstance(artifact_id, int)
            or isinstance(artifact_id, bool)
            or artifact_id < 1
            or artifact_id in expected_artifacts
        ):
            raise ValueError("reserve consolidation source artifact ID invalid/duplicate")
        expected_artifacts[artifact_id] = row

    evidence_dirs = sorted(
        path
        for path in evidence_root.iterdir()
        if path.is_dir() and (path / "ORIGIN.json").exists()
    )
    if len(evidence_dirs) != len(expected_artifacts):
        raise ValueError("reserve consolidation evidence artifact count mismatch")

    ledger_rows: list[dict[str, Any]] = []
    reviewed_by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    adjudication_rows: list[dict[str, Any]] = []
    input_artifacts: list[dict[str, Any]] = []
    seen_tasks: set[str] = set()
    seen_case_ids: set[str] = set()
    seen_artifacts: set[int] = set()

    for evidence_dir in evidence_dirs:
        validated = validate_reserve_run_evidence(
            root,
            evidence_dir,
            activation_path,
            source_cache_dir=source_cache_dir,
        )
        origin = validated["origin"]
        summary = validated["summary"]
        artifact_id = int(origin["artifact_id"])
        expected = expected_artifacts.get(artifact_id)
        if expected is None:
            raise ValueError(f"unreviewed reserve artifact: {artifact_id}")
        if artifact_id in seen_artifacts:
            raise ValueError(f"duplicate reserve artifact: {artifact_id}")
        seen_artifacts.add(artifact_id)

        exact_origin = {
            "github_run_id": target.get("source_run_id"),
            "github_run_attempt": expected.get("run_attempt"),
            "head_sha": target.get("source_head_sha"),
            "artifact_id": artifact_id,
            "artifact_name": expected.get("artifact_name"),
            "artifact_sha256": str(expected.get("artifact_digest", "")).removeprefix("sha256:"),
            "encrypted_bundle_sha256": expected.get("encrypted_bundle_sha256"),
        }
        for field, expected_value in exact_origin.items():
            if origin.get(field) != expected_value:
                raise ValueError(
                    f"reserve artifact origin {field} differs from repository target: {artifact_id}"
                )
        if origin.get("source_job_id") != expected.get("source_job_id"):
            raise ValueError(f"reserve artifact job binding mismatch: {artifact_id}")
        if origin.get("summary_sha256") != expected.get("summary_sha256"):
            raise ValueError(f"reserve artifact summary binding mismatch: {artifact_id}")
        if sha256_file(evidence_dir / "CURATION_RUN_SUMMARY.json") != expected.get(
            "summary_sha256"
        ):
            raise ValueError(f"reserve artifact summary file hash mismatch: {artifact_id}")
        if summary.get("task_offset") != expected.get("task_offset"):
            raise ValueError(f"reserve artifact offset differs from repository target: {artifact_id}")
        if summary.get("task_limit") != expected.get("task_limit"):
            raise ValueError(f"reserve artifact limit differs from repository target: {artifact_id}")

        artifact_offsets = sorted(
            offset_by_slot[str(row["slot_id"])]
            for row in validated["ledger_rows"]
        )
        expected_offsets = list(
            range(
                int(expected["task_offset"]),
                int(expected["task_offset"]) + int(expected["task_limit"]),
            )
        )
        if artifact_offsets != expected_offsets:
            raise ValueError(f"reserve artifact task offsets differ from activation: {artifact_id}")

        input_artifacts.append({
            "github_run_id": origin["github_run_id"],
            "github_run_attempt": origin["github_run_attempt"],
            "source_job_id": origin["source_job_id"],
            "head_sha": origin["head_sha"],
            "artifact_id": artifact_id,
            "artifact_name": origin["artifact_name"],
            "artifact_sha256": origin["artifact_sha256"],
            "summary_sha256": origin["summary_sha256"],
            "encrypted_bundle_sha256": origin["encrypted_bundle_sha256"],
        })

        for row in validated["ledger_rows"]:
            task_id = str(row["task_id"])
            if task_id in seen_tasks:
                raise ValueError(f"duplicate reserve task across evidence: {task_id}")
            seen_tasks.add(task_id)
            if task_id not in offset_by_slot:
                raise ValueError(f"reserve task not present in approved activation: {task_id}")
            activation_row = activated_by_id[task_id]
            if row.get("replacement_for_slot_id") != activation_row.get(
                "replacement_for_slot_id"
            ):
                raise ValueError(f"reserve/primary activation linkage mismatch: {task_id}")
            if row.get("reserve_activation_sha256") != activation_sha:
                raise ValueError(f"reserve ledger activation binding mismatch: {task_id}")
            if row.get("reserve_attempt") != 1:
                raise ValueError(f"unexpected reserve attempt: {task_id}")

            outcome = str(row["outcome"])
            if outcome == "promoted":
                slot_state = "replacement_promoted"
            elif outcome == "adjudication":
                slot_state = "pending_adjudication"
            elif outcome == "skipped" and row.get("terminal_failure") is True:
                slot_state = "exhausted"
            else:
                raise ValueError(f"reserve outcome is not terminally classified: {task_id}")

            enriched = dict(row)
            enriched.update({
                "reserve_offset": offset_by_slot[task_id],
                "slot_state": slot_state,
                "primary_slot_id": activation_row["replacement_for_slot_id"],
                "primary_task_id": activation_row["primary_task_id"],
                "primary_task_fingerprint": activation_row["primary_task_fingerprint"],
                "primary_offset": activation_row["primary_offset"],
                "primary_eligibility_reason": activation_row["eligibility_reason"],
                "activation_manifest_sha256": activation_sha,
                "cumulative_ledger_sha256": activation["cumulative_ledger_sha256"],
                "replacement_eligibility_sha256": activation[
                    "replacement_eligibility_sha256"
                ],
            })
            ledger_rows.append(enriched)

        for task_id, record in validated["reviewed"].items():
            case_id = str(record.get("case_id", ""))
            if not case_id or case_id in seen_case_ids:
                raise ValueError(f"duplicate/empty reserve promoted case_id: {case_id}")
            slot_id = str(record.get("factory_slot_id", ""))
            slot = slots.get(slot_id)
            if slot is None or slot.get("candidate_slot_kind") != "reserve":
                raise ValueError(f"reserve reviewed record references non-reserve slot: {task_id}")
            fv = record.get("factory_verification")
            if (
                not isinstance(fv, dict)
                or fv.get("slot_binding_sha256")
                != sha256_bytes(canonical_json_bytes(slot))
            ):
                raise ValueError(f"reserve reviewed frozen slot binding mismatch: {task_id}")
            seen_case_ids.add(case_id)
            reviewed_by_benchmark[str(record["benchmark_id"])].append(record)

        ledger_by_task = {
            str(row["task_id"]): row for row in validated["ledger_rows"]
        }
        for task_id, row in validated["adjudication"].items():
            source = ledger_by_task[task_id]
            enriched = dict(row)
            enriched.update({
                "source_run_id": source["source_run_id"],
                "source_run_attempt": source["source_run_attempt"],
                "source_artifact_id": source["source_artifact_id"],
                "source_sha": source["source_sha"],
                "canonical_reason": source["canonical_reason"],
                "activation_manifest_sha256": activation_sha,
                "replacement_for_slot_id": source["replacement_for_slot_id"],
            })
            adjudication_rows.append(enriched)

    if seen_artifacts != set(expected_artifacts):
        raise ValueError("reserve consolidation did not consume every reviewed artifact")

    ledger_rows.sort(key=lambda row: int(row["reserve_offset"]))
    offsets = [int(row["reserve_offset"]) for row in ledger_rows]
    if offsets != list(range(expected_task_count)):
        raise ValueError("reserve evidence does not cover exact activated offset range")
    if set(seen_tasks) != set(activated_ids):
        raise ValueError("reserve evidence task set differs from exact activation")

    outcome_counts = Counter(str(row["outcome"]) for row in ledger_rows)
    expected_outcomes = target.get("expected_outcomes")
    if not isinstance(expected_outcomes, dict):
        raise ValueError("reserve consolidation expected outcomes missing")
    for key in ("promoted", "adjudication", "skipped"):
        if outcome_counts.get(key, 0) != int(expected_outcomes.get(key, -1)):
            raise ValueError(f"reserve consolidated {key} count differs from reviewed aggregate")

    if out_dir.exists():
        if any(out_dir.iterdir()):
            raise ValueError("reserve consolidation output directory must be empty")
    else:
        out_dir.mkdir(parents=True)

    ledger_path = out_dir / "RESERVE_LEDGER.jsonl"
    dump_jsonl(ledger_path, ledger_rows)
    ledger_sha = sha256_file(ledger_path)

    offset_by_task = {
        str(row["task_id"]): int(row["reserve_offset"]) for row in ledger_rows
    }
    adjudication_rows.sort(key=lambda row: offset_by_task[str(row["task_id"])])
    adjudication_path = out_dir / "RESERVE_ADJUDICATION.jsonl"
    dump_jsonl(adjudication_path, adjudication_rows)

    reviewed_count = 0
    reviewed_files: list[dict[str, Any]] = []
    for benchmark_id, rows in sorted(reviewed_by_benchmark.items()):
        rows.sort(key=lambda row: offset_by_slot[str(row["factory_slot_id"])])
        reviewed_count += len(rows)
        reviewed_path = out_dir / "reviewed" / benchmark_id / "reviewed.jsonl"
        dump_jsonl(reviewed_path, rows)
        reviewed_files.append({
            "benchmark_id": benchmark_id,
            "record_count": len(rows),
            "path": f"reviewed/{benchmark_id}/reviewed.jsonl",
            "sha256": sha256_file(reviewed_path),
        })

    reserves_by_primary: dict[str, list[str]] = defaultdict(list)
    for slot in plan.get("slots", []):
        if (
            slot.get("partition") == "non_holdout"
            and slot.get("candidate_slot_kind") == "reserve"
        ):
            reserves_by_primary[str(slot.get("replacement_for_slot_id", ""))].append(
                str(slot["slot_id"])
            )

    exhausted_rows: list[dict[str, Any]] = []
    for row in ledger_rows:
        if row["slot_state"] != "exhausted":
            continue
        primary_slot_id = str(row["primary_slot_id"])
        linked = sorted(reserves_by_primary.get(primary_slot_id, []))
        if linked != [str(row["slot_id"])]:
            raise ValueError(
                f"exhausted slot still has unconsumed preregistered reserve capacity: {primary_slot_id}"
            )
        exhausted_rows.append({
            "primary_slot_id": primary_slot_id,
            "reserve_slot_id": row["slot_id"],
            "reserve_task_fingerprint": row["task_fingerprint"],
            "reserve_offset": row["reserve_offset"],
            "canonical_reason": row["canonical_reason"],
            "activation_manifest_sha256": activation_sha,
            "reserve_ledger_sha256": ledger_sha,
        })

    exhausted = {
        "schema_version": RESERVE_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "exhausted_non_holdout_slots",
        "protocol_freeze_schema": FREEZE_SCHEMA_VERSION,
        "activation_manifest_sha256": activation_sha,
        "reserve_ledger_sha256": ledger_sha,
        "exhausted_slot_count": len(exhausted_rows),
        "exhausted": exhausted_rows,
        "policy": {
            "automatic_second_reserve_authorized": False,
            "capacity_extension_requires_reviewed_protocol_change": True,
        },
    }
    exhausted_path = out_dir / "EXHAUSTED_SLOTS.json"
    write_json(exhausted_path, exhausted)

    primary = status.get("last_completed_cumulative_consolidation")
    if not isinstance(primary, dict):
        raise ValueError("canonical primary consolidation status missing")
    primary_total = int(primary.get("expected_primary_tasks", -1))
    primary_promoted = int(primary.get("promoted_primary_count", -1))
    primary_pending = int(primary.get("pending_adjudication_count", -1))
    primary_skipped = int(primary.get("skipped_primary_count", -1))
    if primary_promoted + primary_pending + primary_skipped != primary_total:
        raise ValueError("canonical primary accounting is inconsistent")
    if primary_skipped != expected_task_count:
        raise ValueError("activated reserve count differs from terminal primary count")

    reserve_promoted = outcome_counts.get("promoted", 0)
    reserve_pending = outcome_counts.get("adjudication", 0)
    exhausted_count = len(exhausted_rows)
    if reserve_promoted + reserve_pending + exhausted_count != primary_skipped:
        raise ValueError("reserve outcomes do not close terminal-primary replacement surface")

    validated_promoted = primary_promoted + reserve_promoted
    total_pending = primary_pending + reserve_pending
    maximum_fillable = validated_promoted + total_pending
    minimum_shortfall = primary_total - maximum_fillable
    if minimum_shortfall != exhausted_count:
        raise ValueError("capacity shortfall does not equal exhausted slot count")

    input_artifacts.sort(
        key=lambda row: int(expected_artifacts[int(row["artifact_id"])]["task_offset"])
    )

    manifest = {
        "schema_version": RESERVE_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "consolidated_approved_non_holdout_reserve_evidence",
        "protocol_freeze_schema": FREEZE_SCHEMA_VERSION,
        "factory_plan_sha256": plan_sha,
        "activation_manifest_sha256": activation_sha,
        "cumulative_ledger_sha256": activation["cumulative_ledger_sha256"],
        "replacement_eligibility_sha256": activation[
            "replacement_eligibility_sha256"
        ],
        "source_run_id": target["source_run_id"],
        "source_run_final_attempt": target["source_run_final_attempt"],
        "source_head_sha": target["source_head_sha"],
        "aggregate_artifact_id": target["aggregate_artifact_id"],
        "aggregate_artifact_digest": target["aggregate_artifact_digest"],
        "aggregate_summary_sha256": target["aggregate_summary_sha256"],
        "input_artifacts": input_artifacts,
        "input_artifact_count": len(input_artifacts),
        "task_count": len(ledger_rows),
        "coverage_ranges": _compress_offsets(offsets),
        "reserve_ledger_sha256": ledger_sha,
        "reserve_adjudication_sha256": sha256_file(adjudication_path),
        "exhausted_slots_sha256": sha256_file(exhausted_path),
        "reviewed_files": reviewed_files,
        "reviewed_record_count": reviewed_count,
        "pending_reserve_adjudication_count": len(adjudication_rows),
        "exhausted_slot_count": exhausted_count,
        "minimum_capacity_shortfall": minimum_shortfall,
    }
    write_json(out_dir / "RESERVE_MANIFEST.json", manifest)

    canonical_reason_counts = Counter(
        str(row["canonical_reason"])
        for row in ledger_rows
        if row["outcome"] != "promoted"
    )
    return {
        "schema_version": RESERVE_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "redacted_consolidated_approved_non_holdout_reserve_summary",
        "protocol_freeze_schema": FREEZE_SCHEMA_VERSION,
        "source_run_id": target["source_run_id"],
        "source_run_final_attempt": target["source_run_final_attempt"],
        "source_head_sha": target["source_head_sha"],
        "input_artifact_count": len(input_artifacts),
        "task_count": len(ledger_rows),
        "coverage_ranges": _compress_offsets(offsets),
        "outcomes": dict(sorted(outcome_counts.items())),
        "canonical_reason_counts": dict(sorted(canonical_reason_counts.items())),
        "reviewed_record_count": reviewed_count,
        "pending_reserve_adjudication_count": len(adjudication_rows),
        "exhausted_slot_count": exhausted_count,
        "primary_promoted_record_count": primary_promoted,
        "primary_pending_adjudication_count": primary_pending,
        "validated_promoted_record_count": validated_promoted,
        "total_pending_adjudication_count": total_pending,
        "record_quota": primary_total,
        "maximum_fillable_slots_under_current_capacity": maximum_fillable,
        "minimum_capacity_shortfall": minimum_shortfall,
        "activation_manifest_sha256": activation_sha,
        "reserve_ledger_sha256": ledger_sha,
        "exhausted_slots_sha256": sha256_file(exhausted_path),
        "contains_source_text": False,
        "contains_gold_payloads": False,
        "contains_model_identity": False,
        "reserve_execution_evidence_complete": True,
    }
