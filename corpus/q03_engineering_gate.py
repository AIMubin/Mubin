"""Q0.3 internal engineering *data replay*, read-only and fail-closed.

No religious, edition, canonical Quran, or redistribution approval is implied.
Complete engineering qualification also needs independently checked current CI.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from corpus.audit_linked import audit
from corpus.audit_tafsir_upstream import compare, FLAGGED
from corpus.import_tafsircenter import PIN, sha
from corpus.query import get_ayah

LINKED_SHA256 = "a1bd1811ab1b3a4a0373b6499f916f8c379df64ad77fbaf1988e08d34a1814a0"
EXPECTED_MARKUP_ONLY_TABARY = FLAGGED["tabary"]
EXPECTED_CUTOFF_BAGHAWY = FLAGGED["baghawy"]


def replay(linked: Path, original: Path | None = None,
           *, linked_sha256: str = LINKED_SHA256,
           source_sha256: str = PIN) -> dict:
    """Check pinned real-data invariants; source is mandatory for full PASS.

    Hash and content comparison operate on the source path in read-only SQLite
    mode. Synthetic tests may inject fixture-specific expected hashes; the CLI
    always uses the production pins.
    """
    linked = Path(linked)
    original = Path(original) if original is not None else None
    findings = {}

    def check(name, passed, detail):
        findings[name] = {"status": "PASS" if passed else "FAIL", "detail": detail}

    actual_linked_hash = sha(linked) if linked.is_file() else None
    check("pinned_linked_database", actual_linked_hash == linked_sha256,
          {"observed_sha256": actual_linked_hash, "expected_sha256": linked_sha256})
    if actual_linked_hash != linked_sha256:
        return _result(findings)

    coverage = audit(linked)
    check("linked_structure", coverage["structural_audit_passed"],
          {"verses": coverage["verse_count"], "tafsir_sources": coverage["tafsir_counts"],
           "issues": coverage["issues"]})

    connection = sqlite3.connect(linked.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        connection.execute("PRAGMA query_only=ON")
        slash_rows, slash_chars = connection.execute(
            "SELECT COUNT(*), COALESCE(SUM(LENGTH(text)-LENGTH(REPLACE(text,'/',''))),0) "
            "FROM verses WHERE INSTR(text,'/')>0"
        ).fetchone()
        check("derived_slash_quarantine_baseline",
              (slash_rows, slash_chars) == (364, 371),
              {"affected_derived_verses": slash_rows, "slash_characters": slash_chars,
               "canonical_display_authorized": False})
        truncations = set(connection.execute(
            "SELECT sura,aya FROM tafsirs WHERE source='baghawy' AND LENGTH(text)=32767"
        ).fetchall())
        check("baghawy_32767_quarantine_baseline",
              truncations == EXPECTED_CUTOFF_BAGHAWY,
              {"actual_case_ids": sorted(f"{s}:{a}" for s, a in truncations)})
        markup = set(connection.execute(
            "SELECT sura,aya FROM tafsirs WHERE source='tabary' AND TRIM(text)='<br>'"
        ).fetchall())
        check("tabary_markup_only_baseline",
              markup == EXPECTED_MARKUP_ONLY_TABARY,
              {"actual_case_ids": sorted(f"{s}:{a}" for s, a in markup)})
    finally:
        connection.close()

    held = []
    for sura, aya in sorted(EXPECTED_CUTOFF_BAGHAWY):
        entry = next(
            item for item in get_ayah(linked, sura, aya)["tafsirs"]
            if item["source_id"] == "baghawy"
        )
        held.append(
            entry["displayable"] is False
            and entry["text"] is None
            and entry["display_text"] is None
            and entry["display_status"] == "WITHHELD_PENDING_EDITORIAL_VERIFICATION"
            and entry["scholarly_verification"] is False
        )
    check("baghawy_read_path_quarantine", all(held),
          {"cases_checked": len(held), "all_suppressed": all(held)})

    hidden = []
    for sura, aya in sorted(EXPECTED_MARKUP_ONLY_TABARY):
        row = next(
            item for item in get_ayah(linked, sura, aya)["tafsirs"]
            if item["source_id"] == "tabary"
        )
        hidden.append(row["text"] is None and row["displayable"] is False)
    check("tabary_markup_not_presented_as_text", all(hidden),
          {"cases_checked": len(hidden), "all_suppressed": all(hidden)})

    normal = get_ayah(linked, 2, 21)
    displayable_other_sources = {
        row["source_id"] for row in normal["tafsirs"] if row["displayable"]
    }
    check("default_quran_and_healthy_tafsir_read_path",
          normal["text"] is None
          and normal["text_classification"] == "REFERENCE_REQUIRED_NO_QURAN_TEXT"
          and {"tabary", "katheer", "saadi", "moyassar"}.issubset(displayable_other_sources),
          {"canonical_quran_text_exposed": normal["text"] is not None,
           "other_tafsir_sources_displayable": sorted(displayable_other_sources)})

    if original is None:
        findings["upstream_verbatim_comparison"] = {
            "status": "PENDING", "detail": "Original Tafsir Center SQLite must be supplied locally"
        }
    else:
        observed_source = sha(original) if original.is_file() else None
        if observed_source != source_sha256:
            check("upstream_verbatim_comparison", False,
                  {"source_sha256": observed_source, "expected_sha256": source_sha256})
        else:
            try:
                comparison = compare(original, linked, source_sha=source_sha256)
                matched = sum(
                    item["identical_source_and_import_rows"]
                    for item in comparison["tafsir_sources"].values()
                )
                check("upstream_verbatim_comparison", matched == 31180,
                      {"matched_source_values": matched,
                       "source_sha256": observed_source,
                       "scholarly_verified": False})
            except (ValueError, sqlite3.Error, OSError) as exc:
                check("upstream_verbatim_comparison", False,
                      {"error_type": type(exc).__name__,
                       "note": "Source comparison failed; do not promote data gate"})
    return _result(findings)


def _result(findings):
    failed = sorted(name for name, entry in findings.items() if entry["status"] == "FAIL")
    pending = sorted(name for name, entry in findings.items() if entry["status"] == "PENDING")
    passed = sorted(name for name, entry in findings.items() if entry["status"] == "PASS")
    return {
        "milestone": "Q0.3",
        "status": "FAIL" if failed else "PENDING_UPSTREAM" if pending else "DATA_REPLAY_PASS",
        "engineering_data_gate_passed": not failed and not pending,
        "engineering_milestone_qualified_by_this_tool": False,
        "requires_current_cross_os_ci": True,
        "scholarly_verified": False,
        "source_edition_verified": False,
        "canonical_quran_verified": False,
        "redistribution_approved": False,
        "check_count": len(findings),
        "checks_passed": passed, "checks_failed": failed, "checks_pending": pending,
        "checks": findings,
        "note": "Read-only, pinned-source technical data validation, not a scholarly or content-publication release.",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--linked", type=Path, required=True)
    parser.add_argument("--source", type=Path, help="Original Tafsir Center pinned quran.db")
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    result = replay(args.linked, args.source)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8")
    print(json.dumps({key: value for key, value in result.items() if key != "checks"},
                     ensure_ascii=False, indent=2))
    return 0 if result["status"] == "DATA_REPLAY_PASS" else 3 if result["status"] == "PENDING_UPSTREAM" else 1


if __name__ == "__main__":
    raise SystemExit(main())
