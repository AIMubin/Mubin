"""Quran PR readiness v2: advisory-only, synthetic and adversarial tests."""
from __future__ import annotations
import copy
import json
import os
from unittest.mock import patch
import unittest

from qa.quran_merge_readiness import (
    REPO, ReadinessError, _get_api, assess_pr, fetch_live, main,
)

MAIN = "1" * 40
HEAD = "2" * 40
NUMBER = 89


def fixture():
    return {
        "main": {"protected": True, "commit": {"sha": MAIN}},
        "pr": {
            "number": NUMBER, "state": "open", "merged": False,
            "draft": False, "user": {"login": "maintainer"},
            "base": {"sha": MAIN, "ref": "main",
                     "repo": {"full_name": REPO}},
            "head": {"sha": HEAD, "repo": {"full_name": REPO}},
        },
        "comparison": {"status": "ahead", "ahead_by": 1, "behind_by": 0},
        "check_listing": {"total_count": 2, "check_runs": [
            {"name": "quran", "head_sha": HEAD, "status": "completed",
             "conclusion": "success"},
            {"name": "core", "head_sha": HEAD, "status": "completed",
             "conclusion": "success"},
        ]},
        "reviews": [{"state": "APPROVED", "commit_id": HEAD,
                     "user": {"login": "reviewer"}}],
    }


class QuranReadinessV2Tests(unittest.TestCase):
    def test_green_observation_never_authorizes_merge_or_source(self):
        v = assess_pr(fixture(), NUMBER)
        self.assertTrue(v["engineering_checks_observed_pass"])
        self.assertTrue(v["conditionally_unblocked"])
        self.assertFalse(v["merge_ready"])
        self.assertFalse(v["eligible_for_auto_merge"])
        self.assertFalse(v["source_authenticated"])
        self.assertFalse(v["rights_verified"])
        self.assertFalse(v["scholarly_verified"])
        self.assertFalse(v["juristic_inference_allowed"])
        self.assertFalse(v["public_fatwa_authorized"])
        self.assertIn("REQUIRED_CHECK_COVERAGE_NOT_ATTESTED", v["review_advisories"])

    def test_forged_live_label_cannot_promote_snapshot(self):
        d = fixture()
        d["data_source"] = "github_rest_read_only"
        d["eligible_for_auto_merge"] = True
        result = assess_pr(d, NUMBER)
        self.assertEqual("provided_snapshot_untrusted", result["data_source"])
        self.assertFalse(result["eligible_for_auto_merge"])

    def test_old_stack_numbers_not_hardcoded(self):
        result = assess_pr(fixture(), NUMBER)
        self.assertEqual([NUMBER], [result["pr_number"]])
        self.assertNotIn("73", json.dumps(result))

    def test_draft_or_merged_fails_advisory_checks(self):
        for key, val, reason in (
                ("draft", True, "PR_IS_DRAFT"),
                ("merged", True, "PR_ALREADY_MERGED"),
                ("state", "closed", "PR_IDENTITY_OR_STATE_INVALID")):
            d = fixture()
            d["pr"][key] = val
            self.assertIn(reason, assess_pr(d, NUMBER)["advisory_blockers"])

    def test_moved_main_fail_closed(self):
        d = fixture()
        d["main"]["commit"]["sha"] = "f" * 40
        self.assertIn("BASE_MOVED_OR_UNPINNED",
                      assess_pr(d, NUMBER)["advisory_blockers"])

    def test_foreign_repo_or_stacked_base_refused(self):
        for field, val in (("repo", {"full_name": "other/repo"}),
                           ("ref", "old-stacked-pr")):
            d = fixture()
            d["pr"]["base"][field] = val
            self.assertIn("PR_NOT_ISOLATED_ON_MAIN",
                          assess_pr(d, NUMBER)["advisory_blockers"])

    def test_compare_divergence_refused(self):
        d = fixture()
        d["comparison"]["behind_by"] = 2
        self.assertIn("PR_COMPARE_NOT_CLEAN",
                      assess_pr(d, NUMBER)["advisory_blockers"])

    def test_stale_or_failed_checks_cannot_look_green(self):
        for field, value in (("head_sha", "f"*40),
                             ("conclusion", "failure"),
                             ("status", "in_progress")):
            d = fixture()
            d["check_listing"]["check_runs"][0][field] = value
            v = assess_pr(d, NUMBER)
            self.assertFalse(v["engineering_checks_observed_pass"])
            self.assertIn("CHECK_NOT_GREEN_ON_HEAD", v["advisory_blockers"])

    def test_incomplete_listing_denied(self):
        for count in (0, 3, 101, True):
            d = fixture()
            d["check_listing"]["total_count"] = count
            v = assess_pr(d, NUMBER)
            self.assertIn("CHECK_LISTING_INCOMPLETE", v["advisory_blockers"])
            self.assertFalse(v["engineering_checks_observed_pass"])

    def test_duplicate_check_names_not_silent(self):
        d = fixture()
        d["check_listing"]["check_runs"][1]["name"] = "quran"
        result = assess_pr(d, NUMBER)
        self.assertIn("DUPLICATE_CHECK_NAMES_REVIEW_SCOPE",
                      result["review_advisories"])

    def test_missing_exact_head_reviewer_cannot_claim_approval(self):
        d = fixture()
        d["reviews"][0]["commit_id"] = "f" * 40
        self.assertIn("NO_INDEPENDENT_GITHUB_APPROVAL_ON_HEAD",
                      assess_pr(d, NUMBER)["review_advisories"])
        d["reviews"][0]["commit_id"] = HEAD
        d["reviews"][0]["user"]["login"] = "maintainer"
        self.assertIn("NO_INDEPENDENT_GITHUB_APPROVAL_ON_HEAD",
                      assess_pr(d, NUMBER)["review_advisories"])

    def test_no_main_protection_is_advisory_not_authority(self):
        d = fixture()
        d["main"]["protected"] = False
        v = assess_pr(d, NUMBER)
        self.assertIn("MAIN_BRANCH_PROTECTION_NOT_CONFIRMED",
                      v["review_advisories"])
        self.assertFalse(v["merge_ready"])

    def test_invalid_input_denied(self):
        for value in (True, 0, -1, "89", 1000000):
            with self.assertRaises(ReadinessError):
                assess_pr(fixture(), value)
        with self.assertRaises(ReadinessError):
            assess_pr([], NUMBER)

    def test_reject_unsafe_api_paths_without_network(self):
        for path in ("https://example.com", "//external", "/pulls/../secret",
                     "/pulls/./89", "/pulls/%2e%2e/x", "/foo\\bar",
                     "/pr#fragment", "/api space"):
            with self.subTest(path=path), self.assertRaises(ReadinessError):
                _get_api(path, None)

    def test_live_fetch_checks_main_consistency_and_endpoint_scoping(self):
        d = fixture()
        received = []
        mapping = {
            "/branches/main": [d["main"], d["main"]],
            "/pulls/89": [d["pr"], d["pr"]],
            "/compare/" + MAIN + "..." + HEAD: [d["comparison"]],
            "/commits/" + HEAD + "/check-runs?per_page=100": [d["check_listing"]],
            "/pulls/89/reviews?per_page=100": [d["reviews"]],
        }
        def fake(path, token):
            received.append(path)
            return copy.deepcopy(mapping[path].pop(0))
        with patch("qa.quran_merge_readiness._get_api", side_effect=fake):
            actual = fetch_live(NUMBER)
        self.assertEqual(7, len(received))
        self.assertEqual("provided_snapshot_untrusted",
                         assess_pr(actual, NUMBER)["data_source"])

    def test_live_fetch_fails_when_main_moves(self):
        d = fixture()
        newer = copy.deepcopy(d["main"])
        newer["commit"]["sha"] = "f" * 40
        sequence = [d["main"], d["pr"], d["comparison"],
                    d["check_listing"], d["reviews"], newer, d["pr"]]
        with patch("qa.quran_merge_readiness._get_api", side_effect=sequence):
            with self.assertRaisesRegex(ReadinessError,
                                        "MAIN_CHANGED_DURING_READ"):
                fetch_live(NUMBER)

    def test_live_fetch_fails_on_concurrent_pr_head_change(self):
        d = fixture()
        new_pr = copy.deepcopy(d["pr"])
        new_pr["head"]["sha"] = "f" * 40
        sequence = [d["main"], d["pr"], d["comparison"],
                    d["check_listing"], d["reviews"], d["main"], new_pr]
        with patch("qa.quran_merge_readiness._get_api", side_effect=sequence):
            with self.assertRaisesRegex(ReadinessError,
                                        "PR_CHANGED_DURING_READ"):
                fetch_live(NUMBER)

    def test_late_changes_requested_suppresses_earlier_approval(self):
        d = fixture()
        d["reviews"] = [
            {"state": "APPROVED", "commit_id": HEAD,
             "user": {"login": "reviewer"}},
            {"state": "CHANGES_REQUESTED", "commit_id": HEAD,
             "user": {"login": "reviewer"}},
        ]
        self.assertIn("NO_INDEPENDENT_GITHUB_APPROVAL_ON_HEAD",
                      assess_pr(d, NUMBER)["review_advisories"])

    def test_dismissed_approval_is_not_counted(self):
        d = fixture()
        d["reviews"] = [
            {"state": "APPROVED", "commit_id": HEAD,
             "user": {"login": "reviewer"}},
            {"state": "DISMISSED", "commit_id": HEAD,
             "user": {"login": "reviewer"}},
        ]
        self.assertIn("NO_INDEPENDENT_GITHUB_APPROVAL_ON_HEAD",
                      assess_pr(d, NUMBER)["review_advisories"])

    def test_latest_approval_after_changes_still_counts(self):
        d = fixture()
        d["reviews"] = [
            {"state": "CHANGES_REQUESTED", "commit_id": HEAD,
             "user": {"login": "reviewer"}},
            {"state": "APPROVED", "commit_id": HEAD,
             "user": {"login": "reviewer"}},
        ]
        self.assertNotIn("NO_INDEPENDENT_GITHUB_APPROVAL_ON_HEAD",
                         assess_pr(d, NUMBER)["review_advisories"])

    def test_live_fetch_fails_on_base_ref_retarget_same_sha(self):
        d = fixture()
        retargeted = copy.deepcopy(d["pr"])
        retargeted["base"]["ref"] = "old-stacked-pr"
        sequence = [d["main"], d["pr"], d["comparison"],
                    d["check_listing"], d["reviews"], d["main"], retargeted]
        with patch("qa.quran_merge_readiness._get_api", side_effect=sequence):
            with self.assertRaisesRegex(ReadinessError,
                                        "PR_CHANGED_DURING_READ"):
                fetch_live(NUMBER)

    def test_live_fetch_fails_on_concurrent_pr_draft_change(self):
        d = fixture()
        new_pr = copy.deepcopy(d["pr"])
        new_pr["draft"] = True
        sequence = [d["main"], d["pr"], d["comparison"],
                    d["check_listing"], d["reviews"], d["main"], new_pr]
        with patch("qa.quran_merge_readiness._get_api", side_effect=sequence):
            with self.assertRaisesRegex(ReadinessError,
                                        "PR_CHANGED_DURING_READ"):
                fetch_live(NUMBER)

    def test_cli_never_promotes_forged_live_json(self):
        with patch("qa.quran_merge_readiness.fetch_live", return_value=fixture()):
            with patch("builtins.print") as printer:
                self.assertEqual(0, main(["--pr", str(NUMBER), "--json"]))
        report = json.loads(printer.call_args.args[0])
        self.assertFalse(report["merge_ready"])
        self.assertFalse(report["eligible_for_auto_merge"])
        self.assertEqual("github_rest_read_only", report["data_source"])

    def test_live_unavailable_returns_safe_status_and_exit_2(self):
        with patch("qa.quran_merge_readiness.fetch_live",
                   side_effect=ReadinessError("GITHUB_API_UNAVAILABLE_OR_INVALID")):
            with patch("builtins.print") as printer:
                self.assertEqual(2, main(["--pr", str(NUMBER)]))
        result = json.loads(printer.call_args.args[0])
        self.assertEqual("unavailable", result["data_source"])
        self.assertFalse(result["merge_ready"])


if __name__ == "__main__":
    unittest.main()
