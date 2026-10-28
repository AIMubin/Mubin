"""T0.1: verse-linked tafsir lookup from the pinned Q0.3 local vault.

No downloads, model calls, Quran reconstruction, public API or authority claims.
Source text omitted by default; explicit local research may reveal held-safe text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from corpus.query import get_ayah, SOURCES
from engines.quran.tafsir.catalog import _reference, load_catalog, CatalogError

CONTRACT = "mubin-tafsir-t01-v1"
_LOCK = Path(__file__).resolve().parents[2] / "corpus/locks/quran-tafsir-q03.json"
_SOURCE_IDS = {"tabary": "tafsir_tabari", "katheer": "tafsir_ibn_kathir",
               "baghawy": "tafsir_baghawi", "saadi": "tafsir_saadi",
               "moyassar": "tafsir_muyassar"}
_SHA256 = re.compile(r"[0-9a-f]{64}")


class TafsirError(ValueError):
    """Bounded refusal without disclosing private text or local paths."""


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def _pinned_lock() -> dict:
    try:
        lock = json.loads(_LOCK.read_text(encoding="utf-8"))
        linked = lock["linked_sqlite"]["observed_sha256"]
        upstream = lock["upstream"]["sha256"]
        if (lock["id"] != "quran-tafsir-q03-import-baseline"
                or type(linked) is not str or not _SHA256.fullmatch(linked)
                or type(upstream) is not str or not _SHA256.fullmatch(upstream)):
            raise TafsirError("T01_INVALID_LOCK")
        return {"linked": linked, "upstream_declared": upstream}
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        raise TafsirError("T01_INVALID_LOCK") from exc


def _lookup(db_path: Path, reference: str, *, expected_sha256: str,
            upstream_declared_sha256: str, include_private_text: bool = False) -> dict:
    """Fixture-injectable core; operator CLI never accepts an alternate pin."""
    try:
        sura, ayah = _reference(reference)
    except CatalogError as exc:
        raise TafsirError("T01_INVALID_REFERENCE") from exc
    if type(db_path) is not Path or db_path.is_symlink() or not db_path.is_file():
        raise TafsirError("T01_LOCAL_VAULT_UNAVAILABLE")
    if (type(expected_sha256) is not str or _SHA256.fullmatch(expected_sha256) is None
            or type(upstream_declared_sha256) is not str
            or _SHA256.fullmatch(upstream_declared_sha256) is None
            or type(include_private_text) is not bool):
        raise TafsirError("T01_INVALID_PARAMETERS")
    try:
        if _digest(db_path) != expected_sha256:
            raise TafsirError("T01_DATABASE_PIN_MISMATCH")
        source = get_ayah(db_path, sura, ayah)
        if _digest(db_path) != expected_sha256:
            raise TafsirError("T01_DATABASE_CHANGED_DURING_READ")
        works = {item["id"]: item for item in load_catalog()["sources"]}
        records, seen = [], set()
        for row in source["tafsirs"]:
            key = row["source_id"]
            if key not in SOURCES or key not in _SOURCE_IDS or key in seen:
                raise TafsirError("T01_AMBIGUOUS_SOURCE_RECORDS")
            seen.add(key)
            work_id = _SOURCE_IDS[key]
            work = works[work_id]
            receipt = row["source_citation"]
            digest = receipt["imported_text_sha256"]
            if (receipt["verse_locator"] != reference
                    or receipt["source_dataset"] != "tafsircenter/tafsir-mcp-data"
                    or receipt["dataset_source_key"] != key
                    or type(digest) is not str or not _SHA256.fullmatch(digest)):
                raise TafsirError("T01_SOURCE_CITATION_INVALID")
            readable = bool(row["displayable"])
            reveal = include_private_text and readable
            records.append({
                "evidence_id": f"tafsir:{work_id}:{reference}:{digest}",
                "work_id": work_id,
                "work_title_ar": work["title_ar"],
                "author_ar": work["author_ar"],
                "edition": None, "volume": None, "page": None,
                "verse_locator": reference,
                "source_dataset": receipt["source_dataset"],
                "dataset_source_key": key,
                "imported_record_sha256": digest,
                "quality_flags": list(row["quality_flags"]),
                "display_status": row["display_status"],
                "editorial_review_required": bool(row["editorial_review_required"]),
                "text": row["display_text"] if reveal else None,
                "text_access": ("PRIVATE_UNVERIFIED_RESEARCH_ONLY" if reveal else
                                "NOT_DISPLAYABLE_OR_EDITORIAL_HOLD" if not readable else
                                "OMITTED_BY_DEFAULT"),
                "edition_authenticated": False,
                "textual_interpretation_assessed": False,
                "rights_verified": False,
                "scholarly_verified": False,
                "p1_admitted": False,
            })
        return {
            "contract": CONTRACT, "milestone": "T0.1",
            "quran_reference": reference,
            "quran_anchor": {
                "reference": reference, "quran_text": None,
                "canonical_quran_witness_loaded": False,
                "derived_quran_text_exposed": False,
            },
            "corpus": {
                "source_dataset": "tafsircenter/tafsir-mcp-data",
                "linked_sqlite_sha256": expected_sha256,
                "original_upstream_sqlite_sha256_declared": upstream_declared_sha256,
                "linked_database_pin_matched": True,
                "original_upstream_checked_in_this_query": False,
            },
            "tafsir_count": len(records), "tafsirs": records,
            "link_kind": "DATASET_VERSE_INDEX_NOT_VERIFIED_EXEGETICAL_SCOPE",
            "interpretive_differences_assessed": False,
            "source_authenticated": False, "scholarly_verified": False,
            "rights_verified": False, "publication_allowed": False,
            "juristic_inference_allowed": False,
            "public_fatwa_authorized": False, "p1_admitted": False,
        }
    except TafsirError:
        raise
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        raise TafsirError("T01_LOCAL_SOURCE_UNREADABLE") from exc


def lookup_verse(db_path: Path, reference: str, *,
                 include_private_text: bool = False) -> dict:
    lock = _pinned_lock()
    return _lookup(db_path, reference, expected_sha256=lock["linked"],
                   upstream_declared_sha256=lock["upstream_declared"],
                   include_private_text=include_private_text)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="T0.1 pinned local Tafsir lookup")
    parser.add_argument("reference", help="Sura:ayah, e.g. 2:43")
    parser.add_argument("--database", type=Path,
                        default=Path("corpus-data/linked/quran_tafsir.db"))
    parser.add_argument("--private-text", action="store_true",
                        help="Include unverified text in stdout: DO NOT PIPE TO CI/LOGS")
    args = parser.parse_args(argv)
    try:
        result = lookup_verse(args.database, args.reference,
                              include_private_text=args.private_text)
    except TafsirError as exc:
        print(json.dumps({"status": "REFUSED", "code": str(exc)}, sort_keys=True))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
