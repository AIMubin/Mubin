"""Quran PR readiness v2: read-only, non-authorizing exact-HEAD advisory.

The historical #73->#76 stack was superseded by individual merged/extracted
PRs. This module assesses ONE specified open PR against current main, without
assuming that old branches/PRs are still its parents. No merge/approval writes.
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
CONTRACT = "mubin-quran-pr-readiness-v2"
_SHA = re.compile(r"[0-9a-f]{40}\Z")
_API_PATH = re.compile(r"/[a-zA-Z0-9_/?=&.\-]+\Z")
_MAX_JSON = 3 * 1024 * 1024


class ReadinessError(ValueError):
    """Expose only deterministic status codes (not HTTP/body/private data)."""


def _sha(value: Any) -> bool:
    return type(value) is str and _SHA.fullmatch(value) is not None


def _pr_number(value: Any) -> bool:
    return type(value) is int and 1 <= value <= 999999


def _at(value: Any, *keys: str) -> Any:
    for key in keys:
        if type(value) is not dict:
            return None
        value = value.get(key)
    return value


def assess_pr(snapshot: dict[str, Any], number: int) -> dict[str, Any]:
    """Assess supplied *untrusted* metadata: never grant merge authority."""
    if not _pr_number(number) or type(snapshot) is not dict:
        raise ReadinessError("INVALID_ASSESSMENT_INPUT")

    problems: list[str] = []
    advisories: list[str] = []
    main = snapshot.get("main")
    pr = snapshot.get("pr")
    comparison = snapshot.get("comparison")
    check_listing = snapshot.get("check_listing")
    reviews = snapshot.get("reviews")

    main_sha = _at(main, "commit", "sha")
    head = _at(pr, "head", "sha")
    base_sha = _at(pr, "base", "sha")
    if not _sha(main_sha):
        problems.append("MAIN_SHA_INVALID")
    if type(main) is not dict or main.get("protected") is not True:
        advisories.append("MAIN_BRANCH_PROTECTION_NOT_CONFIRMED")

    if (type(pr) is not dict or pr.get("number") != number or
            pr.get("state") != "open" or not _sha(head) or
            not _sha(base_sha)):
        problems.append("PR_IDENTITY_OR_STATE_INVALID")
    else:
        if (_at(pr, "head", "repo", "full_name") != REPO or
                _at(pr, "base", "repo", "full_name") != REPO or
                _at(pr, "base", "ref") != "main"):
            problems.append("PR_NOT_ISOLATED_ON_MAIN")
        if main_sha != base_sha:
            problems.append("BASE_MOVED_OR_UNPINNED")
        if pr.get("draft") is not False:
            problems.append("PR_IS_DRAFT")
        if pr.get("merged") is True:
            problems.append("PR_ALREADY_MERGED")

    if (type(comparison) is not dict or comparison.get("status") != "ahead"
            or type(comparison.get("ahead_by")) is not int or
            comparison["ahead_by"] < 1 or
            type(comparison.get("behind_by")) is not int or
            comparison["behind_by"] != 0):
        problems.append("PR_COMPARE_NOT_CLEAN")

    if type(check_listing) is not dict:
        problems.append("CHECK_LISTING_MISSING")
        checks = []
    else:
        checks = check_listing.get("check_runs")
        total = check_listing.get("total_count")
        if (type(checks) is not list or type(total) is not int or
                total < 1 or total > 100 or total != len(checks)):
            problems.append("CHECK_LISTING_INCOMPLETE")
            checks = []

    if not checks:
        problems.append("NO_COMPLETE_CHECK_EVIDENCE")
    else:
        names = []
        for check in checks:
            if type(check) is not dict or type(check.get("name")) is not str:
                problems.append("CHECK_METADATA_INVALID")
                continue
            names.append(check["name"])
            if (check.get("head_sha") != head or
                    check.get("status") != "completed" or
                    check.get("conclusion") != "success"):
                problems.append("CHECK_NOT_GREEN_ON_HEAD")
        if len(names) != len(set(names)):
            advisories.append("DUPLICATE_CHECK_NAMES_REVIEW_SCOPE")
        # An observed list cannot prove that every *required* workflow ran.
        advisories.append("REQUIRED_CHECK_COVERAGE_NOT_ATTESTED")

    if type(reviews) is not list or len(reviews) >= 100:
        problems.append("REVIEW_LISTING_INCOMPLETE")
    else:
        author = _at(pr, "user", "login")
        # Reviews arrive chronologically: reduce to each independent
        # reviewer's LATEST decision on this exact head, so an earlier
        # approval cannot outlive that reviewer's later change request.
        latest_state: dict[str, str] = {}
        for review in reviews:
            if type(review) is not dict or review.get("commit_id") != head:
                continue
            login = _at(review, "user", "login")
            state = review.get("state")
            if (type(login) is not str or login == author or
                    state not in ("APPROVED", "CHANGES_REQUESTED", "DISMISSED")):
                continue
            latest_state[login] = state
        approved = any(state == "APPROVED" for state in latest_state.values())
        if not approved:
            advisories.append("NO_INDEPENDENT_GITHUB_APPROVAL_ON_HEAD")
    advisories.append("REVIEW_THREADS_AND_RULESETS_NOT_EVALUATED")

    return {
        "contract": CONTRACT,
        "data_source": "provided_snapshot_untrusted",
        "pr_number": number,
        "observed_main_sha": main_sha if _sha(main_sha) else None,
        "observed_head_sha": head if _sha(head) else None,
        "observed_check_count": len(checks),
        "engineering_checks_observed_pass": bool(checks) and not any(
            x.startswith("CHECK_") or x == "NO_COMPLETE_CHECK_EVIDENCE"
            for x in problems
        ),
        "advisory_blockers": sorted(set(problems)),
        "review_advisories": sorted(set(advisories)),
        "conditionally_unblocked": not problems,
        "merge_ready": False,
        "eligible_for_auto_merge": False,
        "merges_performed": 0,
        "source_authenticated": False,
        "scholarly_verified": False,
        "rights_verified": False,
        "juristic_inference_allowed": False,
        "public_fatwa_authorized": False,
        "note": "Read-only advice. Even all-green observed checks do not confer reviewer authority or prove complete required checks.",
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ReadinessError("UNEXPECTED_API_REDIRECT")


def _get_api(path: str, token: str | None) -> Any:
    """Only relative paths generated by this module under fixed GitHub host."""
    if (type(path) is not str or not _API_PATH.fullmatch(path)
            or "//" in path or "\\" in path or
            any(part in (".", "..") for part in path.split("?", 1)[0].split("/"))):
        raise ReadinessError("UNSAFE_API_PATH")
    url = f"https://api.github.com/repos/{REPO}{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "Mubin-Quran-PR-Readiness-v2",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    try:
        opener = urllib.request.build_opener(_NoRedirect())
        with opener.open(urllib.request.Request(url, headers=headers), timeout=15) as resp:
            if resp.geturl() != url:
                raise ReadinessError("UNEXPECTED_API_REDIRECT")
            blob = resp.read(_MAX_JSON + 1)
        if not 0 < len(blob) <= _MAX_JSON:
            raise ReadinessError("API_REPLY_SIZE_INVALID")

        def pairs(items):
            data = {}
            for key, value in items:
                if key in data:
                    raise ReadinessError("DUPLICATE_API_KEY")
                data[key] = value
            return data

        def nonfinite(_):
            raise ReadinessError("NONFINITE_API_NUMBER")

        return json.loads(blob.decode("utf-8", "strict"),
                          object_pairs_hook=pairs, parse_constant=nonfinite)
    except ReadinessError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
        raise ReadinessError("GITHUB_API_UNAVAILABLE_OR_INVALID") from None


def fetch_live(number: int, token: str | None = None) -> dict[str, Any]:
    if not _pr_number(number):
        raise ReadinessError("INVALID_PR_NUMBER")
    main = _get_api("/branches/main", token)
    pr = _get_api(f"/pulls/{number}", token)
    head = _at(pr, "head", "sha")
    main_sha = _at(main, "commit", "sha")
    if not _sha(head) or not _sha(main_sha):
        raise ReadinessError("LIVE_SHA_MISSING")
    cmp = _get_api(f"/compare/{main_sha}...{head}", token)
    checks = _get_api(f"/commits/{head}/check-runs?per_page=100", token)
    reviews = _get_api(f"/pulls/{number}/reviews?per_page=100", token)
    latest_main = _get_api("/branches/main", token)
    latest_pr = _get_api(f"/pulls/{number}", token)
    if _at(latest_main, "commit", "sha") != main_sha:
        raise ReadinessError("MAIN_CHANGED_DURING_READ")
    if (_at(latest_pr, "head", "sha") != head or
            _at(latest_pr, "base", "sha") != _at(pr, "base", "sha") or
            _at(latest_pr, "base", "ref") != _at(pr, "base", "ref") or
            latest_pr.get("state") != pr.get("state") or
            latest_pr.get("draft") != pr.get("draft")):
        # A retarget to a different branch may keep the same base SHA;
        # the branch identity itself must stay main for isolation.
        raise ReadinessError("PR_CHANGED_DURING_READ")
    return {"main": main, "pr": pr, "comparison": cmp,
            "check_listing": checks, "reviews": reviews}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pr", required=True, type=int)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        snapshot = fetch_live(args.pr, os.environ.get("GITHUB_TOKEN") or None)
        report = assess_pr(snapshot, args.pr)
        report["data_source"] = "github_rest_read_only"
        code = 0
    except ReadinessError as exc:
        report = {
            "contract": CONTRACT, "data_source": "unavailable",
            "merge_ready": False, "eligible_for_auto_merge": False,
            "error_code": str(exc),
        }
        code = 2
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())
