"""Q0.1e: pinned Tanzil-domain download with no automatic source authority.

The previously observed HTTPS file identity is frozen. Its raw bytes are never
normalized, redistributed, written or logged. Source identity and rights are
unverified despite receiving bytes from the official HTTPS domain.
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
from types import MappingProxyType
from typing import Callable

from engines.quran.q01.engine import _VERSE_COUNTS
from engines.quran.q01b.tanzil import MAX_RAW_BYTES, SourceIndex
from engines.quran.q01d.compare import parse_numbered_candidate, CandidateError
from qa.quran_official_probe import _fetch, OFFICIAL_URL, PRESET

PINNED_OFFICIAL_DOMAIN_SHA256 = "7f30c647331a61100ebf24a80507dc0fcdd9f2df97f1312b5b2dfcb982a7f326"
_SOURCE_ID = "tanzil-domain:uthmani-txt2:2026-10-18:unattested"
_NOTICE_ANCHOR = b"# PLEASE DO NOT REMOVE OR CHANGE THIS COPYRIGHT BLOCK"


class OfficialSourceError(ValueError):
    """Source differs from the recorded candidate or is structurally unsafe."""


def load_official_candidate(raw: bytes) -> SourceIndex:
    """Parse ONLY the exact previously-observed candidate bytes.

    The upstream origin of independently supplied bytes is NOT inferred from
    their digest. A verified digest is an integrity check, not publisher signing.
    """
    if (type(raw) is not bytes or not 1 <= len(raw) <= MAX_RAW_BYTES or
            sha256(raw).hexdigest() != PINNED_OFFICIAL_DOMAIN_SHA256):
        raise OfficialSourceError("pinned_tanzil_domain_bytes_mismatch")
    if _NOTICE_ANCHOR not in raw:
        raise OfficialSourceError("missing_verbatim_copyright_notice")
    try:
        verses = parse_numbered_candidate(raw)
    except (CandidateError, ValueError, UnicodeError, TypeError) as exc:
        raise OfficialSourceError("official_domain_candidate_format_invalid") from exc
    if len(verses) != 6236:
        raise OfficialSourceError("official_domain_candidate_incomplete")
    chapter_counts = Counter(s for s, _, _ in verses)
    if tuple(chapter_counts.get(s, 0) for s in range(1, 115)) != _VERSE_COUNTS:
        raise OfficialSourceError("official_domain_candidate_numbering_mismatch")
    manifest = {
        "source_kind": "tanzil_domain_unattested_export",
        "source_id": _SOURCE_ID,
        "source_url": OFFICIAL_URL,
        "source_preset": dict(PRESET),
        "raw_sha256": PINNED_OFFICIAL_DOMAIN_SHA256,
        "raw_byte_count": len(raw),
        "coverage": "complete_hafs_kufan",
        "reading": "hafs_an_asim_kufan",
        "rights_status": "requires_use_review",
        "authority_status": "unverified_tanzil_domain_response",
        "source_observation": "docs/research/QURAN-Q01E-DOMAIN-PROBE.md",
    }
    # Freeze nested preset too; callers cannot silently relabel source metadata.
    manifest["source_preset"] = MappingProxyType(dict(PRESET))
    return SourceIndex(MappingProxyType(manifest), verses,
                       PINNED_OFFICIAL_DOMAIN_SHA256)


def obtain_official_index(*, fetcher: Callable[[str], bytes] = _fetch) -> tuple[SourceIndex, bytes]:
    """Fetch one strict GET and return original bytes held in memory only."""
    if not callable(fetcher):
        raise OfficialSourceError("invalid_fetcher")
    try:
        raw = fetcher("GET")
    except (OSError, UnicodeError, ValueError, TypeError, OverflowError) as exc:
        raise OfficialSourceError("official_domain_https_unavailable") from exc
    index = load_official_candidate(raw)
    return index, raw
