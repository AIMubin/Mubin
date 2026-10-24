"""Q0.1d: bounded *unverified* candidate comparison against Q0.1b pinned bytes.

This module never downloads, writes, edits, or authenticates publisher Quran text.
Passing byte equality only proves equality to the pinned local mirror, not Tanzil.
"""
from __future__ import annotations
from hashlib import sha256
import re
from typing import Any

from engines.quran.q01.engine import _VERSE_COUNTS, _safe_text
from engines.quran.q01b.tanzil import MAX_RAW_BYTES, RawSourceError, load_raw

_ROW = re.compile(r'([1-9][0-9]{0,2})\|([1-9][0-9]{0,2})\|(.+)')
_MAX_FOOTER_LINES = 45
_MAX_BLANK_LINES = 3

class CandidateError(ValueError):
    """A candidate cannot safely be compared with the pinned mirror."""


def parse_numbered_candidate(raw: bytes) -> tuple[tuple[int, int, str], ...]:
    """Parse strict UTF-8 LF `surah|ayah|verbatim text`; never normalize text.

    Accept an optional trailing comment/copyright block. Reject any missing,
    reordered, duplicate, or out-of-range numbered rows at comparison time.
    """
    if type(raw) is not bytes or not (1 <= len(raw) <= MAX_RAW_BYTES) or raw.startswith(b'\xef\xbb\xbf'):
        raise CandidateError('unsafe_candidate_size_or_bom')
    try:
        content = raw.decode('utf-8', 'strict')
    except UnicodeError as exc:
        raise CandidateError('candidate_invalid_utf8') from exc
    if '\r' in content or not content.endswith('\n'):
        raise CandidateError('candidate_requires_lf_and_final_newline')

    rows: list[tuple[int, int, str]] = []
    previous = (0, 0)
    seen_footer = False
    blanks = 0
    footer_lines = 0
    for line in content.split('\n')[:-1]:
        found = _ROW.fullmatch(line) if not seen_footer else None
        if found:
            s, a = int(found[1]), int(found[2])
            if not (1 <= s <= 114 and 1 <= a <= _VERSE_COUNTS[s-1]):
                raise CandidateError('invalid_verse_number')
            if (s, a) <= previous:
                raise CandidateError('candidate_reordered_or_duplicate')
            if not _safe_text(found[3], maxchars=4000, arabic=True):
                raise CandidateError('invalid_verse_text')
            rows.append((s, a, found[3]))
            if len(rows) > 6236:
                raise CandidateError('too_many_verses')
            previous = (s, a)
        elif not line:
            if not rows:
                raise CandidateError('unexpected_blank_before_verses')
            seen_footer = True
            blanks += 1
            if blanks > _MAX_BLANK_LINES:
                raise CandidateError('too_many_footer_blanks')
        elif line.startswith('#') and rows:
            seen_footer = True
            footer_lines += 1
            if footer_lines > _MAX_FOOTER_LINES or len(line) > 512:
                raise CandidateError('footer_too_large')
            if any(ord(ch) < 0x20 or 0xD800 <= ord(ch) <= 0xDFFF for ch in line):
                raise CandidateError('unsafe_footer')
        else:
            raise CandidateError('malformed_verse_or_postverse_payload')
    if not rows:
        raise CandidateError('no_verse_records')
    return tuple(rows)


def compare_raw(mirror_manifest: bytes, mirror_raw: bytes,
                candidate_raw: bytes, *, limit_refs: int = 20) -> dict[str, Any]:
    """Compare exact bytes/coordinates; refuse publisher or rights promotion.

    The candidate's `source` provenance is ALWAYS unverified operator input,
    regardless of its content, apparent footer, or SHA equality with the mirror.
    """
    if type(limit_refs) is not int or not (1 <= limit_refs <= 100):
        raise CandidateError('invalid_difference_report_limit')
    if type(mirror_manifest) is not bytes or type(mirror_raw) is not bytes or type(candidate_raw) is not bytes:
        raise CandidateError('inputs_must_be_raw_bytes')
    try:
        base = load_raw(mirror_manifest, mirror_raw)
    except (RawSourceError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        raise CandidateError('pinned_mirror_unusable') from exc
    candidate = parse_numbered_candidate(candidate_raw)
    original_keys = tuple((s, a) for s, a, _ in base.verses)
    candidate_keys = tuple((s, a) for s, a, _ in candidate)
    if original_keys != candidate_keys:
        raise CandidateError('candidate_numbering_does_not_match_baseline')
    different = [f'{s}:{a}' for (s, a, txt), (_, _, other) in zip(base.verses, candidate)
                 if txt != other]
    byte_equal = mirror_raw == candidate_raw
    content_equal = not different
    kind = ('byte_identical' if byte_equal else
            'verse_equal_bytes_different' if content_equal else 'verse_text_differs')
    return {
        'comparison': kind, 'byte_equal': byte_equal,
        'verse_text_equal': content_equal,
        'mirror_verse_count': len(base.verses),
        'candidate_verse_count': len(candidate),
        'mirror_sha256': base.raw_sha256,
        'candidate_sha256': sha256(candidate_raw).hexdigest(),
        'differing_verse_count': len(different),
        'differing_refs': different[:limit_refs],
        'refs_truncated': len(different) > limit_refs,
        'mirror_source_id': base.manifest['source_id'],
        'candidate_provenance': 'operator_supplied_unverified',
        'source_authenticated': False,
        'official_candidate_attested': False,
        'candidate_publisher_provenance_verified': False,
        'rights_verified': False,
        'eligible_for_religious_ruling': False,
        'source_text_modified': False,
        'note': 'Comparison with an unverified candidate is not official Tanzil authentication; preset and publisher custody require external evidence.',
    }
