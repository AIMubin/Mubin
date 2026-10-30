"""B02-C.6 local witness preparation metadata gate (no private source access).

Validates only the operator's PUBLIC record, never narration identity,
source authenticity, hadith grade, or private H-Search transcript.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

RECEIPT = "b02c6-witness-prep-6-145-v1.json"
SHA = re.compile(r"^[0-9a-f]{64}$")
ARABIC = re.compile(r"[\u0600-\u06ff]")
LOCAL_PATH = re.compile(r"(?:[A-Za-z]:\\|/home/|/Users/)")
BAYHAQI = "openiti:0458Bayhaqi.SunanKubra"
SOURCES = frozenset({
    "openiti:0279Tirmidhi.Sunan",
    BAYHAQI,
    "openiti:0762IbnYusufZaylaci.NasbRaya",
    "openiti:1353IbnCabdRahimMubarakfuri.TuhfatAhwadhi",
})
PROBES = frozenset({"witness-fragment-full", "reduced-frame"})


class WitnessPrepError(ValueError):
    """Fixed public metadata error codes."""


def need(ok, code):
    if not ok:
        raise WitnessPrepError(code)


def is_sha(x):
    return type(x) is str and SHA.fullmatch(x) is not None


def load(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    need(type(data) is dict, "WITNESS_PREP_JSON_INVALID")
    return data


def validate_view(rec, evidence):
    need(type(rec) is dict and
         rec.get("contract") == "mubin-b02c6-witness-prep-metadata-v0.1"
         and rec.get("span_coordinate_unit")
            == "RAW_UNICODE_CODEPOINTS_NOT_UTF8_BYTES"
         and rec.get("public_metadata_scope")
            == "OPERATOR_REPORTED_NO_PRIVATE_SOURCES_OR_SOURCE_TEXT_VERIFIED_IN_CI",
         "WITNESS_PREP_CONTRACT_OR_OFFSET_INVALID")
    raw = json.dumps(rec, ensure_ascii=False, sort_keys=True)
    need(len(raw.encode("utf-8")) <= 16000 and not ARABIC.search(raw)
         and not LOCAL_PATH.search(raw)
         and "shared_span_folded" not in
             rec.get("negative_control", {}).get("shared_span_containment_check", {}),
         "WITNESS_PREP_PRIVATE_CONTENT_PRESENT")
    digest = rec.get("evidence_payload_sha256")
    need(is_sha(digest), "WITNESS_PREP_DIGEST_MISSING")
    body = dict(rec)
    del body["evidence_payload_sha256"]
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False,
                           separators=(",", ":"), allow_nan=False).encode("utf-8")
    need(hashlib.sha256(canonical).hexdigest() == digest,
         "WITNESS_PREP_SELF_DIGEST_INVALID")

    w = rec.get("witness_candidate_block")
    need(type(w) is dict and w.get("locator") == "L144309"
         and w.get("chars") == 290
         and is_sha(w.get("block_sha256"))
         and type(w.get("labels_present")) is list
         and "ISNAD_CUES_OBSERVED" in w["labels_present"]
         and "NO_CRITICAL_JUDGMENT_FOUND_IN_BLOCK" in w["labels_present"]
         and w.get("isnad_cue_counts") == {"akhbarana": 1}
         and w.get("quoted_quran_refs") == [],
         "WITNESS_PREP_BLOCK_INVALID")
    matn = w.get("matn_candidate")
    need(type(matn) is dict and
         matn.get("classification") == "NARRATION_FRAGMENT_CANDIDATE"
         and matn.get("folded_word_count") == 10
         and is_sha(matn.get("sha256"))
         and matn.get("span") == [9739067, 9739108],
         "WITNESS_PREP_MATN_INVALID")

    control = rec.get("negative_control")
    need(type(control) is dict and control.get("locator") == "L142475"
         and control.get("quoted_quran_refs") == []
         and control.get("shows") ==
             "quoted-Quran text separated from matn candidates",
         "WITNESS_PREP_NEGATIVE_CONTROL_INVALID")
    check = control.get("shared_span_containment_check")
    need(type(check) is dict
         and "shared_span_folded" not in check
         and is_sha(check.get("shared_span_folded_sha256"))
         and check.get("shared_span_folded_codepoints") == 45
         and check.get("shared_span_folded_utf8_bytes") == 81
         and check.get("is_substring_of_folded_verse_6_145") is True
         and check.get("verdict_label") == "QUOTED_QURAN_TEXT_CONFIRMED"
         and check.get("verdict_scope") ==
             "FOLDED_LEXICAL_CONTAINMENT_ONLY_NOT_NARRATION_IDENTITY",
         "WITNESS_PREP_NEGATIVE_CONTROL_NOT_CONSERVATIVE")

    probes = rec.get("cross_source_variant_search")
    need(type(probes) is list and len(probes) == 2
         and {p.get("probe_id") for p in probes if type(p) is dict} == PROBES,
         "WITNESS_PREP_PROBES_INVALID")
    for probe in probes:
        records = probe.get("per_source")
        need(type(records) is list and len(records) == 4
             and type(probe.get("sources_with_hits")) is int,
             "WITNESS_PREP_PROBE_STRUCTURE_INVALID")
        # Reject duplicated/unknown source identities before applying the
        # Bayhaqi-specific evidence shape to any row.
        source_ids = [row.get("source_id") if type(row) is dict else None
                      for row in records]
        need(len(set(source_ids)) == 4 and set(source_ids) == SOURCES,
             "WITNESS_PREP_SOURCE_SET_INVALID")
        by_source = {}
        counted = 0
        for item in records:
            need(type(item) is dict and
                 item.get("source_id") in SOURCES and
                 item["source_id"] not in by_source,
                 "WITNESS_PREP_SOURCE_SET_INVALID")
            sid = item["source_id"]
            if sid == BAYHAQI:
                count = item.get("occurrences_within_probe_limit")
                span = item.get("first_span")
                need(type(count) is int and 1 <= count <= 2
                     and type(span) is list and len(span) == 2
                     and all(type(v) is int for v in span)
                     and 9739067 <= span[0] < span[1] <= 9739108
                     and item.get("note") ==
                        "occurrence in this source is NOT narration identity",
                     "WITNESS_PREP_BAYHAQI_HIT_INVALID")
                counted += 1
            else:
                need(item.get("occurrences") == 0
                     and item.get("status") == "NO_MATCH_IN_THIS_SOURCE"
                     and item.get("absence_is_not_proof_of_absence") is True
                     and "occurrences_within_probe_limit" not in item,
                     "WITNESS_PREP_FALSE_ABSENCE_CLAIM")
            by_source[sid] = item
        need(set(by_source) == SOURCES
             and counted == probe["sources_with_hits"] == 1,
             "WITNESS_PREP_SOURCE_COUNT_INVALID")
        if probe["probe_id"] == "witness-fragment-full":
            need(by_source[BAYHAQI]["first_span"] == matn["span"]
                 and by_source[BAYHAQI]["occurrences_within_probe_limit"] == 1,
                 "WITNESS_PREP_PRIMARY_HIT_MISMATCH")

    flags = rec.get("flags")
    need(type(flags) is dict and
         all(flags.get(k) is False for k in (
             "narration_identity_verified", "grade_assigned",
             "scholarly_verified", "juristic_inference_allowed"))
         and flags.get("machine_research_labels_only") is True
         and rec.get("identity_decision") ==
            "NOT_ISSUED_PENDING_LOCAL_IDENTITY_ASSESSMENT"
         and "3ace886" in rec.get("identity_contract_availability", ""),
         "WITNESS_PREP_SCIENTIFIC_PROMOTION")

    need(type(evidence) is dict
         and evidence.get("preserved_candidate", {}).get("selected") is False
         and evidence.get("strict_gate_v3", {}).get("verdict")
             == "REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR",
         "WITNESS_PREP_STRICT_GATE_CHANGED")
    handoff = evidence.get("b02c6_witness_identity_prep")
    need(type(handoff) is dict
         and handoff.get("public_receipt_file") == RECEIPT
         and handoff.get("public_receipt_sha256") == digest
         and handoff.get("identity_decision") ==
             rec["identity_decision"]
         and handoff.get("offset_coordinate_unit") ==
             rec["span_coordinate_unit"]
         and handoff.get("cross_source_witness_search", {}).get(
             "fragment_found_in_sources") == 1
         and handoff.get("cross_source_witness_search", {}).get(
             "of_allowlisted_sources") == 4
         and handoff.get("cross_source_witness_search", {}).get(
             "narration_identity_verified") is False
         and handoff.get("flags", {}).get("source_text_included") is False,
         "WITNESS_PREP_HANDOFF_MISMATCH")
    return {
        "scope": "PUBLISHED_METADATA_ONLY_PRIVATE_WITNESS_NOT_REVERIFIED",
        "candidate_blocks": 1, "search_probes": 2,
        "source_hits_within_four": 1,
        "negative_quran_control_operator_reported": True,
        "raw_unicode_offset_converted_to_bytes": False,
        "identity_contract_executed": False,
        "identity_verified": False, "scientific_gate_passed": False,
    }


def validate(root):
    folder = Path(root) / "research/b02b"
    return validate_view(load(folder / RECEIPT),
                         load(folder / "evidence-receipt.json"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--if-present", action="store_true")
    args = parser.parse_args()
    if args.if_present and not (
        Path(args.root) / "research/b02b" / RECEIPT
    ).is_file():
        print("B02-C.6 local witness prep absent; synthetic tests still execute.")
        return 0
    try:
        result = validate(args.root)
    except (WitnessPrepError, TypeError, ValueError, OSError, KeyError) as exc:
        print("B02C6 PREP FAIL " +
              (str(exc) if isinstance(exc, WitnessPrepError) else "INVALID_INPUT"))
        return 1
    print("B02C6 PREP METADATA VALID " + json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
