"""UT-01.4: optional, loopback-only redacted Usul–Tafsir research view.

An independently pinned W1/W2 private source replay is required; no raw
Tafsir or Usul text and no private filesystem paths are returned over HTTP.
UT-01.3 metadata envelopes keep their UT-01.2 links intact.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from engines.tafsir.t03 import _LEVELS as T03_EVIDENCE_LEVELS
from engines.usul.concept_rule_catalog import build_catalog
from engines.usul.ut012 import (
    TRUSTED_CATALOG_SHA256, TRUSTED_GRAPH_SHA256, UsulTafsirLinkError,
)
from engines.usul.ut013 import match_candidate, summarize as match_summary

CONTRACT = "mubin-usul-tafsir-presentation-v1"
VERSION = "usul-presentation/0.1.1"
EVIDENCE_LEVELS = tuple(T03_EVIDENCE_LEVELS)
USUL_LINK_MAX_LEVEL = "AUTOMATED_CANDIDATE"

_BUNDLE_REQUIRED = frozenset((
    "usul_rule_candidate_id", "usul_research_pointer_id",
    "catalog_sha256", "graph_sha256", "usul_source_id",
    "usul_section_path", "usul_section_sha256", "query_terms",
    "waraqat_primary_html", "waraqat_primary_export",
    "waraqat_primary_manifest", "waraqat_primary_section",
    "waraqat_secondary_html", "waraqat_secondary_section",
    "usul_work_id",
))
_SOURCE_FIELDS = (
    "usul_section_path", "waraqat_primary_html", "waraqat_primary_export",
    "waraqat_primary_manifest", "waraqat_primary_section",
    "waraqat_secondary_html", "waraqat_secondary_section",
)
_DIGEST = re.compile(r"^[a-f0-9]{64}$")
_ID = re.compile(r"^[a-z][a-z0-9_.:-]{2,127}$")
_MAX_LINKS = 4096
_DATA = Path(__file__).resolve().parent / "pilots" / "data"


class UsulPresentationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise UsulPresentationError(code)


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _no_duplicates(items):
    result = {}
    for key, value in items:
        if key in result:
            raise UsulPresentationError("US014_DUPLICATE_BUNDLE_FIELD")
        result[key] = value
    return result


def load_usul_evidence(path: Path) -> dict:
    """Fail closed on any unrecognized field or unsafe local source path."""
    _need(type(path) is Path and path.is_file() and not path.is_symlink(),
          "US014_BUNDLE_UNAVAILABLE")
    _need(0 < path.stat().st_size <= 65536,
          "US014_BUNDLE_TOO_LARGE")
    bundle = json.loads(path.read_bytes().decode("utf-8", "strict"),
                        object_pairs_hook=_no_duplicates)
    _need(type(bundle) is dict and set(bundle) == _BUNDLE_REQUIRED,
          "US014_BUNDLE_FIELDS_INVALID")
    _need(all(type(bundle[field]) is str
              and 0 < len(bundle[field]) <= 1024
              for field in _BUNDLE_REQUIRED - {"query_terms"}),
          "US014_BUNDLE_STRING_INVALID")
    _need(bundle["graph_sha256"] == TRUSTED_GRAPH_SHA256
          and bundle["catalog_sha256"] == TRUSTED_CATALOG_SHA256
          and _DIGEST.fullmatch(bundle["usul_section_sha256"]) is not None,
          "US014_EXTERNAL_SOURCE_PINS_INVALID")
    _need(all(_ID.fullmatch(bundle[k]) is not None for k in (
        "usul_rule_candidate_id", "usul_research_pointer_id",
        "usul_source_id", "usul_work_id")),
        "US014_SOURCE_IDENTIFIERS_INVALID")
    terms = bundle["query_terms"]
    _need(type(terms) is list and len(terms) == 1
          and type(terms[0]) is str
          and 1 <= len(terms[0]) <= 128 and bool(terms[0].strip()),
          "US014_QUERY_TERMS_INVALID")
    for key in _SOURCE_FIELDS:
        p = Path(bundle[key])
        _need(p.is_file() and not p.is_symlink()
              and 0 < p.stat().st_size <= 10_000_000,
              "US014_PRIVATE_SOURCE_UNAVAILABLE")
    return bundle


def usul_research_section(bundle_path: Path, *,
                          tafsir_items: list[dict]) -> dict:
    """Recheck pinned sources and display *every* original Tafsir candidate.

    Items contain the original raw Tafsir row, an independently verified
    T0.2 passage and its T0.2.3 candidate; never send these over HTTP.
    The underlying Stage08 W1/W2 replay is deliberately rerun on each
    invocation, with no network acquisition.
    """
    bundle = load_usul_evidence(bundle_path)
    _need(type(tafsir_items) is list and len(tafsir_items) <= _MAX_LINKS,
          "US014_CANDIDATE_BOUNDS_INVALID")
    from engines.usul.pilots import waraqat_stage08 as s08
    graph = s08.replay_and_graph(
        *(Path(bundle[key]) for key in (
            "waraqat_primary_html", "waraqat_primary_export",
            "waraqat_primary_manifest", "waraqat_primary_section",
            "waraqat_secondary_html", "waraqat_secondary_section")),
        _read_json(_DATA / "waraqat-stage07-queries.json"),
        _read_json(_DATA / "waraqat-stage08-research-pointers.json"))
    _need(graph.get("graph_sha256") == TRUSTED_GRAPH_SHA256
          and graph.get("graph_sha256") == bundle["graph_sha256"],
          "US014_GRAPH_PIN_MISMATCH")
    catalog = build_catalog(
        graph, TRUSTED_GRAPH_SHA256,
        _read_json(_DATA / "waraqat-u02-catalog-candidates.json"))
    _need(catalog["catalog_sha256"] == TRUSTED_CATALOG_SHA256
          and catalog["catalog_sha256"] == bundle["catalog_sha256"],
          "US014_CATALOG_PIN_MISMATCH")
    raw = Path(bundle["usul_section_path"]).read_bytes()
    _need(hashlib.sha256(raw).hexdigest() == bundle["usul_section_sha256"],
          "US014_USUL_SECTION_BYTES_CHANGED")
    sections = [n for n in graph["nodes"]
                if n.get("kind") == "PINNED_SECTION"
                and n.get("source_id") == bundle["usul_source_id"]
                and n.get("section_sha256") == bundle["usul_section_sha256"]]
    _need(len(sections) == 1 and sections[0].get("byte_length") == len(raw),
          "US014_SECTION_NOT_IN_REPLAY_GRAPH")
    links = []
    for item in tafsir_items:
        _need(type(item) is dict and set(item) == {
            "candidate", "passage", "original_raw_text"},
            "US014_TAFSIR_ITEM_INVALID")
        # Any failure of a source chain rejects the *entire* section;
        # never display a partial result as if all candidates were audited.
        link = match_candidate(
            candidate=item["candidate"], passage=item["passage"],
            tafsir_raw_text=item["original_raw_text"],
            usul_catalog=catalog, usul_graph=graph, usul_raw_text=raw,
            rule_candidate_id=bundle["usul_rule_candidate_id"],
            research_pointer_id=bundle["usul_research_pointer_id"],
            rule_query_terms=bundle["query_terms"],
            candidacy_reason=None, candidacy_scope=None)
        links.append(link)
    summary = match_summary(links)
    redacted = []
    for envelope in links:
        stored = envelope["link"]
        evidence = envelope["matching"]
        redacted.append({
            "link_id": stored["link_id"],
            "link_status": stored["link_status"],
            "tafsir_candidate_id": stored["tafsir_candidate_id"],
            "tafsir_passage_id": stored["tafsir_passage_id"],
            "tafsir_work_id": stored["tafsir_work_id"],
            "usul_rule_candidate_id": stored["usul_rule_candidate_id"],
            "usul_research_pointer_id": stored["usul_research_pointer_id"],
            "verification_status": stored["verification_status"],
            "link_method": stored["link_method"],
            "tie_level": evidence["tie_level"],
            "tafsir_tie_span": evidence["tafsir_raw_source_span"],
            "tafsir_tie_sha256": evidence["tafsir_tie"]["digest"],
            "usul_tie_span": evidence["usul_section_relative_byte_span"],
            "usul_tie_sha256": evidence["usul_tie_utf8"]["digest"],
            "tafsir_span_unit": evidence["tafsir_span_unit"],
            "usul_span_unit": evidence["usul_span_unit"],
            "qarinah_status": envelope["qarinah"]["status"],
            "evidence_level": USUL_LINK_MAX_LEVEL,
            "scholarly_verified": False,
            "rule_application_verified": False,
            "text_included": False,
        })
    return {
        "contract": CONTRACT, "version": VERSION,
        "section_title_ar": "القواعد الأصولية المرتبطة بالتفسير",
        "usul_rule_candidate_id": bundle["usul_rule_candidate_id"],
        "usul_research_pointer_id": bundle["usul_research_pointer_id"],
        "usul_work_id": bundle["usul_work_id"],
        "usul_source_id": bundle["usul_source_id"],
        "usul_section_sha256": bundle["usul_section_sha256"],
        "catalog_sha256": catalog["catalog_sha256"],
        "graph_sha256": graph["graph_sha256"],
        "counts": summary, "links_redacted": redacted,
        "evidence_levels": list(EVIDENCE_LEVELS),
        "usul_link_level_cap": USUL_LINK_MAX_LEVEL,
        "tie_levels_explained": {
            "EXACT": "literal lexical observation; not a rule application",
            "FOLDED_CANDIDATE": "Stage07 mark-only folding; not semantic equivalence",
            "NONE": "no source-linked lexical tie in bounded scope",
        },
        "link_status_note": (
            "UNDETERMINED is not evidence for agreement, disagreement, "
            "rule applicability or absence of a qarinah"),
        "scholarly_verified": False,
        "source_support_attested": False,
        "rule_application_verified": False,
        "cross_source_semantic_equivalence_verified": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "text_included": False,
        "p1_admitted": False,
        "rights_status": "legal_review_pending",
    }
