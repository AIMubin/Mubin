"""Diagnostic comparison of Quran witnesses with explicit first-verse basmala boundaries.

Do not infer Quranic equivalence from character normalization. Original strings
and bytes remain unchanged. This is NOT scholarly authentication.
"""
import argparse
from collections import Counter
from difflib import SequenceMatcher
import hashlib
import json
from pathlib import Path
import sqlite3
import unicodedata
from corpus.verify_quran import EXPECTED_COUNTS
from corpus.triage_quran import REFERENCE_SHA256


def file_sha256(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_witness(path, pinned_sha=REFERENCE_SHA256):
    if file_sha256(path).lower() != pinned_sha.lower():
        raise ValueError("Tanzil witness SHA-256 does not match pinned release")
    verses = {}
    for ln, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("|", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid witness line {ln}")
        sura, aya = int(parts[0]), int(parts[1])
        key = (sura, aya)
        if key in verses or not parts[2].strip():
            raise ValueError(f"Duplicate or blank witness at {key}")
        verses[key] = parts[2]
    expected = {(s, a) for s, n in enumerate(EXPECTED_COUNTS, 1) for a in range(1, n+1)}
    if set(verses) != expected:
        raise ValueError("Witness verse keys incomplete or out of range")
    return verses


def segment_first_verse(sura, aya, raw, basmala):
    """Return (verbatim verse substring, optional opening) for pinned Tanzil txt-2.

    112 surahs append opening basmala to ayah 1. Surahs 95 and 97
    have a distinct initial-beh shadda. Reject unknown layouts.
    """
    if aya != 1 or sura in (1, 9):
        return raw, None
    variant = basmala.replace("بِسْمِ", "بِّسْمِ", 1)
    if variant == basmala:
        raise ValueError("Unexpected base basmala format")
    for opening in (basmala, variant):
        prefix = opening + " "
        if raw.startswith(prefix):
            body = raw[len(prefix):]
            if not body:
                raise ValueError(f"Empty first ayah after opening: {sura}")
            return body, opening
    raise ValueError(f"Unrecognized opening basmala boundary in sura {sura}")


def markless(text):
    return "".join(ch for ch in unicodedata.normalize("NFC", text)
                   if not unicodedata.category(ch).startswith("M"))


def normalize_markless(text):
    return " ".join(markless(text).split())


def normalize_alef(text):
    return normalize_markless(text).translate(str.maketrans("ٱأإآ", "اااا"))


def normalize_extended(text):
    # Comparison-only; these operations MUST NOT be used to publish Quran text.
    return (normalize_alef(text).replace("ى", "ي").replace("ـ", "")
            .replace("ۥ", "").replace("ۦ", "").replace("۞", "").replace("۩", ""))


def classify(left, right):
    if left == right:
        return "EXACT"
    l, r = unicodedata.normalize("NFC", left), unicodedata.normalize("NFC", right)
    if l == r:
        return "UNICODE_NFC_ONLY"
    l, r = " ".join(l.split()), " ".join(r.split())
    if l == r:
        return "WHITESPACE_ONLY"
    if normalize_markless(l) == normalize_markless(r):
        return "MARKS_ONLY_CANDIDATE"
    if normalize_alef(l) == normalize_alef(r):
        return "ALEF_VARIANTS_CANDIDATE"
    if normalize_extended(l) == normalize_extended(r):
        return "ADDITIONAL_SCRIPT_VARIANTS_CANDIDATE"
    return "UNRESOLVED_SCRIPT_DIFFERENCE"


def analyze(dbpath, refpath, expected_sha=REFERENCE_SHA256):
    witness = read_witness(refpath, expected_sha)
    expected = set(witness)
    conn = sqlite3.connect(Path(dbpath).resolve().as_uri()+"?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        rows = conn.execute("SELECT sura,aya,text FROM verses").fetchall()
    finally:
        conn.close()
    imported = {(s,a):text for s,a,text in rows}
    if len(rows) != len(expected) or set(imported) != expected or any(
        not isinstance(t,str) or not t.strip() for t in imported.values()
    ):
        raise ValueError("Derived database has incomplete, duplicate or blank Quran rows")
    categories, openings, flags, profiles = Counter(), Counter(), Counter(), Counter()
    followup = []
    basmala = witness[1,1]
    for sura,aya in sorted(expected):
        original_row = witness[sura,aya]
        verse, opening = segment_first_verse(sura,aya,original_row,basmala)
        derived = imported[sura,aya]
        category = classify(derived,verse)
        categories[category] += 1
        if opening:
            openings["record_with_unnumbered_opening"] += 1
            if opening != basmala:
                openings["alternate_opening_diacritics"] += 1
        if "/" in derived:
            flags["verse_keys_with_slash"] += 1
            flags["total_slashes"] += derived.count("/")
        if normalize_markless(derived) == normalize_markless(verse):
            profiles["markless_exact"] += 1
        if normalize_alef(derived) == normalize_alef(verse):
            profiles["alef_candidate_exact"] += 1
        left,right = normalize_extended(derived), normalize_extended(verse)
        if left == right:
            profiles["extended_candidate_exact"] += 1
        ratio = SequenceMatcher(None,left,right,autojunk=False).ratio()
        followup.append({
            "verse_id":f"{sura}:{aya}", "category":category,
            "derived_slash":"/" in derived,
            "reference_opening_prefix":bool(opening),
            "candidate_similarity_ratio":round(ratio,5),
            "derived_sha256":hashlib.sha256(derived.encode()).hexdigest(),
            "verse_segment_sha256":hashlib.sha256(verse.encode()).hexdigest(),
        })
    followup.sort(key=lambda x:(x["candidate_similarity_ratio"],x["verse_id"]))
    return {
        "status":"DIAGNOSTIC_NOT_SCHOLARLY_AUTHENTICATED",
        "source_db_sha256":file_sha256(dbpath),
        "witness_sha256":file_sha256(refpath),
        "verse_count":len(imported),
        "first_verse_openings":dict(openings),
        "derived_format_flags":dict(flags),
        "categories_after_boundary_segmentation":dict(sorted(categories.items())),
        "cumulative_candidate_exact_matches":dict(profiles),
        "unresolved_verse_count":categories["UNRESOLVED_SCRIPT_DIFFERENCE"],
        "lowest_similarity_cases":followup[:40],
        "note":"Source bytes are unchanged; basmala segments are literal substrings. Normalized candidate matching does NOT establish Quranic equivalence.",
        "canonical_quran_verified":False,
        "scholarly_verified":False,
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--database",type=Path,default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--reference",type=Path,required=True)
    p.add_argument("--expected-reference-sha256",default=REFERENCE_SHA256)
    p.add_argument("--report",type=Path,default=Path("corpus-data/linked/quran-witness-analysis.json"))
    a=p.parse_args()
    result=analyze(a.database,a.reference,a.expected_reference_sha256)
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in result.items() if k!="lowest_similarity_cases"},ensure_ascii=False,indent=2))


if __name__=="__main__":
    main()
