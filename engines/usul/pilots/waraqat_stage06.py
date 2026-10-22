"""Stage06 pinned al-Waraqat section alignment; secondary HTML→text linkage pending.

Requires BOTH original HTML captures plus W1 Stage04 full export+manifest,
W1 extracted chapter bytes, and an independently pinned W2 chapter export.
The operator must separately verify W2's HTML→section extractor; we never
promote a normalized compare to full witness identity or semantic agreement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from engines.usul.source_snapshot_coverage import audit
from engines.usul.pilots.waraqat_extract import extract
from engines.usul.pilots.waraqat_witness2_extract import extract as extract_witness2, VERSION as W2_EXTRACT_VERSION
from engines.usul.witness_alignment import align_sections, WitnessAlignmentError

W1_RAW_SHA = "66ec33c1825acdf82b3720f89d89aac15aa6e993356c0d90b41e53fe9a2fa044"
W1_EXPORT_SHA = "9ce9de30f1af3ef32b2bf55b0473c9459e0cf530e3b557535744b284c760f4df"
W1_MANIFEST_SHA = "5bf586787dbb9f84d03fc21c62ee32619b66b474c66a6c890aeb813219f853cf"
W1_SECTION_SHA = "20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab"
W2_RAW_SHA = "3c4de1baa99bad782b5fba066523ca9f12798525907edede93bd1046ef36f0fa"
SECTION = "pilot:waraqat-bab-amr"
W1_URL = "https://www.islamicbook.ws/asol/alwrqat.html"
W2_URL = "https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/"


def _need(condition, msg):
    if not condition:
        raise WitnessAlignmentError("Stage06 source contract: " + msg)


def compare_captured_witnesses(primary_html, primary_export, primary_manifest,
                               primary_section, secondary_html, secondary_section,
                               secondary_section_pin, *, verify_secondary_extraction=False):
    """Outputs raw-source identity, section text alignment, NOT W2 extraction proof."""
    _need(type(secondary_section_pin) is str and len(secondary_section_pin) == 64,
          "independent secondary section SHA256 required")
    report = audit(primary_export, primary_manifest,
                   trusted_manifest_sha256=W1_MANIFEST_SHA)
    sections = [s for s in report["sections"] if s["section_id"] == SECTION]
    _need(report["source_url"] == W1_URL
          and report["snapshot_sha256"] == W1_EXPORT_SHA
          and len(sections) == 1
          and sections[0]["section_sha256"] == W1_SECTION_SHA
          and sections[0]["line_count"] == 22
          and sections[0]["start_byte"] == 3735
          and sections[0]["end_byte_exclusive"] == 4967,
          "primary Stage04 source identity and exact 22-line section must match")
    first_raw = Path(primary_html).read_bytes()
    second_raw = Path(secondary_html).read_bytes()
    _need(hashlib.sha256(first_raw).hexdigest() == W1_RAW_SHA,
          "primary HTML does not match published independent digest")
    _need(hashlib.sha256(second_raw).hexdigest() == W2_RAW_SHA,
          "comparator HTML does not match published independent digest")
    replayed, _ = extract(first_raw)
    exported = Path(primary_export).read_bytes()
    _need(replayed == exported, "primary HTML does not reproduce UTF-8 export")
    target = exported[3735:4967]
    _need(Path(primary_section).read_bytes() == target,
          "primary chapter file differs from original byte slice")
    second_conversion = False
    if verify_secondary_extraction:
        try:
            repeat_section, w2_stats = extract_witness2(second_raw)
        except (ValueError, UnicodeError) as exc:
            raise WitnessAlignmentError("Stage06 secondary HTML section extraction refused") from exc
        _need(repeat_section == Path(secondary_section).read_bytes(),
              "secondary section is not reproduced by frozen W2 HTML capture")
        second_conversion = True

    comparison = align_sections(
        primary_section, secondary_section,
        left_sha256=W1_SECTION_SHA, right_sha256=secondary_section_pin,
        left_source_id="pilot:waraqat-primary",
        right_source_id="pilot:waraqat-comparator",
        left_locator="باب الأمر: Stage04 lines 86–107 inclusive",
        right_locator="باب الأمر: separately pinned private comparator section",
    )
    return {
        **comparison,
        "status": ("STAGE06_DUAL_SOURCE_EXTRACTION_REPLAY_PASS" if second_conversion
                   else "STAGE06_TEXT_ALIGNMENT_PROVENANCE_PARTIAL"),
        "raw_html_witness1_sha256": W1_RAW_SHA,
        "raw_html_witness2_sha256": W2_RAW_SHA,
        "primary_html_to_section_replay_verified": True,
        "secondary_html_to_section_replay_verified": second_conversion,
        "secondary_extractor": (W2_EXTRACT_VERSION if second_conversion else None),
        "secondary_section_pin_origin": "OPERATOR_SUPPLIED_INDEPENDENT_ANCHOR",
        "witness_urls": [W1_URL, W2_URL],
        "comparison_scope": "TWO_PINNED_SECTION_EXPORTS_ONLY",
        "full_witness_comparison_qualified": False,
        "zero_lexical_difference_certified": False,
        "source_text_included": False,
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for k in ("primary-html", "primary-export", "primary-manifest",
              "primary-section", "secondary-html", "secondary-section",
              "report"):
        p.add_argument("--" + k, required=True, type=Path)
    p.add_argument("--secondary-section-sha256", required=True)
    p.add_argument("--require-secondary-extraction", action="store_true",
                   help="Reproduce the exact W2 section from the separately pinned W2 raw HTML")
    a = p.parse_args()
    try:
        inputs = (a.primary_html, a.primary_export, a.primary_manifest,
                  a.primary_section, a.secondary_html, a.secondary_section)
        if not all(f.is_file() for f in inputs):
            data, code = {
                "status": "PENDING_PRIVATE_WITNESS_FILES",
                "full_witness_comparison_qualified": False,
            }, 3
        else:
            data = compare_captured_witnesses(
                *inputs, a.secondary_section_sha256,
                verify_secondary_extraction=a.require_secondary_extraction,
            )
            code = 0
    except (OSError, ValueError, UnicodeError) as exc:
        data, code = {
            "status": "FAIL",
            "reason_code": type(exc).__name__,
            "full_witness_comparison_qualified": False,
        }, 1
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8")
    print(json.dumps({"status": data["status"], "report": str(a.report)},
                     ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
