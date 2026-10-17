"""Heritage-first source-use *routing*, not copyright licensing or legal advice.

All facts are supplied by a human operator, NOT independently certified.
Neither a scholarly attribution nor a public URL proves a reuse license.
"""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata
from typing import Literal

AssetLayer = Literal[
    "classical_base_text", "modern_edition_or_annotation",
    "publisher_database", "personal_annotation",
]
Basis = Literal["public_domain", "statutory_exception", "explicit_license", "unverified"]
Use = Literal[
    "metadata_reference", "local_research", "ai_development_copy",
    "short_public_quote", "full_text_publication", "dataset_redistribution",
]
ClaimStatus = Literal["none", "pending_review", "substantiated"]
Decision = Literal["proceed", "source_hold", "restricted", "invalid"]

LAYER_VALUES = frozenset(("classical_base_text", "modern_edition_or_annotation", "publisher_database", "personal_annotation"))
BASIS_VALUES = frozenset(("public_domain", "statutory_exception", "explicit_license", "unverified"))
USE_VALUES = frozenset(("metadata_reference", "local_research", "ai_development_copy", "short_public_quote", "full_text_publication", "dataset_redistribution"))
CLAIM_VALUES = frozenset(("none", "pending_review", "substantiated"))


@dataclass(frozen=True)
class SourceUseRecord:
    """One source/edition layer: DECLARED rights basis and limits.

    A reference is a pointer to operator evidence, never legal clearance.
    Keep confidential documents out of public repositories.
    """
    source_id: str
    asset_layer: AssetLayer
    basis: Basis = "unverified"
    evidence_ref: str = ""
    lawful_original_publication: bool = False
    lawful_copy_provenance: bool = False
    exact_layer_separated: bool = False
    proportional_copy: bool = False
    source_attribution: bool = False
    noncommercial_research: bool = False
    no_unreasonable_rights_harm: bool = False
    short_quote_only: bool = False
    independent_transcription: bool = False
    permitted_scopes: tuple[Use, ...] = ()
    claim_status: ClaimStatus = "none"


@dataclass(frozen=True)
class Result:
    decision: Decision
    reason: str
    assurance: Literal["operator_declarations_only"] = "operator_declarations_only"


def _bounded_text(value: object, length: int, *, nonempty: bool = False) -> bool:
    if type(value) is not str or len(value) > length:
        return False
    if nonempty and not value.strip():
        return False
    if any(unicodedata.category(c) in {"Cc", "Cs", "Cf"} for c in value):
        return False
    return True


def assess_source_use(record: SourceUseRecord, purpose: Use) -> Result:
    """Route a source-specific request, without fetching books or granting rights.

    'proceed' means a bounded *declared-policy* route, NOT authorization to
    copy, train, redistribute or publish actual third-party content.
    Downstream ingestion must perform its own independent approval.
    """
    if not isinstance(record, SourceUseRecord) or type(purpose) is not str or purpose not in USE_VALUES:
        return Result("invalid", "invalid source-use object or purpose")
    if (
        type(record.asset_layer) is not str or record.asset_layer not in LAYER_VALUES
        or type(record.basis) is not str or record.basis not in BASIS_VALUES
        or type(record.claim_status) is not str or record.claim_status not in CLAIM_VALUES
        or not _bounded_text(record.source_id, 256, nonempty=True)
        or not _bounded_text(record.evidence_ref, 1024)
        or any(type(getattr(record, key)) is not bool for key in (
            "lawful_original_publication", "lawful_copy_provenance",
            "exact_layer_separated", "proportional_copy", "source_attribution",
            "noncommercial_research", "no_unreasonable_rights_harm",
            "short_quote_only", "independent_transcription",
        ))
        or not isinstance(record.permitted_scopes, tuple)
        or len(record.permitted_scopes) > len(USE_VALUES)
        or any(type(x) is not str or x not in USE_VALUES for x in record.permitted_scopes)
        or len(set(record.permitted_scopes)) != len(record.permitted_scopes)
    ):
        return Result("invalid", "invalid declaration structure")

    if record.claim_status != "none":
        return Result("source_hold", "source-specific rights/attribution claim under review")

    if record.asset_layer == "personal_annotation":
        return Result("restricted", "private annotations need separate consent")

    if purpose == "metadata_reference":
        return Result("proceed", "public bibliographic facts and links only")

    if not record.evidence_ref.strip() or not record.lawful_copy_provenance:
        return Result("restricted", "no source-specific basis or lawful copy provenance")

    if record.basis == "public_domain":
        if (record.asset_layer != "classical_base_text"
                or not record.exact_layer_separated
                or not record.independent_transcription
                or not record.source_attribution):
            return Result("restricted", "assertion excludes modern edition, provider database and unisolated transcription")
        return Result("proceed", "operator claims independently transcribed public-domain original")

    if record.basis == "explicit_license":
        if not record.source_attribution:
            return Result("restricted", "scholarly source attribution missing")
        if record.exact_layer_separated and purpose in record.permitted_scopes:
            return Result("proceed", "operator claims named purpose within license")
        return Result("restricted", "purpose absent from referenced license")

    if record.basis != "statutory_exception":
        return Result("restricted", "unverified rights beyond bibliographic metadata")

    if record.asset_layer == "publisher_database":
        return Result("restricted", "database and edition rights require separate assessment")

    if not (record.lawful_original_publication and record.exact_layer_separated
            and record.proportional_copy and record.no_unreasonable_rights_harm
            and record.noncommercial_research):
        return Result("restricted", "bounded statutory conditions not declared")

    if purpose == "local_research":
        return (
            Result("proceed", "bounded noncommercial research declaration")
            if record.source_attribution else
            Result("restricted", "source attribution missing")
        )
    if purpose == "ai_development_copy":
        return Result("proceed", "bounded AI research copying declaration, never redistribution")
    if purpose == "short_public_quote":
        return (
            Result("proceed", "bounded attributed public quotation declaration")
            if record.short_quote_only and record.source_attribution else
            Result("restricted", "quotation conditions not established")
        )
    return Result("restricted", "research/AI exceptions do not grant full-text redistribution")
