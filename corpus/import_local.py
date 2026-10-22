#!/usr/bin/env python3
"""Import a local UTF-8 source safely; keep source bytes and provenance intact."""
import argparse
import hashlib
import json
import pathlib
import shutil
import sys
from datetime import datetime, timezone

def ingest(source: pathlib.Path, root: pathlib.Path, source_id: str, edition: str,
           rights: str, visibility: str, source_url: str) -> dict:
    if not source.is_file():
        raise ValueError("Input must be an existing regular file")
    if not source_id or not all(c.isascii() and (c.isalnum() or c in "-_") for c in source_id):
        raise ValueError("source-id must use ASCII letters, digits, '-' or '_'")
    if not edition.strip() or not rights.strip() or not source_url.strip():
        raise ValueError("edition, rights and source-url are required")
    if visibility not in {"review_pending", "internal_only", "public_eligible_after_review"}:
        raise ValueError("Invalid visibility")
    data = source.read_bytes()
    try:
        data.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise ValueError("Input must be UTF-8, without replacement characters") from exc
    digest = hashlib.sha256(data).hexdigest()
    dest = root / "objects" / digest[:2] / digest
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.read_bytes() != data:
        raise ValueError("Content-address mismatch")
    if not dest.exists():
        dest.write_bytes(data)
    record = {
      "schema_version": "0.1.0",
      "source_id": source_id,
      "edition": edition,
      "source_url": source_url,
      "rights_statement": rights,
      "visibility": visibility,
      "sha256": digest,
      "size_bytes": len(data),
      "encoding": "UTF-8",
      "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
      "object_path": str(dest.relative_to(root)),
      "canonicality": "UNVERIFIED",
      "verification_status": "PENDING",
    }
    manifest = root / "manifests" / (source_id + "-" + digest[:16] + ".json")
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return record

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("file", type=pathlib.Path)
    p.add_argument("--root", type=pathlib.Path, default=pathlib.Path("corpus-data"))
    p.add_argument("--source-id", required=True)
    p.add_argument("--edition", required=True)
    p.add_argument("--rights", required=True)
    p.add_argument("--source-url", required=True)
    p.add_argument("--visibility", default="review_pending")
    a = p.parse_args()
    try:
        print(json.dumps(ingest(a.file,a.root,a.source_id,a.edition,a.rights,a.visibility,a.source_url),ensure_ascii=False,indent=2))
    except (ValueError,OSError) as e:
        p.exit(2, f"Import failed: {e}\n")

if __name__ == "__main__":
    main()
