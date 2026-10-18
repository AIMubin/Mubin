"""U0.3 non-executable researcher question cards, parent-pinned metadata only.

This validator checks structural consistency with a *supplied* U0.2 docket.
The source metadata hash is not an independent book/edition attestation.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .docket import _plain_json_tree, assess_docket, validate_docket
from .engine import _preflight

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/usul-u03-research-cards.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)
GATES = ["independent_edition_collation", "author_editor_attribution", "legal_use_basis_review", "methodology_and_disagreement_review", "conditions_exceptions_counterexamples", "two_independent_scholarly_reviews"]
_EXPECTED = {
    "u03_h001": "u02_c001",
    "u03_h002": "u02_c002",
    "u03_h003": "u02_c003",
    "u03_h004": "u02_c004",
}

def _unexpected_fields(data: dict[str, Any]) -> list[str]:
    if any(type(k) is not str or k not in _SCHEMA["properties"] for k in data):
        return ["unknown:root_field"]
    items = data.get("cards")
    if type(items) is list:
        if len(items) > 4:
            return ["invalid:card_count_exceeded"]
        cp = _SCHEMA["properties"]["cards"]["items"]["properties"]
        gp = cp["evidence_gates"]["items"]["properties"]
        for i, card in enumerate(items):
            if type(card) is dict:
                if any(type(k) is not str or k not in cp for k in card):
                    return [f"unknown:card_field:{i}"]
                gates = card.get("evidence_gates")
                if type(gates) is list:
                    if len(gates) > 6:
                        return [f"invalid:gate_count_exceeded:{i}"]
                    for j, gate in enumerate(gates):
                        if type(gate) is dict and any(
                            type(k) is not str or k not in gp for k in gate
                        ):
                            return [f"unknown:evidence_gate_field:{i}:{j}"]
    return []

def validate_cards(data: Any, source_docket: Any) -> list[str]:
    """Structural only; no interpretation, source rights or human credential check."""
    if type(data) is not dict:
        return ["invalid:cards_must_be_plain_object"]
    issues = _unexpected_fields(data)
    if issues:
        return issues
    if not _plain_json_tree(data):
        return ["invalid:untrusted_json_container"]
    issues = _preflight(data)
    if issues:
        return ["invalid:budget:" + i for i in issues]
    errors: list[str] = []
    try:
        for item in _VALIDATOR.iter_errors(data):
            errors.append("schema:" + "/".join(str(p) for p in item.absolute_path)[:150]
                          + ":" + str(item.validator))
            if len(errors) >= 24:
                break
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        return ["invalid:schema_validation_error"]
    if errors:
        return sorted(set(errors))
    # Parent must be validated before hashing/referencing it.
    parent_errors = validate_docket(source_docket)
    if parent_errors:
        return ["invalid:source_docket"] + parent_errors[:5]
    parent = assess_docket(source_docket)
    if data["source_docket_sha256"] != parent["docket_sha256"]:
        return ["invalid:source_docket_digest_mismatch"]
    lookup = {c["candidate_id"]: c for c in source_docket["candidates"]}
    ids: set[str] = set()
    candidates: set[str] = set()
    for card in data["cards"]:
        card_id = card["card_id"]
        candidate_id = card["candidate_id"]
        if _EXPECTED.get(card_id) != candidate_id:
            return ["invalid:card_candidate_identity_mismatch"]
        if card_id in ids or candidate_id in candidates:
            return ["invalid:duplicate_card_or_candidate"]
        ids.add(card_id)
        candidates.add(candidate_id)
        parent_item = lookup[candidate_id]
        if (card["topic_id"] != parent_item["topic_id"]
                or card["source_route_id"] != parent_item["locator"]["route_id"]
                or card["heading_provenance"] != parent_item["heading_provenance"]):
            return ["invalid:parent_topic_route_editorial_mismatch"]
        if [g["gate_id"] for g in card["evidence_gates"]] != GATES:
            return ["invalid:evidence_gates_must_be_complete_ordered"]
        if not card["question_ar"].strip().endswith("؟"):
            return ["invalid:question_mark_required_not_semantic_certification"]
    if set(_EXPECTED) != ids:
        return ["invalid:incomplete_research_question_set"]
    return []

def assess_cards(data: Any, source_docket: Any) -> dict[str, Any]:
    errors = validate_cards(data, source_docket)
    result = {
        "scope": "research_questions_only",
        "valid_metadata": not errors,
        "source_docket_match": not errors,
        "hypothesis_count": 0,
        "pending_evidence_gate_count": 0,
        "review_queue": [],
        "card_set_sha256": None,
        "reviewed_rule_count": 0,
        "eligible_for_engine": False,
        "human_review_performed": False,
        "scholarly_authority_verified": False,
        "rights_verified": False,
        "edition_authenticated": False,
        "source_bytes_available": False,
        "errors": errors,
    }
    if not errors:
        normalized = dict(data)
        normalized["cards"] = sorted(data["cards"], key=lambda c: c["card_id"])
        raw = json.dumps(normalized, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode("utf-8", "strict")
        result["card_set_sha256"] = hashlib.sha256(raw).hexdigest()
        result["hypothesis_count"] = len(data["cards"])
        result["pending_evidence_gate_count"] = sum(
            len(c["evidence_gates"]) for c in data["cards"])
        result["review_queue"] = [c["card_id"] for c in normalized["cards"]]
    return result
