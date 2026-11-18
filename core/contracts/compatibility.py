"""Cross-engine response verification: statuses and pinned source identities remain distinct."""
from __future__ import annotations
import json
import math
from .types import CONTRACT_VERSION, STATUSES, ContractError, identifier, _ids

_FIELDS = {"contract_version", "request_id", "engine", "engine_version", "status",
           "findings", "evidence_refs", "uncertainties", "errors", "provenance", "trace_id"}

# The published cross-engine receipt must contain metadata, not excerpts.
# This key filter is defense in depth, NOT a complete rights/content scanner:
# publication still requires separate rights and provenance authorization.
_RAW_CONTENT_KEYS = frozenset({
    "text", "raw_text", "source_text", "excerpt", "raw_excerpt",
    "passage_text", "full_text", "source_bytes", "raw_bytes",
    "body_text", "content_text", "original_text", "verse_text",
    "ayah_text", "isnad_text", "quoted_text", "copyrighted_text",
    "private_text", "snippet", "html",
})
_MAX_FINDINGS_BYTES = 65536
_MAX_FINDING_DEPTH = 32
_MAX_FINDING_VALUES = 4096


def _metadata_only_findings(findings):
    # Check size incrementally to avoid constructing a large JSON string
    # from a malicious or defective adapter result.
    stack = [(findings, 0)]
    seen = set()
    nodes = 0
    budget = _MAX_FINDINGS_BYTES
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > _MAX_FINDING_VALUES or depth > _MAX_FINDING_DEPTH:
            return False
        if type(item) in (dict, list):
            if id(item) in seen:  # Reject cycles and shared mutable containers.
                return False
            seen.add(id(item))
        if type(item) is dict:
            if len(item) > 256:
                return False
            for key, value in item.items():
                if type(key) is not str or key.casefold() in _RAW_CONTENT_KEYS:
                    return False
                stack.append((key, depth + 1))
                stack.append((value, depth + 1))
        elif type(item) is list:
            if len(item) > 1000:
                return False
            stack.extend((value, depth + 1) for value in item)
        elif type(item) is str:
            if len(item) > budget:
                return False
            try:
                budget -= len(item.encode("utf-8", "strict"))
            except UnicodeError:
                return False
            if budget < 0:
                return False
        elif type(item) is int:
            if item.bit_length() > 256:
                return False
        elif type(item) is float:
            if not math.isfinite(item):
                return False
        elif item is None or type(item) is bool:
            continue
        else:
            return False
    try:
        serialized = json.dumps(findings, ensure_ascii=False, allow_nan=False,
                                separators=(",", ":")).encode("utf-8", "strict")
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        return False
    return len(serialized) <= _MAX_FINDINGS_BYTES


def validate_result(request, result):
    if type(result) is not dict or set(result) != _FIELDS:
        raise ContractError("RESULT_SHAPE_INVALID")
    if result["contract_version"] != CONTRACT_VERSION:
        raise ContractError("RESULT_VERSION_MISMATCH")
    if result["request_id"] != request["request_id"] or result["engine"] != request["engine"]:
        raise ContractError("RESULT_IDENTITY_MISMATCH")
    if (not identifier(result["trace_id"])
            or type(result["engine_version"]) is not str
            or not 1 <= len(result["engine_version"]) <= 128):
        raise ContractError("RESULT_METADATA_INVALID")
    if type(result["status"]) is not str or result["status"] not in STATUSES:
        raise ContractError("RESULT_STATUS_INVALID")
    if type(result["findings"]) is not list or len(result["findings"]) > request["limits"]["max_results"]:
        raise ContractError("RESULT_FINDINGS_INVALID")
    if (any(type(item) is not dict for item in result["findings"])
            or not _metadata_only_findings(result["findings"])):
        raise ContractError("RESULT_FINDINGS_INVALID")
    if not _ids(result["evidence_refs"]) or len(result["evidence_refs"]) > 128:
        raise ContractError("RESULT_EVIDENCE_INVALID")
    if any(type(result[k]) is not list or len(result[k]) > 128
           or any(type(v) is not str or len(v) > 160 for v in result[k])
           for k in ("uncertainties", "errors")):
        raise ContractError("RESULT_DIAGNOSTICS_INVALID")
    if type(result["provenance"]) is not dict or set(result["provenance"]) != {"snapshot_ids"}:
        raise ContractError("RESULT_PROVENANCE_INVALID")
    if (not _ids(result["provenance"]["snapshot_ids"])
            or result["provenance"]["snapshot_ids"] != request["source_snapshot_ids"]):
        raise ContractError("SOURCE_SNAPSHOT_MISMATCH")
    if result["status"] == "OK" and (not result["findings"] or result["errors"]):
        raise ContractError("RESULT_FALSE_SUCCESS")
    if result["status"] == "PARTIAL" and not result["uncertainties"]:
        raise ContractError("RESULT_PARTIAL_UNLABELED")
    if result["status"] in {"NO_MATCH", "UNAVAILABLE", "REJECTED", "ERROR"} and result["findings"]:
        raise ContractError("RESULT_STATUS_CONTRADICTION")
    return result
