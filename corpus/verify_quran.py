#!/usr/bin/env python3
"""Structural gate for a Tanzil-style Quran: lines 'sura|ayah|text'.

This is a *structural* check, NOT authentication of sacred text.
Requires a separately inspected original file, its version and SHA-256.
"""
import argparse
import hashlib
import json
from pathlib import Path

EXPECTED_COUNTS = (
  7,286,200,176,120,165,206,75,129,109,123,111,43,52,99,128,111,110,
  98,135,112,78,118,64,77,227,93,88,69,60,34,30,73,54,45,83,182,
  88,75,85,54,53,89,59,37,35,38,29,18,45,60,49,62,55,78,96,29,22,
  24,13,14,11,11,18,12,12,30,52,52,44,28,28,20,56,40,31,50,40,46,
  42,29,19,36,25,22,17,19,26,30,20,15,21,11,8,8,19,5,8,8,11,11,
  8,3,9,5,4,7,3,6,3,5,4,5,6,
)

def verify(path: Path, expected_sha256: str | None = None) -> dict:
    raw = path.read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    errors = []
    if expected_sha256 is None:
        errors.append("Missing independently supplied expected SHA-256; cannot establish release identity")
    elif expected_sha256.lower() != digest:
        errors.append("SHA-256 does not match the independently supplied digest")
    try:
        content = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return {"passed": False, "sha256": digest, "errors": errors + ["Invalid UTF-8"]}
    if content.startswith("\ufeff"):
        errors.append("Unexpected BOM")
    if "\ufffd" in content:
        errors.append("Unicode replacement character present")
    if len(EXPECTED_COUNTS) != 114 or sum(EXPECTED_COUNTS) != 6236:
        raise RuntimeError("Internal reference counts invalid")
    verses = []
    for number, line in enumerate(content.splitlines(), start=1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        fields = line.split("|", 2)
        if len(fields) != 3:
            errors.append(f"Line {number}: expected sura|ayah|text")
            continue
        s, a, txt = fields
        try:
            sura, ayah = int(s), int(a)
        except ValueError:
            errors.append(f"Line {number}: nonnumeric verse key")
            continue
        if not s.isascii() or not a.isascii() or not s.isdecimal() or not a.isdecimal():
            errors.append(f"Line {number}: invalid numeric key notation")
        if not txt or not txt.strip() or txt != txt.strip():
            errors.append(f"Line {number}: empty or padded verse text")
        verses.append((sura, ayah))
    target = [(s, a) for s, n in enumerate(EXPECTED_COUNTS, 1) for a in range(1, n + 1)]
    if len(verses) != len(target):
        errors.append(f"Expected 6236 verses, got {len(verses)}")
    mismatches = [(i + 1, seen, expected) for i, (seen, expected) in
                  enumerate(zip(verses, target)) if seen != expected]
    if mismatches:
        i, seen, expected = mismatches[0]
        errors.append(f"Verse order/key mismatch at entry {i}: {seen} vs {expected}")
    return {
      "passed": not errors,
      "status": "STRUCTURALLY_VALID" if not errors else "REJECTED",
      "canonical_authentication": False,
      "sha256": digest,
      "verse_count": len(verses),
      "surah_count_expected": 114,
      "errors": errors[:30],
    }

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("file", type=Path)
    p.add_argument("--expected-sha256", required=True,
                   help="Digest obtained independently from a trusted release record")
    args = p.parse_args()
    result = verify(args.file, args.expected_sha256)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["passed"] else 1)

if __name__ == "__main__":
    main()
