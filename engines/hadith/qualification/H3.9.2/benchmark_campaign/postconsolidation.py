from __future__ import annotations

from collections import Counter
import hashlib
import hmac
from pathlib import Path
from typing import Any, Callable

from .core import (
    canonical_json_bytes,
    dump_jsonl,
    load_json,
    load_jsonl,
    sha256_bytes,
    sha256_file,
    write_json,
)
from .factory import build_factory_plan
from .freeze import FREEZE_SCHEMA_VERSION


PROTOCOL_VERSION = 1
SOURCE_CUMULATIVE_FREEZE_SCHEMA = 25
_DOMAIN_PREFIX = b"mubin-h392-postconsolidation-v1\x00"


def _require_sha256(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        raise ValueError(f"{label} must be a lowercase SHA-256 hex digest")
    return value


def _slot_binding(slot: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(slot))


def _derive_nonce(secret: str, domain: str, identity_binding: str) -> str:
    if not isinstance(secret, str) or not secret:
        raise ValueError("post-consolidation commitment secret must be non-empty")
    _require_sha256(identity_binding, "identity_binding")
    msg = _DOMAIN_PREFIX + domain.encode("ascii") + b"\x00" + identity_binding.encode("ascii")
    return hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).hexdigest()


def _commitment_leaf(
    *,
    domain: str,
    identity_binding: str,
    cumulative_ledger_sha256: str,
    replacement_eligibility_sha256: str,
    nonce: str,
) -> str:
    return sha256_bytes(canonical_json_bytes({
        "protocol_version": PROTOCOL_VERSION,
        "domain": domain,
        "identity_binding_sha256": identity_binding,
        "cumulative_ledger_sha256": cumulative_ledger_sha256,
        "replacement_eligibility_sha256": replacement_eligibility_sha256,
        "nonce": nonce,
    }))


def _commitment_set_sha256(leaves: list[str]) -> str:
    for leaf in leaves:
        _require_sha256(leaf, "commitment leaf")
    if len(leaves) != len(set(leaves)):
        raise ValueError("commitment leaves must be unique")
    return sha256_bytes(canonical_json_bytes(sorted(leaves)))


def _ensure_empty_dir(path: Path) -> None:
    if path.exists():
        if any(path.iterdir()):
            raise ValueError(f"output directory must be empty: {path}")
    else:
        path.mkdir(parents=True)


def _relative_to_root(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError as exc:
        raise ValueError("control evidence path must be inside campaign root") from exc


def _paths_overlap(a: Path, b: Path) -> bool:
    ar = a.resolve()
    br = b.resolve()
    if ar == br:
        return True
    return ar in br.parents or br in ar.parents


def prepare_postconsolidation_bindings(
    root: Path,
    cumulative_dir: Path,
    control_evidence_path: Path,
    public_out_dir: Path,
    private_out_dir: Path,
    *,
    commitment_secret: str,
    nonce_deriver: Callable[[str, str, str], str] = _derive_nonce,
) -> dict[str, Any]:
    """Prepare hash-only public bindings and a private execution map.

    This stage does not enable reserve reconciliation or adjudication execution.
    It transforms the already-frozen schema-25 cumulative evidence into
    schema-26 commitments that can later authorize exact reserve/adjudication
    identities without publishing task IDs, slot IDs, sources, gold, or model
    identity.
    """

    if FREEZE_SCHEMA_VERSION != 26:
        raise ValueError("post-consolidation preparation requires freeze schema 26")
    if _paths_overlap(public_out_dir, private_out_dir):
        raise ValueError("public and private output directories must not overlap")
    if _paths_overlap(cumulative_dir, public_out_dir) or _paths_overlap(
        cumulative_dir, private_out_dir
    ):
        raise ValueError("post-consolidation outputs must not overlap cumulative plaintext")

    control = load_json(control_evidence_path)
    status = load_json(root / "artifacts" / "H3.9.2-STATUS.json")
    control_rel = _relative_to_root(root, control_evidence_path)

    if control.get("campaign_id") != "H3.9.2":
        raise ValueError("cumulative control campaign_id mismatch")
    if control.get("evidence_kind") != "cumulative_non_holdout_primary_consolidation":
        raise ValueError("cumulative control evidence_kind mismatch")
    if control.get("canonical_main_evidence") is not True:
        raise ValueError("cumulative control is not canonical main evidence")

    canonical = control.get("canonical_input")
    result = control.get("result")
    bindings = control.get("bindings")
    artifact = control.get("artifact")
    workflow = control.get("workflow")
    if not all(isinstance(x, dict) for x in (canonical, result, bindings, artifact, workflow)):
        raise ValueError("cumulative control record is incomplete")
    if canonical.get("expected_primary_task_count") != 210:
        raise ValueError("post-consolidation preparation requires exact 210-primary evidence")
    if canonical.get("primary_offset_start") != 0 or canonical.get("primary_offset_end_inclusive") != 209:
        raise ValueError("cumulative control is not the exact 0..209 prefix")
    if canonical.get("exact_zero_based_prefix") is not True:
        raise ValueError("cumulative control does not assert exact zero-based coverage")
    if result.get("task_count") != 210:
        raise ValueError("cumulative control task_count mismatch")
    if workflow.get("path") != ".github/workflows/h392-cumulative-consolidation.yml":
        raise ValueError("cumulative control workflow path mismatch")
    if workflow.get("run_attempt") != 1:
        raise ValueError("cumulative control must bind workflow attempt 1")
    if workflow.get("event") != "workflow_dispatch":
        raise ValueError("cumulative control must bind a manual workflow dispatch")
    if workflow.get("conclusion") != "success":
        raise ValueError("cumulative control workflow did not succeed")
    if status.get("freeze_schema_version") != FREEZE_SCHEMA_VERSION:
        raise ValueError("repository status freeze schema differs from active protocol")

    ledger_sha = _require_sha256(bindings.get("cumulative_ledger_sha256"), "cumulative_ledger_sha256")
    eligibility_sha = _require_sha256(
        bindings.get("replacement_eligibility_sha256"),
        "replacement_eligibility_sha256",
    )

    completed = status.get("last_completed_cumulative_consolidation")
    target = status.get("cumulative_consolidation_target")
    if not isinstance(completed, dict) or not isinstance(target, dict):
        raise ValueError("status lacks completed cumulative state")
    if completed.get("evidence_path") != control_rel:
        raise ValueError("status last-completed evidence path differs from control record")
    if completed.get("successful_run_id") != workflow.get("run_id"):
        raise ValueError("status last-completed run differs from control record")
    if completed.get("runner_commit") != control.get("runner_commit"):
        raise ValueError("status runner commit differs from control record")
    if completed.get("source_run_ids") != canonical.get("campaign_run_ids"):
        raise ValueError("status source run list differs from control record")
    if completed.get("expected_primary_tasks") != canonical.get("expected_primary_task_count"):
        raise ValueError("status cumulative task count differs from control record")
    if completed.get("artifact_id") != artifact.get("id"):
        raise ValueError("status cumulative artifact ID differs from control record")
    if completed.get("artifact_digest") != artifact.get("digest"):
        raise ValueError("status cumulative artifact digest differs from control record")
    if completed.get("summary_sha256") != artifact.get("redacted_summary_sha256"):
        raise ValueError("status cumulative summary hash differs from control record")
    if completed.get("encrypted_bundle_sha256") != artifact.get("encrypted_bundle_sha256"):
        raise ValueError("status cumulative encrypted-bundle hash differs from control record")
    if artifact.get("redacted") is not True or artifact.get("source_bearing_payload_encrypted") is not True:
        raise ValueError("cumulative control artifact policy is not redacted/encrypted")
    if completed.get("cumulative_ledger_sha256") != ledger_sha:
        raise ValueError("status cumulative ledger hash differs from control record")
    if completed.get("replacement_eligibility_sha256") != eligibility_sha:
        raise ValueError("status replacement eligibility hash differs from control record")
    if target.get("ready") is not False or target.get("completed") is not True:
        raise ValueError("210-primary cumulative target is not closed")
    if status.get("reserve_reconciliation_enabled") is not False:
        raise ValueError("reserve reconciliation must remain disabled during preparation")

    manifest_path = cumulative_dir / "CUMULATIVE_MANIFEST.json"
    ledger_path = cumulative_dir / "CUMULATIVE_LEDGER.jsonl"
    adjudication_path = cumulative_dir / "CUMULATIVE_ADJUDICATION.jsonl"
    eligibility_path = cumulative_dir / "REPLACEMENT_ELIGIBILITY.json"
    for path in (manifest_path, ledger_path, adjudication_path, eligibility_path):
        if not path.exists():
            raise ValueError(f"required cumulative file missing: {path.name}")

    if sha256_file(ledger_path) != ledger_sha:
        raise ValueError("materialized cumulative ledger hash differs from frozen control")
    if sha256_file(eligibility_path) != eligibility_sha:
        raise ValueError("materialized replacement eligibility hash differs from frozen control")

    manifest = load_json(manifest_path)
    eligibility = load_json(eligibility_path)
    ledger_rows = load_jsonl(ledger_path)
    adjudication_rows = load_jsonl(adjudication_path)

    if manifest.get("campaign_id") != "H3.9.2" or manifest.get("kind") != "cumulative_non_holdout_primary_evidence":
        raise ValueError("cumulative manifest identity mismatch")
    if manifest.get("freeze_schema_version") != SOURCE_CUMULATIVE_FREEZE_SCHEMA:
        raise ValueError("cumulative manifest must originate from freeze schema 25")
    if manifest.get("task_count") != 210 or manifest.get("coverage_ranges") != [{"start": 0, "end": 210}]:
        raise ValueError("cumulative manifest does not bind exact 0..209 coverage")
    if manifest.get("input_run_ids") != canonical.get("campaign_run_ids"):
        raise ValueError("cumulative manifest run list differs from frozen control")
    if manifest.get("input_run_count") != canonical.get("input_run_count"):
        raise ValueError("cumulative manifest run count differs from frozen control")
    if manifest.get("input_artifact_count") != canonical.get("input_artifact_count"):
        raise ValueError("cumulative manifest artifact count differs from frozen control")
    input_artifacts = manifest.get("input_artifacts")
    if (
        not isinstance(input_artifacts, list)
        or len(input_artifacts) != canonical.get("input_artifact_count")
    ):
        raise ValueError("cumulative manifest input artifact list/count mismatch")
    observed_run_ids = sorted({
        int(row.get("github_run_id"))
        for row in input_artifacts
        if isinstance(row, dict) and isinstance(row.get("github_run_id"), int)
    })
    if observed_run_ids != canonical.get("campaign_run_ids"):
        raise ValueError("cumulative manifest artifact run IDs differ from frozen control")
    if any(
        not isinstance(row, dict)
        or row.get("github_run_attempt") != 1
        or not isinstance(row.get("artifact_id"), int)
        or not isinstance(row.get("artifact_name"), str)
        or not isinstance(row.get("head_sha"), str)
        or len(row.get("head_sha", "")) != 40
        for row in input_artifacts
    ):
        raise ValueError("cumulative manifest input artifact provenance is incomplete")
    if manifest.get("reviewed_record_count") != result.get("reviewed_record_count"):
        raise ValueError("cumulative manifest reviewed count differs from frozen control")
    if manifest.get("adjudication_count") != result.get("pending_adjudication"):
        raise ValueError("cumulative manifest adjudication count differs from frozen control")
    if manifest.get("replacement_eligible_primary_count") != result.get("replacement_eligible_primary_count"):
        raise ValueError("cumulative manifest replacement count differs from frozen control")
    if manifest.get("cumulative_ledger_sha256") != ledger_sha:
        raise ValueError("cumulative manifest ledger hash mismatch")
    if manifest.get("replacement_eligibility_sha256") != eligibility_sha:
        raise ValueError("cumulative manifest eligibility hash mismatch")
    adjudication_sha = _require_sha256(
        manifest.get("cumulative_adjudication_sha256"),
        "cumulative_adjudication_sha256",
    )
    if sha256_file(adjudication_path) != adjudication_sha:
        raise ValueError("materialized cumulative adjudication hash mismatch")

    plan = build_factory_plan(root)
    factory_plan_sha = sha256_bytes(canonical_json_bytes(plan))
    if manifest.get("factory_plan_sha256") != factory_plan_sha:
        raise ValueError("current frozen Factory plan differs from cumulative evidence")

    if eligibility.get("campaign_id") != "H3.9.2" or eligibility.get("kind") != "primary_replacement_eligibility":
        raise ValueError("replacement eligibility identity mismatch")
    if eligibility.get("freeze_schema_version") != SOURCE_CUMULATIVE_FREEZE_SCHEMA:
        raise ValueError("replacement eligibility must originate from freeze schema 25")
    if eligibility.get("factory_plan_sha256") != factory_plan_sha:
        raise ValueError("replacement eligibility Factory-plan binding mismatch")
    if eligibility.get("cumulative_ledger_sha256") != ledger_sha:
        raise ValueError("replacement eligibility ledger binding mismatch")
    rules = eligibility.get("rules")
    if not isinstance(rules, dict):
        raise ValueError("replacement eligibility rules missing")
    if rules.get("promoted_is_replaceable") is not False:
        raise ValueError("promoted primaries must not be replaceable")
    if rules.get("pending_adjudication_is_replaceable") is not False:
        raise ValueError("pending adjudications must not be replaceable")
    if rules.get("terminal_primary_failure_is_replaceable") is not True:
        raise ValueError("terminal-primary eligibility rule mismatch")
    if rules.get("reserve_reconciliation_enabled") is not False:
        raise ValueError("source eligibility artifact unexpectedly enables reserves")

    slots = {str(slot["slot_id"]): slot for slot in plan["slots"]}
    primary_non_holdout = [
        slot for slot in plan["slots"]
        if slot.get("partition") == "non_holdout"
        and slot.get("candidate_slot_kind") != "reserve"
    ]
    offset_by_primary_slot = {
        str(slot["slot_id"]): offset
        for offset, slot in enumerate(primary_non_holdout)
    }

    ledger_by_task: dict[str, dict[str, Any]] = {}
    ledger_by_slot: dict[str, dict[str, Any]] = {}
    observed_offsets: list[int] = []
    benchmark_id = str(canonical.get("benchmark_id", ""))
    for row in ledger_rows:
        tid = str(row.get("task_id", ""))
        sid = str(row.get("slot_id", ""))
        if not tid or not sid or tid in ledger_by_task or sid in ledger_by_slot:
            raise ValueError("cumulative ledger contains missing/duplicate task or slot IDs")
        slot = slots.get(sid)
        if slot is None or slot.get("candidate_slot_kind") == "reserve":
            raise ValueError("cumulative ledger references an unknown/reserve slot")
        if slot.get("partition") != "non_holdout" or slot.get("benchmark_id") != benchmark_id:
            raise ValueError("cumulative ledger escapes frozen benchmark/partition")
        expected_offset = offset_by_primary_slot.get(sid)
        if expected_offset is None or row.get("primary_offset") != expected_offset:
            raise ValueError("cumulative ledger primary offset differs from frozen Factory order")
        if row.get("benchmark_id") != benchmark_id:
            raise ValueError("cumulative ledger benchmark differs from frozen control")
        if row.get("anchor_source_id") != slot.get("anchor_source_id"):
            raise ValueError("cumulative ledger anchor source differs from frozen slot")
        observed_offsets.append(expected_offset)
        ledger_by_task[tid] = row
        ledger_by_slot[sid] = row
    if len(ledger_rows) != 210:
        raise ValueError("cumulative ledger must contain exactly 210 rows")
    if sorted(observed_offsets) != list(range(210)):
        raise ValueError("cumulative ledger does not contain the exact 0..209 primary prefix")

    eligible = eligibility.get("eligible")
    if not isinstance(eligible, list):
        raise ValueError("replacement eligibility rows missing")
    expected_eligible = int(result.get("replacement_eligible_primary_count", -1))
    if len(eligible) != expected_eligible or eligibility.get("eligible_primary_count") != expected_eligible:
        raise ValueError("replacement eligibility count differs from frozen control")

    reserve_private: list[dict[str, Any]] = []
    reserve_leaves: list[str] = []
    seen_primary: set[str] = set()
    seen_reserve: set[str] = set()
    for row in eligible:
        if not isinstance(row, dict):
            raise ValueError("replacement eligibility row must be an object")
        primary_slot_id = str(row.get("primary_slot_id", ""))
        primary_task_id = str(row.get("primary_task_id", ""))
        if not primary_slot_id or primary_slot_id in seen_primary:
            raise ValueError("replacement eligibility contains duplicate/missing primary slot")
        seen_primary.add(primary_slot_id)
        primary_slot = slots.get(primary_slot_id)
        if primary_slot is None or primary_slot.get("candidate_slot_kind") == "reserve":
            raise ValueError("eligible primary slot is missing or is not primary")
        if primary_slot.get("partition") != "non_holdout" or primary_slot.get("benchmark_id") != benchmark_id:
            raise ValueError("eligible primary escapes frozen benchmark/partition")
        primary_binding = _slot_binding(primary_slot)
        if row.get("primary_slot_binding_sha256") != primary_binding:
            raise ValueError("eligible primary slot binding mismatch")
        if row.get("cumulative_ledger_sha256") != ledger_sha:
            raise ValueError("eligible primary row ledger binding mismatch")

        ledger_row = ledger_by_task.get(primary_task_id)
        if ledger_row is None or ledger_row.get("slot_id") != primary_slot_id:
            raise ValueError("eligible primary row does not bind a cumulative ledger task")
        if ledger_row.get("task_fingerprint") != row.get("primary_task_fingerprint"):
            raise ValueError("eligible primary task fingerprint mismatch")
        if ledger_row.get("outcome") != "skipped" or ledger_row.get("replacement_eligible") is not True:
            raise ValueError("replacement eligibility includes a non-terminal primary")
        if row.get("primary_outcome") != "skipped":
            raise ValueError("eligible primary outcome must be skipped")
        if row.get("eligibility_reason") != ledger_row.get("canonical_reason"):
            raise ValueError("eligible primary reason differs from cumulative ledger")

        reserve_slots = row.get("reserve_slots")
        if not isinstance(reserve_slots, list) or len(reserve_slots) != 1:
            raise ValueError("schema-26 preparation requires exactly one linked reserve per eligible primary")
        reserve_row = reserve_slots[0]
        if not isinstance(reserve_row, dict):
            raise ValueError("linked reserve row must be an object")
        reserve_slot_id = str(reserve_row.get("slot_id", ""))
        if not reserve_slot_id or reserve_slot_id in seen_reserve:
            raise ValueError("replacement eligibility contains duplicate/missing reserve slot")
        seen_reserve.add(reserve_slot_id)
        reserve_slot = slots.get(reserve_slot_id)
        if reserve_slot is None or reserve_slot.get("candidate_slot_kind") != "reserve":
            raise ValueError("authorized reserve slot is missing or not reserve")
        if reserve_slot.get("replacement_for_slot_id") != primary_slot_id:
            raise ValueError("authorized reserve does not link to eligible primary")
        if reserve_slot.get("reserve_attempt") != 1:
            raise ValueError("schema-26 preparation authorizes reserve_attempt=1 only")
        reserve_binding = _slot_binding(reserve_slot)
        if reserve_row.get("slot_binding_sha256") != reserve_binding:
            raise ValueError("linked reserve slot binding mismatch")

        identity_binding = sha256_bytes(canonical_json_bytes({
            "primary_slot_binding_sha256": primary_binding,
            "reserve_slot_binding_sha256": reserve_binding,
            "primary_task_fingerprint": row["primary_task_fingerprint"],
            "eligibility_reason": row["eligibility_reason"],
        }))
        nonce = nonce_deriver(commitment_secret, "reserve", identity_binding)
        _require_sha256(nonce, "reserve authorization nonce")
        leaf = _commitment_leaf(
            domain="reserve",
            identity_binding=identity_binding,
            cumulative_ledger_sha256=ledger_sha,
            replacement_eligibility_sha256=eligibility_sha,
            nonce=nonce,
        )
        reserve_leaves.append(leaf)
        reserve_private.append({
            "primary_slot_id": primary_slot_id,
            "primary_slot_binding_sha256": primary_binding,
            "primary_task_id": primary_task_id,
            "primary_task_fingerprint": row["primary_task_fingerprint"],
            "primary_offset": row["primary_offset"],
            "eligibility_reason": row["eligibility_reason"],
            "reserve_slot_id": reserve_slot_id,
            "reserve_slot_binding_sha256": reserve_binding,
            "authorization_identity_sha256": identity_binding,
            "authorization_nonce": nonce,
            "authorization_leaf_sha256": leaf,
            "cumulative_ledger_sha256": ledger_sha,
            "replacement_eligibility_sha256": eligibility_sha,
        })

    if len(reserve_private) != 41:
        raise ValueError("authoritative 210-primary evidence must authorize exactly 41 reserves")

    adjudication_private: list[dict[str, Any]] = []
    adjudication_leaves: list[str] = []
    seen_adjudication: set[str] = set()
    for row in adjudication_rows:
        if not isinstance(row, dict):
            raise ValueError("cumulative adjudication row must be an object")
        tid = str(row.get("task_id", ""))
        if not tid or tid in seen_adjudication:
            raise ValueError("cumulative adjudication contains duplicate/missing task ID")
        seen_adjudication.add(tid)
        ledger_row = ledger_by_task.get(tid)
        if ledger_row is None or ledger_row.get("outcome") != "adjudication":
            raise ValueError("cumulative adjudication row lacks adjudication ledger binding")
        if row.get("canonical_reason") != ledger_row.get("canonical_reason"):
            raise ValueError("cumulative adjudication canonical reason mismatch")
        if row.get("reason") != ledger_row.get("reconcile_reason"):
            raise ValueError("cumulative adjudication reconcile reason mismatch")
        slot_id = str(ledger_row.get("slot_id", ""))
        slot = slots.get(slot_id)
        if slot is None or slot.get("candidate_slot_kind") == "reserve":
            raise ValueError("adjudication task does not bind a primary slot")
        if slot.get("partition") != "non_holdout" or slot.get("benchmark_id") != benchmark_id:
            raise ValueError("adjudication task escapes frozen benchmark/partition")
        if ledger_row.get("replacement_eligible") is not False:
            raise ValueError("pending adjudication must remain replacement-ineligible")
        slot_binding = _slot_binding(slot)
        identity_binding = sha256_bytes(canonical_json_bytes({
            "primary_slot_binding_sha256": slot_binding,
            "task_fingerprint": ledger_row["task_fingerprint"],
            "canonical_reason": ledger_row["canonical_reason"],
        }))
        nonce = nonce_deriver(commitment_secret, "adjudication", identity_binding)
        _require_sha256(nonce, "adjudication nonce")
        leaf = _commitment_leaf(
            domain="adjudication",
            identity_binding=identity_binding,
            cumulative_ledger_sha256=ledger_sha,
            replacement_eligibility_sha256=eligibility_sha,
            nonce=nonce,
        )
        adjudication_leaves.append(leaf)
        adjudication_private.append({
            "task_id": tid,
            "slot_id": slot_id,
            "primary_slot_binding_sha256": slot_binding,
            "task_fingerprint": ledger_row["task_fingerprint"],
            "primary_offset": ledger_row["primary_offset"],
            "reconcile_reason": ledger_row.get("reconcile_reason"),
            "canonical_reason": ledger_row["canonical_reason"],
            "source_run_id": ledger_row["source_run_id"],
            "source_artifact_id": ledger_row["source_artifact_id"],
            "adjudication_identity_sha256": identity_binding,
            "adjudication_nonce": nonce,
            "adjudication_leaf_sha256": leaf,
            "cumulative_ledger_sha256": ledger_sha,
            "replacement_eligibility_sha256": eligibility_sha,
        })

    expected_adjudication = int(result.get("pending_adjudication", -1))
    if len(adjudication_private) != expected_adjudication or len(adjudication_private) != 129:
        raise ValueError("cumulative adjudication count differs from frozen control")
    if set(seen_adjudication) & {str(row["primary_task_id"]) for row in reserve_private}:
        raise ValueError("adjudication and replacement-eligible primary sets overlap")

    reason_counts = dict(sorted(Counter(
        str(row["canonical_reason"]) for row in adjudication_private
    ).items()))
    frozen_reason_counts = result.get("canonical_reason_counts")
    if not isinstance(frozen_reason_counts, dict):
        raise ValueError("frozen cumulative reason counts missing")
    skip_reason_counts = Counter(
        str(row["eligibility_reason"]) for row in eligible
    )
    expected_adjudication_reasons: dict[str, int] = {}
    for key, value in frozen_reason_counts.items():
        remaining = int(value) - int(skip_reason_counts.get(str(key), 0))
        if remaining < 0:
            raise ValueError("eligible skip reasons exceed frozen cumulative reason count")
        if remaining:
            expected_adjudication_reasons[str(key)] = remaining
    if reason_counts != dict(sorted(expected_adjudication_reasons.items())):
        raise ValueError("adjudication reason counts differ from frozen cumulative summary")

    reserve_leaves = sorted(reserve_leaves)
    adjudication_leaves = sorted(adjudication_leaves)
    reserve_set_sha = _commitment_set_sha256(reserve_leaves)
    adjudication_set_sha = _commitment_set_sha256(adjudication_leaves)

    _ensure_empty_dir(public_out_dir)
    _ensure_empty_dir(private_out_dir)

    public_binding = {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "postconsolidation_identity_binding",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "source_cumulative_freeze_schema_version": SOURCE_CUMULATIVE_FREEZE_SCHEMA,
        "source_cumulative_run_id": workflow["run_id"],
        "source_cumulative_evidence_path": control_rel,
        "cumulative_ledger_sha256": ledger_sha,
        "replacement_eligibility_sha256": eligibility_sha,
        "cumulative_adjudication_sha256": adjudication_sha,
        "factory_plan_sha256": factory_plan_sha,
        "reserve": {
            "eligible_primary_count": len(reserve_private),
            "authorized_reserve_count": len(reserve_private),
            "commitment_leaf_sha256": reserve_leaves,
            "commitment_set_sha256": reserve_set_sha,
        },
        "adjudication": {
            "pending_count": len(adjudication_private),
            "canonical_reason_counts": reason_counts,
            "commitment_leaf_sha256": adjudication_leaves,
            "commitment_set_sha256": adjudication_set_sha,
        },
        "contains_task_ids": False,
        "contains_slot_ids": False,
        "contains_source_text": False,
        "contains_gold_payloads": False,
        "contains_model_identity": False,
        "reserve_reconciliation_enabled": False,
        "adjudication_execution_enabled": False,
    }
    binding_path = public_out_dir / "POSTCONSOLIDATION_BINDING.json"
    write_json(binding_path, public_binding)

    private_manifest = {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "postconsolidation_private_identity_map",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "source_cumulative_run_id": workflow["run_id"],
        "cumulative_ledger_sha256": ledger_sha,
        "replacement_eligibility_sha256": eligibility_sha,
        "public_binding_sha256": sha256_file(binding_path),
        "reserve_authorization_count": len(reserve_private),
        "adjudication_count": len(adjudication_private),
    }
    write_json(private_out_dir / "PRIVATE_MANIFEST.json", private_manifest)
    write_json(
        private_out_dir / "RESERVE_AUTHORIZATION_PRIVATE.json",
        {
            "schema_version": 1,
            "campaign_id": "H3.9.2",
            "kind": "reserve_authorization_private_map",
            "rows": sorted(reserve_private, key=lambda row: int(row["primary_offset"])),
        },
    )
    dump_jsonl(
        private_out_dir / "ADJUDICATION_QUEUE_PRIVATE.jsonl",
        sorted(adjudication_private, key=lambda row: int(row["primary_offset"])),
    )

    summary = {
        "schema_version": 1,
        "campaign_id": "H3.9.2",
        "kind": "redacted_postconsolidation_preparation_summary",
        "protocol_version": PROTOCOL_VERSION,
        "protocol_freeze_schema_version": FREEZE_SCHEMA_VERSION,
        "source_cumulative_run_id": workflow["run_id"],
        "source_primary_task_count": 210,
        "reserve_authorized_count": len(reserve_private),
        "pending_adjudication_count": len(adjudication_private),
        "reserve_commitment_set_sha256": reserve_set_sha,
        "adjudication_commitment_set_sha256": adjudication_set_sha,
        "public_binding_sha256": sha256_file(binding_path),
        "contains_task_ids": False,
        "contains_slot_ids": False,
        "contains_source_text": False,
        "contains_gold_payloads": False,
        "contains_model_identity": False,
        "reserve_reconciliation_enabled": False,
        "adjudication_execution_enabled": False,
    }
    write_json(public_out_dir / "POSTCONSOLIDATION_SUMMARY.json", summary)
    return summary
