"""R0.1c: unified private-retrieval result contract (metadata-first).

Aggregates the R0.1b read-only adapters into ONE auditable answer per verse
reference: which pinned private sources hold the coordinate, their qualification
states, and the evidence head the answer is bound to. Text is closed by default
and requires the R0.1b signed-permit path with an independently approved issuer.
This module never promotes a bibliographic label to an authenticated edition
and never grants scholarly, rights, inference or fatwa authority.
"""
from __future__ import annotations

import argparse
import json
from typing import Any

from engines.quran.research.private_adapters import (
    PrivateResearchAdapters, ResearchAdapterError,
)

CONTRACT = "mubin-private-retrieval-v0.1"
VERSION = "quran-research-unified/0.1.0"
MODE_METADATA = "metadata_only"
MODE_RESTRICTED_TEXT = "restricted_local_text"


class UnifiedRetrievalError(ValueError):
    """Stable refusal codes; never contain private text or paths."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _no_text(entry: dict) -> dict:
    return {k: v for k, v in entry.items()
            if k not in ("text", "footnotes")}


def unified_lookup(adapters: PrivateResearchAdapters, reference: str, *,
                   adapter_filter: str | None = None,
                   include_text: bool = False) -> dict:
    """Aggregate one reference across both pinned private source families."""
    if include_text is True:
        # The trusted permit issuer is disabled by default upstream; the
        # R0.1b permit check itself fail-closes when the issuer is unpinned.
        research_mode = MODE_RESTRICTED_TEXT
    elif include_text is False:
        research_mode = MODE_METADATA
    else:
        raise UnifiedRetrievalError("TEXT_MODE_INVALID")
    if adapter_filter not in (None, "corpus", "sidecar"):
        raise UnifiedRetrievalError("ADAPTER_FILTER_INVALID")

    corpus_meta = [] if adapter_filter == "sidecar" else adapters.corpus_sources()
    sidecar_meta = [] if adapter_filter == "corpus" else adapters.sidecar_sources()

    sources: list[dict] = []
    for meta in corpus_meta:
        entry = {
            "source_id": meta["source_id"],
            "source_kind": meta["source_kind"],
            "adapter": meta["adapter"],
            "verse_locator": reference,
            "coordinate_present": None,
            "text_included": False,
            "edition_verified": False,
            "rights_status": "legal_review_pending",
            "scholarly_verified": False,
            "p1_admitted": False,
        }
        try:
            outcome = adapters.lookup(reference, meta["source_id"], adapter="corpus",
                                      include_text=include_text)
            entry["coordinate_present"] = True
            if include_text:
                entry["text"] = outcome["text"]
                entry["footnotes"] = outcome["footnotes"]
                entry["text_included"] = outcome["text_included"]
                entry["restricted_local_use_only"] = True
        except ResearchAdapterError as exc:
            if exc.code == "REFERENCE_NOT_PRESENT":
                entry["coordinate_present"] = False
            else:
                raise
        sources.append(entry)
    for meta in sidecar_meta:
        entry = {
            "source_id": meta["source_id"],
            "source_kind": meta["source_kind"],
            "adapter": meta["adapter"],
            "verse_locator": reference,
            "coordinate_present": None,
            "text_included": False,
            "edition_verified": False,
            "rights_status": "legal_review_pending",
            "scholarly_verified": False,
            "p1_admitted": False,
        }
        try:
            outcome = adapters.lookup(reference, meta["source_id"], adapter="sidecar",
                                      include_text=include_text)
            entry["coordinate_present"] = True
            if include_text:
                entry["text"] = outcome["text"]
                entry["text_included"] = outcome["text_included"]
                entry["restricted_local_use_only"] = True
        except ResearchAdapterError as exc:
            if exc.code == "REFERENCE_NOT_PRESENT":
                entry["coordinate_present"] = False
            else:
                raise
        sources.append(entry)

    result = {
        "contract": CONTRACT,
        "engine": VERSION,
        "reference": reference,
        "research_mode": research_mode,
        "evidence_head_sha256": adapters.evidence_head(),
        "sources": sources,
        "text_included": any(s["text_included"] for s in sources),
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "scholarly_verified": False,
        "source_authenticated": False,
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Local metadata-first private retrieval (research-only)")
    parser.add_argument("--ref", required=True)
    parser.add_argument("--vault", required=True)
    parser.add_argument("--corpus-db", required=True)
    parser.add_argument("--sidecar-db", required=True)
    parser.add_argument("--registry", required=True)
    parser.add_argument("--anchor-dir", required=True)
    parser.add_argument("--evidence-key", required=True)
    parser.add_argument("--adapters", choices=("both", "corpus", "sidecar"),
                        default="both")
    parser.add_argument("--include-text", action="store_true",
                        help="requires a trusted-issuer signed local permit")
    parser.add_argument("--permit-path")
    parser.add_argument("--permit-key")
    args = parser.parse_args(argv)
    adapters = PrivateResearchAdapters(
        vault=args.vault, corpus_db=args.corpus_db, sidecar_db=args.sidecar_db,
        registry=args.registry, anchor_dir=args.anchor_dir,
        evidence_key=args.evidence_key,
        permit_path=args.permit_path, permit_key=args.permit_key)

    try:
        report = unified_lookup(
            adapters, args.ref,
            adapter_filter=None if args.adapters == "both" else args.adapters,
            include_text=args.include_text)
        code = 0
    except ResearchAdapterError as exc:
        report = {"contract": CONTRACT, "status": "REFUSED",
                  "reason_code": exc.code, "text_included": False,
                  "juristic_inference_allowed": False,
                  "public_fatwa_authorized": False}
        code = 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
