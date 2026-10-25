"""I0.1a: operator-only Quran research view with an R0.1d qualification gate.

This module combines R0.1c *metadata-only* private retrieval with the signed
R0.1d two-axis decision ledger. It is deliberately NOT an HTTP endpoint,
public Quran reader, Tafsir text exporter, legal clearance or fatwa engine.
Q0.1c/Q0.1e-b localhost reading and Q0.1f external bibliography remain
separate, already-integrated interfaces and do not gain private-vault access.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from engines.quran.research.private_adapters import (
    PrivateResearchAdapters, ResearchAdapterError, SIDE_TABLES,
)
from qa.corpus_ingest_v01 import VALID_IDS
from engines.quran.research.unified import (
    CONTRACT as RETRIEVAL_CONTRACT,
    MODE_METADATA, UnifiedRetrievalError, unified_lookup,
)
from engines.quran.research import qualification as qual

CONTRACT = "mubin-operator-qualified-retrieval-v0.1"
VERSION = "quran-operator-integration/i0.1a"
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UNVERIFIED = {
    "source_authenticated": False, "scholarly_verified": False,
    "rights_verified": False, "publication_allowed": False,
    "redistribution_approved": False, "edition_verified": False,
    "p1_admitted": False, "juristic_inference_allowed": False,
    "public_fatwa_authorized": False, "text_included": False,
}


class OperatorViewError(ValueError):
    """Safe refusal codes only: no private data, file paths or Quran text."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _states(decisions: list[dict], evidence_head: str) -> tuple[str, str, int, bool]:
    """Old approvals expire on evidence change; old explicit denials persist.

    A later signed decision never silently releases a rejection/quarantine or
    NOT_CLEARED denial. Such a release needs its own future adjudication policy.
    Both axes remain independent and no result is a public-use authorization.
    """
    scholarly = qual.DEFAULT_SCHOLARLY
    rights = qual.DEFAULT_RIGHTS
    quarantine = False
    rejected = False
    not_cleared = False
    matched = 0
    stale = False
    for record in decisions:
        decision = record["decision"]
        axis = record["axis"]
        scope = record["scope"]
        if axis == "scholarly":
            if decision == "SOURCE_REJECTED":
                rejected = True
            if decision == "RECORD_QUARANTINED":
                quarantine = True
        elif axis == "rights" and decision == "NOT_CLEARED":
            not_cleared = True
        if record["evidence_head_sha256"] != evidence_head:
            stale = True
            continue
        matched += 1
        if scope == {"full_source": True}:
            if axis == "scholarly":
                scholarly = decision
            elif axis == "rights":
                rights = decision
    if rejected:
        scholarly = "SOURCE_REJECTED"
    elif quarantine:
        scholarly = "RECORD_QUARANTINED"
    if not_cleared:
        rights = "NOT_CLEARED"
    return scholarly, rights, matched, stale


def operator_lookup(adapters: PrivateResearchAdapters, reference: str, *,
                    ledger: Path, qualification_anchor_dir: Path,
                    qualification_key: Path, vault: Path,
                    adapter_filter: str | None = None) -> dict:
    """Read-only, no text or publication path; fail closed if either head moves."""
    qual._valid_reference(reference)
    before = qual.verify_ledger(ledger, qualification_anchor_dir,
                                qualification_key, vault=vault)
    research = unified_lookup(adapters, reference,
                              adapter_filter=adapter_filter, include_text=False)
    evidence_head = research.get("evidence_head_sha256")
    sources = research.get("sources")
    if (research.get("contract") != RETRIEVAL_CONTRACT
            or research.get("reference") != reference
            or research.get("research_mode") != MODE_METADATA
            or type(evidence_head) is not str or not _SHA.fullmatch(evidence_head)
            or type(sources) is not list
            or research.get("text_included") is not False
            or any(research.get(k) is not v for k, v in _UNVERIFIED.items())):
        raise OperatorViewError("RESEARCH_NOT_METADATA_ONLY")

    rows = []
    seen = set()
    for src in sources:
        if (type(src) is not dict
                or type(src.get("source_id")) is not str
                or src["source_id"] not in qual.SOURCE_IDS
                or src["source_id"] in seen
                or src.get("adapter") not in ("quranenc_corpus", "tafsircenter_sidecar")
                or (src.get("adapter") == "quranenc_corpus"
                    and src["source_id"] not in VALID_IDS)
                or (src.get("adapter") == "tafsircenter_sidecar"
                    and src["source_id"] not in SIDE_TABLES)
                or type(src.get("coordinate_present")) is not bool
                or src.get("text_included") is not False
                or any(src.get(k) is not v for k, v in _UNVERIFIED.items()
                       if k in src)):
            raise OperatorViewError("RESEARCH_SOURCE_INVALID")
        seen.add(src["source_id"])
        decision_rows = qual.decisions_for(
            ledger, src["source_id"], anchor_dir=qualification_anchor_dir,
            key_file=qualification_key, vault=vault, reference=reference)
        scholarly, rights, count, stale = _states(decision_rows, evidence_head)
        rows.append({
            "source_id": src["source_id"],
            "adapter": src["adapter"],
            "coordinate_present": src["coordinate_present"],
            "scholarly_decision_state": scholarly,
            "rights_decision_state": rights,
            "matching_evidence_decisions": count,
            "historical_evidence_decisions_present": stale,
            "text_included": False,
            "publication_allowed": False,
            "juristic_inference_allowed": False,
            "public_fatwa_authorized": False,
        })
    after = qual.verify_ledger(ledger, qualification_anchor_dir,
                               qualification_key, vault=vault)
    if (after["head_entry_sha256"] != before["head_entry_sha256"]
            or after["entries"] != before["entries"]):
        raise OperatorViewError("QUALIFICATION_HEAD_CHANGED_DURING_LOOKUP")
    if adapters.evidence_head(force_rehash=True) != evidence_head:
        # Boundary check with forced full re-hash: any mid-request change
        # to the vault bytes is detected before the answer is returned.
        raise OperatorViewError("EVIDENCE_HEAD_CHANGED_DURING_QUALIFICATION")

    return {
        "contract": CONTRACT, "engine": VERSION,
        "reference": reference,
        "research_mode": MODE_METADATA,
        "evidence_head_sha256": evidence_head,
        "qualification_head_sha256": after["head_entry_sha256"],
        "qualification_decisions": after["entries"],
        "sources": rows,
        "public_quran_reader": "separate_loopback_only",
        "tafsir_catalog": "external_navigation_metadata_only",
        "qualification_gate": "signed_ledger_verified_metadata_only",
        "rights_status": qual.DEFAULT_RIGHTS,
        **_UNVERIFIED,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Local operator-only qualification-bound metadata lookup")
    sub = parser.add_subparsers(dest="action", required=True)
    lookup = sub.add_parser("lookup")
    for name in ("ref", "vault", "corpus-db", "sidecar-db", "registry",
                 "anchor-dir", "evidence-key", "qualification-ledger",
                 "qualification-anchor-dir", "qualification-key"):
        lookup.add_argument("--" + name, required=True)
    lookup.add_argument("--adapters", choices=("both", "corpus", "sidecar"),
                        default="both")
    args = parser.parse_args(argv)
    try:
        adapters = PrivateResearchAdapters(
            vault=Path(args.vault), corpus_db=Path(args.corpus_db),
            sidecar_db=Path(args.sidecar_db), registry=Path(args.registry),
            anchor_dir=Path(args.anchor_dir), evidence_key=Path(args.evidence_key))
        report = operator_lookup(
            adapters, args.ref, vault=Path(args.vault),
            ledger=Path(args.qualification_ledger),
            qualification_anchor_dir=Path(args.qualification_anchor_dir),
            qualification_key=Path(args.qualification_key),
            adapter_filter=None if args.adapters == "both" else args.adapters)
        code = 0
    except (ResearchAdapterError, UnifiedRetrievalError,
            qual.QualificationError, OperatorViewError) as exc:
        report = {"contract": CONTRACT, "status": "REFUSED",
                  "reason_code": exc.code, **_UNVERIFIED}
        code = 1
    except (OSError, ValueError, TypeError, KeyError, UnicodeError):
        report = {"contract": CONTRACT, "status": "REFUSED",
                  "reason_code": "OPERATOR_LOOKUP_INTERNAL_ERROR",
                  **_UNVERIFIED}
        code = 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
