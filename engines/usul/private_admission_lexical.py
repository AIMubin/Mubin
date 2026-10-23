"""Read-only Usul Stage05 replay of an admitted PRIVATE source object.

Uses the merged corpus admission ledger before indexing source bytes. This is
a source-identity and lexical-fidelity check, NOT independent legal, editorial,
textual-variant, methodological or scholarly approval. No source/query text,
private path or URL is returned, and no public artifact is written.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import tempfile

from corpus.internal_research_ingest import (
    ADMISSION_ELIGIBLE, _guard_private_path, is_admitted,
)
from engines.usul.source_lexical_index import index_and_search
from engines.usul.source_snapshot_coverage import SHA256, _bound_read

VERSION = "usul-private-admission-lexical/0.1.0"


class PrivateUsulRefusal(ValueError):
    """Only fixed, non-disclosing codes may leave this adapter."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(ok, code: str):
    if not ok:
        raise PrivateUsulRefusal(code)


def _private(path):
    try:
        return _guard_private_path(Path(path))
    except (OSError, RuntimeError, ValueError, TypeError):
        raise PrivateUsulRefusal("PRIVATE_PATH_REFUSED") from None


def _scan(admission_manifest_path, usage_register_path, snapshot_manifest_path,
          trusted_snapshot_manifest_sha256, section_id, queries):
    admission_path = _private(admission_manifest_path)
    register_path = _private(usage_register_path)
    snapshot_path = _private(snapshot_manifest_path)
    _require(is_admitted(admission_path, register_path), "SOURCE_NOT_ADMITTED")

    # The private intake object, not any caller-supplied source-file path, is
    # the ONLY Stage05 input. Avoid copying/re-exporting original text.
    raw_admission = _bound_read(admission_path, 65536)
    admitted = json.loads(raw_admission.decode("utf-8"))
    _require(type(admitted) is dict, "ADMISSION_MANIFEST_INVALID")
    sha = admitted.get("sha256")
    _require(type(sha) is str and SHA256.fullmatch(sha) is not None
             and admitted.get("independently_pinned_sha256") == sha
             and admitted.get("admission_status") == ADMISSION_ELIGIBLE
             and admitted.get("visibility") == "internal_only"
             and type(admitted.get("source_id")) is str
             and type(admitted.get("source_url")) is str
             and admitted["source_url"], "ADMISSION_MANIFEST_INVALID")
    expected_object = Path("objects") / sha[:2] / sha
    _require(admitted.get("object_path") == str(expected_object),
             "ADMISSION_OBJECT_LAYOUT_INVALID")
    object_path = _private(admission_path.parent.parent / expected_object)
    admission_digest = hashlib.sha256(raw_admission).hexdigest()

    # is_admitted checks chain and exact object/manifest SHA. Also require
    # an entry declaring Usul (not merely some other admitted source kind).
    matching_usul_entry = False
    for line in register_path.read_text(encoding="utf-8").split("\n"):
        if not line.strip():
            continue
        entry = json.loads(line)
        payload = entry["payload"]
        if (payload.get("source_id") == admitted["source_id"]
                and payload.get("source_kind") == "usul"
                and payload.get("source_sha256") == sha
                and payload.get("object_sha256") == sha
                and payload.get("manifest_sha256") == admission_digest
                and payload.get("admission_status") == ADMISSION_ELIGIBLE):
            matching_usul_entry = True
            break
    _require(matching_usul_entry, "USUL_SOURCE_KIND_REFUSED")

    # Stage04 manifest trust is independently frozen by its caller. Neither
    # this SHA nor the intake ledger proves a printed edition or legal title.
    _require(type(trusted_snapshot_manifest_sha256) is str
             and SHA256.fullmatch(trusted_snapshot_manifest_sha256) is not None,
             "SNAPSHOT_MANIFEST_PIN_REQUIRED")
    snapshot_bytes = _bound_read(snapshot_path, 65536)
    _require(hashlib.sha256(snapshot_bytes).hexdigest() ==
             trusted_snapshot_manifest_sha256, "SNAPSHOT_MANIFEST_PIN_MISMATCH")
    snapshot = json.loads(snapshot_bytes.decode("utf-8"))
    _require(type(snapshot) is dict
             and snapshot.get("source_sha256") == sha
             and snapshot.get("source_url") == admitted["source_url"],
             "SNAPSHOT_SOURCE_MISMATCH")

    # Stage04 checks every byte and declared section; Stage05 performs only
    # exact literal matching. The two source-ID/edition namespaces remain
    # distinct; do not infer edition or semantic equivalence from shared bytes.
    try:
        lexical = index_and_search(
            object_path, snapshot_path, trusted_snapshot_manifest_sha256,
            section_id, queries)
    except (OSError, ValueError, TypeError, KeyError, RuntimeError,
            UnicodeError, OverflowError, RecursionError):
        raise PrivateUsulRefusal("STAGE05_LEXICAL_REPLAY_REFUSED") from None
    _require(lexical["status"] == "LEXICAL_INDEX_PASS"
             and lexical["coverage_status"] == "SNAPSHOT_COVERAGE_PASS"
             and lexical["snapshot_sha256"] == sha,
             "STAGE05_LEXICAL_REPLAY_REFUSED")

    # Whitelist output fields: omit private URLs, authors, titles, editions,
    # local paths, source text and the original query literals.
    return {
        "bridge": VERSION,
        "status": "PRIVATE_ADMITTED_LEXICAL_REPLAY_PASS",
        "admission_status": ADMISSION_ELIGIBLE,
        "admission_source_id": admitted["source_id"],
        "snapshot_source_id": lexical["source_id"],
        "admission_manifest_sha256": admission_digest,
        "snapshot_manifest_sha256": trusted_snapshot_manifest_sha256,
        "source_sha256": sha,
        "section_id": lexical["section_id"],
        "section_sha256": lexical["section_sha256"],
        "indexed_line_count": lexical["indexed_line_count"],
        "queries": [{
            "query_id": q["query_id"],
            "query_utf8_sha256": q["query_utf8_sha256"],
            "result_status": q["result_status"],
            "match_count": q["match_count"],
            "matches": q["matches"],
        } for q in lexical["queries"]],
        "classification": "EXACT_LITERAL_ONLY",
        "source_id_equivalence_attested": False,
        "edition_equivalence_verified": False,
        "lawful_acquisition_independently_verified": False,
        "semantic_qarinah_detection_verified": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "source_text_included": False,
        "query_text_included": False,
    }


def scan_admitted_section(admission_manifest_path, usage_register_path,
                          snapshot_manifest_path,
                          trusted_snapshot_manifest_sha256, section_id, queries):
    """Fail-closed scan; no direct source-file path or publication escape hatch."""
    try:
        return _scan(admission_manifest_path, usage_register_path,
                     snapshot_manifest_path, trusted_snapshot_manifest_sha256,
                     section_id, queries)
    except PrivateUsulRefusal:
        raise
    except (OSError, ValueError, KeyError, TypeError, RuntimeError,
            UnicodeError, OverflowError, RecursionError, AttributeError):
        raise PrivateUsulRefusal("PRIVATE_USUL_BRIDGE_FAILED") from None


def _report_destination(report_path, protected_paths):
    """Refuse vault writes and aliases to any private input, even hard links.

    Only one trusted local writer is supported: concurrent path swaps remain
    explicitly out of scope. Recheck again before the atomic replacement.
    """
    destination = _private(report_path)
    _private(destination.parent)
    originals = [_private(item) for item in protected_paths]
    admission_path = originals[0]
    # A report does not belong anywhere in the source vault, even if its
    # filename is not a currently known manifest or content-addressed object.
    vault_root = admission_path.parent.parent
    _require(not destination.is_relative_to(vault_root),
             "PRIVATE_REPORT_DESTINATION_REFUSED")

    # The admitted object is not a CLI argument; derive and protect its inode.
    try:
        if admission_path.is_file():
            candidate = json.loads(_bound_read(admission_path, 65536).decode("utf-8"))
            digest = candidate.get("sha256") if type(candidate) is dict else None
            if type(digest) is str and SHA256.fullmatch(digest) is not None:
                object_path = vault_root / "objects" / digest[:2] / digest
                originals.append(_private(object_path))
    except (OSError, UnicodeError, ValueError, TypeError, RuntimeError):
        # Malformed admission will be refused by the scan. Continue guarding
        # every known input and the whole vault before writing a refusal.
        pass

    for original in originals:
        if destination == original:
            raise PrivateUsulRefusal("PRIVATE_REPORT_DESTINATION_REFUSED")
        try:
            if (destination.exists() and original.exists() and
                    os.path.samefile(destination, original)):
                raise PrivateUsulRefusal("PRIVATE_REPORT_DESTINATION_REFUSED")
        except PrivateUsulRefusal:
            raise
        except (OSError, ValueError, TypeError):
            raise PrivateUsulRefusal("PRIVATE_REPORT_DESTINATION_REFUSED") from None
    return destination


def _write_private_report(destination, result, protected_paths):
    """Atomic replace prevents truncating a prior receipt before commit."""
    destination = _report_destination(destination, protected_paths)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", newline="\n", delete=False,
                prefix=".usul-report-", suffix=".tmp",
                dir=str(destination.parent)) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(result, ensure_ascii=False,
                                    sort_keys=True, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        _report_destination(destination, protected_paths)
        os.replace(temporary, destination)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("admission-manifest", "usage-register", "snapshot-manifest",
                "queries", "report"):
        p.add_argument("--" + arg, type=Path, required=True)
    p.add_argument("--trusted-snapshot-manifest-sha256", required=True)
    p.add_argument("--section-id", required=True)
    args = p.parse_args(argv)
    inputs = (args.admission_manifest, args.usage_register,
              args.snapshot_manifest, args.queries)
    report_path = None
    try:
        # Check all inputs, the derived admitted object, and hard-link aliases
        # BEFORE indexing or writing either success or refusal metadata.
        report_path = _report_destination(args.report, inputs)
        if not all(x.is_file() for x in inputs):
            result, code = {"status": "PENDING_PRIVATE_INPUTS"}, 3
        else:
            query_path = _private(args.queries)
            query_list = json.loads(_bound_read(query_path, 65536).decode("utf-8"))
            result = scan_admitted_section(
                args.admission_manifest, args.usage_register,
                args.snapshot_manifest, args.trusted_snapshot_manifest_sha256,
                args.section_id, query_list)
            code = 0
    except PrivateUsulRefusal as exc:
        result, code = {"status": "REFUSED", "reason_code": exc.code}, 1
    except (OSError, ValueError, TypeError, RuntimeError, UnicodeError):
        result, code = {"status": "REFUSED",
                        "reason_code": "PRIVATE_USUL_BRIDGE_FAILED"}, 1

    # Persist current refusal/PENDING status if destination is safe; never
    # overwrite source evidence through report-path or hard-link aliasing.
    if report_path is not None:
        try:
            _write_private_report(report_path, result, inputs)
        except PrivateUsulRefusal as exc:
            result, code = {"status": "REFUSED", "reason_code": exc.code}, 1
        except (OSError, ValueError, TypeError, RuntimeError, UnicodeError):
            result, code = {"status": "REFUSED",
                            "reason_code": "PRIVATE_REPORT_WRITE_FAILED"}, 1
    print(json.dumps({"status": result["status"],
                      "reason_code": result.get("reason_code"),
                      "source_text_included": False}, ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
