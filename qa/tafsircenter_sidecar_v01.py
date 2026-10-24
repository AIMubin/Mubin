"""Private source-byte-preserving Tafsir Center SQLite sidecar verifier.

This attaches nothing to the public repo. The source is separately licensed;
verifying bytes is not a Mubin scholarly or legal approval. Text is never logged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import os
import sqlite3
from pathlib import Path
from engines.quran.q01.engine import _VERSE_COUNTS

SOURCE_ROOT = Path(__file__).resolve().parents[1]
SOURCE_ID = "tafsircenter_quran_db_sidecar_v01"
SOURCE_URL = "https://huggingface.co/datasets/tafsircenter/tafsir-mcp-data"
SOURCE_LICENSE = "https://github.com/tafsircenter/tafsir-mcp/blob/main/LICENSE-DATA"
EXPECTED_SHA256 = "10e61f615ab5e6a3440e8ecc8ba1dc2273d12cd9048752760fe53a44d191cc27"
TABLES_AR = ("tafsir_tabary", "tafsir_katheer", "tafsir_baghawy", "tafsir_saadi", "tafsir_moyassar")
MAX_SIZE = 320 * 1024 * 1024


class SidecarError(ValueError):
    pass


def _restricted_file(path: Path) -> Path:
    p = Path(path).expanduser().absolute()
    resolved = p.resolve()
    if p.is_symlink() or resolved == SOURCE_ROOT or SOURCE_ROOT in resolved.parents:
        raise SidecarError("source_file_must_be_private_outside_public_checkout")
    if not p.is_file() or not 1 <= p.stat().st_size <= MAX_SIZE:
        raise SidecarError("missing_oversized_or_unsafe_source_file")
    return resolved


def _counts(conn, table, key1, key2):
    # Table and columns chosen only from hard-coded allowlisted schema.
    rows=conn.execute(f'SELECT {key1}, {key2} FROM "{table}"').fetchall()
    if len(rows) != 6236:
        raise SidecarError("source_tafsir_missing_verses:"+table)
    actual = {(s,a) for s,a in rows}
    expected = {(s,a) for s,c in enumerate(_VERSE_COUNTS,1) for a in range(1,c+1)}
    if actual != expected:
        raise SidecarError("source_tafsir_coordinate_mismatch:"+table)


def verify_sidecar(path: Path, *, deep: bool = True) -> dict:
    """Verify exact original data and complete verse-key maps; only metadata out."""
    p = _restricted_file(path)
    digest = hashlib.sha256()
    with p.open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
    if digest.hexdigest() != EXPECTED_SHA256:
        raise SidecarError("source_checksum_mismatch")
    with p.open("rb") as stream:
        if stream.read(16) != b"SQLite format 3\x00":
            raise SidecarError("not_sqlite_database")
    con = sqlite3.connect(p.as_uri()+"?mode=ro&immutable=1",uri=True)
    try:
        con.execute("PRAGMA query_only=ON")
        if con.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise SidecarError("sqlite_integrity_failure")
        tables={row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        required=set(TABLES_AR)|{"QuranTafseer","word_content_rasm","qeraat_info","ayah_content_nozool","surah_stats"}
        if not required.issubset(tables):
            raise SidecarError("missing_expected_source_tables")
        if con.execute('SELECT COUNT(*) FROM "surah_stats"').fetchone()[0]!=114:
            raise SidecarError("incomplete_surah_metadata")
        for t in TABLES_AR:
            _counts(con,t,"sura","aya")
        _counts(con,"QuranTafseer","surahNo","ayahNo")
        source_tables={table:con.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in TABLES_AR}
        source_tables["QuranTafseer"] = 6236
        if deep:
            for t,num in (("word_content_rasm",77432), ("qeraat_info",77432),("ayah_content_nozool",201)):
                if con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]!=num:
                    raise SidecarError("source_sidecar_expected_row_count_changed:"+t)
    except sqlite3.Error as exc:
        raise SidecarError("cannot_verify_readonly_source_schema") from exc
    finally:
        con.close()
    return {
        "contract":"mubin-tafsircenter-private-source-receipt-v0.1",
        "source_id":SOURCE_ID,"source_url":SOURCE_URL,"raw_sha256":EXPECTED_SHA256,
        "table_counts":source_tables,"multi_tafsir_coordinates":6236,
        "tafsir_sources":list(TABLES_AR),"surah_count":114,
        "source_database_used_verbatim":True,"research_access_ready":True,
        "publication_allowed":False,"rights_status":"legal_review_pending",
        "rights_verified":False,"scholarly_verification_by_mubin":False,
        "p1_admitted":False,"source_database_uploaded_to_git":False,
        "publisher_attribution":"Tafsir Center for Quranic Studies (https://tafsir.net)",
        "rights_discrepancy_notice":"LICENSE-DATA CC BY 4.0 vs DATA_SOURCES.md commercial permission statement; legal review pending"
    }


def main(argv=None):
    p=argparse.ArgumentParser(description="Verify private Tafsir Center SQLite source byte for byte")
    p.add_argument("--file",type=Path,required=True)
    args=p.parse_args(argv)
    try:
        print(json.dumps(verify_sidecar(args.file),ensure_ascii=False,sort_keys=True))
        return 0
    except (OSError,SidecarError) as exc:
        print(json.dumps({"source_id":SOURCE_ID,"verified":False,"publication_allowed":False,
                          "error":str(exc)[:220]},sort_keys=True))
        return 2


if __name__=='__main__':raise SystemExit(main())
