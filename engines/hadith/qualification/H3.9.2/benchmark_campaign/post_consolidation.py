from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import canonical_json_bytes, load_json, load_jsonl, sha256_bytes, sha256_file, write_json
from .factory import build_factory_plan
from .freeze import FREEZE_SCHEMA_VERSION


ACTIVATION_SCHEMA_VERSION = 1
SOURCE_CUMULATIVE_FREEZE_SCHEMA = 25


def _factory_plan_binding(root: Path) -> tuple[dict[str, Any], str, dict[str, dict[str, Any]]]:
    plan = build_factory_plan(root)
    plan_sha = sha256_bytes(canonical_json_bytes(plan))
    slots = {str(row["slot_id"]): row for row in plan.get("slots", [])}
    return plan, plan_sha, slots


def build_reserve_activation_manifest(
    root: Path,
    cumulative_dir: Path,
    out_path: Path,
    *,
    expected_cumulative_ledger_sha256: str,
    expected_replacement_eligibility_sha256: str,
) -> dict[str, Any]:
    """Build a fail-closed activation manifest from frozen cumulative evidence.

    This function does not execute reserve tasks. It only converts the exact
    schema-25 replacement-eligibility evidence into a schema-26 authorization
    manifest whose reserve slot set is content-addressed and re-derived from the
    frozen Factory plan.
    """
    ledger_path = cumulative_dir / "CUMULATIVE_LEDGER.jsonl"
    eligibility_path = cumulative_dir / "REPLACEMENT_ELIGIBILITY.json"
    manifest_path = cumulative_dir / "CUMULATIVE_MANIFEST.json"
    for path in (ledger_path, eligibility_path, manifest_path):
        if not path.exists():
            raise FileNotFoundError(path)

    actual_ledger_sha = sha256_file(ledger_path)
    actual_eligibility_sha = sha256_file(eligibility_path)
    if actual_ledger_sha != expected_cumulative_ledger_sha256:
        raise ValueError("cumulative ledger SHA-256 differs from repository-reviewed binding")
    if actual_eligibility_sha != expected_replacement_eligibility_sha256:
        raise ValueError("replacement eligibility SHA-256 differs from repository-reviewed binding")

    source_manifest = load_json(manifest_path)
    if source_manifest.get("campaign_id") != "H3.9.2":
        raise ValueError("unexpected cumulative campaign_id")
    if int(source_manifest.get("freeze_schema_version", 0)) != SOURCE_CUMULATIVE_FREEZE_SCHEMA:
        raise ValueError("activation requires schema-25 cumulative evidence")
    if source_manifest.get("cumulative_ledger_sha256") != actual_ledger_sha:
        raise ValueError("cumulative manifest ledger binding mismatch")
    if source_manifest.get("replacement_eligibility_sha256") != actual_eligibility_sha:
        raise ValueError("cumulative manifest eligibility binding mismatch")

    eligibility = load_json(eligibility_path)
    if eligibility.get("kind") != "primary_replacement_eligibility":
        raise ValueError("unexpected replacement eligibility kind")
    if eligibility.get("campaign_id") != "H3.9.2":
        raise ValueError("unexpected replacement eligibility campaign_id")
    if int(eligibility.get("freeze_schema_version", 0)) != SOURCE_CUMULATIVE_FREEZE_SCHEMA:
        raise ValueError("replacement eligibility must come from schema 25")
    if eligibility.get("cumulative_ledger_sha256") != actual_ledger_sha:
        raise ValueError("replacement eligibility ledger binding mismatch")
    rules = eligibility.get("rules")
    if not isinstance(rules, dict):
        raise ValueError("replacement eligibility rules missing")
    if rules.get("promoted_is_replaceable") is not False:
        raise ValueError("promoted primaries must not be replaceable")
    if rules.get("pending_adjudication_is_replaceable") is not False:
        raise ValueError("pending adjudication must not be replaceable")
    if rules.get("terminal_primary_failure_is_replaceable") is not True:
        raise ValueError("terminal primary failure eligibility rule mismatch")
    if rules.get("reserve_reconciliation_enabled") is not False:
        raise ValueError("source cumulative evidence must not already enable reserves")

    _plan, plan_sha, slots = _factory_plan_binding(root)
    if eligibility.get("factory_plan_sha256") != plan_sha:
        raise ValueError("replacement eligibility factory-plan binding mismatch")

    ledger_rows = load_jsonl(ledger_path)
    ledger_by_task = {str(row.get("task_id", "")): row for row in ledger_rows}
    if len(ledger_by_task) != len(ledger_rows):
        raise ValueError("cumulative ledger contains duplicate/empty task IDs")

    eligible_rows = eligibility.get("eligible")
    if not isinstance(eligible_rows, list):
        raise ValueError("replacement eligibility rows missing")
    if int(eligibility.get("eligible_primary_count", -1)) != len(eligible_rows):
        raise ValueError("replacement eligibility count mismatch")

    activated: list[dict[str, Any]] = []
    seen_primary: set[str] = set()
    seen_reserve: set[str] = set()
    for row in eligible_rows:
        if not isinstance(row, dict):
            raise ValueError("replacement eligibility row must be an object")
        primary_slot_id = str(row.get("primary_slot_id", ""))
        primary_task_id = str(row.get("primary_task_id", ""))
        if not primary_slot_id or primary_slot_id in seen_primary:
            raise ValueError("duplicate/empty eligible primary slot")
        seen_primary.add(primary_slot_id)

        primary_slot = slots.get(primary_slot_id)
        if primary_slot is None or primary_slot.get("candidate_slot_kind") == "reserve":
            raise ValueError(f"eligible primary is not a frozen primary slot: {primary_slot_id}")
        expected_primary_binding = sha256_bytes(canonical_json_bytes(primary_slot))
        if row.get("primary_slot_binding_sha256") != expected_primary_binding:
            raise ValueError(f"eligible primary slot binding mismatch: {primary_slot_id}")

        ledger = ledger_by_task.get(primary_task_id)
        if ledger is None:
            raise ValueError(f"eligible primary task missing from cumulative ledger: {primary_task_id}")
        if str(ledger.get("slot_id", "")) != primary_slot_id:
            raise ValueError(f"eligible primary task/slot mismatch: {primary_task_id}")
        if ledger.get("replacement_eligible") is not True:
            raise ValueError(f"eligible primary ledger row is not replacement eligible: {primary_task_id}")
        if ledger.get("outcome") != "skipped":
            raise ValueError(f"only terminal skipped primaries may activate reserve slots: {primary_task_id}")
        if row.get("primary_task_fingerprint") != ledger.get("task_fingerprint"):
            raise ValueError(f"eligible primary task fingerprint mismatch: {primary_task_id}")
        if row.get("cumulative_ledger_sha256") != actual_ledger_sha:
            raise ValueError(f"eligible primary ledger binding mismatch: {primary_task_id}")

        reserve_slots = row.get("reserve_slots")
        if not isinstance(reserve_slots, list) or not reserve_slots:
            raise ValueError(f"eligible primary has no reserve slots: {primary_slot_id}")
        for reserve in reserve_slots:
            if not isinstance(reserve, dict):
                raise ValueError("reserve slot entry must be an object")
            reserve_id = str(reserve.get("slot_id", ""))
            if not reserve_id or reserve_id in seen_reserve:
                raise ValueError("duplicate/empty activated reserve slot")
            reserve_slot = slots.get(reserve_id)
            if reserve_slot is None or reserve_slot.get("candidate_slot_kind") != "reserve":
                raise ValueError(f"activated slot is not a frozen reserve: {reserve_id}")
            if reserve_slot.get("replacement_for_slot_id") != primary_slot_id:
                raise ValueError(f"reserve linkage mismatch: {reserve_id}")
            expected_reserve_binding = sha256_bytes(canonical_json_bytes(reserve_slot))
            if reserve.get("slot_binding_sha256") != expected_reserve_binding:
                raise ValueError(f"reserve slot binding mismatch: {reserve_id}")
            seen_reserve.add(reserve_id)
            activated.append({
                "reserve_slot_id": reserve_id,
                "reserve_slot_binding_sha256": expected_reserve_binding,
                "replacement_for_slot_id": primary_slot_id,
                "primary_task_id": primary_task_id,
                "primary_task_fingerprint": ledger["task_fingerprint"],
                "primary_offset": row.get("primary_offset"),
                "eligibility_reason": row.get("eligibility_reason"),
            })

    activated.sort(key=lambda row: str(row["reserve_slot_id"]))
    activation = {
        "schema_version": ACTIVATION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "reserve_activation_manifest",
        "protocol_freeze_schema": FREEZE_SCHEMA_VERSION,
        "source_cumulative_freeze_schema": SOURCE_CUMULATIVE_FREEZE_SCHEMA,
        "factory_plan_sha256": plan_sha,
        "cumulative_ledger_sha256": actual_ledger_sha,
        "replacement_eligibility_sha256": actual_eligibility_sha,
        "eligible_primary_count": len(eligible_rows),
        "activated_reserve_slot_count": len(activated),
        "reserve_reconciliation_enabled": True,
        "activated": activated,
        "policy": {
            "pending_adjudication_is_activatable": False,
            "promoted_primary_is_activatable": False,
            "activation_scope": "only hash-bound reserve slots linked to terminal replacement-eligible primaries",
        },
    }
    if out_path.exists():
        raise FileExistsError(f"refusing to overwrite activation manifest: {out_path}")
    write_json(out_path, activation)
    return activation


def validate_reserve_activation(
    root: Path,
    activation_path: Path,
    task_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate reserve tasks against a reviewed activation manifest."""
    activation = load_json(activation_path)
    if activation.get("kind") != "reserve_activation_manifest":
        raise ValueError("unexpected reserve activation kind")
    if activation.get("campaign_id") != "H3.9.2":
        raise ValueError("unexpected reserve activation campaign_id")
    if int(activation.get("protocol_freeze_schema", 0)) != FREEZE_SCHEMA_VERSION:
        raise ValueError("reserve activation protocol freeze schema mismatch")
    if activation.get("reserve_reconciliation_enabled") is not True:
        raise ValueError("reserve activation manifest does not enable reconciliation")

    status_path = root / "artifacts" / "H3.9.2-STATUS.json"
    if not status_path.exists():
        raise ValueError("reserve activation requires repository-approved status binding")
    status = load_json(status_path)
    approved = status.get("reserve_activation")
    if not isinstance(approved, dict) or approved.get("enabled") is not True:
        raise ValueError("reserve activation has not been reviewed and enabled in repository status")
    activation_sha = sha256_file(activation_path)
    if approved.get("manifest_sha256") != activation_sha:
        raise ValueError("reserve activation manifest SHA-256 differs from repository-approved binding")
    if approved.get("cumulative_ledger_sha256") != activation.get("cumulative_ledger_sha256"):
        raise ValueError("reserve activation cumulative-ledger binding differs from repository status")
    if approved.get("replacement_eligibility_sha256") != activation.get("replacement_eligibility_sha256"):
        raise ValueError("reserve activation eligibility binding differs from repository status")

    _plan, plan_sha, slots = _factory_plan_binding(root)
    if activation.get("factory_plan_sha256") != plan_sha:
        raise ValueError("reserve activation factory-plan binding mismatch")

    activated_rows = activation.get("activated")
    if not isinstance(activated_rows, list):
        raise ValueError("reserve activation rows missing")
    allowed: dict[str, dict[str, Any]] = {}
    for row in activated_rows:
        if not isinstance(row, dict):
            raise ValueError("reserve activation row must be an object")
        reserve_id = str(row.get("reserve_slot_id", ""))
        if not reserve_id or reserve_id in allowed:
            raise ValueError("duplicate/empty reserve activation slot")
        slot = slots.get(reserve_id)
        if slot is None or slot.get("candidate_slot_kind") != "reserve":
            raise ValueError(f"activation references non-reserve slot: {reserve_id}")
        if row.get("reserve_slot_binding_sha256") != sha256_bytes(canonical_json_bytes(slot)):
            raise ValueError(f"reserve activation slot binding mismatch: {reserve_id}")
        if row.get("replacement_for_slot_id") != slot.get("replacement_for_slot_id"):
            raise ValueError(f"reserve activation primary linkage mismatch: {reserve_id}")
        allowed[reserve_id] = row

    if int(activation.get("activated_reserve_slot_count", -1)) != len(allowed):
        raise ValueError("reserve activation slot count mismatch")

    for task in task_rows:
        if task.get("candidate_slot_kind") != "reserve":
            continue
        tid = str(task.get("task_id", ""))
        row = allowed.get(tid)
        if row is None:
            raise ValueError(f"reserve task is not activated by reviewed manifest: {tid}")
        if task.get("replacement_for_slot_id") != row.get("replacement_for_slot_id"):
            raise ValueError(f"reserve task replacement linkage differs from activation: {tid}")

    return activation
