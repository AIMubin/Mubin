from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .capacity_extension import validate_frozen_capacity_extension
from .consolidation import validate_reserve2_run_evidence
from .core import (
    canonical_json_bytes,
    dump_jsonl,
    load_json,
    sha256_bytes,
    sha256_file,
    write_json,
)


RESERVE2_CONSOLIDATION_SCHEMA_VERSION = 1
RESERVE2_CONSOLIDATION_PROTOCOL_FREEZE_SCHEMA = 29
SOURCE_CAPACITY_EXTENSION_FREEZE_SCHEMA = 27
SOURCE_EXECUTION_FREEZE_SCHEMA = 28


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
    if int(status.get("freeze_schema_version", 0)) != RESERVE2_CONSOLIDATION_PROTOCOL_FREEZE_SCHEMA:
        raise ValueError("reserve2 consolidation requires freeze schema 29")

    target = status.get("reserve2_consolidation_target")
    if not isinstance(target, dict):
        raise ValueError("reserve2 consolidation target missing from repository status")
    if target.get("ready") is not True or target.get("completed") is not False:
        raise ValueError("reserve2 consolidation target is not open")
    if target.get("workflow") != ".github/workflows/h392-reserve2-consolidation.yml":
        raise ValueError("reserve2 consolidation target workflow mismatch")
    if int(target.get("protocol_freeze_schema", 0)) != RESERVE2_CONSOLIDATION_PROTOCOL_FREEZE_SCHEMA:
        raise ValueError("reserve2 consolidation protocol schema mismatch")

    execution = status.get("reserve2_execution_target")
    if not isinstance(execution, dict):
        raise ValueError("reserve2 execution target missing")
    if execution.get("ready") is not False:
        raise ValueError("reserve2 execution target must be closed against redispatch")
    if execution.get("completed") is not False:
        raise ValueError("reserve2 execution target must remain uncommitted until consolidation")
    if execution.get("execution_succeeded") is not True:
        raise ValueError("reserve2 execution target has no successful execution evidence")
    if execution.get("consolidation_pending") is not True:
        raise ValueError("reserve2 execution target is not awaiting consolidation")
    for execution_key, target_key in (
        ("successful_run_id", "source_run_id"),
        ("successful_run_attempt", "source_run_attempt"),
        ("runner_commit", "source_head_sha"),
        ("aggregate_artifact_id", "aggregate_artifact_id"),
        ("aggregate_artifact_digest", "aggregate_artifact_digest"),
        ("aggregate_summary_sha256", "aggregate_summary_sha256"),
        ("capacity_extension_manifest_sha256", "capacity_extension_manifest_sha256"),
    ):
        if execution.get(execution_key) != target.get(target_key):
            raise ValueError(f"reserve2 execution/consolidation binding mismatch: {execution_key}")
    if int(execution.get("expected_task_count", -1)) != int(target.get("expected_task_count", -2)):
        raise ValueError("reserve2 execution/consolidation task counts differ")

    prior_surface = target.get("prior_promoted_case_id_surface")
    if not isinstance(prior_surface, dict):
        raise ValueError("reserve2 prior promoted case-ID surface missing")
    primary = status.get("last_completed_cumulative_consolidation")
    reserve = status.get("last_completed_reserve_consolidation")
    if not isinstance(primary, dict) or not isinstance(reserve, dict):
        raise ValueError("canonical prior consolidation status missing")
    expected_primary = {
        "source_run_id": primary.get("successful_run_id"),
        "source_run_attempt": 1,
        "source_head_sha": primary.get("runner_commit"),
        "workflow": ".github/workflows/h392-cumulative-consolidation.yml",
        "artifact_id": primary.get("artifact_id"),
        "artifact_name": "h392-cumulative-primary-evidence",
        "artifact_digest": primary.get("artifact_digest"),
        "summary_sha256": primary.get("summary_sha256"),
        "encrypted_bundle_sha256": primary.get("encrypted_bundle_sha256"),
        "ledger_sha256": primary.get("cumulative_ledger_sha256"),
        "promoted_count": primary.get("promoted_primary_count"),
    }
    expected_reserve = {
        "source_run_id": reserve.get("successful_run_id"),
        "source_run_attempt": 1,
        "source_head_sha": reserve.get("runner_commit"),
        "workflow": ".github/workflows/h392-reserve-consolidation.yml",
        "artifact_id": reserve.get("artifact_id"),
        "artifact_name": "h392-reserve-consolidated-evidence",
        "artifact_digest": reserve.get("artifact_digest"),
        "summary_sha256": reserve.get("summary_sha256"),
        "encrypted_bundle_sha256": reserve.get("encrypted_bundle_sha256"),
        "ledger_sha256": reserve.get("reserve_ledger_sha256"),
        "promoted_count": reserve.get("promoted_reserve_count"),
    }
    for name, expected in (("primary", expected_primary), ("reserve", expected_reserve)):
        bound = prior_surface.get(name)
        if not isinstance(bound, dict):
            raise ValueError(f"reserve2 prior {name} promoted surface missing")
        for field, value in expected.items():
            if bound.get(field) != value:
                raise ValueError(
                    f"reserve2 prior {name} promoted binding mismatch: {field}"
                )
    expected_prior_count = int(prior_surface.get("expected_promoted_case_id_count", -1))
    if (
        expected_prior_count
        != int(expected_primary["promoted_count"]) + int(expected_reserve["promoted_count"])
        or expected_prior_count != int(reserve.get("validated_promoted_record_count", -1))
    ):
        raise ValueError("reserve2 prior promoted count differs from canonical status")
    return status, target


def _load_prior_promoted_case_ids(
    path: Path,
    target: dict[str, Any],
) -> tuple[set[str], str]:
    obj = load_json(path)
    if (
        not isinstance(obj, dict)
        or obj.get("schema_version") != 1
        or obj.get("campaign_id") != "H3.9.2"
        or obj.get("kind") != "canonical_prior_promoted_case_id_set"
    ):
        raise ValueError("prior promoted case-ID manifest contract invalid")
    surface = target["prior_promoted_case_id_surface"]
    for name in ("primary", "reserve"):
        expected = surface[name]
        actual = obj.get(name)
        if not isinstance(actual, dict):
            raise ValueError(f"prior promoted case-ID {name} binding missing")
        for field in (
            "source_run_id",
            "source_run_attempt",
            "source_head_sha",
            "workflow",
            "artifact_id",
            "artifact_name",
            "artifact_digest",
            "summary_sha256",
            "encrypted_bundle_sha256",
            "ledger_sha256",
            "promoted_count",
        ):
            if actual.get(field) != expected.get(field):
                raise ValueError(
                    f"prior promoted case-ID {name} binding mismatch: {field}"
                )
    ids = obj.get("promoted_case_ids")
    if not isinstance(ids, list) or any(
        not isinstance(case_id, str) or not case_id.strip() for case_id in ids
    ):
        raise ValueError("prior promoted case IDs must be non-empty strings")
    if ids != sorted(ids) or len(ids) != len(set(ids)):
        raise ValueError("prior promoted case IDs must be sorted and unique")
    expected_count = int(surface["expected_promoted_case_id_count"])
    if (
        obj.get("promoted_case_id_count") != expected_count
        or len(ids) != expected_count
        or sum(int(obj[name]["promoted_count"]) for name in ("primary", "reserve"))
            != expected_count
    ):
        raise ValueError("prior promoted case-ID count mismatch")
    return set(ids), sha256_file(path)


def consolidate_reserve2_evidence(
    root: Path,
    evidence_root: Path,
    out_dir: Path,
    *,
    source_cache_dir: Path,
    capacity_extension_path: Path,
    prior_promoted_case_ids_path: Path,
) -> dict[str, Any]:
    """Consolidate the exact repository-reviewed reserve:02 execution evidence."""

    status, target = _load_repository_target(root)
    prior_promoted_case_ids, prior_promoted_case_ids_sha256 = (
        _load_prior_promoted_case_ids(prior_promoted_case_ids_path, target)
    )
    extension = validate_frozen_capacity_extension(
        root,
        capacity_extension_path,
        require_execution_enabled=False,
    )
    extension_sha = sha256_file(capacity_extension_path)
    if target.get("capacity_extension_manifest_sha256") != extension_sha:
        raise ValueError("reserve2 consolidation capacity-extension SHA mismatch")
    if int(extension.get("protocol_freeze_schema", 0)) != SOURCE_CAPACITY_EXTENSION_FREEZE_SCHEMA:
        raise ValueError("reserve2 consolidation requires schema-27 capacity extension")

    extension_rows = extension.get("extensions")
    if not isinstance(extension_rows, list):
        raise ValueError("capacity extension rows missing")
    approved_ids = [str(row.get("new_reserve_slot_id", "")) for row in extension_rows]
    if not approved_ids or "" in approved_ids or len(approved_ids) != len(set(approved_ids)):
        raise ValueError("capacity extension reserve2 IDs invalid/duplicate")
    expected_task_count = int(target.get("expected_task_count", -1))
    if expected_task_count != len(approved_ids):
        raise ValueError("reserve2 consolidation target count differs from capacity extension")
    offset_by_slot = {slot_id: i for i, slot_id in enumerate(approved_ids)}
    extension_by_id = {
        str(row["new_reserve_slot_id"]): row for row in extension_rows
    }

    expected_artifacts_raw = target.get("source_artifacts")
    if not isinstance(expected_artifacts_raw, list) or not expected_artifacts_raw:
        raise ValueError("reserve2 consolidation source artifact target missing")
    expected_artifacts: dict[int, dict[str, Any]] = {}
    for row in expected_artifacts_raw:
        if not isinstance(row, dict):
            raise ValueError("reserve2 source artifact target must be objects")
        artifact_id = row.get("artifact_id")
        if (
            not isinstance(artifact_id, int)
            or isinstance(artifact_id, bool)
            or artifact_id < 1
            or artifact_id in expected_artifacts
        ):
            raise ValueError("reserve2 source artifact ID invalid/duplicate")
        expected_artifacts[artifact_id] = row

    evidence_dirs = sorted(
        path
        for path in evidence_root.iterdir()
        if path.is_dir() and (path / "ORIGIN.json").exists()
    )
    if len(evidence_dirs) != len(expected_artifacts):
        raise ValueError("reserve2 evidence artifact count mismatch")

    ledger_rows: list[dict[str, Any]] = []
    reviewed_by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    adjudication_rows: list[dict[str, Any]] = []
    input_artifacts: list[dict[str, Any]] = []
    seen_tasks: set[str] = set()
    seen_current_case_ids: set[str] = set()
    seen_artifacts: set[int] = set()

    for evidence_dir in evidence_dirs:
        validated = validate_reserve2_run_evidence(
            root,
            evidence_dir,
            capacity_extension_path,
            source_cache_dir=source_cache_dir,
        )
        origin = validated["origin"]
        summary = validated["summary"]
        artifact_id = int(origin["artifact_id"])
        expected = expected_artifacts.get(artifact_id)
        if expected is None:
            raise ValueError(f"unreviewed reserve2 artifact: {artifact_id}")
        if artifact_id in seen_artifacts:
            raise ValueError(f"duplicate reserve2 artifact: {artifact_id}")
        seen_artifacts.add(artifact_id)

        exact_origin = {
            "github_run_id": target["source_run_id"],
            "github_run_attempt": expected["run_attempt"],
            "head_sha": target["source_head_sha"],
            "artifact_id": artifact_id,
            "artifact_name": expected["artifact_name"],
            "artifact_sha256": str(expected["artifact_digest"]).removeprefix("sha256:"),
            "encrypted_bundle_sha256": expected["encrypted_bundle_sha256"],
        }
        for field, expected_value in exact_origin.items():
            if origin.get(field) != expected_value:
                raise ValueError(
                    f"reserve2 artifact origin {field} differs from repository target: {artifact_id}"
                )
        if origin.get("source_job_id") != expected.get("source_job_id"):
            raise ValueError(f"reserve2 artifact job binding mismatch: {artifact_id}")
        if origin.get("summary_sha256") != expected.get("summary_sha256"):
            raise ValueError(f"reserve2 artifact summary binding mismatch: {artifact_id}")
        if sha256_file(evidence_dir / "CURATION_RUN_SUMMARY.json") != expected.get(
            "summary_sha256"
        ):
            raise ValueError(f"reserve2 artifact summary file hash mismatch: {artifact_id}")
        if int(summary.get("task_offset", -1)) != int(expected["task_offset"]):
            raise ValueError(f"reserve2 artifact offset mismatch: {artifact_id}")
        if int(summary.get("task_limit", -1)) != int(expected["task_limit"]):
            raise ValueError(f"reserve2 artifact limit mismatch: {artifact_id}")

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
            raise ValueError(f"reserve2 artifact task offsets differ from frozen overlay: {artifact_id}")

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
                raise ValueError(f"duplicate reserve2 task across evidence: {task_id}")
            seen_tasks.add(task_id)
            extension_row = extension_by_id.get(task_id)
            if extension_row is None:
                raise ValueError(f"reserve2 task not in frozen capacity extension: {task_id}")
            if row.get("replacement_for_slot_id") != extension_row.get("primary_slot_id"):
                raise ValueError(f"reserve2 primary linkage mismatch: {task_id}")
            if row.get("capacity_extension_sha256") != extension_sha:
                raise ValueError(f"reserve2 ledger capacity binding mismatch: {task_id}")
            if row.get("reserve_attempt") != 2:
                raise ValueError(f"unexpected reserve2 attempt: {task_id}")

            outcome = str(row["outcome"])
            if outcome == "promoted":
                slot_state = "replacement_promoted"
            elif outcome == "adjudication":
                slot_state = "pending_adjudication"
            elif outcome == "skipped" and row.get("terminal_failure") is True:
                slot_state = "exhausted"
            else:
                raise ValueError(f"reserve2 outcome is not terminally classified: {task_id}")

            enriched = dict(row)
            enriched.update({
                "reserve2_offset": offset_by_slot[task_id],
                "slot_state": slot_state,
                "primary_slot_id": extension_row["primary_slot_id"],
                "prior_reserve_slot_id": extension_row["prior_reserve_slot_id"],
                "prior_reserve_offset": extension_row["prior_reserve_offset"],
                "prior_reserve_task_fingerprint": extension_row["prior_reserve_task_fingerprint"],
                "capacity_extension_manifest_sha256": extension_sha,
                "source_reserve_ledger_sha256": extension["reserve_ledger_sha256"],
                "source_exhausted_slots_sha256": extension["exhausted_slots_sha256"],
            })
            ledger_rows.append(enriched)

        for task_id, record in validated["reviewed"].items():
            case_id = str(record.get("case_id", ""))
            if not case_id:
                raise ValueError("empty reserve2 promoted case_id")
            if case_id in prior_promoted_case_ids:
                raise ValueError(
                    f"reserve2 promoted case_id collides with prior canonical record: {case_id}"
                )
            if case_id in seen_current_case_ids:
                raise ValueError(
                    f"duplicate reserve2 promoted case_id across current evidence: {case_id}"
                )
            row = extension_by_id.get(str(record.get("factory_slot_id", "")))
            if row is None:
                raise ValueError(f"reserve2 reviewed record references unapproved slot: {task_id}")
            slot = row["new_reserve_slot"]
            fv = record.get("factory_verification")
            if (
                not isinstance(fv, dict)
                or fv.get("slot_binding_sha256")
                != sha256_bytes(canonical_json_bytes(slot))
            ):
                raise ValueError(f"reserve2 reviewed frozen slot binding mismatch: {task_id}")
            seen_current_case_ids.add(case_id)
            reviewed_by_benchmark[str(record["benchmark_id"])].append(record)

        ledger_by_task = {
            str(row["task_id"]): row for row in validated["ledger_rows"]
        }
        for task_id, row in validated["adjudication"].items():
            source = ledger_by_task[task_id]
            extension_row = extension_by_id[task_id]
            enriched = dict(row)
            enriched.update({
                "source_run_id": source["source_run_id"],
                "source_run_attempt": source["source_run_attempt"],
                "source_artifact_id": source["source_artifact_id"],
                "source_sha": source["source_sha"],
                "canonical_reason": source["canonical_reason"],
                "capacity_extension_manifest_sha256": extension_sha,
                "replacement_for_slot_id": source["replacement_for_slot_id"],
                "prior_reserve_slot_id": extension_row["prior_reserve_slot_id"],
            })
            adjudication_rows.append(enriched)

    if seen_artifacts != set(expected_artifacts):
        raise ValueError("reserve2 consolidation did not consume every reviewed artifact")

    ledger_rows.sort(key=lambda row: int(row["reserve2_offset"]))
    offsets = [int(row["reserve2_offset"]) for row in ledger_rows]
    if offsets != list(range(expected_task_count)):
        raise ValueError("reserve2 evidence does not cover exact overlay offset range")
    if set(seen_tasks) != set(approved_ids):
        raise ValueError("reserve2 evidence task set differs from frozen overlay")

    outcome_counts = Counter(str(row["outcome"]) for row in ledger_rows)
    expected_outcomes = target.get("expected_outcomes")
    if not isinstance(expected_outcomes, dict):
        raise ValueError("reserve2 expected outcomes missing")
    for key in ("promoted", "adjudication", "skipped"):
        if outcome_counts.get(key, 0) != int(expected_outcomes.get(key, -1)):
            raise ValueError(f"reserve2 consolidated {key} count differs from reviewed aggregate")

    if out_dir.exists():
        if any(out_dir.iterdir()):
            raise ValueError("reserve2 consolidation output directory must be empty")
    else:
        out_dir.mkdir(parents=True)

    ledger_path = out_dir / "RESERVE2_LEDGER.jsonl"
    dump_jsonl(ledger_path, ledger_rows)
    ledger_sha = sha256_file(ledger_path)

    offset_by_task = {
        str(row["task_id"]): int(row["reserve2_offset"]) for row in ledger_rows
    }
    adjudication_rows.sort(key=lambda row: offset_by_task[str(row["task_id"])])
    adjudication_path = out_dir / "RESERVE2_ADJUDICATION.jsonl"
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

    exhausted_rows: list[dict[str, Any]] = []
    for row in ledger_rows:
        if row["slot_state"] != "exhausted":
            continue
        extension_row = extension_by_id[str(row["slot_id"])]
        exhausted_rows.append({
            "primary_slot_id": extension_row["primary_slot_id"],
            "prior_reserve_slot_id": extension_row["prior_reserve_slot_id"],
            "reserve2_slot_id": row["slot_id"],
            "reserve2_task_fingerprint": row["task_fingerprint"],
            "reserve2_offset": row["reserve2_offset"],
            "canonical_reason": row["canonical_reason"],
            "capacity_extension_manifest_sha256": extension_sha,
            "reserve2_ledger_sha256": ledger_sha,
        })

    exhausted = {
        "schema_version": RESERVE2_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "exhausted_non_holdout_slots_after_reserve2",
        "protocol_freeze_schema": RESERVE2_CONSOLIDATION_PROTOCOL_FREEZE_SCHEMA,
        "capacity_extension_manifest_sha256": extension_sha,
        "reserve2_ledger_sha256": ledger_sha,
        "exhausted_slot_count": len(exhausted_rows),
        "exhausted": exhausted_rows,
        "policy": {
            "automatic_reserve3_authorized": False,
            "further_capacity_extension_requires_reviewed_protocol_change": True,
        },
    }
    exhausted_path = out_dir / "RESERVE2_EXHAUSTED_SLOTS.json"
    write_json(exhausted_path, exhausted)

    previous = status.get("last_completed_reserve_consolidation")
    if not isinstance(previous, dict):
        raise ValueError("canonical reserve:01 consolidation status missing")
    prior_promoted = int(previous.get("validated_promoted_record_count", -1))
    prior_pending = int(previous.get("total_pending_adjudication_count", -1))
    prior_exhausted = int(previous.get("exhausted_slot_count", -1))
    record_quota = int(previous.get("record_quota", -1))
    if prior_exhausted != expected_task_count:
        raise ValueError("reserve2 task count differs from canonical reserve:01 exhausted surface")

    reserve2_promoted = outcome_counts.get("promoted", 0)
    reserve2_pending = outcome_counts.get("adjudication", 0)
    reserve2_skipped = outcome_counts.get("skipped", 0)
    exhausted_count = len(exhausted_rows)
    if reviewed_count != reserve2_promoted:
        raise ValueError("reserve2 reviewed count differs from promoted outcomes")
    if len(adjudication_rows) != reserve2_pending:
        raise ValueError("reserve2 adjudication rows differ from adjudication outcomes")
    if exhausted_count != reserve2_skipped:
        raise ValueError("reserve2 exhausted rows differ from skipped outcomes")
    if reserve2_promoted + reserve2_pending + exhausted_count != prior_exhausted:
        raise ValueError("reserve2 outcomes do not close prior exhausted surface")

    validated_promoted = prior_promoted + reserve2_promoted
    total_pending = prior_pending + reserve2_pending
    maximum_fillable = validated_promoted + total_pending
    minimum_shortfall = record_quota - maximum_fillable
    if minimum_shortfall != exhausted_count:
        raise ValueError("reserve2 minimum shortfall does not equal remaining exhausted count")

    input_artifacts.sort(
        key=lambda row: int(expected_artifacts[int(row["artifact_id"])]["task_offset"])
    )

    manifest = {
        "schema_version": RESERVE2_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "consolidated_approved_non_holdout_reserve2_evidence",
        "protocol_freeze_schema": RESERVE2_CONSOLIDATION_PROTOCOL_FREEZE_SCHEMA,
        "source_execution_freeze_schema": SOURCE_EXECUTION_FREEZE_SCHEMA,
        "source_capacity_extension_freeze_schema": SOURCE_CAPACITY_EXTENSION_FREEZE_SCHEMA,
        "capacity_extension_manifest_sha256": extension_sha,
        "base_factory_plan_sha256": extension["base_factory_plan_sha256"],
        "source_reserve_ledger_sha256": extension["reserve_ledger_sha256"],
        "source_exhausted_slots_sha256": extension["exhausted_slots_sha256"],
        "source_run_id": target["source_run_id"],
        "source_run_attempt": target["source_run_attempt"],
        "source_head_sha": target["source_head_sha"],
        "aggregate_artifact_id": target["aggregate_artifact_id"],
        "aggregate_artifact_digest": target["aggregate_artifact_digest"],
        "aggregate_summary_sha256": target["aggregate_summary_sha256"],
        "input_artifacts": input_artifacts,
        "input_artifact_count": len(input_artifacts),
        "prior_promoted_case_id_count": len(prior_promoted_case_ids),
        "prior_promoted_case_ids_sha256": prior_promoted_case_ids_sha256,
        "task_count": len(ledger_rows),
        "coverage_ranges": _compress_offsets(offsets),
        "reserve2_ledger_sha256": ledger_sha,
        "reserve2_adjudication_sha256": sha256_file(adjudication_path),
        "reserve2_exhausted_slots_sha256": sha256_file(exhausted_path),
        "reviewed_files": reviewed_files,
        "reviewed_record_count": reviewed_count,
        "pending_reserve2_adjudication_count": len(adjudication_rows),
        "remaining_exhausted_slot_count": exhausted_count,
        "validated_promoted_record_count": validated_promoted,
        "total_pending_adjudication_count": total_pending,
        "record_quota": record_quota,
        "maximum_fillable_slots_under_current_capacity": maximum_fillable,
        "minimum_capacity_shortfall": minimum_shortfall,
    }
    write_json(out_dir / "RESERVE2_MANIFEST.json", manifest)

    canonical_reason_counts = Counter(
        str(row["canonical_reason"])
        for row in ledger_rows
        if row["outcome"] != "promoted"
    )
    return {
        "schema_version": RESERVE2_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "redacted_consolidated_approved_non_holdout_reserve2_summary",
        "protocol_freeze_schema": RESERVE2_CONSOLIDATION_PROTOCOL_FREEZE_SCHEMA,
        "source_run_id": target["source_run_id"],
        "source_run_attempt": target["source_run_attempt"],
        "source_head_sha": target["source_head_sha"],
        "capacity_extension_manifest_sha256": extension_sha,
        "input_artifact_count": len(input_artifacts),
        "prior_promoted_case_id_count": len(prior_promoted_case_ids),
        "prior_promoted_case_ids_sha256": prior_promoted_case_ids_sha256,
        "task_count": len(ledger_rows),
        "coverage_ranges": _compress_offsets(offsets),
        "outcomes": dict(sorted(outcome_counts.items())),
        "canonical_reason_counts": dict(sorted(canonical_reason_counts.items())),
        "reviewed_record_count": reviewed_count,
        "pending_reserve2_adjudication_count": len(adjudication_rows),
        "remaining_exhausted_slot_count": exhausted_count,
        "prior_validated_promoted_record_count": prior_promoted,
        "prior_pending_adjudication_count": prior_pending,
        "validated_promoted_record_count": validated_promoted,
        "total_pending_adjudication_count": total_pending,
        "record_quota": record_quota,
        "maximum_fillable_slots_under_current_capacity": maximum_fillable,
        "minimum_capacity_shortfall": minimum_shortfall,
        "reserve2_ledger_sha256": ledger_sha,
        "reserve2_exhausted_slots_sha256": sha256_file(exhausted_path),
        "contains_source_text": False,
        "contains_gold_payloads": False,
        "contains_model_identity": False,
        "reserve2_execution_evidence_complete": True,
    }
