"""E2E-01.1: first integrated research slice over existing Mubin components.

Aggregates Quran metadata (R0.1c unified lookup), Usul analysis (amr_default
pilot), and qualification states (R0.1d ledger) into ONE research result.
This is a thin aggregation layer, not a new engine. Every component already
exists in main; this module just wires their outputs into a single JSON
document that a researcher can read and audit.

Deliberately NOT: a tafsir engine, a hadith search, a fatwa generator,
or a semantic inference system. All authority flags remain false.
"""
from __future__ import annotations

import json
from typing import Any

from engines.quran.research.private_adapters import PrivateResearchAdapters
from engines.quran.research.unified import unified_lookup
from engines.quran.research.qualification import current_state
from engines.usul.pilots.amr_default import run_pilot

CONTRACT = "mubin-e2e-research-v0.1"
VERSION = "e2e-research-slice/0.1.0"
RESEARCH_MODE = "metadata_only"


def _limits() -> dict:
    return {
        "scholarly_verified": False, "source_authenticated": False,
        "rights_verified": False, "publication_allowed": False,
        "redistribution_approved": False, "edition_verified": False,
        "p1_admitted": False, "juristic_inference_allowed": False,
        "public_fatwa_authorized": False, "text_included": False,
    }


def _gaps(retrieval: dict, usul: dict, qualification_states: dict) -> list[dict]:
    """Identify what the system could NOT determine from available data."""
    gaps = []
    for source in retrieval.get("sources", []):
        if source.get("edition_verified") is False:
            gaps.append({
                "type": "edition_unverified", "source_id": source["source_id"],
                "detail": "Bibliographic metadata only; edition identity not confirmed."
            })
    usul_pilot = usul.get("pilot", "")
    if usul_pilot:
        gaps.append({
            "type": "usul_pilot_scope", "source_id": usul_pilot,
            "detail": "Usul analysis from synthetic pilot scenarios; real fiqh application requires scholarly review."
        })
    for source_id, states in qualification_states.items():
        if states["scholarly"] == "UNREVIEWED":
            gaps.append({
                "type": "scholarly_review_pending", "source_id": source_id,
                "detail": "No scholarly review decision recorded for this source."
            })
        if states["rights"] == "legal_review_pending":
            gaps.append({
                "type": "rights_review_pending", "source_id": source_id,
                "detail": "Rights status not cleared for any use beyond internal research."
            })
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
) -> dict[str, Any]:
    """One integrated research result: Quran + tafsir + usul + qualification."""
    # 1. Quran + tafsir metadata retrieval (R0.1c unified)
    retrieval = unified_lookup(adapters, reference)
    _need_retrieval_valid(retrieval, reference)

    # 2. Usul analysis (amr_default pilot from al-Waraqat)
    usul = run_pilot()

    # 3. Qualification states per source (R0.1d ledger)
    qualification_states = {}
    for source in retrieval.get("sources", []):
        sid = source["source_id"]
        scholarly = current_state(
            ledger, sid, "scholarly",
            anchor_dir=qualification_anchor_dir,
            key_file=qualification_key, vault=vault)
        rights = current_state(
            ledger, sid, "rights",
            anchor_dir=qualification_anchor_dir,
            key_file=qualification_key, vault=vault)
        qualification_states[sid] = {
            "scholarly": scholarly, "rights": rights,
        }

    # 4. Gaps and undetermined
    gaps = _gaps(retrieval, usul, qualification_states)
    undetermined = [
        "دلالة صيغة الأمر غير محسومة: النتائج تعرض قواعد مرشحة فقط،"
        " وليست أحكامًا شرعية نهائية.",
        "القرائن الصارفة تتطلب فحصًا بحثيًا مستقلًا خارج نطاق هذا الاسترجاع.",
        "محرك الحديث غير متاح في هذه الشريحة؛ الأحاديث ذات الصلة غير مُدرجة.",
    ]

    return {
        "contract": CONTRACT,
        "version": VERSION,
        "question": question,
        "reference": reference,
        "research_mode": RESEARCH_MODE,
        "quran_retrieval": {
            "contract": retrieval.get("contract"),
            "evidence_head_sha256": retrieval.get("evidence_head_sha256"),
            "sources": retrieval.get("sources", []),
        },
        "usul_analysis": {
            "pilot": usul.get("pilot"),
            "milestone": usul.get("milestone"),
            "scenarios_tested": list(usul.get("cases", {}).keys()),
            "source_reference": usul.get("source_reference"),
        },
        "qualification_states": qualification_states,
        "gaps": gaps,
        "undetermined": undetermined,
        "limits": _limits(),
    }


def _need_retrieval_valid(retrieval: dict, reference: str) -> None:
    from engines.quran.research.unified import CONTRACT as RETRIEVAL_CONTRACT
    if retrieval.get("contract") != RETRIEVAL_CONTRACT:
        raise ValueError("retrieval_contract_mismatch")
    if retrieval.get("reference") != reference:
        raise ValueError("retrieval_reference_mismatch")
    if retrieval.get("research_mode") != "metadata_only":
        raise ValueError("retrieval_not_metadata_only")


def main(argv=None):
    import argparse
    from engines.quran.research.private_adapters import PrivateResearchAdapters
    parser = argparse.ArgumentParser(description="E2E-01.1 integrated research slice")
    parser.add_argument("--ref", required=True)
    parser.add_argument("--question", required=True)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--corpus-db", required=True)
    parser.add_argument("--sidecar-db", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--anchor-dir", required=True)
    parser.add_argument("--evidence-key", required=True)
    parser.add_argument("--qualification-ledger", required=True)
    parser.add_argument("--qualification-anchor-dir", required=True)
    parser.add_argument("--qualification-key", required=True)
    args = parser.parse_args(argv)
    adapters = PrivateResearchAdapters(
        vault=args.vault, corpus_db=args.corpus_db,
        sidecar_db=args.sidecar_db, registry=args.registry,
        anchor_dir=args.anchor_dir, evidence_key=args.evidence_key)
    report = research_slice(
        adapters, args.ref, args.question,
        ledger=args.qualification_ledger,
        qualification_anchor_dir=args.qualification_anchor_dir,
        qualification_key=args.qualification_key, vault=args.vault)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0

