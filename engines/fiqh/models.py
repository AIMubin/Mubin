"""Typed research models for F0.1. No fatwa, tarjih or scholarly-grade inference."""
from __future__ import annotations
from dataclasses import dataclass
from core.contracts.types import ContractError, identifier


@dataclass(frozen=True)
class FiqhCase:
    case_id: str
    question: str
    methodology_profile_id: str
    fact_refs: tuple[str, ...] = ()

    def __post_init__(self):
        if (not identifier(self.case_id) or not identifier(self.methodology_profile_id)
                or not isinstance(self.question, str) or not self.question.strip()
                or len(self.question) > 4096 or not all(identifier(ref) for ref in self.fact_refs)):
            raise ContractError("FIQH_CASE_INVALID")


@dataclass(frozen=True)
class JuristicOpinion:
    opinion_id: str
    source_ref: str
    methodology_profile_id: str

    def __post_init__(self):
        if not all(identifier(x) for x in (self.opinion_id, self.source_ref, self.methodology_profile_id)):
            raise ContractError("FIQH_OPINION_INVALID")


@dataclass(frozen=True)
class ResearchFinding:
    case_id: str
    status: str
    opinion_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    uncertainties: tuple[str, ...]
    authority: str = "RESEARCH_ONLY"
