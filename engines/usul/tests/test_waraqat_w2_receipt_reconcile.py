"""Synthetic receipt regression: provenance hashes and CRLF arithmetic fail closed."""
from __future__ import annotations

import copy
import json
import re
import unittest

from engines.usul.pilots.waraqat_w2_receipt_reconcile import (
    AUDIT_VERSION, HARDENED_PIN, STAGE06_PIN, W2_RAW_SHA,
    ReceiptReconciliationError, reconcile, sha,
)


class ReceiptReconciliationTests(unittest.TestCase):
    def setUp(self):
        self.audit_sha = sha(b"synthetic-private-audit")
        self.receipt_sha = sha(b"synthetic-historical-receipt")
        self.legacy_sha = "e0f621b46da27175" + "a"*48
        self.audit_report = {
            "engine": AUDIT_VERSION,
            "status": "ALL_THREE_REPRESENTATIONS_FORMAT_ONLY_VERIFIED",
            "pinned_w2_html_sha256": W2_RAW_SHA,
            "historical_lengths_verified": True,
            "source_text_included": False,
            "legacy_lf_serialized_bytes": 1696,
            "legacy_lf_linefeed_count": 10,
            "legacy_windows_extra_cr_bytes": 10,
            "legacy_lf_sha256": HARDENED_PIN,
            "variants": {
                "stage06": {"bytes": 1702, "sha256": STAGE06_PIN},
                "legacy_full": {"bytes": 1706, "sha256": self.legacy_sha},
                "hardened_full": {"bytes": 1696, "sha256": HARDENED_PIN},
            },
            "comparisons": {
                key: {
                    "nonempty_lines_identical": True,
                    "whitespace_delimited_tokens_identical": True,
                    "nonwhitespace_codepoints_identical": True,
                } for key in ("stage06_vs_legacy_full",
                              "stage06_vs_hardened_full",
                              "legacy_full_vs_hardened_full")
            },
        }
        self.previous = {
            "review_id": "u01-w2-three-representations-final-audit",
            "campaign_status": "ALL_THREE_REPRESENTATIONS_FORMAT_ONLY_VERIFIED",
            "pinned_html_sha256": W2_RAW_SHA,
            "private_audit_report_sha256": self.audit_sha,
            "lf_to_crf_translations_on_windows": 10,
            "representations": {
                "stage06_htmlparser": {"bytes": 1702, "sha256": STAGE06_PIN},
                "legacy_full_windows": {
                    "bytes": 1706, "sha256": "e0f621b46da27175",
                    "legacy_lf_only_bytes": 1700
                },
                "hardened_full": {"bytes": 1696,
                                  "sha256": HARDENED_PIN[:16]},
            },
        }

    def build(self):
        return reconcile(self.audit_report, self.previous,
                         private_report_sha256=self.audit_sha,
                         previous_receipt_sha256=self.receipt_sha)

    def test_immutable_1700_error_reconciled_with_measured_1696(self):
        result = self.build()
        self.assertEqual(result["status"], "EVIDENCE_RECONCILIATION_PASS")
        parts = result["delta_accounting"]
        self.assertEqual(parts["archived_claimed_cr_added"], 10)
        self.assertEqual(parts["measured_cr_added"], 10)
        self.assertEqual(parts["archived_legacy_lf_only_bytes"], 1700)
        self.assertEqual(parts["measured_legacy_lf_only_bytes"], 1696)
        self.assertEqual(parts["legacy_windows_minus_legacy_lf"], 10)
        self.assertEqual(parts["legacy_lf_minus_hardened"], 0)
        self.assertEqual(parts["legacy_windows_minus_hardened"], 10)
        self.assertEqual(parts["stage06_minus_hardened"], 6)
        self.assertTrue(result["provenance_correction"]["historical_receipt_unchanged"])
        for record in result["three_representations"].values():
            self.assertRegex(record["sha256"], re.compile(r"^[0-9a-f]{64}$"))
        self.assertFalse(result["source_text_included"])
        self.assertFalse(result["scholarly_verified"])

    def test_replay_report_digest_is_bound_to_previous_receipt(self):
        self.audit_sha = sha(b"changed-report")
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "ARCHIVED_RECEIPT_PROVENANCE_MISMATCH"):
            self.build()

    def test_report_cannot_claim_six_new_carriage_returns(self):
        self.audit_report["legacy_windows_extra_cr_bytes"] = 6
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "WINDOWS_NEWLINE_ACCOUNTING_INVALID"):
            self.build()

    def test_lf_count_forgery_blocked(self):
        self.audit_report["legacy_lf_linefeed_count"] = 6
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "WINDOWS_NEWLINE_ACCOUNTING_INVALID"):
            self.build()

    def test_unrecognized_historical_erratum_not_silently_accepted(self):
        self.previous["representations"]["legacy_full_windows"]["legacy_lf_only_bytes"] = 1701
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "HISTORICAL_RECEIPT_NOT_KNOWN_ERRATUM"):
            self.build()

    def test_previously_measured_new_source_must_equal_hardened_sha(self):
        self.audit_report["legacy_lf_sha256"] = sha(b"other-1696-byte-file")
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "LEGACY_LF_HARDENED_PIN_MISMATCH"):
            self.build()

    def test_legacy_lf_is_not_allowed_to_drift_from_pinned_hardened_length(self):
        self.audit_report["legacy_lf_serialized_bytes"] = 1697
        self.audit_report["legacy_windows_extra_cr_bytes"] = 9
        self.audit_report["legacy_lf_linefeed_count"] = 9
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "LEGACY_LF_HARDENED_PIN_MISMATCH"):
            self.build()

    def test_incomplete_sha256_refused(self):
        self.audit_report["variants"]["legacy_full"]["sha256"] = "e0f621b46da27175"
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "VARIANT_SIZE_OR_DIGEST_INVALID"):
            self.build()

    def test_wrong_previous_sha_prefix_refused(self):
        self.previous["representations"]["legacy_full_windows"]["sha256"] = "ff"*8
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "HISTORICAL_LENGTH_OR_DIGEST_PREFIX_MISMATCH"):
            self.build()

    def test_independent_hardened_witness_pin_refused_if_wrong(self):
        self.audit_report["variants"]["hardened_full"]["sha256"] = sha(b"changed")
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "INDEPENDENT_WITNESS_PINS_MISMATCH"):
            self.build()

    def test_source_word_boundaries_must_match(self):
        self.audit_report["comparisons"]["stage06_vs_hardened_full"][
            "whitespace_delimited_tokens_identical"] = False
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "PAIRWISE_TEXT_MISMATCH"):
            self.build()

    def test_exact_three_variant_inventory_enforced(self):
        self.audit_report["variants"].pop("legacy_full")
        with self.assertRaisesRegex(ReceiptReconciliationError,
                                    "VARIANTS_MISSING"):
            self.build()

    def test_output_deterministic_and_contains_no_source_text(self):
        one, two = self.build(), self.build()
        self.assertEqual(one, two)
        blob = json.dumps(one, ensure_ascii=False)
        self.assertNotIn("الأمر", blob)
        self.assertRegex(one["receipt_sha256"], re.compile(r"^[0-9a-f]{64}$"))


if __name__ == "__main__":
    unittest.main()
