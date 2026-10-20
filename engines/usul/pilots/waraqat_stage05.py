"""Replay Stage05 lexical search over the privately captured al-Waraqat witness.

Every Stage04 SHA and chapter boundary is frozen independently in the public
metadata-only receipt. This command refuses arbitrary new witness versions and
NEVER outputs source text or search strings. It needs the operator's LOCAL raw
HTML/export/manifest bytes; passing CI on synthetic data is not real replay.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.usul.source_lexical_index import index_and_search, LexicalContractError

RAW_SHA = "66ec33c1825acdf82b3720f89d89aac15aa6e993356c0d90b41e53fe9a2fa044"
EXPORT_SHA = "9ce9de30f1af3ef32b2bf55b0473c9459e0cf530e3b557535744b284c760f4df"
MANIFEST_SHA = "5bf586787dbb9f84d03fc21c62ee32619b66b474c66a6c890aeb813219f853cf"
SECTION_SHA = "20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab"
SECTION = "pilot:waraqat-bab-amr"
RULE = "pilot:rule-amr-default"
EXPECTED_SOURCE_ID = "pilot:waraqat-text-export"
EXPECTED_SOURCE_URL = "https://www.islamicbook.ws/asol/alwrqat.html"


def verify_stage04_receipt(result):
    """Enforce published Stage04 values rather than self-attesting current bytes."""
    checks = [
        (result["snapshot_sha256"] == EXPORT_SHA, "export SHA mismatch"),
        (result["trusted_manifest_sha256"] == MANIFEST_SHA, "manifest SHA mismatch"),
        (result["source_id"] == EXPECTED_SOURCE_ID, "source identity mismatch"),
        (result["source_url"] == EXPECTED_SOURCE_URL, "source URL mismatch"),
        (result["section_id"] == SECTION, "chapter identity mismatch"),
        (result["section_sha256"] == SECTION_SHA, "chapter SHA mismatch"),
        (result["section_start_line"] == 86, "chapter start-line mismatch"),
        (result["section_end_line_exclusive"] == 108, "chapter end-line mismatch"),
        (result["indexed_line_count"] == 22, "chapter line count mismatch"),
        (result["indexed_byte_count"] == 1232, "chapter byte count mismatch"),
        (result["upstream_replay"]["raw_html_sha256"] == RAW_SHA, "raw HTML SHA mismatch"),
        (result["upstream_replay"]["source_export_reproduced_from_html"] is True,
         "raw HTML to text export not replayed"),
    ]
    for success, reason in checks:
        if not success:
            raise LexicalContractError("Stage04 published receipt mismatch: " + reason)
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--raw-html", type=Path, required=True)
    p.add_argument("--source", type=Path, required=True)
    p.add_argument("--manifest", type=Path, required=True)
    p.add_argument("--queries", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    args = p.parse_args()
    try:
        if not all(path.is_file() for path in (args.raw_html, args.source, args.manifest)):
            result, exit_code = {
                "status": "PENDING_PRIVATE_STAGE04_FILES",
                "scholarly_verified": False, "redistribution_approved": False,
            }, 3
        else:
            if not args.queries.is_file() or not 0 < args.queries.stat().st_size <= 65536:
                raise LexicalContractError("missing or oversized private query specification")
            qs = json.loads(args.queries.read_text(encoding="utf-8"))
            technical = index_and_search(
                args.source, args.manifest, MANIFEST_SHA, SECTION, qs,
                raw_html_path=args.raw_html, trusted_raw_html_sha256=RAW_SHA,
            )
            technical = verify_stage04_receipt(technical)
            result, exit_code = {
                **technical, "status": "STAGE05_REAL_SOURCE_LEXICAL_REPLAY_PASS",
                "rule_id": RULE,
                "claim_scope": "STAGE04_DIGITAL_WITNESS_BAB_AMR_LEXICAL_ONLY",
                "semantic_qarinah_verified": False,
                "juristic_ruling_authorized": False,
            }, 0
    except (OSError, ValueError, UnicodeError) as exc:
        result, exit_code = {
            "status": "FAIL", "reason_code": type(exc).__name__,
            "scholarly_verified": False, "redistribution_approved": False,
        }, 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({"status": result["status"],
                      "report": str(args.report),
                      "source_text_reproduced": False}, ensure_ascii=True))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
