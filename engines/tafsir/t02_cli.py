"""T0.2 private CLI: T0.1 metadata + byte-verified raw Tafsir rows.

The pinned imported SQLite is the only source of raw text. T0.1 display
text cannot stand in for SHA-pinned original source bytes.
"""
from __future__ import annotations

import argparse
from contextlib import closing
import json
from pathlib import Path
import sqlite3

from engines.tafsir.t01 import (
    lookup_verse, _assert_no_sqlite_sidecars, _digest, TafsirError,
)
from engines.tafsir.t02 import (
    extract_from_t01_record, summarize, TafsirT02Error, _need, _sha,
)


def extract_local_verse(db_path: Path, lookup: dict) -> list[dict]:
    """Read the exact raw rows from the same pinned local SQLite snapshot.

    Used only after T0.1 has already authenticated the Q0.3 file SHA.
    Each imported record's raw-text SHA is independently checked against
    the source citation before constructing source offsets.
    """
    ref = lookup["quran_reference"]
    sura, ayah = (int(x) for x in ref.split(":"))
    expected = lookup["corpus"]["linked_sqlite_sha256"]
    _assert_no_sqlite_sidecars(db_path)
    _need(_digest(db_path) == expected, "T02_DATABASE_PIN_MISMATCH")
    with closing(sqlite3.connect(db_path.resolve().as_uri() + "?mode=ro",
                                 uri=True)) as connection:
        connection.execute("PRAGMA query_only=ON")
        rows = connection.execute(
            "SELECT source,text FROM tafsirs WHERE sura=? AND aya=? ORDER BY source",
            (sura, ayah)).fetchall()
    _assert_no_sqlite_sidecars(db_path)
    _need(_digest(db_path) == expected, "T02_DATABASE_CHANGED_DURING_READ")
    raw_by_key = {}
    expected_keys = {r["dataset_source_key"] for r in lookup["tafsirs"]}
    for key, raw in rows:
        if key not in expected_keys:
            continue
        _need(key not in raw_by_key, "T02_DUPLICATE_RAW_SOURCE")
        raw_by_key[key] = raw
    all_records = []
    for metadata in lookup["tafsirs"]:
        key = metadata["dataset_source_key"]
        _need(key in raw_by_key, "T02_T01_RAW_SOURCE_MISSING")
        raw = raw_by_key[key]
        _need(type(raw) is str, "T02_RAW_SOURCE_INVALID")
        _need(_sha(raw.encode("utf-8")) == metadata["imported_record_sha256"],
              "T02_SOURCE_BYTES_MISMATCH")
        if metadata["text"] is None:  # Keep T0.1 editorial hold.
            continue
        source_record = dict(metadata, raw_original_text=raw)
        all_records.extend(extract_from_t01_record(source_record))
    return all_records


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m engines.tafsir.t02_cli",
        description="T0.2 raw-source-bound candidate passage extraction")
    parser.add_argument("reference", help="Sura:ayah, e.g. 2:43")
    parser.add_argument("--database", type=Path,
                        default=Path("corpus-data/linked/quran_tafsir.db"))
    parser.add_argument("--include-text", action="store_true",
                        help="Print original source passages locally: do not log or upload")
    parser.add_argument("--summary-only", action="store_true",
                        help="Only print counts and identifiers (default)")
    args = parser.parse_args(argv)
    try:
        lookup = lookup_verse(args.database, args.reference,
                              include_private_text=True)
        records = extract_local_verse(args.database, lookup)
    except (TafsirT02Error, TafsirError) as exc:
        code = str(exc)
        print(json.dumps({"status": "REFUSED", "code": code,
                          "text_included": False}, ensure_ascii=False))
        return 2
    except (OSError, ValueError, KeyError, TypeError, sqlite3.Error, UnicodeError):
        print(json.dumps({"status": "REFUSED", "code": "T02_LOCAL_READ_FAILED",
                          "text_included": False}, ensure_ascii=False))
        return 2

    if args.include_text and not args.summary_only:
        payload = {
            "status": "OK", "quran_reference": args.reference,
            "summary": summarize(records),
            "records": records,
            "text_included": True,
            "warning": "PRIVATE SOURCE PASSAGES; NO PUBLICATION OR CLOUD FORWARDING",
        }
    else:
        payload = {
            "status": "OK", "quran_reference": args.reference,
            "summary": summarize(records),
            "text_included": False,
            "note": "Only candidate text segments; not distinct, verified tafsir opinions",
        }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
