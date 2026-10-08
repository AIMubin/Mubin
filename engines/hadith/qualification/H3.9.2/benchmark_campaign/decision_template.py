from __future__ import annotations

from pathlib import Path
from typing import Any
import re

from .core import (
    canonical_json_bytes,
    dump_jsonl,
    load_jsonl,
    sha256_bytes,
    sha256_file,
    write_json,
)


SCHEMA31_DECISION_TEMPLATE_SCHEMA_VERSION = 1
SCHEMA31_PROTOCOL_FREEZE_SCHEMA = 31
EXPECTED_CASE_COUNT = 158
EXPECTED_BENCHMARK_ID = "external-critical-commentary"
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")


def _require_sha256(value: Any, field: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    return value


def build_schema31_decision_template(
    root: Path,
    packet_path: Path,
    out_dir: Path,
    *,
    expected_packet_sha256: str,
) -> dict[str, Any]:
    expected_packet_sha256 = _require_sha256(
        expected_packet_sha256, "expected packet SHA-256"
    )
    if not packet_path.is_file():
        raise ValueError("Schema-30 adjudication packet is missing")
    actual_packet_sha256 = sha256_file(packet_path)
    if actual_packet_sha256 != expected_packet_sha256:
        raise ValueError("Schema-30 adjudication packet SHA-256 mismatch")

    packet_rows = load_jsonl(packet_path)
    if len(packet_rows) != EXPECTED_CASE_COUNT:
        raise ValueError("Schema-31 template source must contain exactly 158 cases")

    ordered = sorted(packet_rows, key=lambda row: int(row.get("ordinal", -1)))
    ordinals = [int(row.get("ordinal", -1)) for row in ordered]
    if ordinals != list(range(EXPECTED_CASE_COUNT)):
        raise ValueError("Schema-30 packet ordinals must be the exact 0..157 surface")

    seen_packet_ids: set[str] = set()
    seen_task_ids: set[str] = set()
    bindings: list[dict[str, Any]] = []
    template_rows: list[dict[str, Any]] = []

    for row in ordered:
        if row.get("campaign_id") != "H3.9.2":
            raise ValueError("Schema-30 packet campaign mismatch")
        if row.get("benchmark_id") != EXPECTED_BENCHMARK_ID:
            raise ValueError("Schema-31 template source benchmark mismatch")

        packet_id = _require_sha256(row.get("packet_id"), "packet_id")
        task_id = row.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            raise ValueError("Schema-30 packet task_id is missing")
        if packet_id in seen_packet_ids:
            raise ValueError("duplicate packet_id in Schema-30 packet")
        if task_id in seen_task_ids:
            raise ValueError("duplicate task_id in Schema-30 packet")
        seen_packet_ids.add(packet_id)
        seen_task_ids.add(task_id)

        binding = {
            "ordinal": int(row["ordinal"]),
            "packet_id": packet_id,
            "task_id": task_id,
            "benchmark_id": EXPECTED_BENCHMARK_ID,
        }
        bindings.append(binding)
        template_rows.append(
            {
                "schema_version": SCHEMA31_DECISION_TEMPLATE_SCHEMA_VERSION,
                "campaign_id": "H3.9.2",
                "protocol_freeze_schema": SCHEMA31_PROTOCOL_FREEZE_SCHEMA,
                "packet_id": packet_id,
                "task_id": task_id,
                "benchmark_id": EXPECTED_BENCHMARK_ID,
                "reviews": [],
                "material_disagreement": None,
                "source_verification": None,
                "adjudication": None,
                "terminal_signoff": None,
                "accepted_candidate_sha256": None,
                "rejection_reason": None,
                "defer_reason": None,
                "authority_evidence": [],
                "reviewer_registry_snapshot_sha256": None,
            }
        )

    if out_dir.exists():
        if any(out_dir.iterdir()):
            raise ValueError("Schema-31 decision-template output directory must be empty")
    else:
        out_dir.mkdir(parents=True)

    template_path = out_dir / "SCHEMA31_ADJUDICATION_DECISION_TEMPLATE.jsonl"
    dump_jsonl(template_path, template_rows)

    decision_schema_path = root / "schemas" / "adjudication-decision.schema.json"
    reviewer_schema_path = (
        root / "schemas" / "adjudication-reviewer-registry.schema.json"
    )
    if not decision_schema_path.is_file() or not reviewer_schema_path.is_file():
        raise ValueError("Schema-31 decision or reviewer-registry schema is missing")

    binding_sha256 = sha256_bytes(canonical_json_bytes(bindings))
    template_sha256 = sha256_file(template_path)
    manifest = {
        "schema_version": SCHEMA31_DECISION_TEMPLATE_SCHEMA_VERSION,
        "campaign_id": "H3.9.2",
        "kind": "schema31_human_adjudication_decision_template",
        "protocol_freeze_schema": SCHEMA31_PROTOCOL_FREEZE_SCHEMA,
        "source_packet_protocol_freeze_schema": 30,
        "source_packet_sha256": actual_packet_sha256,
        "case_count": len(template_rows),
        "benchmark_counts": {EXPECTED_BENCHMARK_ID: len(template_rows)},
        "packet_task_binding_sha256": binding_sha256,
        "decision_template_sha256": template_sha256,
        "decision_schema_sha256": sha256_file(decision_schema_path),
        "reviewer_registry_schema_sha256": sha256_file(reviewer_schema_path),
        "blank_template": True,
        "contains_terminal_decisions": False,
        "contains_source_text": False,
        "contains_gold_payloads": False,
        "contains_model_identity": False,
        "canonical_terminal_decision_path": "terminal_signoff.decision",
        "legacy_top_level_decision_field_present": False,
        "human_attested_terminal_signoff_required_for_completion": True,
        "reviewer_registry_snapshot_required_for_completion": True,
        "final_rows_must_validate_against": "schemas/adjudication-decision.schema.json",
    }
    write_json(out_dir / "SCHEMA31_DECISION_TEMPLATE_MANIFEST.json", manifest)
    return manifest
