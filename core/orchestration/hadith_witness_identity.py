"""B02-C.6: source-pinned Hadith witness TEXTUAL research (not Hadith grading).

Requires trusted operator-local source pins and UTF-8 BYTE windows. The earlier
H-Search raw spans are Unicode codepoint offsets: callers MUST explicitly
convert on original raw source bytes and verify independently, never reuse
codepoint coordinates as byte offsets. No source text/review rationale exported.
"""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from jsonschema import Draft202012Validator

CONTRACT = "mubin-hadith-witness-identity/1.0"
BRIDGE_CONTRACT = "mubin-hsearch-witness-bridge/1.0"
MAX_REQUEST = 128 * 1024
MAX_CONTEXT = 8192
MAX_BRIDGE = 24 * 1024
BRIDGE_FIELDS = {
    "contract", "link_id", "classification", "witness_source_sha256",
    "witness_span_sha256", "pinned_source_count", "source_unavailable",
    "candidate_only", "narration_identity_verified", "grade_assigned",
}


class WitnessIdentityError(ValueError):
    """Stable error codes; raw private sources and callbacks never echoed."""


def _reject(condition, code):
    if not condition:
        raise WitnessIdentityError(code)


def _hash(raw):
    return sha256(raw).hexdigest()


@lru_cache(maxsize=1)
def _schema():
    path = (Path(__file__).resolve().parents[2]
            / "schemas/hadith-witness-identity-v1.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _canonical(data):
    try:
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False,
                         allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise WitnessIdentityError("WITNESS_JSON_INVALID") from exc
    _reject(len(raw) <= MAX_REQUEST, "WITNESS_REQUEST_TOO_LARGE")
    return raw


def _read(read_span, source_id, start, end):
    try:
        raw = read_span(source_id, start, end)
    except Exception as exc:
        raise WitnessIdentityError("WITNESS_LOCAL_READ_FAILED") from exc
    _reject(type(raw) is bytes and len(raw) == end - start,
            "WITNESS_LOCAL_BYTES_INVALID")
    return raw


def _check_span(span, context, source_id, read_span, *, is_context=False):
    a, b = span["start_byte"], span["end_byte"]
    _reject(type(a) is int and type(b) is int and 0 <= a < b
            and b - a <= MAX_CONTEXT, "WITNESS_BYTE_SPAN_INVALID")
    if not is_context:
        _reject(context["start_byte"] <= a < b <= context["end_byte"],
                "WITNESS_OUTSIDE_CONTEXT")
    raw = _read(read_span, source_id, a, b)
    _reject(_hash(raw) == span["sha256"], "WITNESS_SPAN_DIGEST_INVALID")
    return raw


def _check_witness(witness, registry, read_span):
    source = witness["source_id"]
    pinned = registry.get(source)
    _reject(type(pinned) is dict and
            set(pinned) == {"source_sha256", "work_id", "version_ref", "access_scope"}
            and pinned["access_scope"] == "non_holdout"
            and all(pinned[k] == witness[k] for k in
                    ("source_sha256", "work_id", "version_ref")),
            "WITNESS_TRUSTED_SOURCE_PIN_MISMATCH")
    context, section = witness["context"], witness["segment"]
    _reject(type(context["start_byte"]) is int and
            type(context["end_byte"]) is int and
            0 <= context["start_byte"] < context["end_byte"]
            and context["end_byte"] - context["start_byte"] <= MAX_CONTEXT
            and context["end_byte"] - context["start_byte"] -
                (section["end_byte"] - section["start_byte"]) >= 16,
            "WITNESS_CONTEXT_INSUFFICIENT")
    whole = _check_span(context, context, source, read_span, is_context=True)
    text = _check_span(section, context, source, read_span)
    offset = section["start_byte"] - context["start_byte"]
    _reject(whole[offset:offset + len(text)] == text,
            "WITNESS_CONTEXT_SECTION_MISMATCH")
    if "isnad" in witness:
        isnad_span = witness["isnad"]
        a, b = isnad_span["start_byte"], isnad_span["end_byte"]
        _reject(b <= section["start_byte"] or a >= section["end_byte"],
                "WITNESS_ISNAD_MATN_OVERLAP")
        isnad = _check_span(isnad_span, context, source, read_span)
        offset = a - context["start_byte"]
        _reject(whole[offset:offset + len(isnad)] == isnad,
                "WITNESS_ISNAD_CONTEXT_MISMATCH")
    return text, whole


def _bridge(request, candidate, fragment, data):
    _reject(type(data) is bytes and len(data) <= MAX_BRIDGE and
            _hash(data) == request["hsearch_bridge"]["receipt_sha256"],
            "WITNESS_BRIDGE_DIGEST_MISMATCH")
    try:
        evidence = json.loads(data.decode("utf-8", errors="strict"))
    except (ValueError, UnicodeError) as exc:
        raise WitnessIdentityError("WITNESS_BRIDGE_INVALID") from exc
    _reject(type(evidence) is dict and set(evidence) == BRIDGE_FIELDS
            and evidence["contract"] == BRIDGE_CONTRACT
            and evidence["link_id"] == request["hsearch_bridge"]["link_id"]
            and evidence["classification"] == "NARRATION_FRAGMENT_CANDIDATE"
            and request["hsearch_bridge"]["classification"]
                == evidence["classification"]
            and evidence["witness_source_sha256"] == candidate["source_sha256"]
            and evidence["witness_span_sha256"] == _hash(fragment)
            and evidence["candidate_only"] is True
            and evidence["narration_identity_verified"] is False
            and evidence["grade_assigned"] is False
            and type(evidence["pinned_source_count"]) is int
            and 0 <= evidence["pinned_source_count"] <= 4
            and type(evidence["source_unavailable"]) is list
            and len(evidence["source_unavailable"]) <= 4
            and all(type(x) is str and 1 <= len(x) <= 100
                    for x in evidence["source_unavailable"]),
            "WITNESS_BRIDGE_INVALID")
    return (evidence["pinned_source_count"] == 4
            and not evidence["source_unavailable"])


def assess_hadith_witness_identity(request, *, source_registry,
                                   read_span, read_bridge):
    """Research-only text comparison over trusted, pinned UTF-8 byte slices.

    Caller-supplied MATN_CANDIDATE / QURAN_QUOTE / COMMENTARY labels are
    *reported* segment hypotheses, NOT verified historical segmentations.
    Without qualified review the output can never establish narration identity.
    """
    _canonical(request)
    if list(_schema().iter_errors(request)):
        raise WitnessIdentityError("WITNESS_SCHEMA_INVALID")
    _reject(type(source_registry) is dict
            and callable(read_span) and callable(read_bridge),
            "WITNESS_TRUSTED_READERS_REQUIRED")

    records = request["witnesses"]
    candidates = [w for w in records if w["role"] == "candidate"]
    _reject(len(candidates) == 1, "WITNESS_EXACT_ONE_CANDIDATE_REQUIRED")
    ids = [w["source_id"] for w in records]
    _reject(len(set(ids)) == len(ids), "WITNESS_DUPLICATE_SOURCE")
    source_bytes = {}
    for witness in records:
        source_bytes[witness["source_id"]] = _check_witness(
            witness, source_registry, read_span)[0]
    primary = candidates[0]
    fragment_spec = request["candidate_fragment"]
    _reject(primary["context"]["start_byte"]
            <= fragment_spec["start_byte"] < fragment_spec["end_byte"]
            <= primary["context"]["end_byte"],
            "WITNESS_FRAGMENT_OUTSIDE_CONTEXT")
    fragment = _check_span(fragment_spec, primary["context"],
                           primary["source_id"], read_span)
    if primary["segment_type"] == "MATN_CANDIDATE":
        _reject(primary["segment"]["start_byte"]
                <= fragment_spec["start_byte"] < fragment_spec["end_byte"]
                <= primary["segment"]["end_byte"],
                "WITNESS_FRAGMENT_OUTSIDE_REPORTED_MATN")
    try:
        bridge_data = read_bridge(request["hsearch_bridge"]["link_id"])
    except Exception as exc:
        raise WitnessIdentityError("WITNESS_BRIDGE_UNAVAILABLE") from exc
    complete = _bridge(request, primary, fragment, bridge_data)

    distinct = {w["work_id"] for w in records if
                w["segment_type"] == "MATN_CANDIDATE"}
    match_count = sum(
        w["role"] == "comparison"
        and w["work_id"] != primary["work_id"]
        and w["segment_type"] == "MATN_CANDIDATE"
        and source_bytes[w["source_id"]] == source_bytes[primary["source_id"]]
        for w in records
    ) if primary["segment_type"] == "MATN_CANDIDATE" else 0

    if primary["segment_type"] in {"QURAN_QUOTE", "COMMENTARY"}:
        status = "REPORTED_NON_NARRATION_SEGMENT"
    elif request["open_objection_ids"]:
        status = "CONTESTED"
    elif not complete:
        status = "INCOMPLETE_HSEARCH_COVERAGE"
    elif match_count:
        status = "EXACT_MATN_CROSS_SOURCE_RESEARCH_ONLY"
    else:
        status = "UNDETERMINED"
    return {
        "contract": CONTRACT,
        "case_sha256": _hash(request["case_id"].encode("utf-8")),
        "input_sha256": _hash(_canonical(request)),
        "status": status,
        "candidate_link_sha256": _hash(
            request["hsearch_bridge"]["link_id"].encode("utf-8")),
        "witness_records": len(records),
        "reported_distinct_matn_works": len(distinct),
        "exact_matn_comparison_matches": match_count,
        "isnad_spans_reported": sum("isnad" in w for w in records),
        "open_objections": len(request["open_objection_ids"]),
        "hsearch_coverage_reported_complete": complete,
        "operator_source_pin_registry_matched": True,
        "source_windows_byte_digests_matched": True,
        "bridge_receipt_digest_matched": True,
        "raw_source_full_file_hash_recomputed": False,
        "segment_boundaries_scholarly_verified": False,
        "textual_variants_scholarly_adjudicated": False,
        "independent_source_families_verified": False,
        "narration_identity_verified": False,
        "isnad_authenticated": False,
        "hadith_grade_assigned": False,
        "source_authenticity_verified": False,
        "scholarly_verified": False,
        "scientific_chain_established": False,
        "juristic_inference_allowed": False,
        "text_included": False,
    }
