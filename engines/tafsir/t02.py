"""Tafsir T0.2: deterministic RAW-source passage candidates (not opinions).

T0.1 metadata and the pinned Q0.3 database provide source provenance.
The only acceptable grounding basis is the raw, verbatim imported text,
not T0.1's HTML-stripped display_text. Unicode-codepoint offsets refer
to that raw text; hashing always uses exact UTF-8 bytes.
No AI analysis, semantic conclusion, edition attestation or publication.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any

from functools import lru_cache
from engines.quran.tafsir.catalog import _reference, load_catalog, CatalogError

CONTRACT = "mubin-tafsir-t02-interpretation-record-v1"
VERSION = "tafsir-t02/0.1.0"
STATUS_RULE_EXTRACTED_UNVERIFIED = "RULE_EXTRACTED_UNVERIFIED"
METHOD_RULE_SEGMENTER = "RULE_BASED_SEGMENTER"
CONTEXT = "UNCLASSIFIED_SOURCE_PASSAGE"
SPAN_UNIT = "UNICODE_CODEPOINT_OFFSETS_IN_IMPORTED_RAW_TEXT"
_SHA256 = re.compile(r"[0-9a-f]{64}")
_SENTENCE_END = re.compile(r"[.\u06d4\u061f!]+")
_FALSE_FLAGS = (
    "scholarly_verified", "textual_interpretation_assessed",
    "publication_allowed", "juristic_inference_allowed",
    "public_fatwa_authorized", "p1_admitted",
)
_FIELDS = frozenset((
    "contract", "interpretation_id", "quran_reference", "work_id",
    "author_id", "source_record_id", "source_sha256", "evidence_sha256",
    "evidence_span", "evidence_span_unit", "interpretation_statement",
    "interpretation_type", "context_scope", "extraction_method",
    "verification_status", "edition", "volume", "page", "rights_status",
    "candidate_kind",
) + _FALSE_FLAGS)


class TafsirT02Error(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok: bool, code: str):
    if not ok:
        raise TafsirT02Error(code)


def _sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _id(source_id: str, span: tuple[int, int], evidence_sha: str) -> str:
    raw = (source_id + "|" + str(span[0]) + "|" + str(span[1])
           + "|" + evidence_sha).encode("utf-8")
    return "interp:" + _sha(raw)[:40]


@lru_cache(maxsize=1)
def _catalog_authors() -> dict[str, str | None]:
    """Candidate bibliographic names only; not edition/authorship attestation."""
    try:
        return {item["id"]: item["author_ar"] for item in load_catalog()["sources"]}
    except CatalogError as exc:
        raise TafsirT02Error("T02_CATALOG_UNAVAILABLE") from exc


def validate_record(record: dict, *, original_text: str) -> None:
    """Validate the *whole* record against the exact imported raw string.

    A syntactically valid citation without the original bytes cannot pass.
    This proves byte linkage, not scholarly/semantic accuracy.
    """
    _need(type(record) is dict and set(record) == _FIELDS,
          "T02_RECORD_SHAPE_INVALID")
    _need(type(original_text) is str and bool(original_text),
          "T02_RAW_SOURCE_MISSING")
    reference = record["quran_reference"]
    try:
        _reference(reference)
    except CatalogError as exc:
        raise TafsirT02Error("T02_REFERENCE_INVALID") from exc
    work = record["work_id"]
    source_sha = record["source_sha256"]
    _need(type(work) is str and work in _catalog_authors(),
          "T02_WORK_INVALID")
    _need(type(source_sha) is str and _SHA256.fullmatch(source_sha) is not None,
          "T02_SOURCE_SHA_INVALID")
    _need(_sha(original_text.encode("utf-8")) == source_sha,
          "T02_SOURCE_BYTES_MISMATCH")
    _need(record["source_record_id"] == f"tafsir:{work}:{reference}:{source_sha}",
          "T02_SOURCE_IDENTITY_MISMATCH")
    _need(record["author_id"] == _catalog_authors()[work],
          "T02_AUTHOR_MISMATCH")
    span = record["evidence_span"]
    _need(type(span) is list and len(span) == 2
          and all(type(n) is int for n in span)
          and 0 <= span[0] < span[1] <= len(original_text),
          "T02_SPAN_INVALID")
    snippet = original_text[span[0]:span[1]]
    _need(record["evidence_span_unit"] == SPAN_UNIT,
          "T02_SPAN_UNIT_INVALID")
    _need(record["interpretation_statement"] == snippet
          and 0 < len(snippet) <= 2000,
          "T02_STATEMENT_NOT_EXACT_SPAN")
    evidence_sha = _sha(snippet.encode("utf-8"))
    _need(record["evidence_sha256"] == evidence_sha,
          "T02_EVIDENCE_NOT_GROUNDED")
    _need(record["interpretation_id"] ==
          _id(record["source_record_id"], (span[0], span[1]), evidence_sha),
          "T02_INTERPRETATION_ID_INVALID")
    _need(record["interpretation_type"] is None
          and record["context_scope"] == CONTEXT
          and record["candidate_kind"] == "UNCLASSIFIED_TEXT_SEGMENT",
          "T02_SEMANTIC_PROMOTION_FORBIDDEN")
    _need(record["extraction_method"] == METHOD_RULE_SEGMENTER
          and record["verification_status"] == STATUS_RULE_EXTRACTED_UNVERIFIED,
          "T02_METHOD_STATUS_INVALID")
    _need(record["rights_status"] == "legal_review_pending"
          and record["edition"] is None
          and record["volume"] is None and record["page"] is None,
          "T02_EDITION_OR_RIGHTS_PROMOTION")
    _need(record["contract"] == CONTRACT, "T02_CONTRACT_INVALID")
    _need(all(record[flag] is False for flag in _FALSE_FLAGS),
          "T02_AUTHORITY_PROMOTION_FORBIDDEN")


def make_record(*, quran_reference: str, work_id: str, author_id,
                source_record_id: str, source_sha256: str,
                original_text: str, span: tuple[int, int],
                interpretation_type=None, context_scope: str = CONTEXT,
                extraction_method: str = METHOD_RULE_SEGMENTER) -> dict:
    """Build a candidate passage, preserving exact raw-source provenance."""
    _need(type(original_text) is str and bool(original_text),
          "T02_RAW_SOURCE_MISSING")
    _need(type(span) is tuple and len(span) == 2
          and all(type(n) is int for n in span)
          and 0 <= span[0] < span[1] <= len(original_text),
          "T02_SPAN_INVALID")
    statement = original_text[span[0]:span[1]]
    evidence_sha = _sha(statement.encode("utf-8"))
    record = {
        "contract": CONTRACT,
        "interpretation_id": _id(source_record_id, span, evidence_sha),
        "quran_reference": quran_reference,
        "work_id": work_id,
        "author_id": author_id,
        "source_record_id": source_record_id,
        "source_sha256": source_sha256,
        "evidence_sha256": evidence_sha,
        "evidence_span": [span[0], span[1]],
        "evidence_span_unit": SPAN_UNIT,
        "interpretation_statement": statement,
        "interpretation_type": interpretation_type,
        "context_scope": context_scope,
        "candidate_kind": "UNCLASSIFIED_TEXT_SEGMENT",
        "extraction_method": extraction_method,
        "verification_status": STATUS_RULE_EXTRACTED_UNVERIFIED,
        "edition": None, "volume": None, "page": None,
        "rights_status": "legal_review_pending",
        "scholarly_verified": False,
        "textual_interpretation_assessed": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }
    validate_record(record, original_text=original_text)
    return record


def segment_statements(original_text: str, *, min_len: int = 25,
                       max_len: int = 2000) -> list[tuple[int, int]]:
    """Deterministic candidate segments; not a semantic opinion detector.

    Unsplit long passages and short tails may be omitted, never silently
    reclassified as scholarly statements.
    """
    _need(type(original_text) is str and 0 < len(original_text) <= 200_000,
          "T02_TEXT_SIZE_INVALID")
    _need(type(min_len) is int and 1 <= min_len <= 2000 and
          type(max_len) is int and min_len <= max_len <= 2000,
          "T02_SEGMENT_LIMITS_INVALID")
    matches = list(_SENTENCE_END.finditer(original_text))
    pieces: list[tuple[int, int]] = []
    cursor = 0
    for match in matches:
        end = match.end()
        if end - cursor >= min_len:
            pieces.append((cursor, end))
            cursor = end
    if cursor < len(original_text) and len(original_text[cursor:].strip()) >= min_len:
        pieces.append((cursor, len(original_text)))
    spans = []
    for start, end in pieces:
        if end-start > max_len:
            continue
        chunk = original_text[start:end]
        start += len(chunk) - len(chunk.lstrip())
        while end > start and original_text[end - 1] in " \t\r\n":
            end -= 1
        if end - start >= min_len:
            spans.append((start, end))
    return spans


def extract_from_t01_record(t01_record: dict) -> list[dict]:
    """Requires verified raw_original_text inserted by the private CLI.

    T0.1's text is only sanitized *display text*; it is not a raw hash
    witness. No raw original => no extracted source-grounded claims.
    """
    _need(type(t01_record) is dict, "T02_T01_RECORD_NOT_DICT")
    for field in ("evidence_id", "work_id", "imported_record_sha256",
                  "verse_locator", "text", "raw_original_text"):
        _need(field in t01_record, "T02_T01_FIELD_MISSING")
    if t01_record["text"] is None:  # T0.1 editorial hold / markup-only
        return []
    raw_text = t01_record["raw_original_text"]
    _need(type(raw_text) is str and bool(raw_text), "T02_RAW_SOURCE_MISSING")
    digest = _sha(raw_text.encode("utf-8"))
    _need(digest == t01_record["imported_record_sha256"],
          "T02_SOURCE_BYTES_MISMATCH")
    _need(t01_record["evidence_id"] == (
        f"tafsir:{t01_record['work_id']}:"
        f"{t01_record['verse_locator']}:{digest}"),
        "T02_T01_SOURCE_IDENTITY_MISMATCH")
    author = t01_record.get("author_ar")
    if author is not None:
        _need(type(author) is str and bool(author), "T02_AUTHOR_INVALID")
    return [
        make_record(quran_reference=t01_record["verse_locator"],
                    work_id=t01_record["work_id"], author_id=author,
                    source_record_id=t01_record["evidence_id"],
                    source_sha256=digest, original_text=raw_text, span=span)
        for span in segment_statements(raw_text)
    ]


def summarize(records: list[dict]) -> dict:
    """No protected text or exact spans in shared summaries."""
    _need(type(records) is list
          and all(type(row) is dict for row in records),
          "T02_RECORDS_INVALID")
    return {
        "contract": CONTRACT,
        "version": VERSION,
        "records_total": len(records),
        "count_semantics": "DETERMINISTIC_TEXT_SEGMENTS_NOT_DISTINCT_EXEGETICAL_OPINIONS",
        "coverage": "PARTIAL_NONEXHAUSTIVE_SEGMENTATION",
        "by_work": {work: sum(1 for r in records if r["work_id"] == work)
                    for work in sorted({r["work_id"] for r in records})},
        "verification_statuses": {
            status: sum(1 for r in records if r["verification_status"] == status)
            for status in sorted({r["verification_status"] for r in records})
        },
        "interpretation_ids": [row["interpretation_id"] for row in records],
        "scholarly_verified": False,
        "text_included": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }
