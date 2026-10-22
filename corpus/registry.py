"""Reference registry validator for Quran editions, mushaf pages and tafsir references.

Validates cross-references and provenance; does not authenticate text or scholarship.
All reference values are string IDs, not surrogates for verified content.
"""
import json
import re
from pathlib import Path

SHA256 = re.compile(r"^[0-9a-f]{64}$")
STATES = {"staged", "structurally_checked", "source_verified", "scholarly_verified"}
RIGHTS = {"unknown", "restricted", "internal_only", "redistribution_permitted"}
KIND = {"quran", "mushaf", "tafsir"}

def validate_registry(data):
    errors = []
    if not isinstance(data, dict) or not isinstance(data.get("records"), list):
        return ["registry must be an object containing records array"]
    records = data["records"]
    seen = set()
    indexed = {}
    for idx, record in enumerate(records):
        p = f"records[{idx}]"
        if not isinstance(record, dict):
            errors.append(f"{p}: must be object")
            continue
        rid = record.get("id")
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", rid):
            errors.append(f"{p}: invalid id")
            continue
        if rid in seen:
            errors.append(f"{p}: duplicate id {rid}")
        seen.add(rid)
        indexed[rid] = record
        kind = record.get("kind")
        if kind not in KIND:
            errors.append(f"{p}: unknown kind")
        if record.get("verification") not in STATES:
            errors.append(f"{p}: invalid verification state")
        if record.get("rights") not in RIGHTS:
            errors.append(f"{p}: invalid rights state")
        if not isinstance(record.get("source_url"), str) or not record["source_url"].startswith("https://"):
            errors.append(f"{p}: valid https source_url required")
        if not isinstance(record.get("edition"), str) or not record["edition"].strip():
            errors.append(f"{p}: edition required")
        if not isinstance(record.get("sha256"), str) or not SHA256.fullmatch(record["sha256"]):
            errors.append(f"{p}: immutable SHA-256 required")
        if kind == "quran":
            if not record.get("riwayah") or not record.get("verse_numbering"):
                errors.append(f"{p}: riwayah and verse_numbering required")
        elif kind == "mushaf":
            if not isinstance(record.get("page"), int) or isinstance(record.get("page"), bool) or record["page"] < 1:
                errors.append(f"{p}: positive page required")
            if not record.get("quran_ref") or not record.get("riwayah"):
                errors.append(f"{p}: quran_ref and riwayah required")
        elif kind == "tafsir":
            if not record.get("work") or not record.get("author"):
                errors.append(f"{p}: work and author required")
            if not record.get("quran_ref") or not record.get("ayat"):
                errors.append(f"{p}: quran_ref and ayat required")
    for rid, record in indexed.items():
        if record.get("kind") not in {"mushaf", "tafsir"}:
            continue
        target_id = record.get("quran_ref")
        target = indexed.get(target_id)
        if target is None or target.get("kind") != "quran":
            errors.append(f"{rid}: quran_ref must resolve to Quran record")
        elif record.get("kind") == "mushaf" and record.get("riwayah") != target.get("riwayah"):
            errors.append(f"{rid}: riwayah incompatible with Quran reference")
    return errors

def can_publish(record):
    return (record.get("verification") == "scholarly_verified"
            and record.get("rights") == "redistribution_permitted")

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("registry", type=Path)
    args = p.parse_args()
    try:
        data = json.loads(args.registry.read_text(encoding="utf-8"))
        errors = validate_registry(data)
    except (OSError, ValueError) as exc:
        errors = [str(exc)]
    print(json.dumps({"passed": not errors, "errors": errors}, ensure_ascii=False, indent=2))
    raise SystemExit(bool(errors))

if __name__ == "__main__":
    main()
