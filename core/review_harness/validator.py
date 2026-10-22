"""Bounded offline review-packet evaluator.

No model is invoked here.  Reviewer envelopes and CI results are untrusted
operator-provided claims, NEVER independently authenticated attestations.
The evaluator does not merge code, grant source rights or promote scholarly rules.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

_ROOT = Path(__file__).resolve().parents[2]
_SCHEMA = json.loads((_ROOT / "schemas/review-harness-v01.schema.json").read_text(encoding="utf-8"))
Draft202012Validator.check_schema(_SCHEMA)
_VALIDATOR = Draft202012Validator(_SCHEMA)
_CHANNELS = ("code_security", "source_attribution", "methodology_falsifier")
_REQUIRED_CHECKS = frozenset(("unit_tests", "negative_tests", "schema_validation"))
_SEVERITIES = {"info": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
_IMPACT_MIN_TIER = {
    "documentation": 0,
    "code_change": 1,
    "security_boundary": 2,
    "source_attribution": 2,
    "external_source": 2,
    "religious_reasoning": 2,
    "source_rights": 3,
    "real_human_identity": 3,
    "authoritative_scholarly_decision": 3,
    "frozen_holdout": 3,
    "release_action": 3,
}
_SHA = re.compile(r"[a-f0-9]{40}\Z")
_RUN_URL = re.compile(r"https://github[.]com/AIMubin/Mubin/actions/runs/[0-9]+\Z")
_ATTEMPT = re.compile(r"[a-z0-9_-]{3,40}\Z")
_BAD_CODEPOINTS = {0x200B, 0x200C, 0x200D, 0x2060, 0xFEFF}


def _safe_plain_tree(value: Any, *, budget: int = 12000) -> bool:
    """Reject aliases, cycles, subclassed objects and unsafe Unicode.

    Iterative so malformed programmatic callers cannot consume Python's stack.
    Scalar count, string lengths, and nesting are bounded before jsonschema.
    """
    stack: list[tuple[Any, int]] = [(value, 0)]
    seen: set[int] = set()
    n = 0
    while stack:
        obj, depth = stack.pop()
        n += 1
        if n > budget or depth > 24:
            return False
        if type(obj) in (dict, list):
            if id(obj) in seen:
                return False
            seen.add(id(obj))
            if type(obj) is dict:
                if len(obj) > 100:
                    return False
                stack.extend((v, depth+1) for v in obj.values())
                stack.extend((k, depth+1) for k in obj.keys())
            else:
                if len(obj) > 100:
                    return False
                stack.extend((v, depth+1) for v in obj)
        elif type(obj) is str:
            if len(obj) > 16000:
                return False
            for c in obj:
                code = ord(c)
                if 0xD800 <= code <= 0xDFFF or code in _BAD_CODEPOINTS or (
                    code < 32 and c not in "\n\t\r"
                ):
                    return False
        elif type(obj) not in (bool, int, float, type(None)):
            return False
        elif type(obj) is float:
            # IEEE nonfinite is prohibited even for direct non-JSON calls.
            if not (-float('inf') < obj < float('inf')):
                return False
    return True


def _safe_path(path: str) -> bool:
    return (type(path) is str and len(path) <= 200 and bool(path)
            and not path.startswith(("/", "\\"))
            and "\\" not in path and "//" not in path
            and all(part not in ("", ".", "..") for part in path.split("/"))
            and not any(ord(c) < 32 or 0x7F <= ord(c) <= 0x9F or 0x202A <= ord(c) <= 0x202E for c in path))


def _path_tier(path: str) -> int:
    if (path == "VERSION.yaml" or path == "docs/REVIEW_POLICY.md"
        or path.startswith("engines/hadith/qualification/H3.9.2/")
        or path.startswith(".github/workflows/h392-")):
        return 3
    if (path.startswith(("engines/", "core/provenance/", "core/source_authority/",
                             "core/review_harness/", "schemas/review-harness", ".github/"))):
        return 2
    if path.startswith(("core/", "schemas/", "research/", "evaluation/")):
        return 1
    if path.endswith((".md", ".txt")) and path.startswith("docs/"):
        return 0
    return 2  # Unknown path classification is intentionally conservative.


def inferred_tier(packet: dict[str, Any]) -> int:
    candidate = packet["candidate"]
    return max([_path_tier(p) for p in candidate["changed_paths"]] +
               [_IMPACT_MIN_TIER[tag] for tag in candidate["impact_tags"]])


def validate_packet(packet: Any) -> list[str]:
    if type(packet) is not dict:
        return ["invalid:plain_object_required"]
    if not _safe_plain_tree(packet):
        return ["invalid:untrusted_or_oversized_tree"]
    errors = []
    try:
        for e in _VALIDATOR.iter_errors(packet):
            p = "/".join(map(str, e.absolute_path))[:120]
            errors.append(f"schema:{p}:{e.validator}")
            if len(errors) >= 20:
                break
    except (RecursionError, ValueError, TypeError, OverflowError):
        return ["invalid:schema_error"]
    if errors:
        return sorted(set(errors))
    cand = packet["candidate"]
    paths = cand["changed_paths"]
    if len(paths) != len(set(paths)) or not all(map(_safe_path, paths)):
        return ["invalid:unsafe_or_duplicate_path"]
    if not _SHA.fullmatch(cand["base_sha"]) or not _SHA.fullmatch(cand["head_sha"]):
        return ["invalid:noncanonical_commit_identity"]
    if cand["base_sha"] == cand["head_sha"]:
        return ["invalid:unchanged_candidate_sha"]
    if len(cand["impact_tags"]) != len(set(cand["impact_tags"])):
        return ["invalid:duplicate_impact_tags"]
    for check in packet["deterministic_checks"]:
        if (not _SHA.fullmatch(check["target_sha"])
                or not _RUN_URL.fullmatch(check["claimed_run_url"])):
            return ["invalid:noncanonical_check_identity_or_url"]
        if check["target_sha"] != cand["head_sha"]:
            return ["invalid:stale_deterministic_check_sha"]
    names = [c["check_id"] for c in packet["deterministic_checks"]]
    if len(names) != len(set(names)):
        return ["invalid:duplicate_deterministic_check"]
    channels = [r["channel"] for r in packet["review_attempts"]]
    if len(channels) != len(set(channels)):
        return ["invalid:duplicate_review_channel"]
    attempt_ids = [r["attempt_id"] for r in packet["review_attempts"]]
    if len(attempt_ids) != len(set(attempt_ids)):
        return ["invalid:duplicate_attempt_id"]
    for review in packet["review_attempts"]:
        if (not _SHA.fullmatch(review["target_sha"])
                or not _ATTEMPT.fullmatch(review["attempt_id"])):
            return ["invalid:noncanonical_attempt_identity"]
        if review["target_sha"] != cand["head_sha"]:
            return ["invalid:stale_review_head_sha"]
        findings = review["findings"]
        if len({f["finding_id"] for f in findings}) != len(findings):
            return ["invalid:duplicate_finding_id"]
        if review["verdict"] == "pass" and findings:
            return ["invalid:pass_cannot_have_findings"]
        if review["verdict"] == "fail" and not findings:
            return ["invalid:fail_must_name_finding"]
    return []


def build_review_plan(packet: Any) -> dict[str, Any]:
    """Create structured tasks for external reviewers; does NOT execute agents."""
    issues = validate_packet(packet)
    if issues:
        return {"valid_metadata": False, "errors": issues, "review_tasks": [],
                "eligible_for_auto_merge": False}
    cand = packet["candidate"]
    return {
        "valid_metadata": True, "head_sha": cand["head_sha"],
        "inferred_tier": f"T{inferred_tier(packet)}",
        "tasks": [
            {"channel": "code_security", "target_sha": cand["head_sha"],
             "instruction": "Inspect code/schema/CLI/CI security invariants and return reproducible counterexamples; do not trust submitted check results."},
            {"channel": "source_attribution", "target_sha": cand["head_sha"],
             "instruction": "Inspect source provenance, author/editor speaker roles, rights and protected holdouts. Mark unknown facts unknown."},
            {"channel": "methodology_falsifier", "target_sha": cand["head_sha"],
             "instruction": "Challenge premises, defeaters, methodological scope and abstention. Create independent negative cases."},
        ],
        "agent_invocations_performed": 0,
        "reviewer_identity_verified": False,
        "eligible_for_auto_merge": False,
        "notice": "Plan only. Execute agents externally in isolated contexts; inputs are untrusted and no human review is implied.",
    }


def assess_packet(packet: Any) -> dict[str, Any]:
    errors = validate_packet(packet)
    report: dict[str, Any] = {
        "scope": "untrusted_review_intake_and_structural_reconciliation_only",
        "valid_metadata": not errors,
        "errors": errors,
        "inferred_tier": None,
        "disposition": "INVALID_PACKET" if errors else "NEEDS_EVIDENCE",
        "missing_channels": list(_CHANNELS),
        "check_failures_reported": [],
        "findings_reported": [],
        "review_disagreement": False,
        "packet_sha256": None,
        "ci_head_verified": False,
        "reviewer_identity_verified": False,
        "independent_execution_verified": False,
        "source_authenticity_verified": False,
        "rights_verified": False,
        "scholarly_authority_verified": False,
        "human_review_performed": False,
        "h392_gold_eligible": False,
        "eligible_for_engine": False,
        "eligible_for_release": False,
        "eligible_for_auto_merge": False,
        "claim_only_pass": False,
        "agent_invocations_performed": 0,
    }
    if errors:
        return report
    candidate = packet["candidate"]
    tier = inferred_tier(packet)
    report["inferred_tier"] = f"T{tier}"
    review_by_channel = {r["channel"]: r for r in packet["review_attempts"]}
    report["missing_channels"] = [c for c in _CHANNELS if c not in review_by_channel]
    checks = {c["check_id"]: c for c in packet["deterministic_checks"]}
    report["missing_checks"] = sorted(_REQUIRED_CHECKS - checks.keys())
    report["check_failures_reported"] = sorted(
        name for name, c in checks.items() if c["result"] == "fail")
    findings = [f for r in packet["review_attempts"] for f in r["findings"]]
    # This is a summary of UNVERIFIED SUBMISSIONS, not reproducibility proof.
    report["findings_reported"] = sorted(set(f["category"] for f in findings))
    verdicts = {r["verdict"] for r in packet["review_attempts"]}
    report["review_disagreement"] = len(verdicts) > 1
    canon = json.dumps(packet, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":"), allow_nan=False).encode("utf-8", "strict")
    report["packet_sha256"] = hashlib.sha256(canon).hexdigest()
    critical_findings = any(_SEVERITIES[f["severity"]] >= 3 for f in findings)
    if tier == 3 or critical_findings or report["review_disagreement"]:
        report["disposition"] = "ESCALATE_RISK"
    elif report["check_failures_reported"] or "fail" in verdicts:
        report["disposition"] = "FAIL_REPORTED"
    elif (report["missing_channels"] or report["missing_checks"]
          or any(check["result"] != "pass" for check in checks.values())
          or "abstain" in verdicts):
        report["disposition"] = "NEEDS_EVIDENCE"
    else:
        # No verification of CI, model independence or review execution exists.
        report["disposition"] = "PASS_SCOPED_UNVERIFIED"
        report["claim_only_pass"] = True
    return report
