"""Fail-closed private research source triage, NOT legal or scholarly clearance.

Operator-supplied attestations and use records must be independently reviewed
and retained in a restricted store; this metadata validator cannot verify them.
"""
from __future__ import annotations

from datetime import date
import re

SOURCE_KEYS = frozenset(("source_id", "source_kind", "work_id", "edition_id",
                         "source_sha256", "verification_scope", "redistribution_status"))
RECORD_KEYS = frozenset(("work_type", "source_reference", "purpose_code", "use_date"))
ATTEST_KEYS = frozenset((
    "basis", "lawfully_published", "lawfully_acquired", "purpose_bounded",
    "private_local_storage", "applicability_checked", "contract_and_access_terms_checked",
    "no_public_distribution", "no_unnecessary_final_product_inclusion",
    "normal_exploitation_respected", "legitimate_interests_respected",
    "independent_rights_respected", "usage_register_retained", "commercial_context",
    "commercial_exception_checked", "nonprofit_activity", "author_and_source_attributed",
))
KINDS = frozenset(("quran", "hadith", "tafsir", "usul", "fiqh", "other"))
RIGHTS = frozenset(("UNKNOWN", "NOT_CLEARED", "RESTRICTED", "REDISTRIBUTION_PERMITTED"))
BASIS_AI = "SA_2026_ART26_4_AI_DEVELOPMENT"
BASIS_RESEARCH = "SA_2026_ART26_2_NONPROFIT_RESEARCH"
SHA = re.compile(r"[0-9a-f]{64}\Z")
ID = re.compile(r"[a-z][a-z0-9._:-]{2,127}\Z")
PURPOSES = frozenset(("AI_ALGORITHM_DEVELOPMENT", "AI_PRODUCT_DEVELOPMENT", "NONPROFIT_RESEARCH"))
COMMERCIAL = frozenset(("NONCOMMERCIAL", "LIMITED_COMMERCIAL_EXCEPTION", "UNASSESSED_COMMERCIAL"))


def _result(status, eligible=False):
    # No source text, source names, local paths, secrets or untrusted strings.
    return {
        "status": status, "internal_development_eligible": eligible,
        "public_redistribution_authorized": False, "scholarly_verified": False,
        "source_authenticity_attested_by_this_gate": False,
        "automated_hadith_grade_authorized": False,
        "juristic_inference_allowed": False, "public_fatwa_authorized": False,
        "operator_attestations_independently_verified": False,
    }


def assess_internal_source_use(source, attestation, *,
                               independently_pinned_sha256, use_record):
    """Return a scope-limited operator-declared engineering admission state.

    Never treats a hash, an operator assertion or CI passing as a licence.
    Missing source conditions hold THAT source only, not the entire project.
    """
    if type(source) is not dict or set(source) != SOURCE_KEYS:
        return _result("INVALID_SOURCE_SCHEMA")
    if any(type(source[k]) is not str for k in SOURCE_KEYS):
        return _result("INVALID_SOURCE_SCHEMA")
    if any(not ID.fullmatch(source[k])
           for k in ("source_id", "work_id", "edition_id")):
        return _result("INVALID_SOURCE_SCHEMA")
    if (source["source_kind"] not in KINDS or
            source["redistribution_status"] not in RIGHTS):
        return _result("INVALID_SOURCE_SCHEMA")
    if source["verification_scope"] != "PINNED_SOURCE_BYTES_MATCHED":
        return _result("SOURCE_NOT_BYTE_VERIFIED")
    if not SHA.fullmatch(source["source_sha256"]):
        return _result("INVALID_SOURCE_DIGEST")
    if (type(independently_pinned_sha256) is not str or
            not SHA.fullmatch(independently_pinned_sha256)):
        return _result("INDEPENDENT_SOURCE_PIN_REQUIRED")
    if source["source_sha256"] != independently_pinned_sha256:
        return _result("SOURCE_PIN_MISMATCH")

    # Regulation Art.30(3): operator must keep actual work/source/purpose/date.
    # This API checks a supplied record, but does not persist or attest it.
    if type(use_record) is not dict or set(use_record) != RECORD_KEYS:
        return _result("INVALID_USAGE_RECORD_SCHEMA")
    if any(type(use_record[k]) is not str for k in RECORD_KEYS):
        return _result("INVALID_USAGE_RECORD_SCHEMA")
    if (not ID.fullmatch(use_record["source_reference"]) or
            use_record["source_reference"] != source["source_id"] or
            use_record["work_type"] != source["source_kind"] or
            use_record["purpose_code"] not in PURPOSES):
        return _result("USAGE_RECORD_REFERENCE_OR_PURPOSE_INVALID")
    try:
        d = date.fromisoformat(use_record["use_date"])
        if d.isoformat() != use_record["use_date"]:
            raise ValueError
    except ValueError:
        return _result("USAGE_RECORD_DATE_INVALID")

    if type(attestation) is not dict or set(attestation) != ATTEST_KEYS:
        return _result("INVALID_ATTESTATION_SCHEMA")
    if (type(attestation["basis"]) is not str or
            attestation["basis"] not in (BASIS_AI, BASIS_RESEARCH)):
        return _result("UNSUPPORTED_USE_BASIS")
    if (type(attestation["commercial_context"]) is not str or
            attestation["commercial_context"] not in COMMERCIAL):
        return _result("COMMERCIAL_CONTEXT_INVALID")
    if any(type(attestation[k]) is not bool
           for k in ATTEST_KEYS - {"basis", "commercial_context"}):
        return _result("INVALID_ATTESTATION_SCHEMA")
    if not attestation["lawfully_published"] or not attestation["lawfully_acquired"]:
        return _result("LAWFUL_PUBLICATION_OR_ACQUISITION_UNCONFIRMED")
    if not attestation["purpose_bounded"] or not attestation["private_local_storage"]:
        return _result("PURPOSE_OR_STORAGE_OUT_OF_SCOPE")
    if (not attestation["applicability_checked"] or
            not attestation["contract_and_access_terms_checked"]):
        return _result("LEGAL_BASIS_OR_ACCESS_TERMS_UNCONFIRMED")
    if not all(attestation[k] for k in (
            "no_public_distribution", "no_unnecessary_final_product_inclusion",
            "normal_exploitation_respected", "legitimate_interests_respected",
            "independent_rights_respected")):
        return _result("USE_IMPACT_OR_DISCLOSURE_RESTRICTIONS_UNCONFIRMED")
    if not attestation["usage_register_retained"]:
        return _result("USAGE_REGISTER_REQUIRED")
    if attestation["basis"] == BASIS_RESEARCH:
        if (use_record["purpose_code"] != "NONPROFIT_RESEARCH" or
                attestation["commercial_context"] != "NONCOMMERCIAL" or
                not attestation["nonprofit_activity"] or
                not attestation["author_and_source_attributed"]):
            return _result("NONPROFIT_RESEARCH_SCOPE_INVALID")
    elif use_record["purpose_code"] not in (
            "AI_ALGORITHM_DEVELOPMENT", "AI_PRODUCT_DEVELOPMENT"):
        return _result("AI_DEVELOPMENT_PURPOSE_INVALID")
    if attestation["commercial_context"] == "UNASSESSED_COMMERCIAL":
        return _result("COMMERCIAL_CONTEXT_UNASSESSED")
    if (attestation["commercial_context"] == "LIMITED_COMMERCIAL_EXCEPTION" and
            not attestation["commercial_exception_checked"]):
        return _result("COMMERCIAL_EXCEPTION_UNCONFIRMED")
    # Public edition rights deliberately do not block an otherwise applicable
    # PRIVATE development exception. Publication still needs separate approval.
    return _result("INTERNAL_DEVELOPMENT_RESEARCH_ELIGIBLE", True)
