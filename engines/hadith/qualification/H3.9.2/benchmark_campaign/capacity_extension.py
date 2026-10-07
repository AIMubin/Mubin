from __future__ import annotations

from pathlib import Path
from typing import Any

from .core import canonical_json_bytes, load_json, load_jsonl, sha256_bytes, sha256_file, write_json
from .factory import build_factory_plan
from .post_consolidation import validate_reserve_activation


CAPACITY_EXTENSION_SCHEMA_VERSION = 1
CAPACITY_EXTENSION_PROTOCOL_FREEZE_SCHEMA = 27
SOURCE_RESERVE_CONSOLIDATION_FREEZE_SCHEMA = 26
NEW_RESERVE_ATTEMPT = 2


def _repository_file(root: Path, value: Any, label: str) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} path missing")
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError(f"{label} path must stay inside repository")
    candidate = root / relative
    if candidate.is_symlink():
        raise ValueError(f"{label} path must be a regular repository file")
    try:
        resolved = candidate.resolve(strict=True)
        resolved.relative_to(root.resolve())
    except (FileNotFoundError, ValueError) as exc:
        raise ValueError(f"{label} path must resolve inside repository") from exc
    if not resolved.is_file():
        raise ValueError(f"{label} path must be a regular repository file")
    return resolved


def _second_reserve_slot(primary_slot: dict[str, Any]) -> dict[str, Any]:
    if primary_slot.get("candidate_slot_kind") == "reserve":
        raise ValueError("capacity extension requires a primary slot")
    primary_id = str(primary_slot.get("slot_id", ""))
    if not primary_id:
        raise ValueError("capacity extension primary slot_id missing")
    slot = dict(primary_slot)
    slot["slot_id"] = f"{primary_id}:reserve:{NEW_RESERVE_ATTEMPT:02d}"
    slot["candidate_slot_kind"] = "reserve"
    slot["replacement_for_slot_id"] = primary_id
    slot["reserve_attempt"] = NEW_RESERVE_ATTEMPT
    return slot


def build_capacity_extension_manifest(
    root: Path,
    reserve_dir: Path,
    out_path: Path,
    *,
    expected_reserve_ledger_sha256: str,
    expected_exhausted_slots_sha256: str,
    expected_exhausted_slot_count: int,
) -> dict[str, Any]:
    """Build a redacted proposal for reserve-attempt-2 capacity.

    The proposal is derived only from the canonical schema-26 exhausted-slot
    evidence. It does not mutate the base Factory plan and does not authorize
    execution until the resulting manifest is independently reviewed and
    committed into repository state.
    """

    if (
        not isinstance(expected_exhausted_slot_count, int)
        or isinstance(expected_exhausted_slot_count, bool)
        or expected_exhausted_slot_count < 1
    ):
        raise ValueError("expected_exhausted_slot_count must be a positive integer")

    status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
    if int(status.get("freeze_schema_version", 0)) != CAPACITY_EXTENSION_PROTOCOL_FREEZE_SCHEMA:
        raise ValueError("capacity extension requires freeze schema 27")

    completed = status.get("last_completed_reserve_consolidation")
    if not isinstance(completed, dict):
        raise ValueError("canonical reserve consolidation status missing")
    if int(completed.get("exhausted_slot_count", -1)) != expected_exhausted_slot_count:
        raise ValueError("repository exhausted-slot count differs from requested extension")
    if completed.get("reserve_ledger_sha256") != expected_reserve_ledger_sha256:
        raise ValueError("repository reserve-ledger binding mismatch")
    if completed.get("exhausted_slots_sha256") != expected_exhausted_slots_sha256:
        raise ValueError("repository exhausted-slots binding mismatch")
    if int(completed.get("minimum_capacity_shortfall", -1)) != expected_exhausted_slot_count:
        raise ValueError("minimum capacity shortfall differs from exhausted-slot count")

    target = status.get("capacity_extension_target")
    if not isinstance(target, dict):
        raise ValueError("capacity extension target missing from repository status")
    if target.get("ready") is not True or target.get("completed") is not False:
        raise ValueError("capacity extension target is not open")
    if target.get("workflow") != ".github/workflows/h392-capacity-extension.yml":
        raise ValueError("capacity extension target workflow mismatch")
    if int(target.get("protocol_freeze_schema", 0)) != CAPACITY_EXTENSION_PROTOCOL_FREEZE_SCHEMA:
        raise ValueError("capacity extension target protocol schema mismatch")
    if int(target.get("expected_exhausted_slot_count", -1)) != expected_exhausted_slot_count:
        raise ValueError("capacity extension target exhausted count mismatch")
    if int(target.get("new_reserve_attempt", 0)) != NEW_RESERVE_ATTEMPT:
        raise ValueError("capacity extension target reserve attempt mismatch")
    if target.get("reserve_ledger_sha256") != expected_reserve_ledger_sha256:
        raise ValueError("capacity extension target reserve-ledger binding mismatch")
    if target.get("exhausted_slots_sha256") != expected_exhausted_slots_sha256:
        raise ValueError("capacity extension target exhausted-slots binding mismatch")

    repository_evidence_path = _repository_file(
        root,
        completed.get("evidence_path"),
        "reserve consolidation evidence",
    )
    repository_evidence = load_json(repository_evidence_path)
    if repository_evidence.get("evidence_kind") != "approved_non_holdout_reserve_consolidation":
        raise ValueError("unexpected canonical reserve consolidation evidence kind")
    if int(repository_evidence.get("protocol_freeze_schema", 0)) != SOURCE_RESERVE_CONSOLIDATION_FREEZE_SCHEMA:
        raise ValueError("capacity extension requires schema-26 reserve consolidation evidence")
    if repository_evidence.get("bindings", {}).get("reserve_ledger_sha256") != expected_reserve_ledger_sha256:
        raise ValueError("repository evidence reserve-ledger binding mismatch")
    if repository_evidence.get("bindings", {}).get("exhausted_slots_sha256") != expected_exhausted_slots_sha256:
        raise ValueError("repository evidence exhausted-slots binding mismatch")
    if int(repository_evidence.get("result", {}).get("exhausted", -1)) != expected_exhausted_slot_count:
        raise ValueError("repository evidence exhausted count mismatch")

    ledger_path = reserve_dir / "RESERVE_LEDGER.jsonl"
    exhausted_path = reserve_dir / "EXHAUSTED_SLOTS.json"
    manifest_path = reserve_dir / "RESERVE_MANIFEST.json"
    for source in (ledger_path, exhausted_path, manifest_path):
        if not source.exists():
            raise FileNotFoundError(source)

    actual_ledger_sha = sha256_file(ledger_path)
    actual_exhausted_sha = sha256_file(exhausted_path)
    if actual_ledger_sha != expected_reserve_ledger_sha256:
        raise ValueError("decrypted reserve ledger SHA-256 differs from canonical binding")
    if actual_exhausted_sha != expected_exhausted_slots_sha256:
        raise ValueError("decrypted exhausted-slots SHA-256 differs from canonical binding")

    source_manifest = load_json(manifest_path)
    if source_manifest.get("campaign_id") != "H3.9.2":
        raise ValueError("unexpected reserve consolidation campaign_id")
    if source_manifest.get("kind") != "consolidated_approved_non_holdout_reserve_evidence":
        raise ValueError("unexpected reserve consolidation manifest kind")
    if int(source_manifest.get("protocol_freeze_schema", 0)) != SOURCE_RESERVE_CONSOLIDATION_FREEZE_SCHEMA:
        raise ValueError("capacity extension source manifest must be schema 26")
    if source_manifest.get("reserve_ledger_sha256") != actual_ledger_sha:
        raise ValueError("reserve consolidation manifest ledger binding mismatch")
    if source_manifest.get("exhausted_slots_sha256") != actual_exhausted_sha:
        raise ValueError("reserve consolidation manifest exhausted-slots binding mismatch")
    if int(source_manifest.get("exhausted_slot_count", -1)) != expected_exhausted_slot_count:
        raise ValueError("reserve consolidation manifest exhausted count mismatch")

    exhausted = load_json(exhausted_path)
    if exhausted.get("campaign_id") != "H3.9.2":
        raise ValueError("unexpected exhausted-slot campaign_id")
    if exhausted.get("kind") != "exhausted_non_holdout_slots":
        raise ValueError("unexpected exhausted-slot evidence kind")
    if int(exhausted.get("protocol_freeze_schema", 0)) != SOURCE_RESERVE_CONSOLIDATION_FREEZE_SCHEMA:
        raise ValueError("exhausted-slot evidence must be schema 26")
    if exhausted.get("reserve_ledger_sha256") != actual_ledger_sha:
        raise ValueError("exhausted-slot evidence ledger binding mismatch")
    if int(exhausted.get("exhausted_slot_count", -1)) != expected_exhausted_slot_count:
        raise ValueError("exhausted-slot evidence count mismatch")
    policy = exhausted.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("exhausted-slot policy missing")
    if policy.get("automatic_second_reserve_authorized") is not False:
        raise ValueError("source evidence must not already authorize reserve attempt 2")
    if policy.get("capacity_extension_requires_reviewed_protocol_change") is not True:
        raise ValueError("source evidence must require a reviewed capacity extension")

    activation_status = status.get("reserve_activation")
    if not isinstance(activation_status, dict) or activation_status.get("enabled") is not True:
        raise ValueError("approved reserve activation status missing")
    activation_path = _repository_file(
        root,
        activation_status.get("evidence_path"),
        "reserve activation evidence",
    )
    activation = validate_reserve_activation(root, activation_path, [])
    activation_sha = sha256_file(activation_path)
    if source_manifest.get("activation_manifest_sha256") != activation_sha:
        raise ValueError("reserve consolidation activation binding mismatch")
    if target.get("activation_manifest_sha256") != activation_sha:
        raise ValueError("capacity extension target activation binding mismatch")

    base_plan = build_factory_plan(root)
    base_plan_sha = sha256_bytes(canonical_json_bytes(base_plan))
    if source_manifest.get("factory_plan_sha256") != base_plan_sha:
        raise ValueError("reserve consolidation base Factory-plan binding mismatch")
    if activation.get("factory_plan_sha256") != base_plan_sha:
        raise ValueError("reserve activation base Factory-plan binding mismatch")
    if target.get("base_factory_plan_sha256") != base_plan_sha:
        raise ValueError("capacity extension target base Factory-plan binding mismatch")
    slots = {str(row["slot_id"]): row for row in base_plan.get("slots", [])}

    activated_rows = activation.get("activated")
    if not isinstance(activated_rows, list):
        raise ValueError("reserve activation rows missing")
    activated = {
        str(row.get("reserve_slot_id", "")): row
        for row in activated_rows
        if isinstance(row, dict)
    }
    if "" in activated or len(activated) != len(activated_rows):
        raise ValueError("reserve activation contains duplicate/empty reserve IDs")

    ledger_rows = load_jsonl(ledger_path)
    ledger_by_slot: dict[str, dict[str, Any]] = {}
    for row in ledger_rows:
        slot_id = str(row.get("slot_id", ""))
        if not slot_id or slot_id in ledger_by_slot:
            raise ValueError("reserve ledger contains duplicate/empty slot IDs")
        ledger_by_slot[slot_id] = row

    exhausted_rows = exhausted.get("exhausted")
    if not isinstance(exhausted_rows, list):
        raise ValueError("exhausted-slot rows missing")
    if len(exhausted_rows) != expected_exhausted_slot_count:
        raise ValueError("exhausted-slot row count mismatch")

    extensions: list[dict[str, Any]] = []
    seen_primary: set[str] = set()
    seen_prior_reserve: set[str] = set()
    seen_new_reserve: set[str] = set()

    for row in exhausted_rows:
        if not isinstance(row, dict):
            raise ValueError("exhausted-slot row must be an object")
        primary_id = str(row.get("primary_slot_id", ""))
        prior_reserve_id = str(row.get("reserve_slot_id", ""))
        if not primary_id or primary_id in seen_primary:
            raise ValueError("duplicate/empty exhausted primary slot")
        if not prior_reserve_id or prior_reserve_id in seen_prior_reserve:
            raise ValueError("duplicate/empty exhausted reserve slot")
        seen_primary.add(primary_id)
        seen_prior_reserve.add(prior_reserve_id)

        primary_slot = slots.get(primary_id)
        prior_reserve_slot = slots.get(prior_reserve_id)
        if primary_slot is None or primary_slot.get("candidate_slot_kind") == "reserve":
            raise ValueError(f"exhausted linkage references non-primary slot: {primary_id}")
        if primary_slot.get("partition") != "non_holdout":
            raise ValueError(f"capacity extension is non-holdout only: {primary_id}")
        if (
            prior_reserve_slot is None
            or prior_reserve_slot.get("candidate_slot_kind") != "reserve"
            or prior_reserve_slot.get("replacement_for_slot_id") != primary_id
            or prior_reserve_slot.get("reserve_attempt") != 1
        ):
            raise ValueError(f"exhausted linkage does not reference reserve attempt 1: {prior_reserve_id}")
        if prior_reserve_id not in activated:
            raise ValueError(f"exhausted reserve was not in the reviewed activation: {prior_reserve_id}")

        ledger = ledger_by_slot.get(prior_reserve_id)
        if ledger is None:
            raise ValueError(f"exhausted reserve missing from reserve ledger: {prior_reserve_id}")
        if ledger.get("slot_state") != "exhausted":
            raise ValueError(f"reserve ledger row is not exhausted: {prior_reserve_id}")
        if ledger.get("outcome") != "skipped" or ledger.get("terminal_failure") is not True:
            raise ValueError(f"exhausted reserve is not a terminal skipped outcome: {prior_reserve_id}")
        if ledger.get("primary_slot_id") != primary_id:
            raise ValueError(f"reserve ledger primary linkage mismatch: {prior_reserve_id}")
        if row.get("reserve_task_fingerprint") != ledger.get("task_fingerprint"):
            raise ValueError(f"exhausted reserve fingerprint mismatch: {prior_reserve_id}")
        if row.get("reserve_ledger_sha256") != actual_ledger_sha:
            raise ValueError(f"exhausted row ledger binding mismatch: {prior_reserve_id}")
        if row.get("activation_manifest_sha256") != activation_sha:
            raise ValueError(f"exhausted row activation binding mismatch: {prior_reserve_id}")

        new_slot = _second_reserve_slot(primary_slot)
        new_reserve_id = str(new_slot["slot_id"])
        if new_reserve_id in slots:
            raise ValueError(f"reserve attempt 2 already exists in base Factory plan: {new_reserve_id}")
        if new_reserve_id in seen_new_reserve:
            raise ValueError(f"duplicate reserve attempt 2 extension: {new_reserve_id}")
        seen_new_reserve.add(new_reserve_id)

        extensions.append({
            "primary_slot_id": primary_id,
            "primary_slot_binding_sha256": sha256_bytes(canonical_json_bytes(primary_slot)),
            "prior_reserve_slot_id": prior_reserve_id,
            "prior_reserve_slot_binding_sha256": sha256_bytes(
                canonical_json_bytes(prior_reserve_slot)
            ),
            "prior_reserve_task_fingerprint": ledger["task_fingerprint"],
            "prior_reserve_offset": ledger["reserve_offset"],
            "prior_reserve_terminal_reason": ledger["canonical_reason"],
            "new_reserve_slot_id": new_reserve_id,
            "new_reserve_attempt": NEW_RESERVE_ATTEMPT,
            "new_reserve_slot": new_slot,
            "new_reserve_slot_binding_sha256": sha256_bytes(
                canonical_json_bytes(new_slot)
            ),
            "activation_manifest_sha256": activation_sha,
            "reserve_ledger_sha256": actual_ledger_sha,
            "exhausted_slots_sha256": actual_exhausted_sha,
        })

    extensions.sort(key=lambda row: int(row["prior_reserve_offset"]))
    if len(extensions) != expected_exhausted_slot_count:
        raise ValueError("capacity extension count differs from exhausted-slot evidence")

    manifest = {
        "schema_version": CAPACITY_EXTENSION_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "selective_reserve_capacity_extension_manifest",
        "protocol_freeze_schema": CAPACITY_EXTENSION_PROTOCOL_FREEZE_SCHEMA,
        "source_reserve_consolidation_freeze_schema": SOURCE_RESERVE_CONSOLIDATION_FREEZE_SCHEMA,
        "base_factory_plan_sha256": base_plan_sha,
        "reserve_consolidation_evidence_sha256": sha256_file(repository_evidence_path),
        "reserve_consolidation_run_id": completed["successful_run_id"],
        "reserve_consolidation_artifact_id": completed["artifact_id"],
        "reserve_consolidation_artifact_digest": completed["artifact_digest"],
        "activation_manifest_sha256": activation_sha,
        "reserve_ledger_sha256": actual_ledger_sha,
        "exhausted_slots_sha256": actual_exhausted_sha,
        "minimum_capacity_shortfall": completed["minimum_capacity_shortfall"],
        "extended_primary_count": len(extensions),
        "new_reserve_slot_count": len(extensions),
        "new_reserve_attempt": NEW_RESERVE_ATTEMPT,
        "capacity_extension_proposed": True,
        "execution_authorized": False,
        "requires_repository_approval": True,
        "extensions": extensions,
        "policy": {
            "scope": "only schema-26 exhausted non-holdout slots",
            "pending_adjudication_is_extended": False,
            "promoted_slot_is_extended": False,
            "base_factory_plan_is_mutated": False,
            "extension_is_append_only_overlay": True,
            "one_new_candidate_opportunity_per_exhausted_slot": True,
            "automatic_future_reserve_attempts": False,
        },
    }
    if out_path.exists():
        raise FileExistsError(f"refusing to overwrite capacity extension manifest: {out_path}")
    write_json(out_path, manifest)
    return manifest

def validate_frozen_capacity_extension(
    root: Path,
    manifest_path: Path,
    tasks: list[dict[str, Any]] | None = None,
    *,
    require_execution_enabled: bool = False,
) -> dict[str, Any]:
    """Validate the exact repository-frozen schema-27 reserve:02 overlay.

    The schema-27 manifest remains a proposal artifact with
    execution_authorized=false. Schema 28 may separately authorize execution
    of exactly that frozen set through repository status.
    """

    status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
    if int(status.get("freeze_schema_version", 0)) < CAPACITY_EXTENSION_PROTOCOL_FREEZE_SCHEMA:
        raise ValueError("repository schema predates capacity extension")

    frozen = status.get("capacity_extension_proposal")
    if not isinstance(frozen, dict) or frozen.get("frozen") is not True:
        raise ValueError("capacity extension proposal is not frozen")
    approved_path = _repository_file(
        root, frozen.get("evidence_path"), "capacity extension proposal"
    )
    if approved_path != manifest_path.resolve():
        raise ValueError("capacity extension path differs from repository-approved proposal")
    manifest_sha = sha256_file(approved_path)
    if manifest_sha != frozen.get("manifest_sha256"):
        raise ValueError("capacity extension proposal SHA-256 differs from repository status")

    manifest = load_json(approved_path)
    if (
        manifest.get("schema_version") != CAPACITY_EXTENSION_SCHEMA_VERSION
        or manifest.get("campaign_id") != "H3.9.2"
        or manifest.get("kind") != "selective_reserve_capacity_extension_manifest"
        or int(manifest.get("protocol_freeze_schema", 0))
            != CAPACITY_EXTENSION_PROTOCOL_FREEZE_SCHEMA
        or int(manifest.get("source_reserve_consolidation_freeze_schema", 0))
            != SOURCE_RESERVE_CONSOLIDATION_FREEZE_SCHEMA
        or manifest.get("capacity_extension_proposed") is not True
        or manifest.get("execution_authorized") is not False
        or manifest.get("requires_repository_approval") is not True
        or int(manifest.get("new_reserve_attempt", 0)) != NEW_RESERVE_ATTEMPT
    ):
        raise ValueError("capacity extension proposal contract invalid")

    policy = manifest.get("policy")
    if not isinstance(policy, dict):
        raise ValueError("capacity extension policy missing")
    expected_policy = {
        "scope": "only schema-26 exhausted non-holdout slots",
        "pending_adjudication_is_extended": False,
        "promoted_slot_is_extended": False,
        "base_factory_plan_is_mutated": False,
        "extension_is_append_only_overlay": True,
        "one_new_candidate_opportunity_per_exhausted_slot": True,
        "automatic_future_reserve_attempts": False,
    }
    if canonical_json_bytes(policy) != canonical_json_bytes(expected_policy):
        raise ValueError("capacity extension policy differs from reviewed contract")

    bindings = {
        "artifact_id": manifest.get("reserve_consolidation_artifact_id"),
        "artifact_digest": manifest.get("reserve_consolidation_artifact_digest"),
        "reserve_ledger_sha256": manifest.get("reserve_ledger_sha256"),
        "exhausted_slots_sha256": manifest.get("exhausted_slots_sha256"),
        "activation_manifest_sha256": manifest.get("activation_manifest_sha256"),
        "base_factory_plan_sha256": manifest.get("base_factory_plan_sha256"),
    }
    expected_bindings = {
        "artifact_id": frozen.get("source_reserve_consolidation_artifact_id"),
        "artifact_digest": frozen.get("source_reserve_consolidation_artifact_digest"),
        "reserve_ledger_sha256": frozen.get("reserve_ledger_sha256"),
        "exhausted_slots_sha256": frozen.get("exhausted_slots_sha256"),
        "activation_manifest_sha256": frozen.get("activation_manifest_sha256"),
        "base_factory_plan_sha256": frozen.get("base_factory_plan_sha256"),
    }
    if canonical_json_bytes(bindings) != canonical_json_bytes(expected_bindings):
        raise ValueError("capacity extension source bindings differ from frozen status")
    if manifest.get("reserve_consolidation_run_id") != frozen.get(
        "source_reserve_consolidation_run_id"
    ):
        raise ValueError("capacity extension reserve-consolidation run binding mismatch")

    base_plan = build_factory_plan(root)
    base_plan_sha = sha256_bytes(canonical_json_bytes(base_plan))
    if manifest.get("base_factory_plan_sha256") != base_plan_sha:
        raise ValueError("capacity extension base Factory-plan binding mismatch")
    base_slots = {str(row["slot_id"]): row for row in base_plan.get("slots", [])}

    rows = manifest.get("extensions")
    if not isinstance(rows, list):
        raise ValueError("capacity extension rows missing")
    expected_count = int(frozen.get("new_reserve_slot_count", -1))
    if (
        len(rows) != expected_count
        or int(manifest.get("extended_primary_count", -1)) != expected_count
        or int(manifest.get("new_reserve_slot_count", -1)) != expected_count
    ):
        raise ValueError("capacity extension row count differs from frozen status")

    seen_primary: set[str] = set()
    seen_prior: set[str] = set()
    seen_new: set[str] = set()
    by_new_id: dict[str, dict[str, Any]] = {}
    prior_offsets: list[int] = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("capacity extension row must be an object")
        primary_id = str(row.get("primary_slot_id", ""))
        prior_id = str(row.get("prior_reserve_slot_id", ""))
        new_id = str(row.get("new_reserve_slot_id", ""))
        if (
            not primary_id
            or primary_id in seen_primary
            or not prior_id
            or prior_id in seen_prior
            or not new_id
            or new_id in seen_new
        ):
            raise ValueError("capacity extension contains duplicate/empty slot identity")
        seen_primary.add(primary_id)
        seen_prior.add(prior_id)
        seen_new.add(new_id)

        primary = base_slots.get(primary_id)
        prior = base_slots.get(prior_id)
        if primary is None or primary.get("candidate_slot_kind") == "reserve":
            raise ValueError(f"capacity extension primary slot invalid: {primary_id}")
        if primary.get("partition") != "non_holdout":
            raise ValueError(f"capacity extension must remain non-holdout: {primary_id}")
        if (
            prior is None
            or prior.get("candidate_slot_kind") != "reserve"
            or prior.get("replacement_for_slot_id") != primary_id
            or prior.get("reserve_attempt") != 1
        ):
            raise ValueError(f"capacity extension predecessor invalid: {prior_id}")
        if row.get("primary_slot_binding_sha256") != sha256_bytes(
            canonical_json_bytes(primary)
        ):
            raise ValueError(f"capacity extension primary binding mismatch: {primary_id}")
        if row.get("prior_reserve_slot_binding_sha256") != sha256_bytes(
            canonical_json_bytes(prior)
        ):
            raise ValueError(f"capacity extension predecessor binding mismatch: {prior_id}")

        expected_new = _second_reserve_slot(primary)
        if new_id != expected_new["slot_id"]:
            raise ValueError(f"capacity extension reserve:02 ID mismatch: {new_id}")
        if row.get("new_reserve_attempt") != NEW_RESERVE_ATTEMPT:
            raise ValueError(f"capacity extension reserve attempt mismatch: {new_id}")
        if canonical_json_bytes(row.get("new_reserve_slot")) != canonical_json_bytes(
            expected_new
        ):
            raise ValueError(f"capacity extension reserve:02 slot mismatch: {new_id}")
        if row.get("new_reserve_slot_binding_sha256") != sha256_bytes(
            canonical_json_bytes(expected_new)
        ):
            raise ValueError(f"capacity extension reserve:02 binding mismatch: {new_id}")
        if new_id in base_slots:
            raise ValueError(f"capacity extension illegally mutates base Factory plan: {new_id}")
        if row.get("activation_manifest_sha256") != frozen.get(
            "activation_manifest_sha256"
        ):
            raise ValueError(f"capacity extension activation binding mismatch: {new_id}")
        if row.get("reserve_ledger_sha256") != frozen.get("reserve_ledger_sha256"):
            raise ValueError(f"capacity extension ledger binding mismatch: {new_id}")
        if row.get("exhausted_slots_sha256") != frozen.get("exhausted_slots_sha256"):
            raise ValueError(f"capacity extension exhausted binding mismatch: {new_id}")
        if row.get("prior_reserve_terminal_reason") != (
            "curator_rejection:adapter:contract_support_not_verbatim"
        ):
            raise ValueError(f"capacity extension predecessor is not canonical terminal failure: {new_id}")
        offset = row.get("prior_reserve_offset")
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError(f"capacity extension prior reserve offset invalid: {new_id}")
        prior_offsets.append(offset)
        by_new_id[new_id] = row

    if prior_offsets != sorted(prior_offsets) or len(prior_offsets) != len(set(prior_offsets)):
        raise ValueError("capacity extension rows are not in unique canonical offset order")

    if require_execution_enabled:
        if int(status.get("freeze_schema_version", 0)) < 28:
            raise ValueError("reserve:02 execution requires freeze schema 28")
        if status.get("capacity_extension_enabled") is not True:
            raise ValueError("capacity extension execution is not enabled")
        execution = status.get("reserve2_execution_target")
        if not isinstance(execution, dict):
            raise ValueError("reserve:02 execution target missing")
        if execution.get("ready") is not True or execution.get("completed") is not False:
            raise ValueError("reserve:02 execution target is not open")
        if execution.get("workflow") != ".github/workflows/h392-reserve2-campaign.yml":
            raise ValueError("reserve:02 execution workflow binding mismatch")
        if execution.get("task_scope") != "approved_capacity_extension":
            raise ValueError("reserve:02 execution task scope mismatch")
        if int(execution.get("expected_task_count", -1)) != expected_count:
            raise ValueError("reserve:02 execution task count mismatch")
        if execution.get("capacity_extension_manifest_sha256") != manifest_sha:
            raise ValueError("reserve:02 execution manifest binding mismatch")
        if execution.get("capacity_extension_evidence_path") != frozen.get("evidence_path"):
            raise ValueError("reserve:02 execution evidence-path binding mismatch")

    if tasks:
        for task in tasks:
            task_id = str(task.get("task_id", ""))
            row = by_new_id.get(task_id)
            if row is None:
                raise ValueError(f"task is outside approved capacity extension: {task_id}")
            slot = row["new_reserve_slot"]
            if task.get("slot_id") != task_id:
                raise ValueError(f"reserve:02 task_id/slot_id mismatch: {task_id}")
            for field in (
                "benchmark_id", "partition", "anchor_source_id", "task_type",
                "allowed_labels", "auto_promotion", "risk_tier", "visibility",
                "candidate_slot_kind", "replacement_for_slot_id", "reserve_attempt",
            ):
                if task.get(field) != slot.get(field):
                    raise ValueError(
                        f"reserve:02 task {field} differs from approved overlay: {task_id}"
                    )

    return manifest

