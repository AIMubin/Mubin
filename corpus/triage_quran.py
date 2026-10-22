"""Conservative, NON-authoritative triage of differences between Quran witnesses.

Classification is diagnostic only. No script transformation changes either text,
and even a mark-stripped match is NOT a ruling of Quranic equivalence.
"""
import argparse
import hashlib
import json
import sqlite3
import unicodedata
from collections import Counter
from pathlib import Path

from corpus.compare_quran import witness
from corpus.verify_quran import EXPECTED_COUNTS

REFERENCE_SHA256 = "b9027e22eb7e69d326f1eb7467fed8b7bc1eccbe1a894887ed2b3feb4ef5fc90"


def sha_text(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def collapse_spaces(text):
    return " ".join(text.split())


def strip_combining(text):
    return "".join(char for char in text if not unicodedata.category(char).startswith("M"))


def classify(imported, reference):
    if imported == reference:
        return "EXACT"
    a, b = unicodedata.normalize("NFC", imported), unicodedata.normalize("NFC", reference)
    if a == b:
        return "UNICODE_CANONICAL_ONLY"
    a, b = collapse_spaces(a), collapse_spaces(b)
    if a == b:
        return "WHITESPACE_ONLY"
    a, b = strip_combining(a), strip_combining(b)
    if a == b:
        return "COMBINING_MARKS_ONLY_CANDIDATE"
    if a.replace("ـ", "") == b.replace("ـ", ""):
        return "TATWEEL_OR_MARKS_CANDIDATE"
    return "TEXTUAL_REVIEW_REQUIRED"


def read_verses(path):
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute("SELECT sura,aya,text FROM verses").fetchall()
    finally:
        conn.close()
    expected = {(s, a) for s, n in enumerate(EXPECTED_COUNTS, 1) for a in range(1, n + 1)}
    if len(rows) != len(expected) or {(s, a) for s, a, _ in rows} != expected:
        raise ValueError("Imported Quran verse set is invalid")
    if any(not isinstance(text, str) or not text.strip() for _, _, text in rows):
        raise ValueError("Imported Quran contains empty verses")
    return {(s, a): text for s, a, text in rows}


def triage(database, reference, expected_reference_sha256=REFERENCE_SHA256):
    from corpus.import_tafsircenter import sha
    original, reference_hash = witness(reference)
    if reference_hash.lower() != expected_reference_sha256.lower():
        raise ValueError(f"Reference hash mismatch: {reference_hash}")
    derived = read_verses(database)
    if set(original) != set(derived):
        raise ValueError("Independent witness verse keys do not match imported verse keys")
    counters = Counter()
    details = []
    for sura, aya in sorted(derived):
        left, right = derived[(sura, aya)], original[(sura, aya)]
        label = classify(left, right)
        counters[label] += 1
        if label != "EXACT":
            details.append({"verse_id": f"{sura}:{aya}", "class": label,
                            "imported_sha256": sha_text(left),
                            "reference_sha256": sha_text(right)})
    summary = {
        "status": "DIAGNOSTIC_ONLY_REQUIRES_SCHOLARLY_REVIEW",
        "canonical_quran_verified": False,
        "reference_sha256": reference_hash,
        "imported_db_sha256": sha(database),
        "verses_compared": len(derived),
        "class_counts": {name: counters[name] for name in (
            "EXACT", "UNICODE_CANONICAL_ONLY", "WHITESPACE_ONLY",
            "COMBINING_MARKS_ONLY_CANDIDATE", "TATWEEL_OR_MARKS_CANDIDATE",
            "TEXTUAL_REVIEW_REQUIRED")},
        "details_without_verse_text": details,
        "note": "Classifications are diagnostic. Stripping marks can conceal meaningful distinctions. No equivalence inferred."
    }
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--database", type=Path, default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--reference", type=Path, required=True)
    p.add_argument("--expected-reference-sha256", default=REFERENCE_SHA256)
    p.add_argument("--output", type=Path, default=Path("corpus-data/linked/quran-triage.json"))
    args = p.parse_args()
    result = triage(args.database, args.reference, args.expected_reference_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "details_without_verse_text"},
                     ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
