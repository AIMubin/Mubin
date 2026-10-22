"""Fail-closed, metadata-only repair of the frozen W2 three-view audit receipt.

Never edits the historic receipt. Replays the original HTML and demands that
the operator's private audit JSON match replay byte-for-byte at the data level,
then writes a new additive erratum with full SHA-256 values. No private text.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

from engines.usul.pilots.waraqat_w2_representation_audit import (
    W2_RAW_SHA, VERSION as AUDIT_VERSION, audit,
)

VERSION = "waraqat-w2-receipt-reconcile/0.1.0"
EXPECTED = {"stage06": 1702, "legacy_full": 1706, "hardened_full": 1696}
STAGE06_PIN = "db181b1d9466389d2b5aeaf50362dd57e716cc1e36d041948777e3fe0c9c9358"
HARDENED_PIN = "6e88c20addae4744be5d3754fe17e46965d96793f98f869c6d1027f7c343981f"
HEX64 = re.compile(r"[0-9a-f]{64}\Z")


class ReceiptReconciliationError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise ReceiptReconciliationError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def full_digest(value):
    return isinstance(value, str) and HEX64.fullmatch(value) is not None


def reconcile(report, previous, *, private_report_sha256,
              previous_receipt_sha256):
    """Pure verifier: public archive anchors + supplied replay report.

    The CLI additionally replays raw pinned HTML and checks the archived
    private-audit file's SHA against the immutable previous receipt.
    """
    require(type(report) is dict and type(previous) is dict,
            "INVALID_REPORT_TYPES")
    require(report.get("engine") == AUDIT_VERSION
            and report.get("status") == "ALL_THREE_REPRESENTATIONS_FORMAT_ONLY_VERIFIED"
            and report.get("pinned_w2_html_sha256") == W2_RAW_SHA
            and report.get("historical_lengths_verified") is True
            and report.get("source_text_included") is False,
            "AUDIT_CONTRACT_UNVERIFIED")
    require(previous.get("review_id") == "u01-w2-three-representations-final-audit"
            and previous.get("campaign_status")
            == "ALL_THREE_REPRESENTATIONS_FORMAT_ONLY_VERIFIED"
            and previous.get("pinned_html_sha256") == W2_RAW_SHA
            and previous.get("private_audit_report_sha256")
            == private_report_sha256,
            "ARCHIVED_RECEIPT_PROVENANCE_MISMATCH")
    require(full_digest(private_report_sha256)
            and full_digest(previous_receipt_sha256),
            "INPUT_PROVENANCE_SHA_INVALID")
    variants = report.get("variants")
    require(type(variants) is dict and set(variants) == set(EXPECTED),
            "VARIANTS_MISSING")
    for key, expected_bytes in EXPECTED.items():
        row = variants[key]
        require(type(row) is dict and type(row.get("bytes")) is int
                and row["bytes"] == expected_bytes
                and full_digest(row.get("sha256")),
                "VARIANT_SIZE_OR_DIGEST_INVALID_" + key)
    require(variants["stage06"]["sha256"] == STAGE06_PIN
            and variants["hardened_full"]["sha256"] == HARDENED_PIN,
            "INDEPENDENT_WITNESS_PINS_MISMATCH")
    old = previous.get("representations", {})
    keys = {"stage06": "stage06_htmlparser",
            "legacy_full": "legacy_full_windows",
            "hardened_full": "hardened_full"}
    for new_key, old_key in keys.items():
        historic = old.get(old_key, {})
        recorded = historic.get("sha256")
        require(historic.get("bytes") == variants[new_key]["bytes"]
                and isinstance(recorded, str)
                and variants[new_key]["sha256"].startswith(recorded),
                "HISTORICAL_LENGTH_OR_DIGEST_PREFIX_MISMATCH_" + new_key)
    lf_bytes = report.get("legacy_lf_serialized_bytes")
    lf_count = report.get("legacy_lf_linefeed_count")
    cr_added = report.get("legacy_windows_extra_cr_bytes")
    require(all(type(x) is int and x >= 0 for x in (lf_bytes, lf_count, cr_added))
            and lf_count == cr_added
            and lf_bytes + cr_added == variants["legacy_full"]["bytes"]
            and full_digest(report.get("legacy_lf_sha256")),
            "WINDOWS_NEWLINE_ACCOUNTING_INVALID")
    hard_bytes = variants["hardened_full"]["bytes"]
    stage_bytes = variants["stage06"]["bytes"]
    legacy_win = variants["legacy_full"]["bytes"]
    # The frozen receipt contains a KNOWN recording error: it lists 1700
    # LF-only bytes and claims 10 added CR bytes. Those two numbers could
    # not have produced the measured Windows file length of 1706. Preserve
    # the erroneous original, but permit exactly this documented erratum,
    # only after main() independently replays the byte-pinned source HTML.
    archived_lf = old["legacy_full_windows"].get("legacy_lf_only_bytes")
    archived_cr = previous.get("lf_to_crf_translations_on_windows")
    require(type(archived_lf) is int and archived_lf == 1700
            and type(archived_cr) is int and archived_cr == 10,
            "HISTORICAL_RECEIPT_NOT_KNOWN_ERRATUM")
    require(lf_bytes == hard_bytes and lf_bytes == 1696
            and cr_added == 10 and lf_count == 10
            and report["legacy_lf_sha256"] == variants["hardened_full"]["sha256"],
            "LEGACY_LF_HARDENED_PIN_MISMATCH")
    require((legacy_win - hard_bytes) ==
            (lf_bytes - hard_bytes) + cr_added,
            "TOTAL_DELTA_DECOMPOSITION_INVALID")
    profiles = report.get("comparisons")
    expected_profiles = ("stage06_vs_legacy_full", "stage06_vs_hardened_full",
                         "legacy_full_vs_hardened_full")
    require(type(profiles) is dict and set(profiles) == set(expected_profiles),
            "PAIRWISE_PROFILES_INCOMPLETE")
    for key in expected_profiles:
        p = profiles[key]
        require(type(p) is dict
                and all(p.get(name) is True for name in (
                    "nonempty_lines_identical",
                    "whitespace_delimited_tokens_identical",
                    "nonwhitespace_codepoints_identical")),
                "PAIRWISE_TEXT_MISMATCH_" + key)
    result = {
        "schema_version": "0.1.0",
        "review_id": "u01-w2-three-representations-reconciliation-erratum",
        "engine": VERSION,
        "status": "EVIDENCE_RECONCILIATION_PASS",
        "supersedes_interpretation_only": True,
        "superseded_receipt_review_id": previous["review_id"],
        "superseded_receipt_sha256": previous_receipt_sha256,
        "pinned_html_sha256": W2_RAW_SHA,
        "private_audit_report_sha256": private_report_sha256,
        "three_representations": {
            key: {"bytes": variants[key]["bytes"],
                  "sha256": variants[key]["sha256"]}
            for key in ("stage06", "legacy_full", "hardened_full")
        },
        "legacy_lf_only": {"bytes": lf_bytes,
                           "sha256": report["legacy_lf_sha256"],
                           "linefeed_count": lf_count},
        "delta_accounting": {
            "legacy_windows_minus_legacy_lf": cr_added,
            "legacy_lf_minus_hardened": lf_bytes - hard_bytes,
            "legacy_windows_minus_hardened": legacy_win - hard_bytes,
            "stage06_minus_hardened": stage_bytes - hard_bytes,
            "archived_claimed_cr_added": archived_cr,
            "measured_cr_added": cr_added,
            "archived_legacy_lf_only_bytes": archived_lf,
            "measured_legacy_lf_only_bytes": lf_bytes,
            "historical_field_corrected_via_additive_erratum": True,
        },
        "provenance_correction": {
            "historical_receipt_unchanged": True,
            "historical_legacy_lf_only_bytes": archived_lf,
            "measured_legacy_lf_only_bytes": lf_bytes,
            "basis": "pinned-private-audit-exact-replay",
            "historical_legacy_digest_was_prefix_only": True,
            "historical_hardened_digest_was_prefix_only": True,
        },
        "pairwise_text_profiles": {
            key: {name: profiles[key][name]
                  for name in ("nonempty_lines_identical",
                               "whitespace_delimited_tokens_identical",
                               "nonwhitespace_codepoints_identical")}
            for key in expected_profiles
        },
        "source_text_included": False,
        "scholarly_verified": False,
        "redistribution_approved": False,
        "semantic_rules_qualified": False,
        "semantic_equivalence_verified": False,
        "public_fatwa_authorized": False,
    }
    result["receipt_sha256"] = sha(canonical(result))
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-html", type=Path, required=True)
    p.add_argument("--private-audit", type=Path, required=True)
    p.add_argument("--previous-receipt", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    try:
        raw_html = args.raw_html.read_bytes()
        audit_bytes = args.private_audit.read_bytes()
        previous_bytes = args.previous_receipt.read_bytes()
        supplied = json.loads(audit_bytes.decode("utf-8"))
        replayed = audit(raw_html)
        require(supplied == replayed, "PRIVATE_AUDIT_REPLAY_MISMATCH")
        previous = json.loads(previous_bytes.decode("utf-8"))
        output = reconcile(supplied, previous,
                           private_report_sha256=sha(audit_bytes),
                           previous_receipt_sha256=sha(previous_bytes))
        status, code = output["status"], 0
    except (OSError, ValueError, KeyError, TypeError, UnicodeError,
            json.JSONDecodeError) as exc:
        status, code = "EVIDENCE_RECONCILIATION_FAILED", 1
        output = {"engine": VERSION, "status": status,
                  "reason_code": str(exc) if type(exc) is ReceiptReconciliationError
                  else type(exc).__name__,
                  "source_text_included": False}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, sort_keys=True,
                                  indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"status": status, "source_text_included": False}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
