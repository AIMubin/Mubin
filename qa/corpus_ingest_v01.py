"""Private Quran and tafsir research corpus import; no public artifacts or licensing promotion.

Import only exact byte-pinned official Tanzil text + four versioned QuranEnc packs.
Original text/footnotes remain untouched in a PRIVATE SQLite DB outside repo.
This tool NEVER exposes raw content to logs or GitHub artifacts.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import sqlite3
import tempfile
import urllib.request
import zlib
from pathlib import Path
from typing import Any

from engines.quran.q01.engine import _VERSE_COUNTS
from engines.quran.q01e.official import load_official_candidate
from qa.quran_official_probe import _fetch

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "research/corpora/import-sources-v01.json"
MAX_MANIFEST = 32 * 1024
MAX_PACKAGE = 3 * 1024 * 1024
MAX_DECOMPRESSED = 16 * 1024 * 1024
PIN_QURAN_ID = "quran_tanzil_uthmani_hafs_20261018"
VALID_IDS = frozenset((PIN_QURAN_ID, "qe_ar_muyassar", "qe_ar_mukhtasar", "qe_ar_yaseer", "qe_ar_nafahat"))
_SHA = re.compile(r"[0-9a-f]{64}")


class CorpusIngestError(ValueError):
    """Input rejected before it may be imported or published."""


def _pairs(items):
    out = {}
    for key, value in items:
        if key in out:
            raise CorpusIngestError("duplicate_json_key")
        out[key] = value
    return out


def _nonfinite(_):
    raise CorpusIngestError("nonfinite_json")


def _json(raw: bytes) -> Any:
    try:
        return json.loads(raw.decode("utf-8", "strict"), object_pairs_hook=_pairs,
                          parse_constant=_nonfinite)
    except (ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise CorpusIngestError("invalid_json") from exc


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safepath(value: Path, *, output: bool = False) -> Path:
    # Corpus data never belongs in the public Git checkout. No symlinked leaves.
    path = Path(value).expanduser().absolute()
    if path.is_symlink() or path.resolve() == REPO_ROOT or REPO_ROOT in path.resolve().parents:
        raise CorpusIngestError("public_checkout_or_symlink_destination_forbidden")
    if output and path.suffix != ".sqlite3":
        raise CorpusIngestError("output_must_be_sqlite3")
    return path


def load_manifest(path: Path = DEFAULT_MANIFEST) -> dict[str, Any]:
    data = path.read_bytes()
    if not 1 <= len(data) <= MAX_MANIFEST:
        raise CorpusIngestError("manifest_size_limit")
    obj = _json(data)
    if type(obj) is not dict or set(obj) != {"contract", "sources", "rights_policy"}:
        raise CorpusIngestError("invalid_manifest_shape")
    if obj["contract"] != "mubin-private-corpora-v0.1" or obj["rights_policy"] != "internal_research_only_legal_pending":
        raise CorpusIngestError("invalid_manifest_policy")
    sources = obj["sources"]
    if type(sources) is not list or len(sources) != 5:
        raise CorpusIngestError("expected_five_pinned_sources")
    found = set()
    for item in sources:
        if type(item) is not dict or set(item) != {"id", "kind", "publisher", "source_url", "download_url", "format", "version", "sha256", "compressed_bytes", "uncompressed_bytes", "file_name", "attribution", "source_license_url", "rights_status", "publication_enabled"}:
            raise CorpusIngestError("unknown_source_manifest_fields")
        sid = item["id"]
        if sid not in VALID_IDS or sid in found:
            raise CorpusIngestError("duplicate_or_unknown_source")
        found.add(sid)
        if item["rights_status"] != "legal_review_pending" or item["publication_enabled"] is not False:
            raise CorpusIngestError("unapproved_publication_flag")
        if type(item["sha256"]) is not str or not _SHA.fullmatch(item["sha256"]):
            raise CorpusIngestError("bad_source_digest")
        if type(item["file_name"]) is not str or not re.fullmatch(r"[a-z0-9_-]{4,64}\.(?:json\.gz|txt)", item["file_name"]):
            raise CorpusIngestError("unsafe_source_filename")
        if item["kind"] != ("quran" if sid == PIN_QURAN_ID else "tafsir") or item["format"] != ("tanzil-txt-2" if sid == PIN_QURAN_ID else "quranenc-gzip-json"):
            raise CorpusIngestError("unexpected_corpus_format")
        if not all(type(item[k]) is str and 3 <= len(item[k]) <= 500 for k in ("publisher", "source_url", "download_url", "version", "attribution", "source_license_url")):
            raise CorpusIngestError("incomplete_source_attribution")
        if type(item["compressed_bytes"]) is not int or type(item["uncompressed_bytes"]) is not int:
            raise CorpusIngestError("bad_source_size")
        if ((sid == PIN_QURAN_ID and (item["compressed_bytes"] != 0 or item["uncompressed_bytes"] != 0)) or (sid != PIN_QURAN_ID and (item["compressed_bytes"] < 10 or item["compressed_bytes"] > MAX_PACKAGE or item["uncompressed_bytes"] < item["compressed_bytes"] or item["uncompressed_bytes"] > MAX_DECOMPRESSED))):
            raise CorpusIngestError("source_size_out_of_bounds")
        if sid == PIN_QURAN_ID:
            if item["sha256"] != "7f30c647331a61100ebf24a80507dc0fcdd9f2df97f1312b5b2dfcb982a7f326":
                raise CorpusIngestError("incorrect_pinned_official_quran_digest")
            if item["download_url"] != "https://tanzil.net/pub/download/index.php":
                raise CorpusIngestError("unexpected_official_quran_host")
        else:
            if not re.fullmatch(r"https://raw\.githubusercontent\.com/m-alhamry/Quran-text-assets/[0-9a-f]{40}/data/[a-z_]+/[a-z0-9.-]+\.json\.gz", item["download_url"]):
                raise CorpusIngestError("untrusted_tafsir_download_location")
    if found != VALID_IDS:
        raise CorpusIngestError("missing_required_sources")
    return obj


def _decompress(raw: bytes, target_length: int) -> bytes:
    if len(raw) > MAX_PACKAGE or not raw.startswith(b"\x1f\x8b"):
        raise CorpusIngestError("gzip_missing_or_oversized")
    dec = zlib.decompressobj(wbits=31)
    out = bytearray()
    try:
        for i in range(0, len(raw), 32768):
            part = dec.decompress(raw[i:i+32768], target_length - len(out) + 1)
            out.extend(part)
            if len(out) > target_length:
                raise CorpusIngestError("gzip_expansion_limit")
        out.extend(dec.flush())
    except zlib.error as exc:
        raise CorpusIngestError("invalid_gzip") from exc
    if len(out) != target_length or not dec.eof or dec.unused_data or dec.unconsumed_tail:
        raise CorpusIngestError("gzip_trailer_or_size_mismatch")
    return bytes(out)


def _validate_quran(raw: bytes) -> list[tuple[int, int, str, str]]:
    index = load_official_candidate(raw)
    return [(s, a, text, "") for s, a, text in index.verses]


def _validate_tafsir(raw: bytes, item: dict) -> list[tuple[int, int, str, str]]:
    decompressed = _decompress(raw, item["uncompressed_bytes"])
    root = _json(decompressed)
    if type(root) is not dict or set(root) != {"schemaVersion", "edition", "verses"}:
        raise CorpusIngestError("bad_tafsir_schema")
    if root["schemaVersion"] != 1 or type(root["edition"]) is not dict:
        raise CorpusIngestError("bad_tafsir_edition")
    if root["edition"].get("id") != item["version"].split("@")[0]:
        raise CorpusIngestError("edition_identity_mismatch")
    if root["edition"].get("source") != "QuranEnc.com":
        raise CorpusIngestError("source_identity_mismatch")
    verses = root["verses"]
    if type(verses) is not dict or len(verses) != 114:
        raise CorpusIngestError("incomplete_tafsir_surahs")
    records = []
    for s, count in enumerate(_VERSE_COUNTS, 1):
        row = verses.get(str(s))
        if type(row) is not dict or len(row) != count:
            raise CorpusIngestError("incomplete_tafsir_verse_map")
        for a in range(1, count + 1):
            cell = row.get(str(a))
            if type(cell) is not dict or set(cell) != {"text", "footnotes"}:
                raise CorpusIngestError("bad_tafsir_cell")
            text, notes = cell["text"], cell["footnotes"]
            if (type(text) is not str or not text.strip() or len(text) > 150000 or
                (notes is not None and (type(notes) is not str or len(notes) > 100000))):
                raise CorpusIngestError("bad_or_empty_tafsir_text")
            records.append((s, a, text, notes or ""))
    if len(records) != 6236:
        raise CorpusIngestError("incomplete_tafsir_records")
    return records


def _validate_source(item: dict, raw: bytes) -> list[tuple[int,int,str,str]]:
    if type(raw) is not bytes or (item["kind"] != "quran" and len(raw) != item["compressed_bytes"]) or _sha(raw) != item["sha256"]:
        raise CorpusIngestError("raw_source_integrity_mismatch")
    if item["kind"] == "quran":
        return _validate_quran(raw)
    return _validate_tafsir(raw, item)


def ingest_corpus(manifest: dict, input_dir: Path, output_db: Path, *, allow_partial=False) -> dict:
    """Atomic private import; report *metadata*, never content/footnotes."""
    destination = _safepath(output_db, output=True)
    base = _safepath(input_dir)
    if not base.is_dir() or destination.exists():
        raise CorpusIngestError("missing_input_dir_or_existing_output")
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".mubin-private-", suffix=".sqlite3", dir=str(destination.parent))
    os.close(fd)
    records_imported = 0
    imported, skipped = [], []
    try:
        conn=sqlite3.connect(temporary)
        try:
            conn.executescript("""
              PRAGMA journal_mode=DELETE;
              PRAGMA synchronous=FULL;
              CREATE TABLE corpus_sources(source_id TEXT PRIMARY KEY, source_kind TEXT NOT NULL,
                publisher TEXT NOT NULL, source_url TEXT NOT NULL, version TEXT NOT NULL,
                raw_sha256 TEXT NOT NULL, attribution TEXT NOT NULL, source_license_url TEXT NOT NULL,
                rights_status TEXT NOT NULL CHECK(rights_status='legal_review_pending'),
                publication_enabled INTEGER NOT NULL CHECK(publication_enabled=0),
                source_authenticated INTEGER NOT NULL CHECK(source_authenticated=0),
                p1_admitted INTEGER NOT NULL CHECK(p1_admitted=0));
              CREATE TABLE corpus_entries(source_id TEXT NOT NULL, sura INTEGER NOT NULL,
                aya INTEGER NOT NULL, source_kind TEXT NOT NULL, text TEXT NOT NULL,
                footnotes TEXT NOT NULL, PRIMARY KEY(source_id,sura,aya),
                FOREIGN KEY(source_id) REFERENCES corpus_sources(source_id));
              CREATE INDEX ix_entries_verse ON corpus_entries(sura,aya,source_id);
            """)
            for item in manifest["sources"]:
                path=base/item["file_name"]
                if path.is_symlink() or not path.is_file():
                    if allow_partial:
                        skipped.append({"id":item["id"],"reason":"file_missing_or_unsafe"})
                        continue
                    raise CorpusIngestError("missing_or_unsafe_source:"+item["id"])
                size=path.stat().st_size
                if (item["kind"] != "quran" and size != item["compressed_bytes"]) or size > MAX_DECOMPRESSED:
                    raise CorpusIngestError("source_bytes_changed:"+item["id"])
                raw=path.read_bytes()
                rows=_validate_source(item, raw)
                conn.execute("INSERT INTO corpus_sources VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",(
                    item["id"],item["kind"],item["publisher"],item["source_url"],item["version"],
                    item["sha256"],item["attribution"],item["source_license_url"],
                    "legal_review_pending",0,0,0))
                conn.executemany("INSERT INTO corpus_entries VALUES(?,?,?,?,?,?)",
                                 ((item["id"],s,a,item["kind"],text,footnotes)
                                  for s,a,text,footnotes in rows))
                imported.append({"id":item["id"],"kind":item["kind"],"verses":len(rows),
                                 "sha256":item["sha256"],"status":"research_imported_unpublished"})
                records_imported += len(rows)
            if not imported:
                raise CorpusIngestError("nothing_imported")
            conn.commit()
            check=conn.execute("PRAGMA quick_check").fetchone()[0]
            if check != "ok":
                raise CorpusIngestError("sqlite_integrity_failure")
        finally:
            conn.close()
        os.chmod(temporary, 0o600)
        os.replace(temporary, destination)
    except Exception:
        Path(temporary).unlink(missing_ok=True)
        raise
    return {"contract":"mubin-private-corpus-receipt-v0.1",
            "imported_sources":imported,"skipped_sources":skipped,
            "records":records_imported,"internal_research_ready":True,
            "rights_review_pending":True,"publication_allowed":False,
            "p1_evidence_admitted":False,"scholarly_verified":False,
            "source_artifacts_added_to_public_git":False}


def download_pinned(manifest: dict, input_dir: Path) -> list[str]:
    """Downloads to private user directory only. Check hashes before atomic rename."""
    dest=_safepath(input_dir)
    dest.mkdir(parents=True, exist_ok=True)
    completed=[]
    for item in manifest["sources"]:
        target=dest/item["file_name"]
        if target.exists():
            if target.is_symlink() or _sha(target.read_bytes()) != item["sha256"]:
                raise CorpusIngestError("existing_download_digest_invalid:"+item["id"])
            completed.append(item["id"])
            continue
        if item["kind"] == "quran":
            raw=_fetch("GET")
        else:
            req=urllib.request.Request(item["download_url"],
                    headers={"User-Agent":"MubinPrivateResearchImporter/0.1"})
            with urllib.request.urlopen(req, timeout=65) as res:
                if res.geturl() != item["download_url"]:
                    raise CorpusIngestError("download_redirect_not_allowed")
                raw=res.read(item["compressed_bytes"]+1)
        if _sha(raw) != item["sha256"] or (item["kind"] != "quran" and len(raw) != item["compressed_bytes"]):
            raise CorpusIngestError("download_digest_invalid:"+item["id"])
        # Restrict to private directory with restrictive permissions.
        fd, tmp=tempfile.mkstemp(prefix=".mubin-source-",dir=str(dest))
        try:
            with os.fdopen(fd,"wb") as stream:
                stream.write(raw)
            os.chmod(tmp,0o600)
            os.replace(tmp,target)
        finally:
            Path(tmp).unlink(missing_ok=True)
        completed.append(item["id"])
    return completed


def main(argv=None):
    p=argparse.ArgumentParser(description="Import private, pinned Quran/Tafsir research corpus outside Git")
    p.add_argument("--manifest",type=Path,default=DEFAULT_MANIFEST)
    p.add_argument("--input-dir",type=Path,required=True)
    p.add_argument("--output-db",type=Path,required=True)
    p.add_argument("--download",action="store_true")
    p.add_argument("--allow-partial",action="store_true")
    args=p.parse_args(argv)
    try:
        catalog=load_manifest(args.manifest)
        if args.download:
            download_pinned(catalog,args.input_dir)
        report=ingest_corpus(catalog,args.input_dir,args.output_db,
                             allow_partial=args.allow_partial)
        print(json.dumps(report,ensure_ascii=False,sort_keys=True))
        return 0
    except (CorpusIngestError,OSError,sqlite3.Error) as exc:
        print(json.dumps({"contract":"mubin-private-corpus-receipt-v0.1",
                          "internal_research_ready":False,"publication_allowed":False,
                          "error":str(exc)[:250]},ensure_ascii=False))
        return 2


if __name__=="__main__":
    raise SystemExit(main())
