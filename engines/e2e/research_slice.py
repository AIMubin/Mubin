"""E2E-01.1: one bounded Quran/tafsir + al-Waraqat research demonstration.

Composes the *existing* I0.1a operator_lookup (R0.1c unified retrieval,
authenticated R0.1d qualification decisions, before/after head checks) with
the source-attributed U0.1 al-Waraqat synthetic pilot.

IMPORTANT: The selected verse is a coordinate lookup, NOT evidence for the
al-Waraqat modeled rule. No semantic relation is inferred in this phase.
No new inference engine, publishing authority, or private text output.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from engines.quran.research.private_adapters import (
    PrivateResearchAdapters, ResearchAdapterError,
)
from engines.quran.research.operator_view import (
    operator_lookup, OperatorViewError, CONTRACT as OPERATOR_CONTRACT,
)
from engines.quran.research.unified import UnifiedRetrievalError
from engines.quran.research import qualification as qual
from engines.usul.pilots.amr_default import run_pilot
from engines.e2e.semantic_linkage import build_linkage, LinkageError

CONTRACT = "mubin-e2e-research-v0.1"
VERSION = "e2e-research-slice/0.1.1"
QUESTION = "دلالة صيغة الأمر والقرائن المؤثرة فيه"
RESEARCH_MODE = "metadata_only"


class ResearchSliceError(ValueError):
    """Stable, non-disclosing refusal code."""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _limits() -> dict[str, Any]:
    return {
        "scholarly_verified": False, "source_authenticated": False,
        "rights_status": "legal_review_pending",
        "rights_verified": False, "publication_allowed": False,
        "redistribution_approved": False, "edition_verified": False,
        "p1_admitted": False, "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "text_included": False,
    }


def _qualified_gaps(sources: list[dict]) -> list[dict]:
    """Report actual review state, not a fabricated review outcome."""
    gaps = [{"type": "semantic_link_unassessed", "source_id": "pilot:waraqat-bab-al-amr",
             "detail": "Verse coordinate and modeled Usul rule have no established semantic evidence link."}]
    for s in sources:
        sid = s["source_id"]
        if s["scholarly_decision_state"] == "UNREVIEWED":
            gaps.append({"type": "scholarly_review_pending", "source_id": sid})
        if s["rights_decision_state"] == "legal_review_pending":
            gaps.append({"type": "rights_review_pending", "source_id": sid})
    gaps.append({"type": "edition_unverified", "source_id": "pilot:waraqat-bab-al-amr",
                 "detail": "Online excerpt digest only; printed edition not authenticated."})
    gaps.append({"type": "hadith_retrieval_missing", "source_id": "hadith"})
    return gaps


def research_slice(
    adapters: PrivateResearchAdapters,
    reference: str,
    question: str,
    *,
    ledger: Path,
    qualification_anchor_dir: Path,
    qualification_key: Path,
    vault: Path,
    linkage_observation: dict | None = None,
) -> dict[str, Any]:
    """One auditable, research-only aggregate of existing component outputs.

    Input question is fixed because the modeled Usul pilot is fixed. Arbitrary
    user questions would otherwise receive an unrelated al-Waraqat answer.
    """
    if type(question) is not str or question != QUESTION:
        raise ResearchSliceError("E2E_QUESTION_OUT_OF_SCOPE")

    # Reuse established operator contract: signed ledger head before/after,
    # per-source sticky denials and evidence-head checks. Do not duplicate
    # qualification logic with current_state(), which lacks head expiry.
    qualified = operator_lookup(
        adapters, reference, ledger=Path(ledger),
        qualification_anchor_dir=Path(qualification_anchor_dir),
        qualification_key=Path(qualification_key), vault=Path(vault))
    if (qualified.get("contract") != OPERATOR_CONTRACT
            or qualified.get("reference") != reference
            or qualified.get("research_mode") != RESEARCH_MODE
            or qualified.get("text_included") is not False
            or qualified.get("publication_allowed") is not False
            or qualified.get("source_authenticated") is not False
            or qualified.get("public_fatwa_authorized") is not False):
        raise ResearchSliceError("E2E_OPERATOR_CONTRACT_INVALID")

    # Independent, static synthetic scenarios from existing al-Waraqat pilot.
    usul = run_pilot()
    if (usul.get("pilot") != "waraqat-bab-al-amr"
            or usul.get("scenario_kind") != "SYNTHETIC_TEST_INPUTS"
            or usul.get("scholarly_verified") is not False
            or usul.get("valid_juristic_ruling") is not False
            or usul.get("public_fatwa_authorized") is not False):
        raise ResearchSliceError("E2E_USUL_CONTRACT_INVALID")

    # Recheck BOTH signed heads after running pilot, to refuse mixed epochs.
    ledger_after = qual.verify_ledger(
        Path(ledger), Path(qualification_anchor_dir), Path(qualification_key),
        vault=Path(vault))
    if (ledger_after["head_entry_sha256"] != qualified["qualification_head_sha256"]
            or ledger_after["entries"] != qualified["qualification_decisions"]):
        raise ResearchSliceError("E2E_QUALIFICATION_HEAD_CHANGED")
    if adapters.evidence_head() != qualified["evidence_head_sha256"]:
        raise ResearchSliceError("E2E_EVIDENCE_HEAD_CHANGED")

    research_linkage = {
        "status": "UNASSESSED",
        "quran_coordinate_role": "INDEPENDENT_LOOKUP_NOT_RULE_EVIDENCE",
        "verse_is_evidence_for_usul_rule": False,
        "synthetic_scenarios_are_real_case_evidence": False,
    }
    if linkage_observation is not None:
        # Accept a metadata-only OPERATOR proposal only when it is bound to
        # this already authenticated E2E-01.1 evidence head and coordinate.
        # A true digest/word correspondence or semantic scholarly relation
        # is NOT established by this matching.
        if type(linkage_observation) is not dict:
            raise ResearchSliceError("E2E_LINKAGE_INPUT_INVALID")
        try:
            proposal = build_linkage(**linkage_observation)
        except (TypeError, LinkageError) as exc:
            raise ResearchSliceError("E2E_LINKAGE_INPUT_INVALID") from exc
        if proposal["verse"]["reference"] != reference:
            raise ResearchSliceError("E2E_LINKAGE_REFERENCE_MISMATCH")
        if proposal["evidence_head_sha256"] != qualified["evidence_head_sha256"]:
            raise ResearchSliceError("E2E_LINKAGE_EVIDENCE_HEAD_MISMATCH")
        if not any(row["coordinate_present"] is True
                   for row in qualified["sources"]):
            raise ResearchSliceError("E2E_LINKAGE_COORDINATE_NOT_RETRIEVED")
        research_linkage = {
            "status": "PROPOSED_NOT_CERTIFIED",
            "quran_coordinate_role": "OPERATOR_RECORDED_RESEARCH_CANDIDATE",
            "verse_is_evidence_for_usul_rule": False,
            "synthetic_scenarios_are_real_case_evidence": False,
            "proposal": proposal,
            "evidence_head_bound_to_qualified_retrieval": True,
            "verse_text_byte_match_independently_verified": False,
        }

    sources = qualified["sources"]
    states = {s["source_id"]: {
        "scholarly": s["scholarly_decision_state"],
        "rights": s["rights_decision_state"],
        "matching_evidence_decisions": s["matching_evidence_decisions"],
        "historical_evidence_decisions_present":
            s["historical_evidence_decisions_present"],
    } for s in sources}

    return {
        "contract": CONTRACT, "version": VERSION,
        "question": QUESTION, "reference": reference,
        "research_mode": RESEARCH_MODE,
        "quran_retrieval": {
            "contract": qualified["contract"],
            "evidence_head_sha256": qualified["evidence_head_sha256"],
            "qualification_head_sha256": qualified["qualification_head_sha256"],
            "sources": sources,
        },
        "usul_analysis": {
            "pilot": usul["pilot"], "milestone": usul["milestone"],
            "source_reference": usul["source_reference"],
            "scenario_kind": usul["scenario_kind"],
            "cases": usul["cases"],
            "semantic_equivalence_verified": False,
        },
        "research_linkage": research_linkage,
        "qualification_states": states,
        "gaps": _qualified_gaps(sources),
        "undetermined": [
            "لم يُثبت ارتباط الآية المسترجعة بالقاعدة الأصولية دلاليًا.",
            "وجود القرينة الصارفة أو غيابها في مسألة حقيقية لم يُفحص.",
            "لم تُسترجع أحاديث ذات صلة، ولا يمكن استخراج حكم فقهي.",
        ],
        "limits": _limits(),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="E2E-01.1 bounded, metadata-only research slice")
    parser.add_argument("--ref", required=True)
    parser.add_argument("--question", required=True)
    for name in (
        "vault", "corpus-db", "sidecar-db", "registry", "anchor-dir",
        "evidence-key", "qualification-ledger",
        "qualification-anchor-dir", "qualification-key",
    ):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        adapters = PrivateResearchAdapters(
            vault=args.vault, corpus_db=args.corpus_db,
            sidecar_db=args.sidecar_db, registry=args.registry,
            anchor_dir=args.anchor_dir, evidence_key=args.evidence_key)
        report = research_slice(
            adapters, args.ref, args.question,
            ledger=args.qualification_ledger,
            qualification_anchor_dir=args.qualification_anchor_dir,
            qualification_key=args.qualification_key, vault=args.vault)
        code = 0
    except (ResearchSliceError, ResearchAdapterError, OperatorViewError,
            UnifiedRetrievalError, qual.QualificationError) as exc:
        report, code = {"contract": CONTRACT, "status": "REFUSED",
                        "reason_code": exc.code, **_limits()}, 1
    except (OSError, ValueError, TypeError, KeyError, RuntimeError,
            UnicodeError):
        report, code = {"contract": CONTRACT, "status": "REFUSED",
                        "reason_code": "E2E_INTERNAL_REFUSED", **_limits()}, 1
    # Portable on Windows terminals whose legacy encoding cannot print Arabic.
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
