"""Cross-engine response verification: statuses and pinned source identities remain distinct."""
from __future__ import annotations
from .types import CONTRACT_VERSION, STATUSES, ContractError, identifier, _ids

_FIELDS = {"contract_version", "request_id", "engine", "engine_version", "status",
           "findings", "evidence_refs", "uncertainties", "errors", "provenance", "trace_id"}


def validate_result(request, result):
    if type(result) is not dict or set(result) != _FIELDS:
        raise ContractError("RESULT_SHAPE_INVALID")
    if result["contract_version"] != CONTRACT_VERSION:
        raise ContractError("RESULT_VERSION_MISMATCH")
    if result["request_id"] != request["request_id"] or result["engine"] != request["engine"]:
        raise ContractError("RESULT_IDENTITY_MISMATCH")
    if not identifier(result["trace_id"]) or not isinstance(result["engine_version"], str) or not result["engine_version"]:
        raise ContractError("RESULT_METADATA_INVALID")
    if result["status"] not in STATUSES:
        raise ContractError("RESULT_STATUS_INVALID")
    if type(result["findings"]) is not list or len(result["findings"]) > request["limits"]["max_results"]:
        raise ContractError("RESULT_FINDINGS_INVALID")
    if any(type(item) is not dict for item in result["findings"]):
        raise ContractError("RESULT_FINDINGS_INVALID")
    if not _ids(result["evidence_refs"]) or len(result["evidence_refs"]) > 128:
        raise ContractError("RESULT_EVIDENCE_INVALID")
    if any(type(result[k]) is not list or any(type(v) is not str or len(v) > 160 for v in result[k])
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
