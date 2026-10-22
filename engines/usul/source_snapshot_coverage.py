"""U0.1 read-only original snapshot/UTF-8 transcript coverage audit.

No network fetching, no claims of a critically edited edition, no semantically
exhaustive qarinah search. A matching digest attests only exact bytes against
the caller's *independently pinned* manifest. Outputs contain NO source text.

The accepted snapshot is a UTF-8 plain-text export, not raw HTML. The export
must be separately documented; this tool cannot prove faithful HTML→text
conversion, completeness of a printed edition, or redistribution permission.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

MAX_SOURCE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_LINES = 100_000
MAX_SECTIONS = 24
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class SnapshotContractError(ValueError):
    pass


def _require(test, message):
    if not test:
        raise SnapshotContractError(message)


def _keys(obj, keys, where):
    _require(type(obj) is dict and set(obj) == set(keys),
             f"{where}: unrecognized or missing fields")


def _digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _bound_read(path: Path, maximum: int) -> bytes:
    # Read-only and bounded to stop unexpectedly large or mutable inputs.
    length = path.stat().st_size
    _require(0 < length <= maximum, "source or manifest byte size outside limit")
    with path.open("rb") as handle:
        result = handle.read(maximum + 1)
    _require(len(result) == length and len(result) <= maximum,
             "source size changed while reading")
    return result


def _line_index(raw: bytes):
    """Partition the complete original byte buffer without normalizing bytes."""
    lines = raw.splitlines(keepends=True)
    _require(0 < len(lines) <= MAX_SOURCE_LINES, "invalid source line count")
    _require(b"".join(lines) == raw, "loss in byte-preserving line split")
    positions = []
    offset = 0
    for i, line in enumerate(lines):
        end = offset + len(line)
        positions.append({
            "line_number": i + 1, "byte_start": offset, "byte_end": end,
            "sha256": _digest(line),
        })
        offset = end
    _require(offset == len(raw), "source index does not cover all source bytes")
    return lines, positions


def _validate_manifest(manifest):
    _keys(manifest, ("schema_version", "source_id", "work_title",
                     "author", "edition", "source_url", "locator",
                     "input_format", "transcription_provenance",
                     "source_sha256", "source_size_bytes",
                     "sections"), "manifest")
    _require(manifest["schema_version"] == "0.1.0", "unsupported snapshot contract")
    _require(manifest["input_format"] == "UTF8_PLAINTEXT_EXPORT_V1",
             "raw HTML/PDF/OCR input not accepted by this extractor")
    for key in ("source_id", "work_title", "author", "edition", "source_url",
                "locator", "transcription_provenance"):
        _require(type(manifest[key]) is str and manifest[key].strip(),
                 f"missing/invalid source metadata: {key}")
    _require(type(manifest["source_size_bytes"]) is int
             and 0 < manifest["source_size_bytes"] <= MAX_SOURCE_BYTES,
             "invalid source size")
    _require(type(manifest["source_sha256"]) is str
             and SHA256.fullmatch(manifest["source_sha256"]) is not None,
             "malformed source SHA-256")
    sections = manifest["sections"]
    _require(type(sections) is list and 0 < len(sections) <= MAX_SECTIONS,
             "no bounded sections supplied")
    names = set()
    for j, item in enumerate(sections):
        where = f"sections[{j}]"
        _keys(item, ("id", "start_line", "end_line",
                     "section_sha256", "expected_line_count"), where)
        for field in ("id", "start_line", "end_line"):
            _require(type(item[field]) is str and item[field].strip(),
                     f"{where}: invalid {field}")
        _require(item["id"] not in names, f"{where}: duplicate ID")
        names.add(item["id"])
        _require(item["start_line"] != item["end_line"], "identical section bounds")
        _require(type(item["section_sha256"]) is str and
                 SHA256.fullmatch(item["section_sha256"]) is not None,
                 f"{where}: section hash not pinned")
        _require(type(item["expected_line_count"]) is int
                 and 1 <= item["expected_line_count"] <= MAX_SOURCE_LINES,
                 f"{where}: invalid section line count")
    return manifest


def audit(snapshot_path: Path, manifest_path: Path,
          *, trusted_manifest_sha256: str) -> dict:
    """Return reproducible source/scope coverage, with no text in the report.

    trusted_manifest_sha256 MUST be from an independent trust anchor, not
    freshly calculated from the same untrusted manifest in this call.
    """
    _require(type(trusted_manifest_sha256) is str
             and SHA256.fullmatch(trusted_manifest_sha256) is not None,
             "trusted manifest SHA-256 must be an independently pinned hex digest")
    manifest_bytes = _bound_read(Path(manifest_path), 65536)
    _require(_digest(manifest_bytes) == trusted_manifest_sha256,
             "manifest does not match independently supplied trust anchor")
    try:
        manifest = _validate_manifest(json.loads(manifest_bytes.decode("utf-8")))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SnapshotContractError("malformed UTF-8 JSON manifest") from exc

    raw = _bound_read(Path(snapshot_path), MAX_SOURCE_BYTES)
    _require(len(raw) == manifest["source_size_bytes"], "source byte-size mismatch")
    _require(_digest(raw) == manifest["source_sha256"], "source SHA-256 mismatch")
    _require(not raw.startswith(b"\xef\xbb\xbf"), "BOM not supported")
    _require(b"\x00" not in raw, "binary-looking source bytes")
    try:
        text = raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError as exc:
        raise SnapshotContractError("source is not exact UTF-8") from exc
    _require(text.encode("utf-8") == raw, "UTF-8 byte-preserving roundtrip failed")
    lines, indexed = _line_index(raw)
    decoded = [line.decode("utf-8").strip() for line in lines]

    sections = []
    spans = []
    for section in manifest["sections"]:
        starts = [i for i, value in enumerate(decoded) if value == section["start_line"]]
        ends = [i for i, value in enumerate(decoded) if value == section["end_line"]]
        _require(len(starts) == 1 and len(ends) == 1,
                 f"section {section['id']}: ambiguous/missing unique headings")
        start, end = starts[0], ends[0]
        _require(end > start, f"section {section['id']}: invalid heading order")
        _require(end - start == section["expected_line_count"],
                 f"section {section['id']}: source line coverage count mismatch")
        begin = indexed[start]["byte_start"]
        stop = indexed[end]["byte_start"]
        covered = raw[begin:stop]
        _require(_digest(covered) == section["section_sha256"],
                 f"section {section['id']}: anchored section hash mismatch")
        _require(b"".join(lines[start:end]) == covered,
                 f"section {section['id']}: extracted text coverage has gaps")
        spans.append((begin, stop, section["id"]))
        line_meta = indexed[start:end]
        sections.append({
            "section_id": section["id"], "status": "PASS",
            "begin_line_inclusive": start + 1,
            "end_line_exclusive": end + 1,
            "start_byte": begin, "end_byte_exclusive": stop,
            "line_count": end - start, "byte_count": len(covered),
            "section_sha256": _digest(covered),
            "all_indexed_lines_reassemble_to_source_slice": True,
            "indexed_line_sha256": [x["sha256"] for x in line_meta],
            "source_text_included": False,
        })
    spans.sort()
    _require(all(prev[1] <= now[0] for prev, now in zip(spans, spans[1:])),
             "declared extraction sections overlap")
    return {
        "status": "SNAPSHOT_COVERAGE_PASS",
        "source_id": manifest["source_id"],
        "work_title": manifest["work_title"],
        "author": manifest["author"],
        "edition": manifest["edition"],
        "source_url": manifest["source_url"],
        "locator": manifest["locator"],
        "transcription_provenance": manifest["transcription_provenance"],
        "input_format": manifest["input_format"],
        "snapshot_sha256": _digest(raw),
        "source_size_bytes": len(raw),
        "trusted_manifest_sha256": trusted_manifest_sha256,
        "total_source_lines": len(lines),
        "total_source_byte_partition_coverage": True,
        "full_source_line_index_sha256": _digest(
            json.dumps(indexed, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ),
        "sections": sections,
        "sections_passed": len(sections),
        "external_original_html_or_print_equivalence_verified": False,
        "full_edition_completeness_verified": False,
        "semantic_qarinah_detection_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "source_text_reproduced": False,
        "scope": "PINNED_UTF8_EXPORT_BYTE_AND_DECLARED_SECTION_COVERAGE_ONLY",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--trusted-manifest-sha256", required=True)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    try:
        if not args.source.is_file():
            result, code = {
                "status": "PENDING_SOURCE",
                "reason": "Original private UTF-8 export not supplied; no source attestation",
                "scholarly_verified": False,
            }, 3
        else:
            result, code = audit(args.source, args.manifest,
                                 trusted_manifest_sha256=args.trusted_manifest_sha256), 0
    except (OSError, ValueError) as exc:
        result, code = {
            "status": "FAIL", "error_type": type(exc).__name__,
            "reason": str(exc), "scholarly_verified": False,
        }, 1
    # Result contains hashes, locators and line counts only.
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "report": str(args.report)}, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
