"""T0.2.1 + T0.2.2: structured interpretation records with source-grounded
extraction from T0.1 records.

Every record carries the exact original-text substring (evidence_span offsets
into the source record text), its SHA-256, and the original record digest.
No attribution without textual evidence; no invented edition metadata;
AI extraction is never scholarly verification. Original text is preserved
byte-for-byte; normalisation, if any, is stored separately.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

CONTRACT = "mubin-tafsir-t02-interpretation-record-v1"
VERSION = "tafsir-t02/0.1.0"
STATUS_AI_UNVERIFIED = "AI_EXTRACTED_UNVERIFIED"
STATUS_RULE_EXTRACTED_UNVERIFIED = "RULE_EXTRACTED_UNVERIFIED"
METHOD_RULE_SEGMENTER = "RULE_BASED_SEGMENTER"
_VERIFICATION_STATUSES = frozenset((STATUS_AI_UNVERIFIED, STATUS_RULE_EXTRACTED_UNVERIFIED))
_SHA256 = re.compile(r"[0-9a-f]{64}")
_REF = re.compile(r"^(?:[1-9][0-9]{0,2}:[1-9][0-9]{0,2})(?:-[1-9][0-9]{0,2}:[1-9][0-9]{0,2})?$")
# Sentence-final punctuation used for deterministic segmentation.
_SENTENCE_END = re.compile(r"[.\u06d4\u061f!]+")

REQUIRED_FIELDS = (
    "interpretation_id", "quran_reference", "work_id", "author_id",
    "source_record_id", "source_sha256", "evidence_sha256", "evidence_span",
    "interpretation_statement", "interpretation_type", "context_scope",
    "extraction_method", "verification_status", "edition", "volume", "page",
    "rights_status",
)


class TafsirT02Error(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _need(ok, code):
    if not ok:
        raise TafsirT02Error(code)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_record(record: dict, *, original_text: str) -> None:
    """Fail-closed structural + grounding validation of one record."""
    _need(type(record) is dict, "T02_RECORD_NOT_DICT")
    for field in REQUIRED_FIELDS:
        _need(field in record, f"T02_FIELD_MISSING_{field}")
    _need(_REF.fullmatch(str(record["quran_reference"])) is not None,
          "T02_REFERENCE_INVALID")
    _need(type(record["work_id"]) is str and record["work_id"], "T02_WORK_INVALID")
    _need(_SHA256.fullmatch(str(record["source_sha256"])) is not None,
          "T02_SOURCE_SHA_INVALID")
    _need(_SHA256.fullmatch(str(record["evidence_sha256"])) is not None,
          "T02_EVIDENCE_SHA_INVALID")
    span = record["evidence_span"]
    _need(type(span) is list and len(span) == 2
          and type(span[0]) is int and type(span[1]) is int
          and 0 <= span[0] < span[1] <= len(original_text),
          "T02_SPAN_INVALID")
    # Grounding: the cited span must exist byte-exact in the source text.
    snippet = original_text[span[0]:span[1]]
    _need(_sha(snippet.encode("utf-8")) == record["evidence_sha256"],
          "T02_EVIDENCE_NOT_GROUNDED")
    statement = record["interpretation_statement"]
    _need(type(statement) is str and 0 < len(statement) <= 4096,
          "T02_STATEMENT_INVALID")
    _need(statement in original_text, "T02_STATEMENT_NOT_IN_SOURCE")
    _need(record["verification_status"] in _VERIFICATION_STATUSES,
          "T02_STATUS_INVALID")
    _need(record["extraction_method"] in (METHOD_RULE_SEGMENTER, "AI_TOOL_EXTRACTION"),
          "T02_METHOD_INVALID")
    _need(record["rights_status"] == "legal_review_pending",
          "T02_RIGHTS_INVALID")
    _need(record["edition"] is None and record["volume"] is None
          and record["page"] is None,
          "T02_EDITION_METADATA_INVENTED")


def make_record(*, quran_reference: str, work_id: str, author_id,
                source_record_id: str, source_sha256: str,
                original_text: str, span: tuple[int, int],
                interpretation_type, context_scope: str,
                extraction_method: str = METHOD_RULE_SEGMENTER) -> dict:
    """Build one grounded interpretation record from an exact text span."""
    _need(type(original_text) is str and original_text, "T02_TEXT_EMPTY")
    _need(type(span) is tuple and len(span) == 2
          and type(span[0]) is int and type(span[1]) is int
          and 0 <= span[0] < span[1] <= len(original_text), "T02_SPAN_INVALID")
    statement = original_text[span[0]:span[1]]
    digest_source = source_record_id.encode("utf-8")
    interpretation_id = "interp:" + _sha(
        digest_source + b"|" + str(span[0]).encode() + b"|" + str(span[1]).encode()
        + b"|" + _sha(statement.encode("utf-8")).encode())[:40]
    record = {
        "contract": CONTRACT,
        "interpretation_id": interpretation_id,
        "quran_reference": quran_reference,
        "work_id": work_id,
        "author_id": author_id,
        "source_record_id": source_record_id,
        "source_sha256": source_sha256,
        "evidence_sha256": _sha(statement.encode("utf-8")),
        "evidence_span": [span[0], span[1]],
        "interpretation_statement": statement,
        "interpretation_type": interpretation_type,
        "context_scope": context_scope,
        "extraction_method": extraction_method,
        "verification_status": (STATUS_RULE_EXTRACTED_UNVERIFIED
                                if extraction_method == METHOD_RULE_SEGMENTER
                                else STATUS_AI_UNVERIFIED),
        "edition": None, "volume": None, "page": None,
        "rights_status": "legal_review_pending",
        "scholarly_verified": False,
        "textual_interpretation_assessed": False,
        "text_included": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }
    validate_record(record, original_text=original_text)
    return record


def segment_statements(original_text: str, *, min_len: int = 25,
                       max_len: int = 2000) -> list[tuple[int, int]]:
    """Deterministic sentence segmentation of a tafsir text.

    Returns non-overlapping (start, end) spans of sentence groups. Never
    rewrites text: spans index directly into the original string.
    """
    _need(type(original_text) is str and 0 < len(original_text) <= 200_000,
          "T02_TEXT_SIZE_INVALID")
    spans: list[tuple[int, int]] = []
    matches = list(_SENTENCE_END.finditer(original_text))
    pieces: list[tuple[int, int]] = []
    cursor = 0
    for m in matches:
        end = m.end()
        if end - cursor >= min_len:
            pieces.append((cursor, end))
            cursor = end
    if cursor < len(original_text):
        tail = original_text[cursor:]
        if len(tail.strip()) >= min_len:
            pieces.append((cursor, len(original_text)))
    for start, end in pieces:
        chunk = original_text[start:end]
        if len(chunk) <= max_len:
            stripped_left = len(chunk) - len(chunk.lstrip())
            s0, s1 = start + stripped_left, end
            while s1 > s0 and original_text[s1 - 1] in " \t":
                s1 -= 1
            if s1 - s0 >= min_len:
                spans.append((s0, s1))
    return spans


def extract_from_t01_record(t01_record: dict, *,
                            extraction_method: str = METHOD_RULE_SEGMENTER
                            ) -> list[dict]:
    """Extract grounded interpretation records from one T0.1 record dict.

    Requires the record's local text (field 'text') to be present; records
    with held-safe text (text null) are returned empty and must be fetched
    through T0.1's explicit local path by the operator.
    """
    _need(type(t01_record) is dict, "T01_RECORD_NOT_DICT")
    for field in ("evidence_id", "work_id", "imported_record_sha256",
                  "verse_locator"):
        _need(field in t01_record, f"T02_T01_FIELD_MISSING_{field}")
    text = t01_record.get("text")
    if not isinstance(text, str) or not text:
        return []
    author = t01_record.get("author_ar")
    author_id = author if isinstance(author, str) and author else None
    spans = segment_statements(text)
    records = []
    for span in spans:
        records.append(make_record(
            quran_reference=t01_record["verse_locator"],
            work_id=t01_record["work_id"],
            author_id=author_id,
            source_record_id=t01_record["evidence_id"],
            source_sha256=t01_record["imported_record_sha256"],
            original_text=text,
            span=span,
            interpretation_type=None,
            context_scope="VERSE_LOCAL_EXEGESIS",
            extraction_method=extraction_method))
    return records


def summarize(records: list[dict]) -> dict:
    """Safe summary: counts and ids only, never statement text."""
    _need(type(records) is list, "T02_RECORDS_NOT_LIST")
    for r in records:
        _need(type(r) is dict, "T02_RECORD_NOT_DICT")
    return {
        "contract": CONTRACT, "version": VERSION,
        "records_total": len(records),
        "by_work": {w: sum(1 for r in records if r.get("work_id") == w)
                    for w in sorted({r.get("work_id", "") for r in records})},
        "verification_statuses": {
            s: sum(1 for r in records if r.get("verification_status") == s)
            for s in sorted({r.get("verification_status", "") for r in records})},
        "interpretation_ids": [r.get("interpretation_id", "") for r in records],
        "scholarly_verified": False,
        "text_included": False,
        "publication_allowed": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "p1_admitted": False,
    }
