"""B02-C.2 six-node research replay consistency, NOT source-custody verification.

No private Waraqat passages or AI reviewer receipts are accessible to CI.
Verification of hashes here is metadata-internal, not recomputation over the
original private corpus. Never interpret a pass as semantic or juristic proof.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

from jsonschema import Draft202012Validator

FROM = "b02c2-kernel-receipt-6-145-v1.json"
DIAG = "b02c2-diagnostic-run-v1.json"
HANDOFF = "evidence-receipt.json"
MANIFEST = "source-manifest.json"
EXPECTED = {
    "b02c2.us1": ("usul", "usul-source-bridge/0.1", "OK", 4, 4),
    "b02c2.q1": ("quran", "q01/0.1", "OK", 1, 1),
    "b02c2.t1": ("tafsir", "tafsir-t03/0.1", "OK", 5, 5),
    "b02c2.h1": ("hadith", "hsearch01/0.1", "OK", 23, 23),
    "b02c2.u2": ("usul", "usul-u01/0.1", "OK", 3, 0),
    "b02c2.f1": ("fiqh", "fiqh-f01/0.1", "PARTIAL", 1, 33),
}
SHA256 = re.compile(r"^[a-f0-9]{64}$")


class ReplayError(ValueError):
    pass


def need(condition, code):
    if not condition:
        raise ReplayError(code)


def verify_source_handles(usul, known_source_digests):
    """Check the *published handles* are derived from reported span metadata.

    DOES NOT verify the private source bytes or that the cited scholarly
    statement actually occurs in the source.
    """
    findings = usul["findings"]
    refs = usul["evidence_refs"]
    need(len(findings) == 4 and len(refs) == 4 and len(set(refs)) == 4,
         "B02C2_SOURCE_COUNT")
    derived = set()
    for finding in findings:
        need(type(finding) is dict and
             finding.get("kind") == "USUL_RAW_SOURCE_SPAN"
             and finding.get("source_authenticated") is False
             and finding.get("source_semantics_verified") is False
             and finding.get("opinion_attributed") is False
             and finding.get("synthetic_fixture") is False
             and finding.get("source_text_included") is False,
             "B02C2_SOURCE_NONAUTHORITY")
        full = finding.get("source_sha256")
        span = finding.get("span_sha256")
        start, end = finding.get("start_byte"), finding.get("end_byte")
        need(type(full) is str and type(span) is str and
             SHA256.fullmatch(full) is not None and
             SHA256.fullmatch(span) is not None and
             full in known_source_digests and
             type(start) is int and type(end) is int and
             0 <= start < end and end - start <= 8192 and
             type(finding.get("rule_id")) is str,
             "B02C2_SOURCE_HANDLE_INVALID")
        derived.add(f"ev.usul.{full[:24]}.{start}.{end}.{span[:24]}")
    need(derived == set(refs), "B02C2_SOURCE_HANDLE_DERIVATION")
    need(len({f["source_sha256"] for f in findings}) == 2,
         "B02C2_SOURCE_PIN_COVERAGE")
    need(len({f["rule_id"] for f in findings}) == 2,
         "B02C2_SOURCE_RULE_COVERAGE")


def verify_fiqh(fiqh, source_refs, all_prior_refs, *, case_id):
    need(fiqh["status"] == "PARTIAL" and
         fiqh["uncertainties"] == [
             "USUL_APPLICATION_NOT_EXECUTED",
             "SOURCE_SPAN_MATCH_NOT_OPINION_ATTRIBUTION"] and
         len(fiqh["findings"]) == 1,
         "B02C2_FIQH_NOT_RESEARCH_ONLY")
    research = fiqh["findings"][0]
    need(type(research) is dict and
         research.get("case_id") == case_id and
         research.get("authority") == "RESEARCH_ONLY" and
         research.get("juristic_conclusion") is None and
         research.get("source_claims_verified") is False and
         research.get("opinion_source_attribution_verified") is False and
         research.get("linked_evidence_count") == len(all_prior_refs) and
         len(research.get("opinion_refs", [])) == 2,
         "B02C2_FIQH_FALSE_ATTRIBUTION")
    need(len(set(fiqh["evidence_refs"])) == len(fiqh["evidence_refs"])
         and set(fiqh["evidence_refs"]) == all_prior_refs
         and set(source_refs).issubset(set(fiqh["evidence_refs"])),
         "B02C2_FIQH_REFERENCES_UNBOUND")


def validate(root):
    root = Path(root)
    directory = root / "research/b02b"
    def load(name):
        x = json.loads((directory / name).read_text(encoding="utf-8-sig"))
        need(type(x) is dict, "B02C2_ROOT_INVALID")
        return x
    kernel, diagnostic, evidence, manifest = [load(p) for p in (
        FROM, DIAG, HANDOFF, MANIFEST)]
    need(kernel.get("contract_version") == "engine-contract/1.0"
         and kernel.get("status") == "PARTIAL"
         and kernel.get("synthetic_acceptance") is False
         and kernel.get("case_id") == diagnostic.get("kernel_case_id"),
         "B02C2_KERNEL_SCOPE")
    snapshots = kernel.get("source_snapshot_ids")
    need(type(snapshots) is list and len(snapshots) >= 1,
         "B02C2_SNAPSHOTS_INVALID")
    entries = kernel.get("nodes")
    need(type(entries) is list and len(entries) == len(EXPECTED),
         "B02C2_NODE_COUNT")
    schema = json.loads(
        (root / "schemas/engine-result-v1.schema.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    by_id = {}
    for entry in entries:
        need(type(entry) is dict and type(entry.get("node_id")) is str
             and type(entry.get("result")) is dict,
             "B02C2_RECEIPT_NODE_INVALID")
        node_id, result = entry["node_id"], entry["result"]
        need(node_id not in by_id and node_id in EXPECTED
             and not list(validator.iter_errors(result))
             and result["request_id"] == node_id
             and result["trace_id"] == node_id
             and result["provenance"]["snapshot_ids"] == snapshots
             and result["errors"] == [],
             "B02C2_RESULT_SCHEMA_OR_IDENTITY")
        exp = EXPECTED[node_id]
        need((result["engine"], result["engine_version"], result["status"],
              len(result["findings"]), len(result["evidence_refs"])) == exp,
             "B02C2_NODE_STATUS_OR_COUNTS")
        by_id[node_id] = result
    need(set(by_id) == set(EXPECTED),
         "B02C2_NODE_SET_INVALID")

    source_digests = {
        x["sha256"] for x in manifest.get("sources", [])
        if type(x) is dict and x.get("kind") == "usul_section_extract"
        and type(x.get("sha256")) is str
    }
    need(len(source_digests) == 2, "B02C2_MANIFEST_SOURCES_INVALID")
    usul = by_id["b02c2.us1"]
    verify_source_handles(usul, source_digests)
    need(usul["uncertainties"] ==
         ["SOURCE_BYTE_FIDELITY_ONLY_NO_JURISTIC_ATTRIBUTION"],
         "B02C2_USUL_UNCERTAINTY_MISSING")
    simulation = by_id["b02c2.u2"]
    need(simulation["evidence_refs"] == [] and
         "ONE_STEP_PROPOSITIONAL_SIMULATION_NOT_JURISTIC_REASONING"
         in simulation["uncertainties"] and
         all(f.get("scholarly_verified") is False
             for f in simulation["findings"]),
         "B02C2_SIMULATION_PROMOTION")
    hadith = by_id["b02c2.h1"]
    need("HADITH_IDENTITY_AND_GRADE_NOT_VERIFIED" in hadith["uncertainties"]
         and all(f.get("candidate_only") is True and
                 f.get("grade_assigned") is False
                 for f in hadith["findings"]),
         "B02C2_HADITH_IDENTITY_UNGROUNDED")
    prior = set()
    for key in EXPECTED:
        if key != "b02c2.f1":
            refs = by_id[key]["evidence_refs"]
            need(len(refs) == len(set(refs))
                 and not prior.intersection(refs),
                 "B02C2_PRIOR_EVIDENCE_DUPLICATE")
            prior.update(refs)
    need(len(prior) == 33, "B02C2_PRIOR_EVIDENCE_COUNT")
    verify_fiqh(by_id["b02c2.f1"], usul["evidence_refs"],
                prior, case_id=kernel["case_id"])

    need(diagnostic.get("kernel_status") == "PARTIAL"
         and diagnostic.get("kernel_receipt") == FROM
         and diagnostic.get("kernel_case_id") == kernel["case_id"]
         and len(diagnostic.get("kernel_nodes", [])) == 6,
         "B02C2_DIAGNOSTIC_SCOPE")
    seen = set()
    for summary in diagnostic["kernel_nodes"]:
        need(type(summary) is dict and summary.get("node") in by_id
             and summary["node"] not in seen,
             "B02C2_DIAGNOSTIC_NODE_INVALID")
        seen.add(summary["node"])
        result = by_id[summary["node"]]
        need(summary.get("status") == result["status"]
             and summary.get("engine") == result["engine"]
             and summary.get("findings") == len(result["findings"])
             and summary.get("evidence_refs") == len(result["evidence_refs"])
             and summary.get("uncertainties") == result["uncertainties"],
             "B02C2_DIAGNOSTIC_MISMATCH")
    need(diagnostic.get("closure_criteria", {})
         .get("pinned_usul_refs_inside_kernel_results") is True
         and diagnostic.get("closure_criteria", {})
         .get("fiqh_binding_gap_measurable", {})
         .get("opinion_source_attribution_verified") is False,
         "B02C2_CLOSURE_CLAIM_INVALID")
    need(diagnostic.get("unchanged", {}).get("selection_gate_verdict")
         == "REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR"
         and diagnostic.get("unchanged", {})
         .get("machine_supported_status_is_scholarly") is False
         and diagnostic.get("claims", {}).get("completed_inference_claimed") is False
         and diagnostic.get("claims", {}).get("juristic_inference_allowed") is False,
         "B02C2_SELECTION_OR_AUTHORITY_PROMOTED")
    claim = evidence.get("b02c2_source_bound_replay", {})
    need(claim.get("kernel_status") == "PARTIAL"
         and claim.get("fiqh_binding_result", {})
         .get("status_v2_bound") == "PARTIAL"
         and claim.get("unchanged", {}).get("selection_gate_verdict")
         == "REJECTED_ALL_CANDIDATES_UNDER_FULL_BAR"
         and evidence.get("preserved_candidate", {}).get("selected") is False,
         "B02C2_HANDOFF_INCONSISTENT")
    # The committed record must contain no raw Arabic excerpts or local paths.
    raw = json.dumps({"kernel": kernel, "diagnostic": diagnostic},
                     ensure_ascii=False)
    need(re.search(r"[\u0600-\u06ff]", raw) is None and
         re.search(r"(?:[A-Za-z]:\\|/home/|/Users/)", raw) is None,
         "B02C2_POSSIBLE_PRIVATE_TEXT_LEAK")
    return {"nodes": 6, "source_spans": 4, "linked_evidence": 33,
            "selection_gate_passed": False,
            "scope": "METADATA_INTERNAL_ONLY_NO_PRIVATE_CORPUS_ATTESTATION"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    parser.add_argument("--if-present", action="store_true")
    args = parser.parse_args()
    path = Path(args.root) / "research/b02b" / FROM
    if args.if_present and not path.is_file():
        print("No B02-C.2 receipt; only synthetic negative tests run.")
        return 0
    try:
        report = validate(args.root)
    except (ReplayError, OSError, TypeError, ValueError, KeyError) as exc:
        print("B02C2 METADATA FAIL: " +
              (str(exc) if isinstance(exc, ReplayError) else "INVALID_JSON_OR_SCHEMA"))
        return 1
    print("B02C2 METADATA VALID " + json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
