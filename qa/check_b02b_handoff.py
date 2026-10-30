"""Offline GitHub-safe B02-B metadata consistency gate.

The private vault source bytes/reviewer receipts are NOT available here.
A passing check asserts internal research handoff consistency ONLY.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator
from core.orchestration.evidence_projection import verify_redacted_projection

FILE_NAMES = (
    "task.yaml", "source-manifest.json", "evidence-receipt.json",
    "test-report.json", "handoff.md", "p0-projection-b02b-6-145-v1.json",
    "b02c-kernel-receipt-6-145-v1.json", "b02c-diagnostic-run-v1.json",
)
EXPECTED_ENGINES = frozenset(("quran", "tafsir", "hadith", "usul", "fiqh"))


class HandoffError(ValueError):
    """Stable non-content reporting only."""


def need(ok, code):
    if not ok:
        raise HandoffError(code)


def validate(root: Path):
    root = Path(root)
    directory = root / "research/b02b"
    need(directory.is_dir(), "B02B_PACKAGE_MISSING")
    need(all((directory / name).is_file() for name in FILE_NAMES),
         "B02B_FILES_INCOMPLETE")
    task = (directory / "task.yaml").read_text(encoding="utf-8-sig")
    handoff = (directory / "handoff.md").read_text(encoding="utf-8-sig")
    need(re.search(r"(?m)^preserved_candidate\s*:", task) is not None,
         "B02B_TASK_PRESERVED_CANDIDATE_REQUIRED")
    need(re.search(r"(?m)^selected_case\s*:", task) is None,
         "B02B_TASK_FALSE_SELECTED_CASE")
    need("REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR" in task,
         "B02B_TASK_SELECTION_VERDICT_MISSING")
    need("UNDETERMINED" in handoff and "PARTIAL" in handoff,
         "B02B_HANDOFF_ABSTENTION_MISSING")

    def load(name):
        data = json.loads((directory / name).read_text(encoding="utf-8-sig"))
        need(type(data) is dict, "B02B_ROOT_OBJECT_EXPECTED")
        return data
    source, evidence, report, projection, kernel, diagnostic = [
        load(name) for name in FILE_NAMES
        if name.endswith(".json")
    ]
    need(source.get("case_id") == evidence.get("case_id"),
         "B02B_CASE_ID_MISMATCH")
    candidate = evidence.get("preserved_candidate", {})
    need(type(candidate) is dict and candidate.get("selected") is False,
         "B02B_SELECTION_NOT_REFUSED")
    gate = evidence.get("strict_gate_v3", {})
    need(type(gate) is dict and
         gate.get("verdict") == "REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR"
         and gate.get("no_bar_lowered") is True,
         "B02B_STRICT_GATE_FAILURE")
    need(evidence.get("scholarly_verified") is False and
         evidence.get("juristic_inference_allowed") is False and
         evidence.get("text_included") is False,
         "B02B_FALSE_AUTHORITY_CLAIM")

    totals, suites = report.get("totals", {}), report.get("suites", [])
    need(type(totals) is dict and type(suites) is list
         and len(suites) >= 1 and all(type(s) is dict for s in suites),
         "B02B_TEST_REPORT_INVALID")
    for key in ("tests_run", "passed", "skipped", "failed", "suites"):
        need(type(totals.get(key)) is int and totals[key] >= 0,
             "B02B_TEST_COUNT_INVALID")
    need(totals["suites"] == len(suites) and
         totals["tests_run"] == totals["passed"] + totals["skipped"] + totals["failed"] and
         totals["tests_run"] == sum(s.get("ran", -1) for s in suites) and
         totals["passed"] == sum(s.get("passed", -1) for s in suites) and
         totals["skipped"] == sum(s.get("skipped", -1) for s in suites) and
         totals["failed"] == 0 and
         all(s.get("exit_code") == 0 for s in suites),
         "B02B_TEST_TOTALS_INCONSISTENT")
    need(report.get("engineering_test_gate_passed") is True and
         report.get("strict_selection_gate_passed") is False,
         "B02B_TEST_GATE_SCOPE_AMBIGUOUS")

    need(verify_redacted_projection(projection), "B02B_PROJECTION_INVALID")
    need(projection.get("status") == "P0_STRUCTURALLY_VALID" and
         projection.get("engine_bindings") == [],
         "B02B_PROJECTION_SCOPE_MISREPRESENTED")
    p0 = evidence.get("p0_projection_b02a", {})
    need(type(p0) is dict and
         p0.get("private_bundle_sha256") == projection.get("private_bundle_sha256"),
         "B02B_P0_COMMITMENT_MISMATCH")
    need(not re.search(r"[\u0600-\u06ff]", json.dumps(projection, ensure_ascii=False)),
         "B02B_PROJECTION_CONTAINS_ARABIC")

    need(kernel.get("contract_version") == "engine-contract/1.0"
         and kernel.get("status") == "PARTIAL"
         and kernel.get("synthetic_acceptance") is False,
         "B02B_KERNEL_STATE_MISMATCH")
    entries = kernel.get("nodes", [])
    need(type(entries) is list and len(entries) == 5,
         "B02B_KERNEL_NODE_COUNT_MISMATCH")
    result_schema = json.loads(
        (root / "schemas/engine-result-v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(result_schema)
    names, ids = set(), set()
    by_id = {}
    for entry in entries:
        need(type(entry) is dict and
             type(entry.get("result")) is dict and
             type(entry.get("node_id")) is str,
             "B02B_KERNEL_NODE_INVALID")
        result = entry["result"]
        need(not list(validator.iter_errors(result)),
             "B02B_ENGINE_RESULT_SCHEMA_INVALID")
        need(result["request_id"] == entry["node_id"]
             and result["trace_id"] == entry["node_id"]
             and result["provenance"]["snapshot_ids"] == kernel.get("source_snapshot_ids")
             and entry["node_id"] not in ids
             and result["engine"] not in names,
             "B02B_KERNEL_IDENTITY_OR_PIN_MISMATCH")
        names.add(result["engine"])
        ids.add(entry["node_id"])
        by_id[entry["node_id"]] = result
    need(names == EXPECTED_ENGINES, "B02B_ENGINE_SET_INCOMPLETE")
    fiqh = next(r for r in by_id.values() if r["engine"] == "fiqh")
    hadith = next(r for r in by_id.values() if r["engine"] == "hadith")
    usul = next(r for r in by_id.values() if r["engine"] == "usul")
    need(fiqh["status"] == "UNDETERMINED" and fiqh["findings"] == []
         and "OPINION_SOURCE_NOT_IN_UPSTREAM_EVIDENCE" in fiqh["uncertainties"],
         "B02B_FIQH_FALSE_PROMOTION")
    need(hadith["status"] == "OK"
         and all(x.get("candidate_only") is True and
                 x.get("grade_assigned") is False for x in hadith["findings"]),
         "B02B_HADITH_SCOPE_INVALID")
    need(usul["evidence_refs"] == []
         and all(x.get("scholarly_verified") is False for x in usul["findings"]),
         "B02B_USUL_SCOPE_INVALID")
    need(kernel.get("case_id") == diagnostic.get("kernel_case_id")
         and kernel.get("status") == diagnostic.get("kernel_status")
         and diagnostic.get("kernel_receipt") == "b02c-kernel-receipt-6-145-v1.json",
         "B02B_DIAGNOSTIC_CASE_MISMATCH")
    summaries = diagnostic.get("kernel_nodes", [])
    need(type(summaries) is list and len(summaries) == len(entries),
         "B02B_DIAGNOSTIC_NODE_COUNT_MISMATCH")
    for item in summaries:
        need(type(item) is dict and item.get("node") in by_id,
             "B02B_DIAGNOSTIC_NODE_INVALID")
        result = by_id[item["node"]]
        need(item.get("status") == result["status"]
             and item.get("engine") == result["engine"]
             and item.get("findings") == len(result["findings"])
             and item.get("evidence_refs") == len(result["evidence_refs"]),
             "B02B_DIAGNOSTIC_NODE_INCONSISTENT")
    claims = diagnostic.get("claims", {})
    need(type(claims) is dict and
         all(claims.get(x) is False for x in (
             "completed_inference_claimed", "selected_case_integration_claimed",
             "scholarly_verified", "juristic_inference_allowed"))
         and diagnostic.get("text_included") is False,
         "B02B_DIAGNOSTIC_FALSE_CLAIMS")
    need(evidence.get("b02c_diagnostic_run", {}).get("kernel_status") == "PARTIAL",
         "B02B_DIAGNOSTIC_EVIDENCE_MISMATCH")
    # Historical F0.0 gap is permitted ONLY when explicitly scoped to the old run.
    active_gap = [x for x in evidence.get("gaps_declared", [])
                  if type(x) is dict and x.get("type") == "fiqh_f00_no_engine"]
    need(not active_gap or all(x.get("historical_initial_run") is True
                               for x in active_gap),
         "B02B_STALE_FIQH_GAP_UNSCOPED")
    return {
        "files": len(FILE_NAMES), "engine_nodes": len(entries),
        "p0_nodes": len(projection["nodes"]),
        "p0_edges": len(projection["edges"]),
        "tests_documented": totals["tests_run"], "failed": totals["failed"],
        "strict_selection_gate_passed": False,
        "content_verification": "METADATA_ONLY_PRIVATE_SOURCE_NOT_VERIFIED",
    }


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--if-present", action="store_true")
    ns = parser.parse_args(argv)
    root = Path(ns.root)
    try:
        if ns.if_present and not (root / "research/b02b").exists():
            print("No B02-B handoff in checkout; synthetic tests still required.")
            return 0
        report = validate(root)
    except (HandoffError, ValueError, KeyError, TypeError, OSError) as exc:
        print("B02B HANDOFF FAIL: " +
              (str(exc) if isinstance(exc, HandoffError) else "INVALID_INPUT"))
        return 1
    print("B02B HANDOFF METADATA VALID: " + json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
