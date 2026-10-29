"""Fiqh orchestration foundation: source-attributed opinions, no invented verdict."""
from __future__ import annotations
from core.contracts.types import ContractError, identifier
from .models import FiqhCase, JuristicOpinion, ResearchFinding


def prepare_research(case: FiqhCase, opinions: tuple[JuristicOpinion, ...],
                     evidence_refs: tuple[str, ...] = ()) -> ResearchFinding:
    if not isinstance(case, FiqhCase) or not isinstance(opinions, tuple):
        raise ContractError("FIQH_INPUT_INVALID")
    if not isinstance(evidence_refs, tuple) or not all(identifier(x) for x in evidence_refs):
        raise ContractError("FIQH_EVIDENCE_INVALID")
    if any(not isinstance(op, JuristicOpinion) or op.methodology_profile_id != case.methodology_profile_id
           for op in opinions):
        raise ContractError("FIQH_METHODOLOGY_MISMATCH")
    if len({x.opinion_id for x in opinions}) != len(opinions):
        raise ContractError("FIQH_DUPLICATE_OPINION")
    missing = not opinions or not evidence_refs
    return ResearchFinding(
        case_id=case.case_id,
        status="UNDETERMINED" if missing else "PARTIAL",
        opinion_refs=tuple(op.opinion_id for op in opinions),
        evidence_refs=evidence_refs,
        uncertainties=("INSUFFICIENT_EVIDENCE_FOR_REASONED_FINDING",) if missing
                      else ("USUL_APPLICATION_NOT_EXECUTED",),
    )
