"""B02-C.4: Hadith -> Usul source-bound *research* mediation.

The output is never a Hadith identification, sanad grade, authenticated rule
application, scholarly conclusion, juristic opinion or a fatwa. The normalized
H-Search bridge and AI assessments remain operator-supplied data; their byte
digests establish immutable payload matching, NOT source or model authenticity.
"""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from jsonschema import Draft202012Validator

CONTRACT = "mubin-hadith-usul-mediation/1.0"
MAX_REQUEST_BYTES = 128 * 1024
MAX_WINDOW = 8192
MAX_REVIEW_BYTES = 24 * 1024
_MAX_WITNESS_RECEIPT_BYTES = 24 * 1024
_ROLES = {"supporter", "critic"}


class MediationError(ValueError):
    """Never echo external text, local paths, private span contents or errors."""


@lru_cache(maxsize=1)
def _validator():
    path = (Path(__file__).resolve().parents[2] /
            "schemas/hadith-usul-mediation-v1.schema.json")
    schema = json.loads(path.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _canonical(data):
    try:
        return json.dumps(
            data, ensure_ascii=False, sort_keys=True, allow_nan=False,
            separators=(",", ":")).encode("utf-8")
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise MediationError("MEDIATION_JSON_INVALID") from exc


def _sha(data):
    return sha256(data).hexdigest()


def _load_receipt(raw, limit, malformed):
    if type(raw) is not bytes or len(raw) > limit:
        raise MediationError(malformed)
    try:
        obj = json.loads(raw.decode("utf-8", "strict"))
    except (ValueError, UnicodeError) as exc:
        raise MediationError(malformed) from exc
    if type(obj) is not dict:
        raise MediationError(malformed)
    return obj


def _check_source_span(anchor, pins, read_span):
    source_id, full_hash = anchor["source_id"], anchor["source_sha256"]
    if pins.get(source_id) != full_hash:
        raise MediationError("MEDIATION_SOURCE_PIN_MISMATCH")
    st, en = anchor["start_byte"], anchor["end_byte"]
    cs, ce = anchor["context_start_byte"], anchor["context_end_byte"]
    if (type(st) is not int or type(en) is not int
            or type(cs) is not int or type(ce) is not int
            or not 0 <= cs <= st < en <= ce
            or not 0 < en-st <= MAX_WINDOW
            or not 0 < ce-cs <= MAX_WINDOW
            or (ce-cs)-(en-st) < 16):
        # A cited excerpt alone is not source context. Require surrounding
        # raw bytes; this is a *minimal* engineering guard, not a guarantee
        # of adequate linguistic or historical context.
        raise MediationError("MEDIATION_SPAN_INVALID")
    try:
        excerpt = read_span(source_id, st, en)
        context = read_span(source_id, cs, ce)
    except Exception as exc:
        raise MediationError("MEDIATION_LOCAL_SOURCE_READ_FAILED") from exc
    if (type(excerpt) is not bytes or type(context) is not bytes
            or len(excerpt) != en-st or len(context) != ce-cs
            or _sha(excerpt) != anchor["span_sha256"]
            or _sha(context) != anchor["context_sha256"]
            or context[st-cs:en-cs] != excerpt):
        raise MediationError("MEDIATION_SOURCE_BYTES_DIFFER")
    return True


def _check_witness(witness, read_witness):
    try:
        raw = read_witness(witness["link_id"])
    except Exception as exc:
        raise MediationError("MEDIATION_HSEARCH_RECEIPT_UNAVAILABLE") from exc
    if type(raw) is not bytes or _sha(raw) != witness["hsearch_receipt_sha256"]:
        raise MediationError("MEDIATION_HSEARCH_RECEIPT_DIGEST_MISMATCH")
    data = _load_receipt(
        raw, _MAX_WITNESS_RECEIPT_BYTES,
        "MEDIATION_HSEARCH_BRIDGE_INVALID")
    required = {
        "contract", "link_id", "classification", "witness_source_sha256",
        "witness_span_sha256", "pinned_source_count", "source_unavailable",
        "candidate_only", "narration_identity_verified", "grade_assigned",
    }
    if (set(data) != required
            or data["contract"] != "mubin-hsearch-witness-bridge/1.0"
            or data["link_id"] != witness["link_id"]
            or data["classification"] != witness["classification"]
            or data["witness_source_sha256"] != witness["source_span"]["source_sha256"]
            or data["witness_span_sha256"] != witness["source_span"]["span_sha256"]
            or data["candidate_only"] is not True
            or data["narration_identity_verified"] is not False
            or data["grade_assigned"] is not False
            or type(data["pinned_source_count"]) is not int
            or not 0 <= data["pinned_source_count"] <= 4
            or type(data["source_unavailable"]) is not list
            or len(data["source_unavailable"]) > 4
            or any(type(x) is not str or len(x) > 100
                   for x in data["source_unavailable"])):
        raise MediationError("MEDIATION_HSEARCH_BRIDGE_INVALID")
    full = data["pinned_source_count"] == 4 and not data["source_unavailable"]
    if full != (witness["coverage_state"] == "COMPLETE"):
        raise MediationError("MEDIATION_HSEARCH_COVERAGE_MISMATCH")
    return full


def _reviews(request, read_assessment, input_sha):
    roles, run_ids = {x: [] for x in _ROLES}, set()
    seen_model_roles = set()
    for review in request["reviews"]:
        run_id = review["run_id"]
        if run_id in run_ids:
            raise MediationError("MEDIATION_DUPLICATE_REVIEW_RUN")
        run_ids.add(run_id)
        try:
            raw = read_assessment(run_id)
        except Exception as exc:
            raise MediationError("MEDIATION_REVIEW_RECEIPT_MISSING") from exc
        if type(raw) is not bytes or _sha(raw) != review["receipt_sha256"]:
            raise MediationError("MEDIATION_REVIEW_DIGEST_MISMATCH")
        attestation = _load_receipt(raw, MAX_REVIEW_BYTES,
                                    "MEDIATION_REVIEW_RECEIPT_INVALID")
        required = {
            "contract", "input_sha256", "run_id", "model_id", "role",
            "verdict", "anchor_roles", "rationale",
        }
        if (set(attestation) != required
                or attestation["contract"] != "mubin-hadith-usul-review/1.0"
                or attestation["input_sha256"] != input_sha
                or any(attestation[k] != review[k] for k in
                       ("run_id", "model_id", "role", "verdict"))
                or attestation["anchor_roles"] != ["hadith", "usul"]
                or type(attestation["rationale"]) is not str
                or len(attestation["rationale"].strip()) < 50):
            raise MediationError("MEDIATION_REVIEW_NOT_SOURCE_BOUND")
        if ((review["role"] == "supporter"
             and review["verdict"] == "NO_OPEN_DEFEATER")
                or (review["role"] == "critic"
                    and review["verdict"] == "SUPPORTS_HYPOTHESIS")):
            raise MediationError("MEDIATION_REVIEW_ROLE_INVALID")
        # One model may submit multiple traces; those cannot substitute for
        # two *declared* supporting models. This is still NOT a proof that
        # the underlying models are independent organizations/families.
        identity = (review["model_id"], review["role"])
        if identity in seen_model_roles:
            raise MediationError("MEDIATION_DUPLICATE_MODEL_ROLE")
        seen_model_roles.add(identity)
        roles[review["role"]].append(review["verdict"])
    return roles


def assess_hadith_usul_hop(request, *, source_pins, read_span,
                          read_witness, read_assessment):
    """Assess locally pinned two-source research link with mandatory abstention.

    HSearch normalized candidate receipt is separate from the actual frozen
    H-Search corpus and may be fabricated by a caller. Its SHA only confirms
    matching bytes of the operator-supplied bridge document.
    """
    raw = _canonical(request)
    if len(raw) > MAX_REQUEST_BYTES:
        raise MediationError("MEDIATION_INPUT_TOO_LARGE")
    if list(_validator().iter_errors(request)):
        raise MediationError("MEDIATION_SCHEMA_INVALID")
    if (type(source_pins) is not dict or
            not callable(read_span) or
            not callable(read_witness) or not callable(read_assessment)):
        raise MediationError("MEDIATION_TRUSTED_READERS_REQUIRED")
    if (request["witness"]["source_span"]["source_id"] ==
            request["usul"]["source_span"]["source_id"]):
        raise MediationError("MEDIATION_SOURCE_DOMAINS_COLLAPSED")
    _check_source_span(request["witness"]["source_span"], source_pins, read_span)
    _check_source_span(request["usul"]["source_span"], source_pins, read_span)
    complete = _check_witness(request["witness"], read_witness)

    # Bind objections to the reviewed immutable input. A caller must not
    # delete open defeaters and replay old positive AI votes.
    core = {k: request[k] for k in (
        "contract", "case_id", "verse_reference", "hypothesis", "witness",
        "usul", "open_defeater_ids")}
    input_sha = _sha(_canonical(core))
    roles = _reviews(request, read_assessment, input_sha)
    challenged = bool(request["open_defeater_ids"]) or any(
        v in {"OPEN_DEFEATER", "REFUTES_HYPOTHESIS"} for group in roles.values()
        for v in group)
    supporters = sum(x == "SUPPORTS_HYPOTHESIS" for x in roles["supporter"])
    clears = sum(x == "NO_OPEN_DEFEATER" for x in roles["critic"])

    if not complete:
        status = "INCOMPLETE_SOURCE_COVERAGE"
    elif request["hypothesis"]["relation_type"] == "LEXICAL_PARALLEL":
        status = "LEXICAL_CANDIDATE_ONLY"
    elif challenged:
        status = "CONTESTED"
    elif supporters >= 2 and clears >= 1:
        status = "MACHINE_RESEARCH_CANDIDATE_ONLY"
    else:
        status = "UNDETERMINED"
    return {
        "contract": CONTRACT,
        "case_handle": _sha(request["case_id"].encode("utf-8")),
        "input_sha256": input_sha,
        "status": status,
        "witness_bridge_digest_matched": True,
        "source_span_digests_matched": True,
        "candidate_hsearch_coverage_reported_complete": complete,
        "review_receipts_digest_matched": True,
        "review_runs": len(request["reviews"]),
        "open_defeaters": len(request["open_defeater_ids"]),
        "source_text_included": False,
        "narration_identity_verified": False,
        "hadith_grade_assigned": False,
        "source_authenticity_verified": False,
        "semantic_truth_verified": False,
        "independent_model_families_verified": False,
        "juristic_inference_allowed": False,
        "scholarly_verified": False,
        "scientifically_established_hop": False,
        "limitations": [
            "HSEARCH_BRIDGE_IS_OPERATOR_REPORTED_NOT_SOURCE_AUTHENTICITY",
            "BYTE_PINNING_IS_NOT_TEXTUAL_OR_SCHOLARLY_VERIFICATION",
            "MODEL_REVIEWS_ARE_RESEARCH_RECEIPTS_NOT_SCIENTIFIC_CONSENSUS",
        ],
    }
