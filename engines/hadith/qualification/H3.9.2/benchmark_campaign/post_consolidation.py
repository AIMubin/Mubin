from __future__ import annotations

from collections import Counter
from pathlib import Path
import tarfile
import tempfile
from typing import Any

from .core import (
    canonical_json_bytes,
    load_json,
    load_jsonl,
    sha256_bytes,
    sha256_file,
    write_json,
)
from .factory import build_factory_plan
from .artifact_crypto import decrypt_file


POST_CONSOLIDATION_SCHEMA_VERSION = 1
SOURCE_CUMULATIVE_FREEZE_SCHEMA_VERSION = 25


def _require_hex_sha256(value: Any, field: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(f"{field} must be a lowercase SHA-256 hex digest")
    return value


def _require_empty_output(out_dir: Path) -> None:
    if out_dir.exists():
        if any(out_dir.iterdir()):
            raise ValueError("post-consolidation output directory must be empty")
    else:
        out_dir.mkdir(parents=True)


def _factory_plan_bindings(root: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]], str]:
    plan = build_factory_plan(root)
    slots = {str(row["slot_id"]): row for row in plan["slots"]}
    if len(slots) != len(plan["slots"]):
        raise ValueError("frozen factory plan contains duplicate slot IDs")
    return plan, slots, sha256_bytes(canonical_json_bytes(plan))


def build_post_consolidation_plan(
    root: Path,
    encrypted_bundle_path: Path,
    out_dir: Path,
    evidence_path: Path,
    passphrase: str,
) -> dict[str, Any]:
    """Validate a frozen cumulative bundle and derive redacted next-step plans.

    This planner deliberately does not adjudicate cases and does not enable reserve
    execution. It verifies and decrypts the repository-bound cumulative ciphertext,
    then turns that exact boundary into two content-addressed,
    content-addressed control-plane plans: one for pending adjudication and one for
    linked reserve slots whose primaries are already proven terminally replaceable.
    """

    try:
        evidence_rel = str(evidence_path.resolve().relative_to(root.resolve()))
    except ValueError as exc:
        raise ValueError("post-consolidation evidence path must be inside campaign root") from exc
    evidence = load_json(evidence_path)

    status_path = root / "artifacts" / "H3.9.2-STATUS.json"
    if not status_path.is_file():
        raise FileNotFoundError(status_path)
    status = load_json(status_path)
    if int(status.get("freeze_schema_version", 0)) != 26:
        raise ValueError("post-consolidation planner requires repository freeze schema 26")
    protocol = status.get("post_consolidation_protocol")
    completed = status.get("last_completed_cumulative_consolidation")
    if not isinstance(protocol, dict) or not isinstance(completed, dict):
        raise ValueError("post-consolidation repository state is incomplete")
    if protocol.get("planning_ready") is not True or protocol.get("planning_completed") is not False:
        raise ValueError("post-consolidation planning target is not open")
    for key in (
        "adjudication_execution_enabled",
        "reserve_execution_enabled",
        "reserve_reconciliation_enabled",
    ):
        if protocol.get(key) is not False:
            raise ValueError(f"post-consolidation {key} must remain disabled")
    if status.get("reserve_reconciliation_enabled") is not False:
        raise ValueError("repository reserve reconciliation must remain disabled")
    if protocol.get("source_cumulative_evidence_path") != evidence_rel:
        raise ValueError("evidence path is not the reviewed post-consolidation source")
    if completed.get("evidence_path") != evidence_rel:
        raise ValueError("evidence path is not the last completed cumulative checkpoint")

    if evidence.get("campaign_id") != "H3.9.2":
        raise ValueError("post-consolidation evidence campaign mismatch")
    if evidence.get("evidence_kind") != "cumulative_non_holdout_primary_consolidation":
        raise ValueError("post-consolidation evidence kind mismatch")
    if evidence.get("canonical_main_evidence") is not True:
        raise ValueError("post-consolidation evidence is not canonical main evidence")
    if evidence.get("workflow", {}).get("conclusion") != "success":
        raise ValueError("post-consolidation source workflow is not successful")
    if int(evidence.get("workflow", {}).get("run_attempt", 0)) != 1:
        raise ValueError("post-consolidation source workflow must be attempt 1")

    expected_ledger_sha = _require_hex_sha256(
        evidence.get("bindings", {}).get("cumulative_ledger_sha256"),
        "evidence cumulative_ledger_sha256",
    )
    expected_eligibility_sha = _require_hex_sha256(
        evidence.get("bindings", {}).get("replacement_eligibility_sha256"),
        "evidence replacement_eligibility_sha256",
    )

    evidence_run_id = int(evidence.get("workflow", {}).get("run_id", 0))
    if evidence_run_id != int(protocol.get("source_cumulative_run_id", -1)):
        raise ValueError("evidence run is not the reviewed post-consolidation source")
    if evidence_run_id != int(completed.get("successful_run_id", -1)):
        raise ValueError("evidence run is not the last completed cumulative run")
    if evidence.get("runner_commit") != completed.get("runner_commit"):
        raise ValueError("evidence runner commit differs from completed cumulative state")
    if evidence.get("artifact", {}).get("id") != completed.get("artifact_id"):
        raise ValueError("evidence artifact ID differs from completed cumulative state")
    if evidence.get("artifact", {}).get("digest") != completed.get("artifact_digest"):
        raise ValueError("evidence artifact digest differs from completed cumulative state")
    if expected_ledger_sha != protocol.get("source_cumulative_ledger_sha256"):
        raise ValueError("evidence ledger hash differs from reviewed planning source")
    if expected_ledger_sha != completed.get("cumulative_ledger_sha256"):
        raise ValueError("evidence ledger hash differs from completed cumulative state")
    if expected_eligibility_sha != protocol.get("source_replacement_eligibility_sha256"):
        raise ValueError("evidence eligibility hash differs from reviewed planning source")
    if expected_eligibility_sha != completed.get("replacement_eligibility_sha256"):
        raise ValueError("evidence eligibility hash differs from completed cumulative state")

    expected_bundle_sha = _require_hex_sha256(
        evidence.get("artifact", {}).get("encrypted_bundle_sha256"),
        "evidence encrypted_bundle_sha256",
    )
    if expected_bundle_sha != protocol.get("source_encrypted_bundle_sha256"):
        raise ValueError("evidence encrypted bundle differs from reviewed planning source")
    if expected_bundle_sha != completed.get("encrypted_bundle_sha256"):
        raise ValueError("evidence encrypted bundle differs from completed cumulative state")
    if not encrypted_bundle_path.is_file():
        raise FileNotFoundError(encrypted_bundle_path)
    if sha256_file(encrypted_bundle_path) != expected_bundle_sha:
        raise ValueError("encrypted cumulative bundle differs from frozen repository evidence")
    if not isinstance(passphrase, str) or not passphrase:
        raise ValueError("post-consolidation artifact passphrase is required")

    with tempfile.TemporaryDirectory(prefix="h392-post-consolidation-") as tmp:
        work = Path(tmp)
        archive = work / "cumulative.tar.gz"
        cumulative_dir = work / "cumulative"
        decrypt_file(encrypted_bundle_path, archive, passphrase)
        cumulative_dir.mkdir()
        with tarfile.open(archive, "r:gz") as tf:
            members = tf.getmembers()
            for member in members:
                member_path = Path(member.name)
                if (
                    member_path.is_absolute()
                    or ".." in member_path.parts
                    or member.issym()
                    or member.islnk()
                    or member.isdev()
                ):
                    raise ValueError(f"unsafe cumulative tar member: {member.name}")
            tf.extractall(cumulative_dir, members=members, filter="data")
        return _build_from_decrypted_cumulative(
            root,
            cumulative_dir,
            out_dir,
            evidence,
            evidence_rel,
            protocol,
            completed,
            expected_ledger_sha,
            expected_eligibility_sha,
        )


def _build_from_decrypted_cumulative(
    root: Path,
    cumulative_dir: Path,
    out_dir: Path,
    evidence: dict[str, Any],
    evidence_rel: str,
    protocol: dict[str, Any],
    completed: dict[str, Any],
    expected_ledger_sha: str,
    expected_eligibility_sha: str,
) -> dict[str, Any]:
    manifest_path = cumulative_dir / "CUMULATIVE_MANIFEST.json"
    ledger_path = cumulative_dir / "CUMULATIVE_LEDGER.jsonl"
    adjudication_path = cumulative_dir / "CUMULATIVE_ADJUDICATION.jsonl"
    eligibility_path = cumulative_dir / "REPLACEMENT_ELIGIBILITY.json"
    for path in (manifest_path, ledger_path, adjudication_path, eligibility_path):
        if not path.is_file():
            raise FileNotFoundError(path)

    manifest = load_json(manifest_path)
    ledger = load_jsonl(ledger_path)
    adjudication = load_jsonl(adjudication_path)
    eligibility = load_json(eligibility_path)

    if manifest.get("campaign_id") != "H3.9.2":
        raise ValueError("cumulative manifest campaign mismatch")
    if manifest.get("kind") != "cumulative_non_holdout_primary_evidence":
        raise ValueError("cumulative manifest kind mismatch")
    if int(manifest.get("freeze_schema_version", 0)) != SOURCE_CUMULATIVE_FREEZE_SCHEMA_VERSION:
        raise ValueError("cumulative manifest must originate from freeze schema 25")

    actual_ledger_sha = sha256_file(ledger_path)
    actual_adjudication_sha = sha256_file(adjudication_path)
    actual_eligibility_sha = sha256_file(eligibility_path)
    if actual_ledger_sha != expected_ledger_sha:
        raise ValueError("cumulative ledger differs from frozen repository evidence")
    if actual_eligibility_sha != expected_eligibility_sha:
        raise ValueError("replacement eligibility differs from frozen repository evidence")
    if manifest.get("cumulative_ledger_sha256") != actual_ledger_sha:
        raise ValueError("cumulative manifest ledger binding mismatch")
    if manifest.get("cumulative_adjudication_sha256") != actual_adjudication_sha:
        raise ValueError("cumulative manifest adjudication binding mismatch")
    if manifest.get("replacement_eligibility_sha256") != actual_eligibility_sha:
        raise ValueError("cumulative manifest eligibility binding mismatch")

    canonical = evidence.get("canonical_input", {})
    result = evidence.get("result", {})
    expected_task_count = int(canonical.get("expected_primary_task_count", 0))
    expected_adjudication_count = int(result.get("pending_adjudication", -1))
    expected_eligible_count = int(result.get("replacement_eligible_primary_count", -1))
    expected_reviewed_count = int(result.get("reviewed_record_count", -1))
    if expected_task_count < 1:
        raise ValueError("frozen evidence expected task count is invalid")

    if expected_adjudication_count != int(protocol.get("expected_pending_adjudication_count", -1)):
        raise ValueError("evidence adjudication count differs from reviewed planning target")
    if expected_eligible_count != int(protocol.get("expected_eligible_primary_count", -1)):
        raise ValueError("evidence eligibility count differs from reviewed planning target")
    if expected_eligible_count != int(protocol.get("expected_reserve_task_count", -1)):
        raise ValueError("evidence reserve-task count differs from reviewed planning target")
    if expected_task_count != int(completed.get("expected_primary_tasks", -1)):
        raise ValueError("evidence task count differs from completed cumulative state")
    if canonical.get("campaign_run_ids") != completed.get("source_run_ids"):
        raise ValueError("evidence run history differs from completed cumulative state")
    if expected_adjudication_count != int(completed.get("pending_adjudication_count", -1)):
        raise ValueError("evidence adjudication count differs from completed cumulative state")
    if expected_eligible_count != int(completed.get("replacement_eligible_primary_count", -1)):
        raise ValueError("evidence eligibility count differs from completed cumulative state")
    if expected_reviewed_count != int(completed.get("reviewed_record_count", -1)):
        raise ValueError("evidence reviewed count differs from completed cumulative state")

    if int(manifest.get("task_count", -1)) != expected_task_count:
        raise ValueError("cumulative manifest task count differs from frozen evidence")
    if int(manifest.get("adjudication_count", -1)) != expected_adjudication_count:
        raise ValueError("cumulative manifest adjudication count differs from frozen evidence")
    if int(manifest.get("replacement_eligible_primary_count", -1)) != expected_eligible_count:
        raise ValueError("cumulative manifest eligibility count differs from frozen evidence")
    if int(manifest.get("reviewed_record_count", -1)) != expected_reviewed_count:
        raise ValueError("cumulative manifest reviewed count differs from frozen evidence")
    if manifest.get("input_run_ids") != canonical.get("campaign_run_ids"):
        raise ValueError("cumulative manifest run history differs from frozen evidence")

    if len(ledger) != expected_task_count:
        raise ValueError("cumulative ledger row count differs from frozen evidence")
    ledger_by_task: dict[str, dict[str, Any]] = {}
    offsets: list[int] = []
    for row in ledger:
        task_id = str(row.get("task_id", ""))
        if not task_id or task_id in ledger_by_task:
            raise ValueError("cumulative ledger contains empty or duplicate task IDs")
        ledger_by_task[task_id] = row
        offset = row.get("primary_offset")
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise ValueError(f"cumulative ledger primary offset invalid: {task_id}")
        offsets.append(offset)
    if offsets != list(range(expected_task_count)):
        raise ValueError("cumulative ledger is not the exact zero-based primary prefix")

    outcome_counts = Counter(str(row.get("outcome")) for row in ledger)
    if int(result.get("promoted", -1)) != outcome_counts.get("promoted", 0):
        raise ValueError("promoted count differs from frozen cumulative evidence")
    if expected_adjudication_count != outcome_counts.get("adjudication", 0):
        raise ValueError("adjudication count differs from frozen cumulative evidence")
    if int(result.get("skipped", -1)) != outcome_counts.get("skipped", 0):
        raise ValueError("skipped count differs from frozen cumulative evidence")

    adjudication_by_task: dict[str, dict[str, Any]] = {}
    for row in adjudication:
        task_id = str(row.get("task_id", ""))
        if not task_id or task_id in adjudication_by_task:
            raise ValueError("cumulative adjudication contains empty or duplicate task IDs")
        ledger_row = ledger_by_task.get(task_id)
        if ledger_row is None or ledger_row.get("outcome") != "adjudication":
            raise ValueError(f"adjudication row is not bound to an adjudication ledger row: {task_id}")
        if row.get("canonical_reason") != ledger_row.get("canonical_reason"):
            raise ValueError(f"adjudication canonical reason mismatch: {task_id}")
        adjudication_by_task[task_id] = row

    ledger_adjudication_ids = {
        task_id
        for task_id, row in ledger_by_task.items()
        if row.get("outcome") == "adjudication"
    }
    if set(adjudication_by_task) != ledger_adjudication_ids:
        raise ValueError("cumulative adjudication set differs from ledger adjudication set")
    if len(adjudication_by_task) != expected_adjudication_count:
        raise ValueError("cumulative adjudication row count mismatch")

    if eligibility.get("campaign_id") != "H3.9.2":
        raise ValueError("replacement eligibility campaign mismatch")
    if eligibility.get("kind") != "primary_replacement_eligibility":
        raise ValueError("replacement eligibility kind mismatch")
    if int(eligibility.get("freeze_schema_version", 0)) != SOURCE_CUMULATIVE_FREEZE_SCHEMA_VERSION:
        raise ValueError("replacement eligibility must originate from freeze schema 25")
    if eligibility.get("cumulative_ledger_sha256") != actual_ledger_sha:
        raise ValueError("replacement eligibility ledger binding mismatch")
    if eligibility.get("rules", {}).get("reserve_reconciliation_enabled") is not False:
        raise ValueError("source cumulative evidence unexpectedly enabled reserve reconciliation")

    plan, slot_by_id, factory_plan_sha = _factory_plan_bindings(root)
    if manifest.get("factory_plan_sha256") != factory_plan_sha:
        raise ValueError("cumulative manifest factory plan binding mismatch")
    if eligibility.get("factory_plan_sha256") != factory_plan_sha:
        raise ValueError("replacement eligibility factory plan binding mismatch")

    eligible_rows = eligibility.get("eligible")
    if not isinstance(eligible_rows, list):
        raise ValueError("replacement eligibility rows missing")
    if int(eligibility.get("eligible_primary_count", -1)) != len(eligible_rows):
        raise ValueError("replacement eligibility declared count mismatch")
    if len(eligible_rows) != expected_eligible_count:
        raise ValueError("replacement eligibility count differs from frozen evidence")

    eligible_primary_ids: set[str] = set()
    seen_reserve_ids: set[str] = set()
    reserve_plan_rows: list[dict[str, Any]] = []

    for entry in eligible_rows:
        if not isinstance(entry, dict):
            raise ValueError("replacement eligibility entry must be an object")
        primary_slot_id = str(entry.get("primary_slot_id", ""))
        primary_task_id = str(entry.get("primary_task_id", ""))
        if not primary_slot_id or primary_slot_id in eligible_primary_ids:
            raise ValueError("duplicate or empty eligible primary slot")
        primary_slot = slot_by_id.get(primary_slot_id)
        if primary_slot is None or primary_slot.get("candidate_slot_kind") == "reserve":
            raise ValueError(f"eligible primary slot is not a frozen primary: {primary_slot_id}")
        expected_primary_binding = sha256_bytes(canonical_json_bytes(primary_slot))
        if entry.get("primary_slot_binding_sha256") != expected_primary_binding:
            raise ValueError(f"eligible primary slot binding mismatch: {primary_slot_id}")

        ledger_row = ledger_by_task.get(primary_task_id)
        if ledger_row is None:
            raise ValueError(f"eligible primary task is absent from cumulative ledger: {primary_task_id}")
        if ledger_row.get("slot_id") != primary_slot_id:
            raise ValueError(f"eligible primary task/slot mismatch: {primary_task_id}")
        if ledger_row.get("outcome") != "skipped" or ledger_row.get("replacement_eligible") is not True:
            raise ValueError(f"eligible primary is not terminally replaceable in ledger: {primary_task_id}")
        if entry.get("primary_task_fingerprint") != ledger_row.get("task_fingerprint"):
            raise ValueError(f"eligible primary task fingerprint mismatch: {primary_task_id}")
        if entry.get("primary_offset") != ledger_row.get("primary_offset"):
            raise ValueError(f"eligible primary offset mismatch: {primary_task_id}")
        if entry.get("eligibility_reason") != ledger_row.get("canonical_reason"):
            raise ValueError(f"eligible primary reason mismatch: {primary_task_id}")
        if entry.get("cumulative_ledger_sha256") != actual_ledger_sha:
            raise ValueError(f"eligible primary ledger binding mismatch: {primary_task_id}")

        reserves = entry.get("reserve_slots")
        if not isinstance(reserves, list) or len(reserves) != 1:
            raise ValueError(f"eligible primary must bind exactly one frozen reserve slot: {primary_slot_id}")
        reserve = reserves[0]
        if not isinstance(reserve, dict):
            raise ValueError(f"eligible reserve binding must be an object: {primary_slot_id}")
        reserve_id = str(reserve.get("slot_id", ""))
        if not reserve_id or reserve_id in seen_reserve_ids:
            raise ValueError("duplicate or empty eligible reserve slot")
        reserve_slot = slot_by_id.get(reserve_id)
        if reserve_slot is None or reserve_slot.get("candidate_slot_kind") != "reserve":
            raise ValueError(f"eligible linked slot is not a frozen reserve: {reserve_id}")
        if reserve_slot.get("replacement_for_slot_id") != primary_slot_id:
            raise ValueError(f"reserve replacement link mismatch: {reserve_id}")
        if reserve_slot.get("partition") != "non_holdout":
            raise ValueError(f"post-consolidation reserve must be non-holdout: {reserve_id}")
        if reserve_slot.get("benchmark_id") != primary_slot.get("benchmark_id"):
            raise ValueError(f"reserve benchmark differs from linked primary: {reserve_id}")
        if reserve_slot.get("anchor_source_id") != primary_slot.get("anchor_source_id"):
            raise ValueError(f"reserve anchor differs from linked primary: {reserve_id}")
        expected_reserve_binding = sha256_bytes(canonical_json_bytes(reserve_slot))
        if reserve.get("slot_binding_sha256") != expected_reserve_binding:
            raise ValueError(f"reserve slot binding mismatch: {reserve_id}")

        eligible_primary_ids.add(primary_slot_id)
        seen_reserve_ids.add(reserve_id)
        reserve_plan_rows.append({
            "primary_slot_id": primary_slot_id,
            "primary_task_id": primary_task_id,
            "primary_offset": ledger_row["primary_offset"],
            "eligibility_reason": ledger_row["canonical_reason"],
            "primary_task_fingerprint": ledger_row["task_fingerprint"],
            "primary_slot_binding_sha256": expected_primary_binding,
            "reserve_slot_id": reserve_id,
            "reserve_slot_binding_sha256": expected_reserve_binding,
            "cumulative_ledger_sha256": actual_ledger_sha,
            "replacement_eligibility_sha256": actual_eligibility_sha,
        })

    ledger_eligible_slots = {
        str(row.get("slot_id"))
        for row in ledger
        if row.get("replacement_eligible") is True
    }
    if eligible_primary_ids != ledger_eligible_slots:
        raise ValueError("replacement eligibility set differs from cumulative ledger")

    adjudication_slot_ids = {
        str(ledger_by_task[task_id].get("slot_id"))
        for task_id in adjudication_by_task
    }
    if eligible_primary_ids & adjudication_slot_ids:
        raise ValueError("pending adjudication cannot also be replacement eligible")

    adjudication_plan_rows: list[dict[str, Any]] = []
    for task_id in sorted(
        adjudication_by_task,
        key=lambda tid: int(ledger_by_task[tid]["primary_offset"]),
    ):
        ledger_row = ledger_by_task[task_id]
        adjudication_plan_rows.append({
            "task_id": task_id,
            "slot_id": ledger_row["slot_id"],
            "primary_offset": ledger_row["primary_offset"],
            "benchmark_id": ledger_row["benchmark_id"],
            "anchor_source_id": ledger_row["anchor_source_id"],
            "canonical_reason": ledger_row["canonical_reason"],
            "source_run_id": ledger_row["source_run_id"],
            "source_sha": ledger_row["source_sha"],
            "cumulative_ledger_sha256": actual_ledger_sha,
        })

    reserve_plan_rows.sort(key=lambda row: int(row["primary_offset"]))

    _require_empty_output(out_dir)
    adjudication_plan = {
        "schema_version": POST_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "pending_adjudication_plan",
        "source_cumulative_run_id": evidence["workflow"]["run_id"],
        "cumulative_ledger_sha256": actual_ledger_sha,
        "pending_adjudication_count": len(adjudication_plan_rows),
        "execution_enabled": False,
        "decision_contract": {
            "automatic_acceptance": False,
            "reserve_substitution_allowed": False,
            "source_grounding_required": True,
            "final_resolution_protocol_required": True,
        },
        "items": adjudication_plan_rows,
    }
    adjudication_plan_path = out_dir / "ADJUDICATION_PLAN.json"
    write_json(adjudication_plan_path, adjudication_plan)

    reserve_plan = {
        "schema_version": POST_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "reserve_activation_plan",
        "source_cumulative_run_id": evidence["workflow"]["run_id"],
        "cumulative_ledger_sha256": actual_ledger_sha,
        "replacement_eligibility_sha256": actual_eligibility_sha,
        "eligible_primary_count": len(reserve_plan_rows),
        "reserve_task_count": len(reserve_plan_rows),
        "execution_enabled": False,
        "reconciliation_enabled": False,
        "activation_contract": {
            "only_hash_bound_eligible_reserves": True,
            "pending_adjudication_is_replaceable": False,
            "one_reserve_per_eligible_primary": True,
            "separate_reviewed_activation_required": True,
        },
        "items": reserve_plan_rows,
    }
    reserve_plan_path = out_dir / "RESERVE_ACTIVATION_PLAN.json"
    write_json(reserve_plan_path, reserve_plan)

    post_manifest = {
        "schema_version": POST_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "post_consolidation_planning_manifest",
        "source_cumulative_run_id": evidence["workflow"]["run_id"],
        "source_cumulative_evidence_path": evidence_rel,
        "source_cumulative_freeze_schema_version": SOURCE_CUMULATIVE_FREEZE_SCHEMA_VERSION,
        "factory_plan_sha256": factory_plan_sha,
        "cumulative_ledger_sha256": actual_ledger_sha,
        "replacement_eligibility_sha256": actual_eligibility_sha,
        "adjudication_plan_sha256": sha256_file(adjudication_plan_path),
        "reserve_activation_plan_sha256": sha256_file(reserve_plan_path),
        "pending_adjudication_count": len(adjudication_plan_rows),
        "eligible_primary_count": len(reserve_plan_rows),
        "reserve_task_count": len(reserve_plan_rows),
        "adjudication_execution_enabled": False,
        "reserve_execution_enabled": False,
        "reserve_reconciliation_enabled": False,
    }
    manifest_out_path = out_dir / "POST_CONSOLIDATION_MANIFEST.json"
    write_json(manifest_out_path, post_manifest)

    return {
        "schema_version": POST_CONSOLIDATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "redacted_post_consolidation_planning_summary",
        "source_cumulative_run_id": evidence["workflow"]["run_id"],
        "source_task_count": expected_task_count,
        "pending_adjudication_count": len(adjudication_plan_rows),
        "eligible_primary_count": len(reserve_plan_rows),
        "reserve_task_count": len(reserve_plan_rows),
        "cumulative_ledger_sha256": actual_ledger_sha,
        "replacement_eligibility_sha256": actual_eligibility_sha,
        "adjudication_plan_sha256": post_manifest["adjudication_plan_sha256"],
        "reserve_activation_plan_sha256": post_manifest["reserve_activation_plan_sha256"],
        "post_consolidation_manifest_sha256": sha256_file(manifest_out_path),
        "contains_source_text": False,
        "contains_gold_payloads": False,
        "contains_model_identity": False,
        "adjudication_execution_enabled": False,
        "reserve_execution_enabled": False,
        "reserve_reconciliation_enabled": False,
    }
