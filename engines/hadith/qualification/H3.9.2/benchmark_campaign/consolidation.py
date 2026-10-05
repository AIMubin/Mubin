from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import re

from .core import canonical_json_bytes, dump_jsonl, load_json, load_jsonl, sha256_bytes, sha256_file, write_json
from .factory import (
    _task_rows,
    _validate_response_identity,
    _validate_tasks_against_frozen_plan,
    build_factory_plan,
)
from .freeze import FREEZE_SCHEMA_VERSION


_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_COLLECTABLE_CURATOR_REJECTION_PREFIXES = (
    "adapter:contract_",
    "adapter:model_output_",
)


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _load_origin(path: Path) -> dict[str, Any]:
    row = load_json(path)
    if not isinstance(row, dict):
        raise ValueError(f"origin manifest must be an object: {path}")
    run_id = row.get("github_run_id")
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        raise ValueError(f"origin github_run_id invalid: {path}")
    run_attempt = row.get("github_run_attempt")
    if not isinstance(run_attempt, int) or isinstance(run_attempt, bool) or run_attempt < 1:
        raise ValueError(f"origin github_run_attempt invalid: {run_id}")
    if row.get("conclusion") != "success":
        raise ValueError(f"origin workflow run is not successful: {run_id}")
    if row.get("head_branch") != "main":
        raise ValueError(f"origin workflow run is not bound to main: {run_id}")
    head_sha = row.get("head_sha")
    if not isinstance(head_sha, str) or re.fullmatch(r"[a-f0-9]{40}", head_sha) is None:
        raise ValueError(f"origin head_sha invalid: {run_id}")
    artifact_id = row.get("artifact_id")
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool) or artifact_id < 1:
        raise ValueError(f"origin artifact_id invalid: {run_id}")
    if row.get("workflow_path") != ".github/workflows/h392-curation-campaign.yml":
        raise ValueError(f"origin workflow_path invalid: {run_id}")
    artifact_name = row.get("artifact_name")
    if not isinstance(artifact_name, str) or re.fullmatch(r"h392-curation-chunk-(\d+)-(\d+)", artifact_name) is None:
        raise ValueError(f"origin artifact_name invalid: {run_id}")
    _require_sha256(row.get("artifact_sha256"), f"origin artifact_sha256 for {run_id}")
    _require_sha256(row.get("encrypted_bundle_sha256"), f"origin encrypted_bundle_sha256 for {run_id}")
    return row


def _load_summary(path: Path) -> dict[str, Any]:
    row = load_json(path)
    if not isinstance(row, dict):
        raise ValueError(f"run summary must be an object: {path}")
    if row.get("schema_version") != 1:
        raise ValueError(f"run summary schema mismatch: {path}")
    if row.get("campaign_id") != "H3.9.2":
        raise ValueError(f"run summary campaign mismatch: {path}")
    if row.get("kind") != "non_holdout_curator_verifier_chunk":
        raise ValueError(f"run summary kind mismatch: {path}")
    if row.get("contains_source_text") is not False or row.get("contains_gold_payloads") is not False:
        raise ValueError(f"run summary is not redacted: {path}")
    if row.get("source_bearing_bundle_encrypted") is not True:
        raise ValueError(f"run summary does not assert encrypted source-bearing evidence: {path}")
    return row


def _rejection_map(manifest: dict[str, Any], role: str) -> dict[str, dict[str, Any]]:
    raw = manifest.get("rejections", [])
    if not isinstance(raw, list):
        raise ValueError(f"{role} manifest rejections must be a list")
    out: dict[str, dict[str, Any]] = {}
    for row in raw:
        if not isinstance(row, dict):
            raise ValueError(f"{role} manifest rejection must be an object")
        tid = str(row.get("task_id", ""))
        if not tid or tid in out:
            raise ValueError(f"{role} manifest has invalid/duplicate rejection task_id")
        error_code = row.get("error_code")
        if not isinstance(error_code, str) or not error_code:
            raise ValueError(f"{role} manifest rejection requires error_code: {tid}")
        out[tid] = row
    return out


def _response_map(path: Path, role: str) -> dict[str, dict[str, Any]]:
    rows = load_jsonl(path)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        tid = str(row.get("task_id", ""))
        if not tid or tid in out:
            raise ValueError(f"{role} responses contain invalid/duplicate task_id")
        out[tid] = row
    return out


def _verifier_task_ids(path: Path) -> set[str]:
    rows = load_jsonl(path)
    ids: set[str] = set()
    for row in rows:
        tid = str(row.get("task_id", ""))
        if not tid or tid in ids:
            raise ValueError("verifier tasks contain invalid/duplicate task_id")
        ids.add(tid)
    return ids


def _reviewed_by_task(reviewed_dir: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    if not reviewed_dir.exists():
        return out
    for path in sorted(reviewed_dir.glob("*/reviewed.jsonl")):
        for row in load_jsonl(path):
            tid = str(row.get("factory_task_id", ""))
            if not tid or tid in out:
                raise ValueError(f"reviewed records contain invalid/duplicate factory_task_id: {tid}")
            out[tid] = row
    return out


def _adjudication_by_task(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for row in load_jsonl(path):
        tid = str(row.get("task_id", ""))
        if not tid or tid in out:
            raise ValueError(f"adjudication contains invalid/duplicate task_id: {tid}")
        out[tid] = row
    return out


def _canonical_skip_reason(
    task_id: str,
    curator_response: dict[str, Any] | None,
    curator_rejection: dict[str, Any] | None,
) -> tuple[str, bool]:
    if curator_response is not None:
        if curator_response.get("status") == "no_candidate":
            return "curator_no_candidate", True
        raise ValueError(
            f"skipped task has a Curator response that is not no_candidate: {task_id}"
        )
    if curator_rejection is None:
        raise ValueError(
            f"skipped task has neither Curator no_candidate nor recorded rejection: {task_id}"
        )
    code = str(curator_rejection.get("error_code", ""))
    if not any(code.startswith(prefix) for prefix in _COLLECTABLE_CURATOR_REJECTION_PREFIXES):
        raise ValueError(
            f"skipped task has non-terminal Curator rejection category: {task_id}: {code}"
        )
    return f"curator_rejection:{code}", True


def _canonical_adjudication_reason(
    task_id: str,
    reconcile_reason: str | None,
    curator_response: dict[str, Any] | None,
    verifier_task_ids: set[str],
    verifier_response: dict[str, Any] | None,
    verifier_rejection: dict[str, Any] | None,
) -> str:
    if reconcile_reason != "missing_verifier_response":
        return reconcile_reason or "adjudication_unspecified"
    if (
        curator_response is not None
        and curator_response.get("status") == "candidate"
        and task_id not in verifier_task_ids
    ):
        return "candidate_input_blindness"
    if task_id in verifier_task_ids and verifier_response is None and verifier_rejection is not None:
        return f"verifier_rejection:{verifier_rejection.get('error_code')}"
    return "missing_verifier_response"


def _validate_manifest_counts(
    manifest: dict[str, Any],
    task_count: int,
    response_count: int,
    rejection_count: int,
    role: str,
) -> None:
    if manifest.get("task_count") != task_count:
        raise ValueError(f"{role} manifest task_count mismatch")
    if manifest.get("completed_task_count") != response_count:
        raise ValueError(f"{role} manifest completed_task_count mismatch")
    if manifest.get("rejected_task_count") != rejection_count:
        raise ValueError(f"{role} manifest rejected_task_count mismatch")
    if manifest.get("pending_task_count") != 0:
        raise ValueError(f"{role} manifest has pending tasks")
    if manifest.get("attempted_task_count") != response_count + rejection_count:
        raise ValueError(f"{role} manifest attempted_task_count mismatch")


def validate_primary_run_evidence(root: Path, evidence_dir: Path) -> dict[str, Any]:
    """Validate one decrypted canonical non-holdout primary curation artifact."""

    origin = _load_origin(evidence_dir / "ORIGIN.json")
    summary = _load_summary(evidence_dir / "CURATION_RUN_SUMMARY.json")
    bundle = evidence_dir / "source-bearing"
    if not bundle.is_dir():
        raise ValueError(f"decrypted source-bearing directory missing: {evidence_dir}")

    if str(summary.get("github_run_id")) != str(origin["github_run_id"]):
        raise ValueError("run summary github_run_id differs from origin")
    if summary.get("github_sha") != origin["head_sha"]:
        raise ValueError("run summary github_sha differs from origin")
    try:
        task_offset = int(summary.get("task_offset"))
        task_limit = int(summary.get("task_limit"))
        selected_task_count = int(summary.get("selected_task_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("run summary chunk bounds must be integers") from exc
    if task_offset < 0 or task_limit < 1 or selected_task_count < 1:
        raise ValueError("run summary chunk bounds must be positive")
    match = re.fullmatch(r"h392-curation-chunk-(\d+)-(\d+)", str(origin["artifact_name"]))
    assert match is not None
    if (int(match.group(1)), int(match.group(2))) != (task_offset, task_limit):
        raise ValueError("artifact name chunk bounds differ from run summary")
    if selected_task_count != task_limit:
        raise ValueError("run summary selected_task_count differs from task_limit")

    tasks_path = bundle / "curator-tasks.jsonl"
    curator_responses_path = bundle / "curator-responses.jsonl"
    curator_manifest_path = bundle / "curator-run.json"
    verifier_tasks_path = bundle / "verifier-tasks.jsonl"
    verifier_responses_path = bundle / "verifier-responses.jsonl"
    verifier_manifest_path = bundle / "verifier-run.json"
    adjudication_path = bundle / "adjudication.jsonl"
    ledger_path = bundle / "CURATION_LEDGER.jsonl"
    reviewed_dir = bundle / "reviewed"

    required = (
        tasks_path, curator_responses_path, curator_manifest_path,
        verifier_tasks_path, verifier_responses_path,
        adjudication_path, ledger_path,
    )
    for path in required:
        if not path.exists():
            raise ValueError(f"required run evidence missing: {path}")

    tasks = _task_rows(tasks_path)
    _validate_tasks_against_frozen_plan(root, tasks)
    if any(task.get("partition") != "non_holdout" for task in tasks):
        raise ValueError("cumulative primary evidence must be non-holdout only")
    if any(task.get("candidate_slot_kind") == "reserve" for task in tasks):
        raise ValueError("cumulative primary evidence must not contain reserve tasks")
    if len(tasks) != int(summary["selected_task_count"]):
        raise ValueError("run summary selected_task_count differs from decrypted tasks")
    _require_sha256(summary.get("selected_tasks_sha256"), "selected_tasks_sha256")
    if summary["selected_tasks_sha256"] != sha256_file(tasks_path):
        raise ValueError("run summary selected_tasks_sha256 mismatch")

    task_map = {str(row["task_id"]): row for row in tasks}
    curator_responses = _response_map(curator_responses_path, "curator")
    curator_manifest = load_json(curator_manifest_path)
    if curator_manifest.get("role") != "curator" or curator_manifest.get("partition") != "non_holdout":
        raise ValueError("Curator execution manifest role/partition mismatch")
    curator_rejections = _rejection_map(curator_manifest, "curator")
    _validate_manifest_counts(
        curator_manifest, len(tasks), len(curator_responses), len(curator_rejections), "curator"
    )
    if curator_manifest.get("tasks_sha256") != sha256_file(tasks_path):
        raise ValueError("Curator manifest task hash mismatch")
    if curator_manifest.get("output_sha256") != sha256_file(curator_responses_path):
        raise ValueError("Curator manifest output hash mismatch")
    if summary.get("curator", {}).get("output_sha256") != sha256_file(curator_responses_path):
        raise ValueError("run summary Curator output hash mismatch")
    curator_accounted = set(curator_responses) | set(curator_rejections)
    if curator_accounted != set(task_map):
        raise ValueError("Curator manifest does not account for every selected task")
    if set(curator_responses) & set(curator_rejections):
        raise ValueError("Curator response/rejection sets overlap")
    for tid, response in curator_responses.items():
        _validate_response_identity(response, task_map[tid], "curator")
    for tid, rejection in curator_rejections.items():
        if rejection.get("task_fingerprint") != task_map[tid].get("task_fingerprint"):
            raise ValueError(f"Curator rejection task fingerprint mismatch: {tid}")

    verifier_task_ids = _verifier_task_ids(verifier_tasks_path)
    if not verifier_task_ids.issubset(task_map):
        raise ValueError("Verifier tasks escape selected Curator task set")
    for tid in verifier_task_ids:
        if curator_responses.get(tid, {}).get("status") != "candidate":
            raise ValueError(f"Verifier task is not backed by a Curator candidate: {tid}")

    verifier_responses = _response_map(verifier_responses_path, "verifier")
    verifier_rejections: dict[str, dict[str, Any]] = {}
    if verifier_task_ids:
        if not verifier_manifest_path.exists():
            raise ValueError("Verifier execution manifest missing for non-empty verifier task set")
        verifier_manifest = load_json(verifier_manifest_path)
        if verifier_manifest.get("role") != "verifier" or verifier_manifest.get("partition") != "non_holdout":
            raise ValueError("Verifier execution manifest role/partition mismatch")
        verifier_rejections = _rejection_map(verifier_manifest, "verifier")
        _validate_manifest_counts(
            verifier_manifest,
            len(verifier_task_ids),
            len(verifier_responses),
            len(verifier_rejections),
            "verifier",
        )
        if verifier_manifest.get("tasks_sha256") != sha256_file(verifier_tasks_path):
            raise ValueError("Verifier manifest task hash mismatch")
        if verifier_manifest.get("output_sha256") != sha256_file(verifier_responses_path):
            raise ValueError("Verifier manifest output hash mismatch")
        if summary.get("verifier", {}).get("output_sha256") != sha256_file(verifier_responses_path):
            raise ValueError("run summary Verifier output hash mismatch")
        verifier_accounted = set(verifier_responses) | set(verifier_rejections)
        if verifier_accounted != verifier_task_ids:
            raise ValueError("Verifier manifest does not account for every verifier task")
        if set(verifier_responses) & set(verifier_rejections):
            raise ValueError("Verifier response/rejection sets overlap")
        for tid, response in verifier_responses.items():
            _validate_response_identity(response, task_map[tid], "verifier")
        for tid, rejection in verifier_rejections.items():
            if rejection.get("task_fingerprint") != task_map[tid].get("task_fingerprint"):
                raise ValueError(f"Verifier rejection task fingerprint mismatch: {tid}")
    elif load_jsonl(verifier_responses_path):
        raise ValueError("Verifier responses exist without verifier tasks")
    elif verifier_manifest_path.exists():
        raise ValueError("Verifier execution manifest exists without verifier tasks")

    ledger_rows = load_jsonl(ledger_path)
    ledger: dict[str, dict[str, Any]] = {}
    for row in ledger_rows:
        tid = str(row.get("task_id", ""))
        if tid not in task_map or tid in ledger:
            raise ValueError(f"curation ledger contains unknown/duplicate task: {tid}")
        if row.get("task_fingerprint") != task_map[tid].get("task_fingerprint"):
            raise ValueError(f"curation ledger task fingerprint mismatch: {tid}")
        if row.get("benchmark_id") != task_map[tid].get("benchmark_id"):
            raise ValueError(f"curation ledger benchmark mismatch: {tid}")
        if row.get("partition") != "non_holdout":
            raise ValueError(f"curation ledger partition mismatch: {tid}")
        if row.get("outcome") not in {"promoted", "adjudication", "skipped"}:
            raise ValueError(f"curation ledger outcome invalid: {tid}")
        ledger[tid] = row
    if set(ledger) != set(task_map):
        raise ValueError("curation ledger does not account for every selected task")

    reviewed = _reviewed_by_task(reviewed_dir)
    adjudication = _adjudication_by_task(adjudication_path)
    promoted_ids = {tid for tid, row in ledger.items() if row["outcome"] == "promoted"}
    adjudication_ids = {tid for tid, row in ledger.items() if row["outcome"] == "adjudication"}
    skipped_ids = {tid for tid, row in ledger.items() if row["outcome"] == "skipped"}
    if set(reviewed) != promoted_ids:
        raise ValueError("reviewed record set differs from promoted ledger set")
    if set(adjudication) != adjudication_ids:
        raise ValueError("adjudication record set differs from adjudication ledger set")
    if promoted_ids & adjudication_ids or promoted_ids & skipped_ids or adjudication_ids & skipped_ids:
        raise ValueError("curation ledger outcome sets overlap")

    for tid in promoted_ids:
        if curator_responses.get(tid, {}).get("status") != "candidate":
            raise ValueError(f"promoted task lacks Curator candidate response: {tid}")
        if tid not in verifier_task_ids or verifier_responses.get(tid, {}).get("status") != "candidate":
            raise ValueError(f"promoted task lacks independent Verifier candidate response: {tid}")
    for tid in adjudication_ids:
        if curator_responses.get(tid, {}).get("status") != "candidate":
            raise ValueError(f"adjudication task lacks Curator candidate response: {tid}")

    for tid, record in reviewed.items():
        task = task_map[tid]
        if record.get("factory_slot_id") != task.get("slot_id"):
            raise ValueError(f"reviewed record slot binding mismatch: {tid}")
        if record.get("factory_task_fingerprint") != task.get("task_fingerprint"):
            raise ValueError(f"reviewed record task fingerprint mismatch: {tid}")
        if str(record.get("case_id")) != str(ledger[tid].get("case_id")):
            raise ValueError(f"reviewed record case_id differs from ledger: {tid}")

    for tid, row in adjudication.items():
        if row.get("reason") != ledger[tid].get("reason"):
            raise ValueError(f"adjudication reason differs from ledger: {tid}")

    reconcile_summary = summary.get("reconciliation")
    if not isinstance(reconcile_summary, dict):
        raise ValueError("run summary reconciliation missing")
    observed_counts = Counter(row["outcome"] for row in ledger.values())
    expected_triplet = {
        "promoted": int(reconcile_summary.get("promoted_count", -1)),
        "adjudication": int(reconcile_summary.get("adjudication_count", -1)),
        "skipped": int(reconcile_summary.get("skipped_count", -1)),
    }
    if {k: observed_counts.get(k, 0) for k in expected_triplet} != expected_triplet:
        raise ValueError("run summary reconciliation counts differ from decrypted ledger")

    rows: list[dict[str, Any]] = []
    for tid in sorted(task_map):
        task = task_map[tid]
        entry = ledger[tid]
        outcome = entry["outcome"]
        reconcile_reason = entry.get("reason")
        eligible = False
        if outcome == "skipped":
            canonical_reason, eligible = _canonical_skip_reason(
                tid, curator_responses.get(tid), curator_rejections.get(tid)
            )
        elif outcome == "adjudication":
            canonical_reason = _canonical_adjudication_reason(
                tid,
                reconcile_reason if isinstance(reconcile_reason, str) else None,
                curator_responses.get(tid),
                verifier_task_ids,
                verifier_responses.get(tid),
                verifier_rejections.get(tid),
            )
        else:
            canonical_reason = "promoted"

        rows.append({
            "task_id": tid,
            "slot_id": task["slot_id"],
            "task_fingerprint": task["task_fingerprint"],
            "benchmark_id": task["benchmark_id"],
            "anchor_source_id": task["anchor_source_id"],
            "outcome": outcome,
            "reconcile_reason": reconcile_reason,
            "canonical_reason": canonical_reason,
            "case_id": entry.get("case_id"),
            "replacement_eligible": bool(eligible),
            "source_run_id": origin["github_run_id"],
            "source_run_attempt": origin["github_run_attempt"],
            "source_sha": origin["head_sha"],
            "source_artifact_id": origin["artifact_id"],
            "source_artifact_sha256": origin["artifact_sha256"],
            "source_encrypted_bundle_sha256": origin["encrypted_bundle_sha256"],
        })

    return {
        "origin": origin,
        "summary": summary,
        "tasks": task_map,
        "ledger_rows": rows,
        "reviewed": reviewed,
        "adjudication": adjudication,
    }


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


def consolidate_primary_evidence(
    root: Path,
    evidence_root: Path,
    out_dir: Path,
    *,
    expected_task_count: int | None = None,
) -> dict[str, Any]:
    evidence_dirs = sorted(
        path for path in evidence_root.iterdir()
        if path.is_dir() and (path / "ORIGIN.json").exists()
    )
    if not evidence_dirs:
        raise ValueError("no cumulative evidence directories found")

    plan = build_factory_plan(root)
    factory_plan_sha = sha256_bytes(canonical_json_bytes(plan))
    slot_by_id = {str(slot["slot_id"]): slot for slot in plan["slots"]}
    primary_non_holdout = [
        slot for slot in plan["slots"]
        if slot["partition"] == "non_holdout"
        and slot.get("candidate_slot_kind") != "reserve"
    ]
    offset_by_slot = {str(slot["slot_id"]): i for i, slot in enumerate(primary_non_holdout)}
    reserves_by_primary: dict[str, list[str]] = defaultdict(list)
    for slot in plan["slots"]:
        if slot["partition"] != "non_holdout" or slot.get("candidate_slot_kind") != "reserve":
            continue
        primary = str(slot.get("replacement_for_slot_id", ""))
        if primary not in offset_by_slot:
            raise ValueError(f"reserve candidate links to unknown non-holdout primary: {slot.get('slot_id')}")
        reserves_by_primary[primary].append(str(slot["slot_id"]))

    cumulative_rows: list[dict[str, Any]] = []
    reviewed_by_benchmark: dict[str, list[dict[str, Any]]] = defaultdict(list)
    adjudication_rows: list[dict[str, Any]] = []
    input_artifacts: list[dict[str, Any]] = []
    seen_tasks: set[str] = set()
    seen_case_ids: set[str] = set()
    seen_artifacts: set[tuple[int, int]] = set()
    run_sha_by_id: dict[int, str] = {}

    for evidence_dir in evidence_dirs:
        validated = validate_primary_run_evidence(root, evidence_dir)
        origin = validated["origin"]
        run_id = int(origin["github_run_id"])
        artifact_id = int(origin["artifact_id"])
        artifact_key = (run_id, artifact_id)
        if artifact_key in seen_artifacts:
            raise ValueError(f"duplicate source artifact in cumulative evidence: {run_id}/{artifact_id}")
        seen_artifacts.add(artifact_key)
        prior_sha = run_sha_by_id.setdefault(run_id, str(origin["head_sha"]))
        if prior_sha != origin["head_sha"]:
            raise ValueError(f"source run SHA differs across artifacts: {run_id}")
        input_artifacts.append({
            "github_run_id": run_id,
            "github_run_attempt": origin["github_run_attempt"],
            "head_sha": origin["head_sha"],
            "artifact_id": artifact_id,
            "artifact_name": origin["artifact_name"],
            "artifact_sha256": origin["artifact_sha256"],
            "encrypted_bundle_sha256": origin["encrypted_bundle_sha256"],
        })
        summary = validated["summary"]
        artifact_offsets = sorted(
            offset_by_slot[str(row["slot_id"])]
            for row in validated["ledger_rows"]
        )
        expected_artifact_offsets = list(range(
            int(summary["task_offset"]),
            int(summary["task_offset"]) + int(summary["selected_task_count"]),
        ))
        if artifact_offsets != expected_artifact_offsets:
            raise ValueError(
                f"artifact task offsets differ from bound chunk summary: {origin['artifact_id']}"
            )
        for row in validated["ledger_rows"]:
            tid = row["task_id"]
            if tid in seen_tasks:
                raise ValueError(f"duplicate primary task across cumulative evidence: {tid}")
            seen_tasks.add(tid)
            slot_id = str(row["slot_id"])
            if slot_id not in offset_by_slot:
                raise ValueError(f"cumulative evidence task is not a current frozen non-holdout primary: {tid}")
            enriched = dict(row)
            enriched["primary_offset"] = offset_by_slot[slot_id]
            cumulative_rows.append(enriched)

        for _tid, record in validated["reviewed"].items():
            cid = str(record.get("case_id"))
            if not cid or cid in seen_case_ids:
                raise ValueError(f"duplicate/empty case_id across cumulative evidence: {cid}")
            seen_case_ids.add(cid)
            reviewed_by_benchmark[str(record["benchmark_id"])].append(record)

        ledger_by_task = {row["task_id"]: row for row in validated["ledger_rows"]}
        for tid, row in validated["adjudication"].items():
            source = ledger_by_task[tid]
            enriched = dict(row)
            enriched["source_run_id"] = source["source_run_id"]
            enriched["source_sha"] = source["source_sha"]
            enriched["canonical_reason"] = source["canonical_reason"]
            adjudication_rows.append(enriched)

    cumulative_rows.sort(key=lambda row: int(row["primary_offset"]))
    offsets = [int(row["primary_offset"]) for row in cumulative_rows]
    if len(offsets) != len(set(offsets)):
        raise ValueError("cumulative primary offsets contain duplicates")
    if expected_task_count is not None:
        if not isinstance(expected_task_count, int) or isinstance(expected_task_count, bool) or expected_task_count < 1:
            raise ValueError("expected_task_count must be a positive integer")
        if len(cumulative_rows) != expected_task_count:
            raise ValueError(
                f"cumulative task count {len(cumulative_rows)} does not match expected {expected_task_count}"
            )
        if offsets != list(range(expected_task_count)):
            raise ValueError("cumulative primary evidence is not an exact zero-based prefix")

    out_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = out_dir / "CUMULATIVE_LEDGER.jsonl"
    dump_jsonl(ledger_path, cumulative_rows)
    ledger_sha = sha256_file(ledger_path)
    offset_by_task = {
        str(row["task_id"]): int(row["primary_offset"])
        for row in cumulative_rows
    }

    adjudication_rows.sort(key=lambda row: offset_by_task[str(row["task_id"])])
    adjudication_path = out_dir / "CUMULATIVE_ADJUDICATION.jsonl"
    dump_jsonl(adjudication_path, adjudication_rows)

    reviewed_count = 0
    reviewed_files: list[dict[str, Any]] = []
    for bid, rows in sorted(reviewed_by_benchmark.items()):
        rows.sort(key=lambda row: offset_by_slot[str(row["factory_slot_id"])])
        reviewed_count += len(rows)
        reviewed_path = out_dir / "reviewed" / bid / "reviewed.jsonl"
        dump_jsonl(reviewed_path, rows)
        reviewed_files.append({
            "benchmark_id": bid,
            "record_count": len(rows),
            "path": f"reviewed/{bid}/reviewed.jsonl",
            "sha256": sha256_file(reviewed_path),
        })

    eligibility_rows: list[dict[str, Any]] = []
    for row in cumulative_rows:
        if row["replacement_eligible"] is not True:
            continue
        primary_slot_id = str(row["slot_id"])
        reserve_ids = sorted(reserves_by_primary.get(primary_slot_id, []))
        if not reserve_ids:
            raise ValueError(f"eligible primary has no frozen linked reserve: {primary_slot_id}")
        primary_slot = slot_by_id[primary_slot_id]
        eligibility_rows.append({
            "primary_slot_id": primary_slot_id,
            "primary_slot_binding_sha256": sha256_bytes(canonical_json_bytes(primary_slot)),
            "primary_task_id": row["task_id"],
            "primary_task_fingerprint": row["task_fingerprint"],
            "primary_offset": row["primary_offset"],
            "primary_outcome": row["outcome"],
            "eligibility_reason": row["canonical_reason"],
            "reserve_slots": [
                {
                    "slot_id": reserve_id,
                    "slot_binding_sha256": sha256_bytes(canonical_json_bytes(slot_by_id[reserve_id])),
                }
                for reserve_id in reserve_ids
            ],
            "cumulative_ledger_sha256": ledger_sha,
        })

    eligibility = {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "primary_replacement_eligibility",
        "freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "factory_plan_sha256": factory_plan_sha,
        "cumulative_ledger_sha256": ledger_sha,
        "rules": {
            "promoted_is_replaceable": False,
            "pending_adjudication_is_replaceable": False,
            "terminal_primary_failure_is_replaceable": True,
            "reserve_reconciliation_enabled": False,
        },
        "eligible_primary_count": len(eligibility_rows),
        "eligible": eligibility_rows,
    }
    eligibility_path = out_dir / "REPLACEMENT_ELIGIBILITY.json"
    write_json(eligibility_path, eligibility)

    outcome_counts = Counter(str(row["outcome"]) for row in cumulative_rows)
    canonical_reasons = Counter(
        str(row["canonical_reason"]) for row in cumulative_rows
        if row["outcome"] != "promoted"
    )
    by_benchmark: dict[str, Counter[str]] = defaultdict(Counter)
    by_anchor: dict[str, Counter[str]] = defaultdict(Counter)
    for row in cumulative_rows:
        by_benchmark[str(row["benchmark_id"])][str(row["outcome"])] += 1
        by_anchor[str(row["anchor_source_id"])][str(row["outcome"])] += 1

    input_artifacts.sort(key=lambda row: (int(row["github_run_id"]), int(row["artifact_id"])))
    input_run_ids = sorted({int(row["github_run_id"]) for row in input_artifacts})
    manifest = {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "cumulative_non_holdout_primary_evidence",
        "freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "factory_plan_sha256": factory_plan_sha,
        "input_artifacts": input_artifacts,
        "input_artifact_count": len(input_artifacts),
        "input_run_ids": input_run_ids,
        "input_run_count": len(input_run_ids),
        "task_count": len(cumulative_rows),
        "coverage_ranges": _compress_offsets(offsets),
        "cumulative_ledger_sha256": ledger_sha,
        "cumulative_adjudication_sha256": sha256_file(adjudication_path),
        "replacement_eligibility_sha256": sha256_file(eligibility_path),
        "reviewed_files": reviewed_files,
        "reviewed_record_count": reviewed_count,
        "adjudication_count": len(adjudication_rows),
        "replacement_eligible_primary_count": len(eligibility_rows),
    }
    write_json(out_dir / "CUMULATIVE_MANIFEST.json", manifest)

    return {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "redacted_cumulative_non_holdout_primary_summary",
        "freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "input_run_ids": input_run_ids,
        "input_run_count": len(input_run_ids),
        "input_artifact_count": len(input_artifacts),
        "task_count": len(cumulative_rows),
        "coverage_ranges": _compress_offsets(offsets),
        "outcomes": dict(sorted(outcome_counts.items())),
        "canonical_reason_counts": dict(sorted(canonical_reasons.items())),
        "outcome_by_benchmark": {
            bid: dict(sorted(counts.items())) for bid, counts in sorted(by_benchmark.items())
        },
        "outcome_by_anchor_source": {
            sid: dict(sorted(counts.items())) for sid, counts in sorted(by_anchor.items())
        },
        "replacement_eligible_primary_count": len(eligibility_rows),
        "pending_adjudication_count": outcome_counts.get("adjudication", 0),
        "reviewed_record_count": reviewed_count,
        "cumulative_ledger_sha256": ledger_sha,
        "replacement_eligibility_sha256": sha256_file(eligibility_path),
        "contains_source_text": False,
        "contains_gold_payloads": False,
        "contains_model_identity": False,
        "reserve_reconciliation_enabled": False,
    }
