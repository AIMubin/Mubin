"""Generate a candidate UTF-8 snapshot manifest. NEVER self-attests source origin.

A local export -> draft manifest -> independently archived digest -> subsequent
coverage audit is a multi-step process. Only the audit checks the frozen pin.
"""
from __future__ import annotations
import argparse
import json
from pathlib import Path

from engines.usul.source_snapshot_coverage import (
    MAX_SOURCE_BYTES, SnapshotContractError, _bound_read, _digest,
    _line_index, _validate_manifest,
)

METADATA = {"source_id", "work_title", "author", "edition",
            "source_url", "locator", "transcription_provenance"}


def propose(source_path, metadata, section_id, heading, next_heading):
    if not isinstance(metadata, dict) or set(metadata) != METADATA:
        raise SnapshotContractError("source metadata incomplete")
    if not all(type(v) is str and v.strip() for v in metadata.values()):
        raise SnapshotContractError("blank or nontext source metadata")
    if not all(type(v) is str and v.strip() for v in
               (section_id, heading, next_heading)):
        raise SnapshotContractError("invalid section identity/bounds")
    raw = _bound_read(Path(source_path), MAX_SOURCE_BYTES)
    if raw.startswith(b"\xef\xbb\xbf") or b"\x00" in raw:
        raise SnapshotContractError("BOM/binary source not accepted")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SnapshotContractError("source must be strict UTF-8") from exc
    rows, index = _line_index(raw)
    labels = [row.decode("utf-8").strip() for row in rows]
    starts = [i for i, label in enumerate(labels) if label == heading]
    ends = [i for i, label in enumerate(labels) if label == next_heading]
    if len(starts) != 1 or len(ends) != 1 or ends[0] <= starts[0]:
        raise SnapshotContractError("ambiguous or reversed section boundaries")
    start, end = starts[0], ends[0]
    span = raw[index[start]["byte_start"]:index[end]["byte_start"]]
    return _validate_manifest({
        "schema_version": "0.1.0", **metadata,
        "input_format": "UTF8_PLAINTEXT_EXPORT_V1",
        "source_sha256": _digest(raw), "source_size_bytes": len(raw),
        "sections": [{
            "id": section_id, "start_line": heading, "end_line": next_heading,
            "section_sha256": _digest(span), "expected_line_count": end-start,
        }],
    })


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--metadata", type=Path, required=True)
    p.add_argument("--section-id", required=True)
    p.add_argument("--start-line", required=True)
    p.add_argument("--end-line", required=True)
    p.add_argument("--draft-manifest", type=Path, required=True)
    x = p.parse_args()
    try:
        m = json.loads(_bound_read(x.metadata, 65536).decode("utf-8"))
        candidate = propose(x.source, m, x.section_id,
                            x.start_line, x.end_line)
        raw = (json.dumps(candidate, ensure_ascii=False, sort_keys=True,
                          separators=(",", ":")) + "\n").encode("utf-8")
        x.draft_manifest.parent.mkdir(parents=True, exist_ok=True)
        x.draft_manifest.write_bytes(raw)
        print(json.dumps({
            "status": "DRAFT_NOT_ATTESTED",
            "manifest_sha256_to_independently_pin": _digest(raw),
            "source_sha256": candidate["source_sha256"],
            "independently_attested": False,
        }, ensure_ascii=True))
        return 0
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        print(json.dumps({"status": "INVALID_DRAFT_SOURCE",
                          "error_type": type(exc).__name__}, ensure_ascii=True))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
