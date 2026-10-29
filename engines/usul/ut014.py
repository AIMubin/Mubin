"""UT-01.4: unified research presentation of Usul-Tafsir links.

Loads an operator-supplied, digest-pinned usul evidence bundle (metadata
only), reruns the conservative UT-01.3 matching per request against the
pinned tafsir database, and emits a metadata-only presentation section.
Lexical usul links sit at AUTOMATED_CANDIDATE level and can never rise to
TEXTUALLY_ATTRIBUTED or SCHOLARLY_VERIFIED through this layer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engines.usul.ut013 import (
    match_candidate, summarize as match_summary, OFFSET_UTF8_BYTES,
)
from engines.tafsir.t01 import lookup_verse
from engines.tafsir.t02_cli import extract_local_verse
from engines.tafsir.t023 import identify_candidates

CONTRACT = "mubin-usul-tafsir-presentation-v1"
VERSION = "usul-presentation/0.1.0"
EVIDENCE_LEVELS = (
    "RETRIEVED_SOURCE_MATERIAL", "GROUNDED_PASSAGE", "AUTOMATED_CANDIDATE",
    "TEXTUALLY_ATTRIBUTED", "SCHOLARLY_VERIFIED")
USUL_LINK_MAX_LEVEL = "AUTOMATED_CANDIDATE"
_BUNDLE_REQUIRED = (
    "usul_rule_candidate_id", "usul_research_pointer_id",
    "catalog_sha256", "graph_sha256", "usul_source_id",
    "usul_section_path", "usul_section_sha256", "query_terms",
    "waraqat_primary_html", "waraqat_primary_export",
    "waraqat_primary_manifest", "waraqat_primary_section",
    "waraqat_secondary_html", "waraqat_secondary_section",
    "usul_work_id")
_FORBIDDEN_BUNDLE_FIELDS = (
    "text", "passage_text", "statement", "matn", "html",
    "scholarly_verified", "juristic_inference_allowed",
    "public_fatwa_authorized", "source_support_attested")


class UsulPresentationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise UsulPresentationError(code)


def load_usul_evidence(path: Path) -> dict:
    """Load and validate the operator's usul evidence bundle (metadata-only)."""
    _need(path.is_file() and not path.is_symlink(), "US014_BUNDLE_UNAVAILABLE")
    raw = path.read_bytes()
    _need(0 < len(raw) <= 65536, "US014_BUNDLE_TOO_LARGE")
    bundle = json.loads(raw.decode("utf-8", "strict"))
    _need(type(bundle) is dict, "US014_BUNDLE_NOT_DICT")
    for field in _BUNDLE_REQUIRED:
        _need(field in bundle, f"US014_BUNDLE_FIELD_MISSING_{field}")
    for bad in _FORBIDDEN_BUNDLE_FIELDS:
        _need(bad not in bundle, f"US014_BUNDLE_FIELD_FORBIDDEN_{bad}")
    _need(bundle["usul_section_path"] and
          not Path(bundle["usul_section_path"]).is_symlink(),
          "US014_SECTION_PATH_INVALID")
    _need(type(bundle["query_terms"]) is list and bundle["query_terms"],
          "US014_QUERY_TERMS_INVALID")
    return bundle


def usul_research_section(bundle_path: Path, tafsir_db: Path,
                          reference: str, *,
                          tafsir_raw_by_record: dict | None = None,
                          tafsir_candidates_by_record: dict | None = None,
                          ) -> dict:
    """Recompute conservative matching and return the presentation section.

    The caller supplies digest-verified raw rows and candidates recomputed by
    the same pinned T0.1->T0.2->T0.2.3 pipeline (private CLI pattern). This
    function rebuilds the accepted Bab al-Amr catalog/graph from the pinned
    W1 files on every call. Metadata-only output.
    """
    bundle = load_usul_evidence(bundle_path)
    _need(tafsir_raw_by_record and tafsir_candidates_by_record,
          "US014_TAFSIR_CHAIN_INPUTS_REQUIRED")
    import engines.usul.pilots.waraqat_stage08 as s08
    graph = s08.replay_and_graph(
        Path(bundle["waraqat_primary_html"]),
        Path(bundle["waraqat_primary_export"]),
        Path(bundle["waraqat_primary_manifest"]),
        Path(bundle["waraqat_primary_section"]),
        Path(bundle["waraqat_secondary_html"]),
        Path(bundle["waraqat_secondary_section"]),
        json.loads(Path(__file__).resolve().parents[2].joinpath(
            "usul/pilots/data/waraqat-stage07-queries.json").read_text(encoding="utf-8")) if False else
        json.loads(Path("engines/usul/pilots/data/waraqat-stage07-queries.json").read_text(encoding="utf-8")),
        json.loads(Path("engines/usul/pilots/data/waraqat-stage08-research-pointers.json").read_text(encoding="utf-8")))
    _need(graph["graph_sha256"] == bundle["graph_sha256"],
          "US014_GRAPH_DIGEST_NOT_THE_ACCEPTED_ONE")
    from engines.usul.concept_rule_catalog import build_catalog
    catalog = build_catalog(graph, graph["graph_sha256"],
        json.loads(Path("engines/usul/pilots/data/waraqat-u02-catalog-candidates.json").read_text(encoding="utf-8")))
    _need(catalog["catalog_sha256"] == bundle["catalog_sha256"],
          "US014_CATALOG_DIGEST_NOT_THE_ACCEPTED_ONE")
    usul_raw = Path(bundle["usul_section_path"]).read_bytes()
    _need(hashlib.sha256(usul_raw).hexdigest() == bundle["usul_section_sha256"],
          "US014_SECTION_DIGEST_MISMATCH")
    links = []
    refused = {}
    for record_id, raw in tafsir_raw_by_record.items():
        for c in tafsir_candidates_by_record.get(record_id, []):
            try:
                passage = tafsir_candidates_by_record.get(
                    record_id + "::passage")
                links.append(match_candidate(
                    candidate=c, passage=passage, tafsir_raw_text=raw,
                    usul_catalog=catalog, usul_graph=graph,
                    usul_raw_text=usul_raw,
                    rule_candidate_id=bundle["usul_rule_candidate_id"],
                    research_pointer_id=bundle["usul_research_pointer_id"],
                    rule_query_terms=bundle["query_terms"],
                    candidacy_reason=bundle.get("candidacy_reason"),
                    candidacy_scope=bundle.get("candidacy_scope")))
            except Exception as exc:
                code = getattr(exc, "code", type(exc).__name__)
                refused[code] = refused.get(code, 0) + 1
    counts = match_summary(links)
    import hashlib as _h
    redacted_links = []
    for l in links:
        redacted_links.append({
            "link_id": l.get("link_id"),
            "link_status": l.get("link_status"),
            "match_method": l.get("match_method", "N/A_IN_UT012_RECORD"),
            "tafsir_candidate_id": l.get("tafsir_candidate_id"),
            "usul_rule_candidate_id": l.get("usul_rule_candidate_id"),
            "usul_section_sha256": l.get("usul_section_sha256"),
            "verification_status": l.get("verification_status"),
            "scholarly_verified": False,
        })
    return {
        "contract": CONTRACT, "version": VERSION,
        "section_title_ar": "القواعد الأصولية المرتبطة بالتفسير",
        "usul_rule_candidate_id": bundle["usul_rule_candidate_id"],
        "usul_research_pointer_id": bundle["usul_research_pointer_id"],
        "usul_work_id": bundle.get("usul_work_id", ""),
        "usul_source_id": bundle["usul_source_id"],
        "usul_section_sha256": bundle["usul_section_sha256"],
        "catalog_sha256": bundle["catalog_sha256"],
        "graph_sha256": bundle["graph_sha256"],
        "counts": counts,
        "links_redacted": redacted_links,
        "refusals": refused,
        "evidence_levels": list(EVIDENCE_LEVELS),
        "usul_link_level_cap": USUL_LINK_MAX_LEVEL,
        "level_note": ("lexical usul links are AUTOMATED_CANDIDATE level; "
                       "they never rise to TEXTUALLY_ATTRIBUTED or "
                       "SCHOLARLY_VERIFIED through this layer"),
        "tie_levels_explained": {
            "EXACT": "literal match at original offsets, digest-pinned",
            "FOLDED_CANDIDATE": "match after removing Arabic marks only; "
                                "no letter-equivalence or semantic claims"},
        "link_status_note": ("UNDETERMINED means insufficient lexical "
                            "evidence; it is not agreement, preference, "
                            "or rule application"),
        "scholarly_verified": False,
        "source_support_attested": False,
        "rule_application_verified": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "text_included": False,
        "p1_admitted": False,
        "rights_status": "legal_review_pending",
    }
