"""U0.2 *site metadata* docket. Never promotes bibliographic fields to Usul AST.

URL identity and schema checks are NOT printed-edition authentication, permission
to reproduce content, exact quoted source bytes, or juristic endorsement.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .engine import _preflight

SCHEMA_PATH = Path(__file__).resolve().parents[2] / "schemas/usul-u02-source-docket.schema.json"
_SCHEMA = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)


def _plain_json_tree(obj: Any) -> bool:
    """No custom object, container or scalar subclasses at the trust boundary."""
    stack = [(obj, 0)]
    seen: set[int] = set()
    n = 0
    while stack:
        value, depth = stack.pop()
        n += 1
        if n > 16384 or depth > 48:
            return False
        if type(value) in (dict, list):
            if id(value) in seen:
                return False
            seen.add(id(value))
            if len(value) > 1024:
                return False
            if type(value) is dict:
                stack.extend((k, depth + 1) for k in value)
                stack.extend((v, depth + 1) for v in value.values())
            else:
                stack.extend((v, depth + 1) for v in value)
        elif type(value) not in (str, bool, int, float, type(None)):
            return False
    return True


def _early_unknowns(document: dict[str, Any]) -> list[str]:
    # Fail early on arbitrary nested unknown values before JSON schema traversal.
    if any(type(key) is not str or key not in _SCHEMA["properties"] for key in document):
        return ["unknown:root_field"]
    book = document.get("book")
    if type(book) is dict:
        allowed = _SCHEMA["properties"]["book"]["properties"]
        if any(type(key) is not str or key not in allowed for key in book):
            return ["unknown:book_field"]
    items = document.get("candidates")
    if type(items) is list:
        if len(items) > 16:
            return ["invalid:candidate_count_exceeded"]
        cprop = _SCHEMA["properties"]["candidates"]["items"]["properties"]
        lprop = cprop["locator"]["properties"]
        for i, item in enumerate(items):
            if type(item) is dict:
                if any(type(k) is not str or k not in cprop for k in item):
                    return [f"unknown:candidate_field:{i}"]
                loc = item.get("locator")
                if type(loc) is dict and any(type(k) is not str or k not in lprop for k in loc):
                    return [f"unknown:locator_field:{i}"]
    return []


def validate_docket(document: Any) -> list[str]:
    """Validate metadata structure only; never validate scholarly doctrine."""
    if type(document) is not dict:
        return ["invalid:docket_must_be_plain_object"]
    # Unknown fields caught before an attacker can pack them with nested data.
    errors = _early_unknowns(document)
    if errors:
        return errors
    if not _plain_json_tree(document):
        return ["invalid:untrusted_json_container"]
    issues = _preflight(document)
    if issues:
        return ["invalid:budget:" + i for i in issues]
    errors = []
    try:
        for item in _VALIDATOR.iter_errors(document):
            path = "/".join(str(p) for p in item.absolute_path)[:150]
            errors.append("schema:" + path + ":" + str(item.validator))
            if len(errors) >= 24:
                break
    except (TypeError, ValueError, UnicodeError, RecursionError, OverflowError):
        return ["invalid:schema_validation_error"]
    if errors:
        return sorted(set(errors))
    book = document["book"]
    base = f"https://shamela.ws/book/{book['book_id']}"
    if book["book_url"] != base or book["source_id"] != f"shamela:book:{book['book_id']}":
        return ["invalid:book_identity_mismatch"]
    # This is a four-slot pilot, not an open-ended catalog. A route and topic
    # may not be reassigned to a different candidate ID by editing JSON.
    expected = {
        "u02_c001": ("generality_with_exception", 146),
        "u02_c002": ("mixed_generality_and_particularity", 149),
        "u02_c003": ("sunnah_specifies_generality", 157),
        "u02_c004": ("ijma_chapter", 556),
    }
    if len(document["candidates"]) != 4:
        return ["invalid:incomplete_research_docket"]
    for cand in document["candidates"]:
        if expected.get(cand["candidate_id"]) != (cand["topic_id"], cand["locator"]["route_id"]):
            return ["invalid:candidate_topic_route_identity_mismatch"]
    ids: set[str] = set()
    routes: set[int] = set()
    for i, cand in enumerate(document["candidates"]):
        loc = cand["locator"]
        if loc["url"] != f"{base}/{loc['route_id']}":
            return [f"invalid:locator_book_route_mismatch:{i}"]
        if cand["candidate_id"] in ids:
            return ["invalid:duplicate_candidate_id"]
        if loc["route_id"] in routes:
            return ["invalid:duplicate_route_id"]
        ids.add(cand["candidate_id"])
        routes.add(loc["route_id"])
    return []


def assess_docket(document: Any) -> dict[str, Any]:
    """A valid docket is not evidence for content rights or scientific adoption."""
    errors = validate_docket(document)
    result = {
        "valid_metadata": not errors,
        "scope": "source_candidate_metadata_only",
        "assurance": "operator_recorded_bibliographic_candidates",
        "candidate_count": 0,
        "review_queue": [],
        "verified_rule_count": 0,
        "eligible_for_engine": False,
        "rights_verified": False,
        "edition_authenticated": False,
        "source_bytes_available": False,
        "scholarly_authority_verified": False,
        "docket_sha256": None,
        "errors": errors,
    }
    if not errors:
        raw = json.dumps(document, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode("utf-8", "strict")
        result["candidate_count"] = len(document["candidates"])
        result["review_queue"] = sorted(x["candidate_id"] for x in document["candidates"])
        # Hashes docket JSON only, NOT a printed edition, source bytes or license.
        result["docket_sha256"] = hashlib.sha256(raw).hexdigest()
    return result
