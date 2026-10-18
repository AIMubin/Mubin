"""Quran stacked-PR merge-readiness RED tests: statuses cannot be laundered into approvals."""
import copy
import unittest

from qa.quran_merge_readiness import assess_chain, EXPECTED, CHAIN


SHA_MAIN = "567e55858a9911a23430ef81f1e41b7a5f26480e"
REPO = "AIMubin/Mubin"


def fixture():
    shas = {73: "a" * 40, 74: "b" * 40, 75: "c" * 40, 76: "d" * 40}
    branches = {73: "main", 74: "quran-q01", 75: "quran-q01b", 76: "quran-q01c"}
    result = {
        "main": {"name": "main", "protected": True, "commit": {"sha": SHA_MAIN}},
        "prs": {}, "runs": {}, "reviews": {}, "comparisons": {},
    }
    for n in CHAIN:
        base_sha = SHA_MAIN if n == 73 else shas[n - 1]
        result["prs"][n] = {
            "number": n, "state": "open", "draft": False,
            "user": {"login": "author"},
            "base": {"ref": branches[n], "sha": base_sha, "repo": {"full_name": REPO}},
            "head": {"sha": shas[n], "repo": {"full_name": REPO}},
        }
        result["runs"][n] = [
            {"name": name, "event": "pull_request", "status": "completed",
             "conclusion": "success", "head_sha": shas[n], "id": n * 100 + i}
            for i, name in enumerate(EXPECTED[n])
        ]
        result["reviews"][n] = [{
            "state": "APPROVED", "commit_id": shas[n], "user": {"login": "reviewer"}
        }]
        result["comparisons"][n] = {"status": "ahead", "ahead_by": 1, "behind_by": 0}
    return result


class QuranMergeReadinessTests(unittest.TestCase):
    def test_clean_engineering_snapshot_is_not_scholarly_approval(self):
        x = assess_chain(fixture())
        self.assertTrue(x["engineering_qa_passed"])
        self.assertTrue(x["conditionally_merge_ready"])
        self.assertFalse(x["merge_ready"])
        self.assertFalse(x["quran_source_authenticated"])
        self.assertFalse(x["scholarly_approval_verified"])
        self.assertEqual("provided_snapshot_untrusted", x["data_source"])

    def test_forged_complete_offline_snapshot_never_authorizes_merge(self):
        d = fixture()
        d["data_source"] = "github_rest_read_only"
        x = assess_chain(d)
        self.assertFalse(x["merge_ready"])
        self.assertFalse(x["eligible_for_auto_merge"])
        self.assertTrue(x["conditionally_merge_ready"])
        self.assertEqual("provided_snapshot_untrusted", x["data_source"])

    def test_draft_blocks_only_merge_not_engineering_progress(self):
        d = fixture()
        d["prs"][76]["draft"] = True
        x = assess_chain(d)
        self.assertTrue(x["engineering_qa_passed"])
        self.assertFalse(x["merge_ready"])
        self.assertIn("PR76_DRAFT", x["blockers"])

    def test_unprotected_main_is_a_merge_blocker(self):
        d = fixture()
        d["main"]["protected"] = False
        x = assess_chain(d)
        self.assertFalse(x["merge_ready"])
        self.assertTrue(x["engineering_qa_passed"])
        self.assertIn("MAIN_NOT_PROTECTED", x["blockers"])

    def test_no_review_is_not_ai_signoff_or_approval(self):
        d = fixture()
        d["reviews"][75] = []
        x = assess_chain(d)
        self.assertFalse(x["merge_ready"])
        self.assertIn("PR75_NO_EXACT_HEAD_CODE_REVIEW", x["review_advisories"])
        self.assertNotIn("PR75_NO_EXACT_HEAD_CODE_REVIEW", x["blockers"])

    def test_review_on_old_commit_does_not_count(self):
        d = fixture()
        d["reviews"][74][0]["commit_id"] = "f" * 40
        self.assertIn("PR74_NO_EXACT_HEAD_CODE_REVIEW", assess_chain(d)["review_advisories"])

    def test_author_self_approval_does_not_count(self):
        d = fixture()
        d["reviews"][73][0]["user"]["login"] = "author"
        self.assertIn("PR73_NO_EXACT_HEAD_CODE_REVIEW", assess_chain(d)["review_advisories"])

    def test_no_independent_reviewer_is_advisory_for_research_prs(self):
        d = fixture()
        for n in CHAIN:
            d["reviews"][n] = []
        x = assess_chain(d)
        self.assertTrue(x["engineering_qa_passed"])
        self.assertTrue(x["conditionally_merge_ready"])
        self.assertFalse(x["merge_ready"])
        self.assertEqual(4, len(x["review_advisories"]))
        self.assertEqual([], x["blockers"])

    def test_pending_ci_no_false_green(self):
        d = fixture()
        d["runs"][76][0]["conclusion"] = None
        d["runs"][76][0]["status"] = "in_progress"
        x = assess_chain(d)
        self.assertFalse(x["engineering_qa_passed"])
        self.assertFalse(x["merge_ready"])
        self.assertIn("PR76_CHECK_INCOMPLETE", x["blockers"])

    def test_old_head_ci_no_false_green(self):
        d = fixture()
        d["runs"][74][0]["head_sha"] = "f" * 40
        x = assess_chain(d)
        self.assertIn("PR74_CHECK_INCOMPLETE", x["blockers"])
        self.assertFalse(x["merge_ready"])

    def test_bad_parent_base_breaks_stack(self):
        d = fixture()
        d["prs"][75]["base"]["sha"] = "f" * 40
        x = assess_chain(d)
        self.assertIn("PR75_PARENT_MISMATCH", x["blockers"])

    def test_cross_repo_pr_is_rejected(self):
        d = fixture()
        d["prs"][73]["head"]["repo"]["full_name"] = "attacker/repo"
        self.assertIn("PR73_FOREIGN_REPO", assess_chain(d)["blockers"])

    def test_bad_comparison_blocks_merge(self):
        d = fixture()
        d["comparisons"][76]["status"] = "diverged"
        self.assertIn("PR76_NOT_FAST_FORWARD", assess_chain(d)["blockers"])

    def test_same_name_failed_job_not_hidden_by_success_duplicate(self):
        d = fixture()
        failed = copy.deepcopy(d["runs"][76][0])
        failed["conclusion"] = "failure"
        failed["id"] = 9999
        d["runs"][76].append(failed)
        self.assertIn("PR76_CHECK_AMBIGUOUS", assess_chain(d)["blockers"])

    def test_no_fake_source_authority_and_missing_fields(self):
        d = fixture()
        d["main"].pop("protected")
        x = assess_chain(d)
        self.assertFalse(x["merge_ready"])
        self.assertIn("MAIN_NOT_PROTECTED", x["blockers"])
        self.assertFalse(x["quran_source_authenticated"])


if __name__ == "__main__":
    unittest.main()
