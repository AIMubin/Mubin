from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
from typing import Any
import json
import re

from .consolidation import (
    validate_primary_run_evidence,
    validate_reserve_run_evidence,
    validate_reserve2_run_evidence,
)
from .core import (
    canonical_json_bytes,
    dump_jsonl,
    load_json,
    load_jsonl,
    sha256_bytes,
    sha256_file,
    write_json,
)


ADJUDICATION_PACKET_SCHEMA_VERSION = 1
ADJUDICATION_PROTOCOL_FREEZE_SCHEMA = 30
EXPECTED_TOTAL_ADJUDICATIONS = 158
EXPECTED_LAYER_COUNTS = {"primary": 129, "reserve01": 24, "reserve02": 5}
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def _status(root: Path) -> dict[str, Any]:
    status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
    if int(status.get("freeze_schema_version", 0)) != ADJUDICATION_PROTOCOL_FREEZE_SCHEMA:
        raise ValueError("adjudication packet preparation requires freeze schema 30")
    surface = status.get("adjudication_review_surface")
    if not isinstance(surface, dict):
        raise ValueError("adjudication review surface missing")
    if int(surface.get("combined_pending_case_count", -1)) != EXPECTED_TOTAL_ADJUDICATIONS:
        raise ValueError("adjudication review surface count is not 158")
    if surface.get("human_or_authority_decision_required") is not True:
        raise ValueError("human/authority adjudication requirement missing")
    if surface.get("ai_may_self_authorize_acceptance") is not False:
        raise ValueError("AI self-authorization must remain disabled")
    target = status.get("adjudication_packet_target")
    if not isinstance(target, dict):
        raise ValueError("adjudication packet target missing")
    if target.get("ready") is not True or target.get("completed") is not False:
        raise ValueError("adjudication packet target is not open")
    if target.get("workflow") != ".github/workflows/h392-adjudication-packet.yml":
        raise ValueError("adjudication packet workflow binding mismatch")
    if int(target.get("expected_case_count", -1)) != EXPECTED_TOTAL_ADJUDICATIONS:
        raise ValueError("adjudication packet target count mismatch")
    if target.get("layer_counts") != EXPECTED_LAYER_COUNTS:
        raise ValueError("adjudication packet target layer counts mismatch")
    return status


def _layer_bindings(status: dict[str, Any]) -> dict[str, dict[str, Any]]:
    primary = status.get("last_completed_cumulative_consolidation")
    reserve = status.get("last_completed_reserve_consolidation")
    reserve2 = status.get("last_completed_reserve2_consolidation")
    if not all(isinstance(row, dict) for row in (primary, reserve, reserve2)):
        raise ValueError("canonical consolidation bindings incomplete")
    assert isinstance(primary, dict) and isinstance(reserve, dict) and isinstance(reserve2, dict)
    return {
        "primary": {
            "dir": "primary",
            "ledger": "CUMULATIVE_LEDGER.jsonl",
            "adjudication": "CUMULATIVE_ADJUDICATION.jsonl",
            "manifest": "CUMULATIVE_MANIFEST.json",
            "ledger_sha256": primary["cumulative_ledger_sha256"],
            "artifact_id": primary["artifact_id"],
            "artifact_digest": primary["artifact_digest"],
            "encrypted_bundle_sha256": primary["encrypted_bundle_sha256"],
            "source_run_id": primary["successful_run_id"],
            "source_head_sha": primary["runner_commit"],
            "workflow": ".github/workflows/h392-cumulative-consolidation.yml",
        },
        "reserve01": {
            "dir": "reserve01",
            "ledger": "RESERVE_LEDGER.jsonl",
            "adjudication": "RESERVE_ADJUDICATION.jsonl",
            "manifest": "RESERVE_MANIFEST.json",
            "ledger_sha256": reserve["reserve_ledger_sha256"],
            "artifact_id": reserve["artifact_id"],
            "artifact_digest": reserve["artifact_digest"],
            "encrypted_bundle_sha256": reserve["encrypted_bundle_sha256"],
            "source_run_id": reserve["successful_run_id"],
            "source_head_sha": reserve["runner_commit"],
            "workflow": ".github/workflows/h392-reserve-consolidation.yml",
        },
        "reserve02": {
            "dir": "reserve02",
            "ledger": "RESERVE2_LEDGER.jsonl",
            "adjudication": "RESERVE2_ADJUDICATION.jsonl",
            "manifest": "RESERVE2_MANIFEST.json",
            "ledger_sha256": reserve2["reserve2_ledger_sha256"],
            "artifact_id": reserve2["artifact_id"],
            "artifact_digest": reserve2["artifact_digest"],
            "encrypted_bundle_sha256": reserve2["encrypted_bundle_sha256"],
            "source_run_id": reserve2["successful_run_id"],
            "source_head_sha": reserve2["runner_commit"],
            "workflow": ".github/workflows/h392-reserve2-consolidation.yml",
        },
    }


def _verify_canonical_layer(
    layer: str,
    directory: Path,
    binding: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    ledger_path = directory / str(binding["ledger"])
    adjudication_path = directory / str(binding["adjudication"])
    manifest_path = directory / str(binding["manifest"])
    for path in (ledger_path, adjudication_path, manifest_path):
        if not path.is_file():
            raise ValueError(f"canonical {layer} file missing: {path.name}")
    if sha256_file(ledger_path) != binding["ledger_sha256"]:
        raise ValueError(f"canonical {layer} ledger SHA mismatch")

    manifest = load_json(manifest_path)
    if not isinstance(manifest, dict):
        raise ValueError(f"canonical {layer} manifest invalid")
    manifest_ledger_field = {
        "primary": "cumulative_ledger_sha256",
        "reserve01": "reserve_ledger_sha256",
        "reserve02": "reserve2_ledger_sha256",
    }[layer]
    manifest_adjudication_field = {
        "primary": "cumulative_adjudication_sha256",
        "reserve01": "reserve_adjudication_sha256",
        "reserve02": "reserve2_adjudication_sha256",
    }[layer]
    if manifest.get(manifest_ledger_field) != binding["ledger_sha256"]:
        raise ValueError(f"canonical {layer} manifest ledger binding mismatch")
    if manifest.get(manifest_adjudication_field) != sha256_file(adjudication_path):
        raise ValueError(f"canonical {layer} manifest adjudication binding mismatch")
    expected_manifest = {
        "primary": ("cumulative_non_holdout_primary_evidence", "freeze_schema_version", 25),
        "reserve01": ("consolidated_approved_non_holdout_reserve_evidence", "protocol_freeze_schema", 26),
        "reserve02": ("consolidated_approved_non_holdout_reserve2_evidence", "protocol_freeze_schema", 29),
    }[layer]
    expected_kind, schema_field, expected_schema = expected_manifest
    if (
        manifest.get("campaign_id") != "H3.9.2"
        or manifest.get("kind") != expected_kind
        or int(manifest.get(schema_field, -1)) != expected_schema
    ):
        raise ValueError(f"canonical {layer} manifest identity/schema mismatch")

    ledger = load_jsonl(ledger_path)
    adjudication = load_jsonl(adjudication_path)
    adjudication_ids = [str(row.get("task_id", "")) for row in adjudication]
    if "" in adjudication_ids or len(adjudication_ids) != len(set(adjudication_ids)):
        raise ValueError(f"canonical {layer} adjudication IDs invalid/duplicate")
    ledger_by_task = {str(row.get("task_id", "")): row for row in ledger}
    if "" in ledger_by_task or len(ledger_by_task) != len(ledger):
        raise ValueError(f"canonical {layer} ledger task IDs invalid/duplicate")
    ledger_adjudication_ids = {
        tid for tid, row in ledger_by_task.items() if row.get("outcome") == "adjudication"
    }
    if set(adjudication_ids) != ledger_adjudication_ids:
        raise ValueError(f"canonical {layer} adjudication file is not the exact ledger adjudication set")
    if (
        "adjudication_count" in manifest
        and int(manifest.get("adjudication_count", -1)) != len(adjudication)
    ):
        raise ValueError(f"canonical {layer} manifest adjudication count mismatch")
    for row in adjudication:
        tid = str(row["task_id"])
        source = ledger_by_task.get(tid)
        if source is None or source.get("outcome") != "adjudication":
            raise ValueError(f"canonical {layer} adjudication lacks adjudication ledger row: {tid}")
        if row.get("canonical_reason") is not None and row.get("canonical_reason") != source.get("canonical_reason"):
            raise ValueError(f"canonical {layer} adjudication reason mismatch: {tid}")
    return ledger, adjudication, manifest


def derive_adjudication_source_target(
    root: Path,
    canonical_root: Path,
) -> dict[str, Any]:
    status = _status(root)
    bindings = _layer_bindings(status)

    task_rows: list[dict[str, Any]] = []
    artifact_rows: dict[tuple[str, int], dict[str, Any]] = {}
    counts: Counter[str] = Counter()
    seen_tasks: set[str] = set()

    for layer in ("primary", "reserve01", "reserve02"):
        binding = bindings[layer]
        directory = canonical_root / str(binding["dir"])
        ledger, adjudication, _manifest = _verify_canonical_layer(
            layer, directory, binding
        )
        ledger_by_task = {str(row["task_id"]): row for row in ledger}
        order_field = {
            "primary": "primary_offset",
            "reserve01": "reserve_offset",
            "reserve02": "reserve2_offset",
        }[layer]
        ordered = sorted(
            adjudication,
            key=lambda row: int(ledger_by_task[str(row["task_id"])][order_field]),
        )
        for row in ordered:
            tid = str(row["task_id"])
            if tid in seen_tasks:
                raise ValueError(f"adjudication task repeated across canonical layers: {tid}")
            seen_tasks.add(tid)
            ledger_row = ledger_by_task[tid]
            artifact_id = int(ledger_row["source_artifact_id"])
            artifact_key = (layer, artifact_id)
            artifact = artifact_rows.setdefault(
                artifact_key,
                {
                    "layer": layer,
                    "source_run_id": int(ledger_row["source_run_id"]),
                    "source_run_attempt": int(ledger_row["source_run_attempt"]),
                    "source_head_sha": str(ledger_row["source_sha"]),
                    "artifact_id": artifact_id,
                    "artifact_sha256": _require_sha256(
                        ledger_row["source_artifact_sha256"],
                        f"{layer} artifact SHA",
                    ),
                    "encrypted_bundle_sha256": _require_sha256(
                        ledger_row["source_encrypted_bundle_sha256"],
                        f"{layer} encrypted bundle SHA",
                    ),
                    "task_ids": [],
                },
            )
            for field, value in (
                ("source_run_id", int(ledger_row["source_run_id"])),
                ("source_run_attempt", int(ledger_row["source_run_attempt"])),
                ("source_head_sha", str(ledger_row["source_sha"])),
                ("artifact_sha256", str(ledger_row["source_artifact_sha256"])),
                ("encrypted_bundle_sha256", str(ledger_row["source_encrypted_bundle_sha256"])),
            ):
                if artifact[field] != value:
                    raise ValueError(
                        f"canonical {layer} artifact provenance conflicts within ledger: {artifact_id}"
                    )
            artifact["task_ids"].append(tid)
            task_rows.append({
                "ordinal": len(task_rows),
                "layer": layer,
                "task_id": tid,
                "slot_id": ledger_row["slot_id"],
                "task_fingerprint": ledger_row["task_fingerprint"],
                "benchmark_id": ledger_row["benchmark_id"],
                "anchor_source_id": ledger_row["anchor_source_id"],
                "canonical_reason": ledger_row["canonical_reason"],
                "reconcile_reason": ledger_row.get("reconcile_reason"),
                "source_run_id": ledger_row["source_run_id"],
                "source_run_attempt": ledger_row["source_run_attempt"],
                "source_head_sha": ledger_row["source_sha"],
                "source_artifact_id": artifact_id,
                "source_artifact_sha256": ledger_row["source_artifact_sha256"],
                "source_encrypted_bundle_sha256": ledger_row[
                    "source_encrypted_bundle_sha256"
                ],
            })
            counts[layer] += 1

    if dict(counts) != EXPECTED_LAYER_COUNTS:
        raise ValueError(
            f"canonical adjudication layer counts differ: {dict(counts)}"
        )
    if len(task_rows) != EXPECTED_TOTAL_ADJUDICATIONS:
        raise ValueError("canonical adjudication surface is not exactly 158 cases")

    artifacts = sorted(
        artifact_rows.values(),
        key=lambda row: (
            {"primary": 0, "reserve01": 1, "reserve02": 2}[str(row["layer"])],
            int(row["source_run_id"]),
            int(row["artifact_id"]),
        ),
    )
    for row in artifacts:
        row["task_ids"] = sorted(row["task_ids"])

    target = {
        "schema_version": ADJUDICATION_PACKET_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "canonical_adjudication_source_target",
        "protocol_freeze_schema": ADJUDICATION_PROTOCOL_FREEZE_SCHEMA,
        "case_count": len(task_rows),
        "layer_counts": dict(sorted(counts.items())),
        "tasks": task_rows,
        "source_artifact_count": len(artifacts),
        "source_artifacts": artifacts,
        "canonical_layers": {
            layer: {
                "artifact_id": bindings[layer]["artifact_id"],
                "artifact_digest": bindings[layer]["artifact_digest"],
                "encrypted_bundle_sha256": bindings[layer][
                    "encrypted_bundle_sha256"
                ],
                "ledger_sha256": bindings[layer]["ledger_sha256"],
                "source_run_id": bindings[layer]["source_run_id"],
                "source_head_sha": bindings[layer]["source_head_sha"],
                "workflow": bindings[layer]["workflow"],
            }
            for layer in ("primary", "reserve01", "reserve02")
        },
    }
    target["target_sha256"] = sha256_bytes(canonical_json_bytes(target))
    return target


def _map_rows(path: Path, role: str) -> dict[str, dict[str, Any]]:
    rows = load_jsonl(path)
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        tid = str(row.get("task_id", ""))
        if not tid or tid in out:
            raise ValueError(f"{role} has invalid/duplicate task_id")
        out[tid] = row
    return out


def build_adjudication_packet(
    root: Path,
    canonical_root: Path,
    evidence_root: Path,
    source_cache_dir: Path,
    out_dir: Path,
    *,
    activation_path: Path,
    capacity_extension_path: Path,
) -> dict[str, Any]:
    target = derive_adjudication_source_target(root, canonical_root)
    expected_artifacts = {
        (str(row["layer"]), int(row["artifact_id"])): row
        for row in target["source_artifacts"]
    }

    evidence_dirs = sorted(
        path
        for path in evidence_root.iterdir()
        if path.is_dir() and (path / "ORIGIN.json").is_file()
    )
    if len(evidence_dirs) != len(expected_artifacts):
        raise ValueError("adjudication source evidence artifact count mismatch")

    validated_by_artifact: dict[tuple[str, int], dict[str, Any]] = {}
    raw_by_artifact: dict[tuple[str, int], dict[str, dict[str, dict[str, Any]]]] = {}

    for evidence in evidence_dirs:
        origin = load_json(evidence / "ORIGIN.json")
        layer = str(origin.get("adjudication_layer", ""))
        artifact_id = int(origin.get("artifact_id", 0))
        key = (layer, artifact_id)
        expected = expected_artifacts.get(key)
        if expected is None:
            raise ValueError(f"unreviewed adjudication source artifact: {layer}/{artifact_id}")
        for field in (
            "source_run_id",
            "source_run_attempt",
            "source_head_sha",
            "artifact_sha256",
            "encrypted_bundle_sha256",
        ):
            origin_field = {
                "source_run_id": "github_run_id",
                "source_run_attempt": "github_run_attempt",
                "source_head_sha": "head_sha",
                "artifact_sha256": "artifact_sha256",
                "encrypted_bundle_sha256": "encrypted_bundle_sha256",
            }[field]
            if origin.get(origin_field) != expected[field]:
                raise ValueError(
                    f"adjudication source artifact provenance mismatch: {layer}/{artifact_id}:{field}"
                )

        if layer == "primary":
            validated = validate_primary_run_evidence(
                root, evidence, source_cache_dir=source_cache_dir
            )
        elif layer == "reserve01":
            validated = validate_reserve_run_evidence(
                root,
                evidence,
                activation_path,
                source_cache_dir=source_cache_dir,
            )
        elif layer == "reserve02":
            validated = validate_reserve2_run_evidence(
                root,
                evidence,
                capacity_extension_path,
                source_cache_dir=source_cache_dir,
            )
        else:
            raise ValueError(f"unsupported adjudication layer: {layer}")

        bundle = evidence / "source-bearing"
        tasks = _map_rows(bundle / "curator-tasks.jsonl", "curator tasks")
        curator = _map_rows(bundle / "curator-responses.jsonl", "curator responses")
        verifier_tasks = _map_rows(bundle / "verifier-tasks.jsonl", "verifier tasks")
        verifier = _map_rows(bundle / "verifier-responses.jsonl", "verifier responses")
        adjudication = _map_rows(bundle / "adjudication.jsonl", "raw adjudication")
        validated_by_artifact[key] = validated
        raw_by_artifact[key] = {
            "tasks": tasks,
            "curator": curator,
            "verifier_tasks": verifier_tasks,
            "verifier": verifier,
            "adjudication": adjudication,
        }

    if set(validated_by_artifact) != set(expected_artifacts):
        raise ValueError("adjudication packet did not consume every expected source artifact")

    packet_rows: list[dict[str, Any]] = []
    decisions: list[dict[str, Any]] = []
    by_reason: Counter[str] = Counter()
    by_benchmark: Counter[str] = Counter()
    by_layer: Counter[str] = Counter()

    for target_row in target["tasks"]:
        layer = str(target_row["layer"])
        artifact_id = int(target_row["source_artifact_id"])
        key = (layer, artifact_id)
        validated = validated_by_artifact[key]
        raw = raw_by_artifact[key]
        tid = str(target_row["task_id"])
        ledger = {
            str(row["task_id"]): row for row in validated["ledger_rows"]
        }.get(tid)
        if ledger is None or ledger.get("outcome") != "adjudication":
            raise ValueError(f"source artifact no longer classifies task as adjudication: {tid}")
        if (
            ledger.get("task_fingerprint") != target_row["task_fingerprint"]
            or ledger.get("canonical_reason") != target_row["canonical_reason"]
        ):
            raise ValueError(f"source adjudication binding differs from canonical target: {tid}")
        task = validated["tasks"].get(tid)
        if task is None:
            raise ValueError(f"source task missing from validated artifact: {tid}")
        adjudication_row = validated["adjudication"].get(tid)
        if adjudication_row is None:
            raise ValueError(f"validated adjudication row missing: {tid}")
        if raw["adjudication"].get(tid) != adjudication_row:
            raise ValueError(f"raw adjudication row differs from validated row: {tid}")

        packet_id = sha256_bytes(
            canonical_json_bytes(
                {
                    "campaign_id": "H3.9.2",
                    "layer": layer,
                    "task_id": tid,
                    "task_fingerprint": target_row["task_fingerprint"],
                    "canonical_reason": target_row["canonical_reason"],
                }
            )
        )
        row = {
            "schema_version": ADJUDICATION_PACKET_SCHEMA_VERSION,
            "campaign_id": "H3.9.2",
            "packet_id": packet_id,
            "ordinal": target_row["ordinal"],
            "layer": layer,
            "task_id": tid,
            "slot_id": target_row["slot_id"],
            "task_fingerprint": target_row["task_fingerprint"],
            "benchmark_id": target_row["benchmark_id"],
            "anchor_source_id": target_row["anchor_source_id"],
            "canonical_reason": target_row["canonical_reason"],
            "reconcile_reason": target_row["reconcile_reason"],
            "source_provenance": {
                "source_run_id": target_row["source_run_id"],
                "source_run_attempt": target_row["source_run_attempt"],
                "source_head_sha": target_row["source_head_sha"],
                "source_artifact_id": artifact_id,
                "source_artifact_sha256": target_row["source_artifact_sha256"],
                "source_encrypted_bundle_sha256": target_row[
                    "source_encrypted_bundle_sha256"
                ],
            },
            "task": task,
            "curator_response": raw["curator"].get(tid),
            "verifier_task": raw["verifier_tasks"].get(tid),
            "verifier_response": raw["verifier"].get(tid),
            "adjudication_record": adjudication_row,
            "decision_policy": {
                "human_or_authority_decision_required": True,
                "ai_may_self_authorize_acceptance": False,
                "allowed_decisions": ["accepted", "rejected", "deferred"],
                "accepted_record_must_be_source_verified_and_resealed": True,
                "rejected_does_not_auto_authorize_reserve": True,
                "deferred_remains_nonreplaceable": True,
            },
        }
        packet_rows.append(row)
        decisions.append({
            "packet_id": packet_id,
            "task_id": tid,
            "decision": None,
            "reviewer": None,
            "reviewer_role": None,
            "reviewed_at": None,
            "source_verified": None,
            "accepted_candidate": None,
            "rationale": None,
        })
        by_reason[str(target_row["canonical_reason"])] += 1
        by_benchmark[str(target_row["benchmark_id"])] += 1
        by_layer[layer] += 1

    if len(packet_rows) != EXPECTED_TOTAL_ADJUDICATIONS:
        raise ValueError("adjudication packet case count mismatch")
    if dict(by_layer) != EXPECTED_LAYER_COUNTS:
        raise ValueError("adjudication packet layer counts mismatch")

    if out_dir.exists():
        if any(out_dir.iterdir()):
            raise ValueError("adjudication packet output directory must be empty")
    else:
        out_dir.mkdir(parents=True)

    packet_path = out_dir / "ADJUDICATION_PACKET.jsonl"
    dump_jsonl(packet_path, packet_rows)
    decisions_path = out_dir / "ADJUDICATION_DECISION_TEMPLATE.jsonl"
    dump_jsonl(decisions_path, decisions)
    target_path = out_dir / "ADJUDICATION_SOURCE_TARGET.json"
    write_json(target_path, target)

    packet_sha = sha256_file(packet_path)
    decision_template_sha = sha256_file(decisions_path)
    manifest = {
        "schema_version": ADJUDICATION_PACKET_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "human_authority_adjudication_packet",
        "protocol_freeze_schema": ADJUDICATION_PROTOCOL_FREEZE_SCHEMA,
        "case_count": len(packet_rows),
        "layer_counts": dict(sorted(by_layer.items())),
        "reason_counts": dict(sorted(by_reason.items())),
        "benchmark_counts": dict(sorted(by_benchmark.items())),
        "source_artifact_count": target["source_artifact_count"],
        "source_target_sha256": target["target_sha256"],
        "packet_sha256": packet_sha,
        "decision_template_sha256": decision_template_sha,
        "human_or_authority_decision_required": True,
        "ai_may_self_authorize_acceptance": False,
        "automatic_reserve_authorization_from_rejection": False,
    }
    write_json(out_dir / "ADJUDICATION_PACKET_MANIFEST.json", manifest)

    return {
        "schema_version": ADJUDICATION_PACKET_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "redacted_human_authority_adjudication_packet_summary",
        "protocol_freeze_schema": ADJUDICATION_PROTOCOL_FREEZE_SCHEMA,
        "case_count": len(packet_rows),
        "layer_counts": dict(sorted(by_layer.items())),
        "reason_counts": dict(sorted(by_reason.items())),
        "benchmark_counts": dict(sorted(by_benchmark.items())),
        "source_artifact_count": target["source_artifact_count"],
        "source_target_sha256": target["target_sha256"],
        "packet_sha256": packet_sha,
        "decision_template_sha256": decision_template_sha,
        "contains_source_text": False,
        "contains_gold_payloads": False,
        "contains_model_identity": False,
        "source_bearing_packet_encrypted": True,
        "human_or_authority_decision_required": True,
        "ai_may_self_authorize_acceptance": False,
    }
