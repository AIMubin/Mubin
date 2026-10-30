"""B02-C contract: source-byte-anchored, machine-assessed semantic research links.

This checks *recorded* AI judgments against a trusted local source-pin registry.
It cannot verify the semantic truth of those AI judgments. NEVER interpret
MACHINE_SUPPORTED_RESEARCH_ONLY as authenticated religious interpretation,
Hadith grading, authoritative Usul inference, or permission to issue a fatwa.
"""
from __future__ import annotations

import hashlib
import json
from functools import lru_cache
from pathlib import Path

from jsonschema import Draft202012Validator

CONTRACT = "mubin-semantic-link-research/1.0"
MAX_JSON_BYTES = 128 * 1024
MAX_WINDOW_BYTES = 8192
SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/semantic-link-research-v1.schema.json"
_ROLES = {"quran", "tafsir", "usul"}
_SUPPORT = {"SUPPORTS_LINK"}
_NO_DEFEATER = {"NO_OPEN_DEFEATER"}


class SemanticLinkError(ValueError):
    """Non-disclosing code only; never prints local text or filesystem paths."""


@lru_cache(maxsize=1)
def _schema_validator():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _digest(value):
    return hashlib.sha256(value).hexdigest()


def evaluate_research_link(bundle, *, source_pins, read_span):
    """Local-only source read/check + explicitly non-authoritative machine assessment.

    source_pins: trusted source_id -> sha256 of the pinned complete source.
    read_span: trusted callback(source_id, start_byte, end_byte) -> exact source bytes.
    Neither source file paths nor raw source text come from the AI/request bundle.
    A correct source-pinned quote does not prove correct contextual interpretation.
    """
    try:
        encoded = json.dumps(bundle, ensure_ascii=False, allow_nan=False,
                             separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise SemanticLinkError("SEMANTIC_LINK_JSON_INVALID") from exc
    if len(encoded) > MAX_JSON_BYTES:
        raise SemanticLinkError("SEMANTIC_LINK_SIZE_EXCEEDED")
    if list(_schema_validator().iter_errors(bundle)):
        raise SemanticLinkError("SEMANTIC_LINK_SCHEMA_INVALID")
    if type(source_pins) is not dict or not callable(read_span):
        raise SemanticLinkError("SEMANTIC_LINK_READER_REQUIRED")

    refs = set()
    roles = set()
    identifiers = set()
    for anchor in bundle["anchors"]:
        ident = anchor["id"]
        if ident in identifiers:
            raise SemanticLinkError("SEMANTIC_LINK_DUPLICATE_ANCHOR")
        identifiers.add(ident)
        role = anchor["role"]
        roles.add(role)
        if (role in {"quran", "tafsir"} and
                anchor["reference"] != bundle["verse_reference"]):
            raise SemanticLinkError("SEMANTIC_LINK_REFERENCE_MISMATCH")
        if role == "usul" and anchor["reference"] != bundle["rule_id"]:
            raise SemanticLinkError("SEMANTIC_LINK_RULE_MISMATCH")
        if (source_pins.get(anchor["source_id"]) != anchor["source_sha256"]
                or type(source_pins.get(anchor["source_id"])) is not str):
            raise SemanticLinkError("SEMANTIC_LINK_SOURCE_PIN_MISMATCH")
        start, end = anchor["start_byte"], anchor["end_byte"]
        cs, ce = anchor["context_start_byte"], anchor["context_end_byte"]
        if not (0 <= cs <= start < end <= ce and
                0 < end - start <= MAX_WINDOW_BYTES and
                0 < ce - cs <= MAX_WINDOW_BYTES):
            raise SemanticLinkError("SEMANTIC_LINK_SPAN_INVALID")
        try:
            excerpt = read_span(anchor["source_id"], start, end)
            context = read_span(anchor["source_id"], cs, ce)
        except Exception as exc:
            raise SemanticLinkError("SEMANTIC_LINK_SOURCE_READ_FAILED") from exc
        if (type(excerpt) is not bytes or type(context) is not bytes or
                len(excerpt) != end - start or len(context) != ce - cs or
                _digest(excerpt) != anchor["excerpt_sha256"] or
                _digest(context) != anchor["context_sha256"] or
                context[start-cs:end-cs] != excerpt):
            raise SemanticLinkError("SEMANTIC_LINK_SOURCE_SPAN_MISMATCH")
        refs.add((anchor["source_id"], cs, ce))
    if roles != _ROLES:
        raise SemanticLinkError("SEMANTIC_LINK_REQUIRED_ROLES_MISSING")

    analyses = bundle["assessments"]
    run_ids = [r["run_id"] for r in analyses]
    if len(set(run_ids)) != len(run_ids):
        raise SemanticLinkError("SEMANTIC_LINK_REUSED_REVIEW_RUN")
    by_role = {role: [] for role in ("supporter", "critic")}
    for review in analyses:
        if any(x not in identifiers for x in review["anchor_ids"]):
            raise SemanticLinkError("SEMANTIC_LINK_UNKNOWN_REVIEW_ANCHOR")
        review_roles = {a["role"] for a in bundle["anchors"]
                        if a["id"] in review["anchor_ids"]}
        if (review["verdict"] in (_SUPPORT | _NO_DEFEATER) and
                review_roles != _ROLES):
            raise SemanticLinkError("SEMANTIC_LINK_REVIEW_MISSING_CONTEXT")
        if (review["role"] == "supporter" and review["verdict"] == "NO_OPEN_DEFEATER"
                or review["role"] == "critic" and review["verdict"] == "SUPPORTS_LINK"):
            raise SemanticLinkError("SEMANTIC_LINK_REVIEW_ROLE_INVALID")
        by_role[review["role"]].append(review)
    supports = sum(r["verdict"] == "SUPPORTS_LINK" for r in by_role["supporter"])
    clears = sum(r["verdict"] == "NO_OPEN_DEFEATER" for r in by_role["critic"])
    objections = bool(bundle["open_defeater_ids"]) or any(
        r["verdict"] in {"OPEN_DEFEATER", "REFUTES_LINK"} for r in analyses)

    if bundle["relation_type"] == "LEXICAL_OVERLAP":
        status = "LEXICAL_ONLY"
    elif objections:
        status = "CONTESTED"
    elif supports >= 2 and clears >= 1:
        status = "MACHINE_SUPPORTED_RESEARCH_ONLY"
    else:
        status = "UNDETERMINED"
    return {
        "contract": CONTRACT,
        "case_id": bundle["case_id"],
        "rule_id": bundle["rule_id"],
        "verse_reference": bundle["verse_reference"],
        "status": status,
        "source_span_digests_matched": True,
        "machine_research_gate_passed": status == "MACHINE_SUPPORTED_RESEARCH_ONLY",
        "verified_source_authenticity": False,
        "scholarly_verified": False,
        "juristic_inference_allowed": False,
        "model_independence_established": False,
        "evidence_roles": sorted(roles),
        "anchors_checked": len(bundle["anchors"]),
        "review_runs": len(analyses),
        "unresolved_defeater_count": len(bundle["open_defeater_ids"]),
        "assessment_digest": _digest(encoded),
        "limitations": [
            "SOURCE_DIGEST_IS_BYTE_FIDELITY_NOT_AUTHENTICITY",
            "AI_ASSESSMENTS_ARE_DECLARATIONS_NOT_SEMANTIC_PROOFS",
            "RESEARCH_GATE_IS_NOT_SCHOLARLY_APPROVAL",
        ],
    }
