"""Read-only merge readiness evidence for the four stacked Quran PRs.

The output is advisory, never an authorization to merge or scholarly/source
attestation. Pure assessment accepts UNTRUSTED snapshots for deterministic tests.
Only live() fetches GitHub API responses, and no source text or secrets are logged.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from typing import Any
import urllib.error
import urllib.request

REPO = "AIMubin/Mubin"
CHAIN = (73, 74, 75, 76)
EXPECTED = {
    73: ("Mubin P0 inference foundation", "Mubin Quran Q0.1 offline snapshot lookup"),
    74: ("Mubin P0 inference foundation", "Mubin Quran Q0.1 offline snapshot lookup",
         "Mubin Quran Q0.1b pinned raw mirror candidate"),
    75: ("Mubin P0 inference foundation", "Mubin Quran Q0.1 offline snapshot lookup",
         "Mubin Quran Q0.1c loopback reader offline"),
    76: ("Mubin P0 inference foundation", "Mubin Quran Q0.1 offline snapshot lookup",
         "Mubin Quran Q0.1d publisher-candidate comparison (unverified)",
         "Mubin Quran actual Chrome browser smoke"),
}
_SHA = re.compile(r"[a-f0-9]{40}")
_MAX_REPLY = 3 * 1024 * 1024

class ReadinessError(ValueError):
    """Cannot safely assess the current published PR chain."""


def _sha(value: Any) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _nested(obj: Any, *path: str) -> Any:
    for key in path:
        if type(obj) is not dict:
            return None
        obj = obj.get(key)
    return obj


def assess_chain(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Classify *asserted* provider data; NOT proof of live API provenance."""
    blockers: list[str] = []
    qa_blockers: list[str] = []
    review_advisories: list[str] = []
    if type(snapshot) is not dict:
        raise ReadinessError("invalid_snapshot")
    main = snapshot.get("main")
    base_sha = _nested(main, "commit", "sha")
    if type(_nested(main, "protected")) is not bool or not main["protected"]:
        blockers.append("MAIN_NOT_PROTECTED")
    if not _sha(base_sha):
        blockers.append("MAIN_SHA_UNAVAILABLE")
    prev = base_sha
    for n in CHAIN:
        num = str(n)
        pr = _nested(snapshot, "prs", n)
        head = _nested(pr, "head", "sha")
        actual_base = _nested(pr, "base", "sha")
        if (type(pr) is not dict or pr.get("number") != n or
            pr.get("state") != "open" or not _sha(head) or not _sha(actual_base)):
            code = f"PR{n}_METADATA_INVALID"
            blockers.append(code); qa_blockers.append(code)
            prev = head
            continue
        if _nested(pr, "head", "repo", "full_name") != REPO or _nested(pr, "base", "repo", "full_name") != REPO:
            code = f"PR{n}_FOREIGN_REPO"
            blockers.append(code); qa_blockers.append(code)
        if actual_base != prev:
            code = f"PR{n}_PARENT_MISMATCH"
            blockers.append(code); qa_blockers.append(code)
        if pr.get("draft") is not False:
            blockers.append(f"PR{n}_DRAFT")
        comparison = _nested(snapshot, "comparisons", n)
        if (type(comparison) is not dict or comparison.get("status") != "ahead" or
            type(comparison.get("behind_by")) is not int or comparison["behind_by"] != 0 or
            type(comparison.get("ahead_by")) is not int or comparison["ahead_by"] < 1):
            code = f"PR{n}_NOT_FAST_FORWARD"
            blockers.append(code); qa_blockers.append(code)
        runs = _nested(snapshot, "runs", n)
        if type(runs) is not list:
            runs = []
        selected = [run for run in runs if type(run) is dict and
                    run.get("name") in EXPECTED[n]]
        if len(selected) != len(EXPECTED[n]) or len({run.get("name") for run in selected}) != len(selected):
            code = f"PR{n}_CHECK_AMBIGUOUS"
            blockers.append(code); qa_blockers.append(code)
        else:
            if (any(run.get("head_sha") != head or run.get("event") != "pull_request" or
                   run.get("status") != "completed" or run.get("conclusion") != "success"
                   for run in selected)):
                code = f"PR{n}_CHECK_INCOMPLETE"
                blockers.append(code); qa_blockers.append(code)
        reviews = _nested(snapshot, "reviews", n)
        author = _nested(pr, "user", "login")
        if type(reviews) is not list:
            reviews = []
        if not any(type(review) is dict and review.get("state") == "APPROVED" and
                   review.get("commit_id") == head and
                   type(_nested(review, "user", "login")) is str and
                   _nested(review, "user", "login") != author
                   for review in reviews):
            review_advisories.append(f"PR{n}_NO_EXACT_HEAD_CODE_REVIEW")
        prev = head
    # Only an advisory on an asserted snapshot; NOT a trusted external release gate.
    return {
        "contract": "mubin-quran-merge-readiness-v1",
        "data_source": "provided_snapshot_untrusted",
        "checked_pr_numbers": list(CHAIN),
        "engineering_qa_passed": not qa_blockers,
        "merge_ready": False,
        "conditionally_merge_ready": not blockers,
        "blockers": sorted(set(blockers)),
        "review_advisories": sorted(set(review_advisories)),
        "mandatory_independent_code_review_assumed": False,
        "eligible_for_auto_merge": False,
        "merges_performed": 0,
        "quran_source_authenticated": False,
        "scholarly_approval_verified": False,
        "rights_verified": False,
        "note": "Advisory only; review records are code metadata, not scientific certification.",
    }


def _get_api(path: str, token: str | None) -> Any:
    """Only allow predetermined public GitHub REST repository paths."""
    if (type(path) is not str or not path.startswith("/") or
        "//" in path or "/../" in path or "/./" in path or
        path.endswith("/..") or path.endswith("/.") or chr(92) in path or
        not re.fullmatch(r"/[a-zA-Z0-9_/?.=&-]+", path)):
        raise ReadinessError("unsafe_api_path")
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {"Accept": "application/vnd.github+json",
               "X-GitHub-Api-Version": "2022-11-28",
               "User-Agent": "Mubin-Quran-Readiness-1"}
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as response:
            if response.geturl() != url:
                raise ReadinessError("unexpected_api_redirect")
            blob = response.read(_MAX_REPLY + 1)
        if not 0 < len(blob) <= _MAX_REPLY:
            raise ReadinessError("api_response_missing_or_unbounded")
        def pairs(v):
            d = {}
            for k, val in v:
                if k in d:
                    raise ReadinessError("duplicate_api_json_key")
                d[k] = val
            return d
        def nonfinite(_):
            raise ReadinessError("nonfinite_api_json")
        return json.loads(blob.decode("utf-8", "strict"),
                          object_pairs_hook=pairs, parse_constant=nonfinite)
    except (OSError, ValueError, UnicodeError, RecursionError, OverflowError) as exc:
        raise ReadinessError("github_api_unavailable_or_invalid") from exc


def fetch_live(token: str | None = None) -> dict[str, Any]:
    """Gather authoritative API responses; no PR edits, no approval or merge."""
    main = _get_api("/branches/main", token)
    out: dict[str, Any] = {"main": main, "prs": {}, "runs": {},
                           "reviews": {}, "comparisons": {}}
    for n in CHAIN:
        pr = _get_api(f"/pulls/{n}", token)
        head = _nested(pr, "head", "sha")
        base = _nested(pr, "base", "sha")
        if not _sha(head) or not _sha(base):
            raise ReadinessError("missing_current_pr_ref")
        out["prs"][n] = pr
        actions = _get_api(f"/actions/runs?head_sha={head}&per_page=100", token)
        if (type(actions) is not dict or type(actions.get("total_count")) is not int
            or actions["total_count"] > 100 or type(actions.get("workflow_runs")) is not list):
            raise ReadinessError("incomplete_run_listing")
        out["runs"][n] = actions["workflow_runs"]
        reviews = _get_api(f"/pulls/{n}/reviews?per_page=100", token)
        if type(reviews) is not list or len(reviews) >= 100:
            raise ReadinessError("incomplete_review_listing")
        out["reviews"][n] = reviews
        out["comparisons"][n] = _get_api(f"/compare/{base}...{head}", token)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Read-only stacked Quran PR merge-readiness advisory")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        payload = fetch_live(os.environ.get("GITHUB_TOKEN") or None)
        report = assess_chain(payload)
        # This label applies only to the synchronous, host-fixed live adapter.
        report["data_source"] = "github_rest_read_only"
        print(json.dumps(report, sort_keys=True, ensure_ascii=False))
        return 0  # Informational; blockers must not stall all unrelated CI.
    except ReadinessError as exc:
        print(json.dumps({"contract": "mubin-quran-merge-readiness-v1",
                          "data_source": "unavailable",
                          "engineering_qa_passed": False,
                          "merge_ready": False,
                          "eligible_for_auto_merge": False,
                          "error": str(exc)},
                         sort_keys=True))
        return 2


if __name__ == "__main__":
    sys.exit(main())
