"""Dependency-free, strict runtime validation for the MUBIN-SYS-A01 wire contract."""
from __future__ import annotations

import re
import json

CONTRACT_VERSION = "engine-contract/1.0"
ENGINE_NAMES = frozenset({"quran", "tafsir", "hadith", "usul", "fiqh"})
STATUSES = frozenset({"OK", "PARTIAL", "UNDETERMINED", "NO_MATCH", "UNAVAILABLE", "REJECTED", "ERROR"})
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
_REQUIRED = {"contract_version", "request_id", "case_id", "engine", "operation",
             "inputs", "methodology_profile_id", "source_snapshot_ids", "limits", "idempotency_key"}


class ContractError(ValueError):
    """Safe, non-disclosing failure code."""


def identifier(value):
    return type(value) is str and bool(_IDENTIFIER.fullmatch(value))


def _ids(values, *, max_items=128):
    return (type(values) is list and len(values) <= max_items
            and all(identifier(x) for x in values) and len(set(values)) == len(values))


def validate_request(request):
    if type(request) is not dict or set(request) != _REQUIRED:
        raise ContractError("REQUEST_SHAPE_INVALID")
    if request["contract_version"] != CONTRACT_VERSION:
        raise ContractError("CONTRACT_VERSION_UNSUPPORTED")
    if not all(identifier(request[field]) for field in (
            "request_id", "case_id", "operation", "methodology_profile_id", "idempotency_key")):
        raise ContractError("REQUEST_IDENTIFIER_INVALID")
    if request["engine"] not in ENGINE_NAMES:
        raise ContractError("ENGINE_UNKNOWN")
    if type(request["inputs"]) is not dict:
        raise ContractError("REQUEST_INPUT_INVALID")
    try:
        encoded = json.dumps(request["inputs"], sort_keys=True, allow_nan=False, ensure_ascii=False)
    except (TypeError, ValueError, RecursionError) as exc:
        raise ContractError("REQUEST_INPUT_INVALID") from exc
    if len(encoded.encode("utf-8")) > 65536:
        raise ContractError("REQUEST_INPUT_INVALID")
    if not _ids(request["source_snapshot_ids"]):
        raise ContractError("SOURCE_SNAPSHOTS_INVALID")
    limits = request["limits"]
    if type(limits) is not dict or set(limits) != {"timeout_ms", "max_results"}:
        raise ContractError("LIMITS_INVALID")
    if (type(limits["timeout_ms"]) is not int or not 1 <= limits["timeout_ms"] <= 120000
            or type(limits["max_results"]) is not int or not 1 <= limits["max_results"] <= 1000):
        raise ContractError("LIMITS_INVALID")
    return request
