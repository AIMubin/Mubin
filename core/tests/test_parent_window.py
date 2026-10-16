"""P1.1 Phase-C adversarial proof of parent-bound windows and P1 local receipts.

All test material is synthetic. No qualified source, release edition or rights are attested.
"""
from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.provenance import verify_bundle
from core.source_authority import cache_filename
from core.source_authority.windows import (
    derive_parent_window,
    validate_parent_window_binding,
    check_linked_p1_receipt,
    verify_staged_parent_window,
)
from test_inference_foundation import fixture


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


class TestP11ParentWindow(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.cache = self.root / "private-cache"
        self.cache.mkdir()
        self.source_id = "openiti:001Synthetic.Work"
        self.excerpt = "نصّ تجريبي 😀"
        self.raw = ("مقدمة عربيّة\n" + self.excerpt + "\nخاتمة").encode("utf-8")
        self.source = {
            "source_id": self.source_id,
            "work_id": "001Synthetic.Work",
            "title_ar": "ملف اصطناعي",
            "qualification_eligible": True,
            "provider": "OpenITI",
            "source_repo": "OpenITI/RELEASE",
            "source_path": "data/001Synthetic/001Synthetic.Work/sample",
            "repo_ref": "a" * 40,
            "source_blob_sha": git_blob(self.raw),
            "version_id": "001Synthetic.Work.unit-test",
            "format": "OpenITI-mARkdown",
        }
        self.registry = {
            "schema_version": 2,
            "registry_id": "synthetic-registry-only",
            "sources": [self.source],
        }
        self.file = self.cache / cache_filename(self.source_id)
        self.file.write_bytes(self.raw)

    def locator(self):
        decoded = self.raw.decode("utf-8")
        start = decoded.index(self.excerpt)
        return f"gitblob:{self.source['source_blob_sha']}#char={start}:{start+len(self.excerpt)}"

    def derive(self, **kwargs):
        return derive_parent_window(
            self.registry, self.cache, self.source_id,
            self.locator(), self.excerpt, **kwargs
        )

    def test_distinct_parent_and_window_identity(self):
        result, content = self.derive(left_context_bytes=0, right_context_bytes=0)
        self.assertTrue(result["valid"], result)
        self.assertEqual(self.excerpt.encode(), content)
        binding = result["binding"]
        self.assertEqual("parent_pinned_window_only", result["scope"])
        self.assertEqual("not_authenticated", result["authority"]["edition"])
        self.assertEqual("not_reviewed", result["authority"]["rights"])
        self.assertEqual("not_checked", result["authority"]["entailment"])
        self.assertEqual(sha(self.raw), binding["parent"]["source_sha256"])
        self.assertEqual(git_blob(self.raw), binding["parent"]["git_blob_sha1"])
        self.assertEqual(sha(content), binding["window"]["content_sha256"])
        self.assertNotEqual(binding["parent"]["source_sha256"], binding["window"]["content_sha256"])
        self.assertTrue(binding["window"]["id"].startswith("win."))
        self.assertEqual([], validate_parent_window_binding(binding, content))
        self.assertNotIn(self.excerpt, json.dumps(result, ensure_ascii=False))

    def test_context_window_contains_exact_quote_with_absolute_and_relative_offsets(self):
        result, content = self.derive(left_context_bytes=1, right_context_bytes=1)
        self.assertTrue(result["valid"], result)
        b = result["binding"]
        quote_offset = b["quote"]["start_in_window_byte"]
        self.assertEqual(self.excerpt.encode(), content[quote_offset:b["quote"]["end_in_window_byte"]])
        self.assertEqual(
            b["parent"]["quote_start_byte"],
            b["window"]["absolute_start_byte"] + quote_offset
        )
        self.assertEqual(self.raw[b["window"]["absolute_start_byte"]:b["window"]["absolute_end_byte"]], content)

    def test_utf8_boundary_split_rejected_not_normalized(self):
        result, content = self.derive(left_context_bytes=1, right_context_bytes=0)
        # Previous example's immediately preceding character is LF; choose a
        # window byte offset that ends half-way into an Arabic codepoint instead.
        if result["valid"]:
            self.raw = "ع" .encode() + self.excerpt.encode()
            self.source["source_blob_sha"] = git_blob(self.raw)
            self.file.write_bytes(self.raw)
            result, content = self.derive(left_context_bytes=1, right_context_bytes=0)
        self.assertFalse(result["valid"])
        self.assertIsNone(content)
        self.assertTrue(any("UTF-8" in msg or "boundary" in msg for msg in result["errors"]), result)

    def test_modified_parent_rejected_and_never_returns_window_bytes(self):
        self.file.write_bytes(self.raw + b"altered")
        result, content = self.derive()
        self.assertFalse(result["valid"])
        self.assertIsNone(content)
        self.assertIsNone(result["binding"])

    def test_bad_bytes_cannot_reuse_binding(self):
        result, content = self.derive()
        self.assertTrue(result["valid"], result)
        assert content is not None
        corrupted = b"X" + content[1:]
        problems = validate_parent_window_binding(result["binding"], corrupted)
        self.assertTrue(any("digest" in x or "quote" in x for x in problems), problems)

    def test_forged_parent_identity_breaks_binding_fingerprint(self):
        result, content = self.derive()
        self.assertTrue(result["valid"], result)
        binding = copy.deepcopy(result["binding"])
        binding["parent"]["version_id"] = "forged-edition"
        problems = validate_parent_window_binding(binding, content)
        self.assertTrue(any("binding" in x for x in problems), problems)

    def test_window_is_not_the_original_book_in_p1_receipt(self):
        result, content = self.derive()
        self.assertTrue(result["valid"], result)
        assert content is not None
        binding = result["binding"]
        stage = self.root / "stage"
        (stage / "windows").mkdir(parents=True)
        (stage / "windows" / "quote.txt").write_bytes(content)
        data = fixture()
        source = data["sources"][0]
        source.update({
            "id": binding["window"]["id"],
            "kind": "hadith",
            "work_title": "Synthetic derived quote window, not original book",
            "edition": "synthetic-window-unit-test",
            "locator": "derived-parent-quote-window",
            "content_sha256": binding["window"]["content_sha256"],
        })
        evidence = data["evidence"][0]
        evidence.update({
            "source_id": source["id"],
            "locator": "quote-byte-span",
            "excerpt": self.excerpt,
            "excerpt_sha256": sha(self.excerpt.encode()),
        })
        manifest = {
            "contract_version": "0.1.0",
            "sources": [{
                "id": source["id"],
                "relative_path": "windows/quote.txt",
                "work_title": source["work_title"],
                "edition": source["edition"],
                "scope_locator": source["locator"],
                "content_sha256": source["content_sha256"],
                "rights": {
                    "status": "operator_cleared",
                    "basis": "synthetic generated test bytes only",
                    "reference": "unit-test:locally-generated",
                },
                "spans": [{
                    "locator": evidence["locator"],
                    "start_byte": binding["quote"]["start_in_window_byte"],
                    "end_byte": binding["quote"]["end_in_window_byte"],
                }],
            }],
        }
        linked = verify_staged_parent_window(binding, content, data, manifest, stage)
        self.assertTrue(linked["valid"], linked)
        self.assertEqual("derived_window_local_p1_only", linked["scope"])
        self.assertEqual("not_authenticated", linked["authority"]["edition"])
        self.assertEqual("not_reviewed", linked["authority"]["rights"])
        self.assertEqual("not_checked", linked["authority"]["entailment"])
        self.assertEqual("operator_assertion_only", linked["rights_assurance"])
        self.assertEqual(binding["binding_sha256"], linked["parent_window_binding_sha256"])
        self.assertEqual(binding["window"]["id"], linked["receipt"]["source_id"])
        self.assertEqual(binding["window"]["content_sha256"], linked["receipt"]["source_sha256"])
        self.assertNotIn(self.excerpt, json.dumps(linked, ensure_ascii=False))
        p1 = verify_bundle(data, manifest, stage)
        self.assertTrue(p1["valid"], p1)
        self.assertEqual(1, len(p1["receipts"]))
        self.assertEqual(sha(content), p1["receipts"][0]["source_sha256"])
        self.assertNotEqual(sha(self.raw), p1["receipts"][0]["source_sha256"])
        self.assertEqual("local_byte_exact_match_only", p1["scope"])
        self.assertEqual("operator_assertion_only", p1["rights_assurance"])
        # The *separate* parent-window binding carries full-parent identity.
        self.assertEqual(sha(self.raw), binding["parent"]["source_sha256"])
        self.assertEqual([], check_linked_p1_receipt(binding, p1, content))
        other = copy.deepcopy(p1)
        other["receipts"][0]["source_sha256"] = binding["parent"]["source_sha256"]
        self.assertTrue(check_linked_p1_receipt(binding, other, content))
        other = copy.deepcopy(p1)
        other["receipts"][0]["start_byte"] += 1
        self.assertTrue(check_linked_p1_receipt(binding, other, content))
        other = copy.deepcopy(p1)
        other["receipts"][0]["source_id"] = "win.forged"
        self.assertTrue(check_linked_p1_receipt(binding, other, content))
        altered_binding = copy.deepcopy(binding)
        altered_binding["parent"]["version_id"] = "forged-source-edition"
        self.assertTrue(check_linked_p1_receipt(altered_binding, p1, content))

        # A hash is NOT a signature: rehash a physically impossible window
        # to prove that the linker performs semantic checks, not just hashes.
        for wrong_length in (len(content) + 1, 4 * 1024 * 1024 + 1):
            malformed = copy.deepcopy(binding)
            malformed["window"]["size_bytes"] = wrong_length
            unsigned = dict(malformed)
            unsigned.pop("binding_sha256", None)
            malformed["binding_sha256"] = sha(json.dumps(
                unsigned, ensure_ascii=False, sort_keys=True,
                separators=(",", ":")
            ).encode("utf-8"))
            self.assertTrue(
                check_linked_p1_receipt(malformed, p1, content),
                "linker accepted impossible or over-budget window size"
            )

        other = copy.deepcopy(p1)
        other["scope"] = "fabricated_external_authentication"
        self.assertTrue(check_linked_p1_receipt(binding, other, content))

        restricted_manifest = copy.deepcopy(manifest)
        restricted_manifest["sources"][0]["rights"]["status"] = "unknown"
        denied = verify_staged_parent_window(
            binding, content, data, restricted_manifest, stage
        )
        self.assertFalse(denied["valid"])
        self.assertIsNone(denied["receipt"])
        self.assertTrue(any("rights" in e for e in denied["errors"]), denied)
        (stage / "windows" / "quote.txt").write_bytes(content + b"!")
        rejected = verify_bundle(data, manifest, stage)
        self.assertFalse(rejected["valid"])
        self.assertEqual([], rejected["receipts"])
        after_swap = verify_staged_parent_window(binding, content, data, manifest, stage)
        self.assertFalse(after_swap["valid"])
        self.assertIsNone(after_swap["receipt"])

    def test_parent_changed_after_locator_preflight_fails_closed(self):
        from core.source_authority.locators import verify_hadith_locator
        real = verify_hadith_locator

        def mutate_after_valid_locator(*args, **kwargs):
            receipt = real(*args, **kwargs)
            self.assertTrue(receipt["valid"], receipt)
            self.file.write_bytes(self.raw + b"!")
            return receipt

        with patch(
            "core.source_authority.windows.verify_hadith_locator",
            side_effect=mutate_after_valid_locator,
        ):
            result, content = self.derive()
        self.assertFalse(result["valid"])
        self.assertIsNone(content)
        self.assertIsNone(result["binding"])
        self.assertTrue(any("pin" in x or "SHA-256" in x for x in result["errors"]), result)

    def test_binding_char_range_must_match_original_locator(self):
        result, content = self.derive()
        self.assertTrue(result["valid"], result)
        bad = copy.deepcopy(result["binding"])
        bad["quote"]["start_char"] += 1
        self.assertTrue(
            any("locator" in x or "character" in x for x in validate_parent_window_binding(bad, content))
        )

    def test_window_validator_rejects_self_consistent_invalid_utf8_and_cr(self):
        from core.source_authority.windows import _identity_payload, _canonical, _sha, _binding_digest
        result, original = self.derive(left_context_bytes=1)
        self.assertTrue(result["valid"], result)
        self.assertIsNotNone(original)
        self.assertEqual(b"\n", original[:1])
        for wrong_prefix in (b"\xff", b"\r"):
            with self.subTest(wrong_prefix=wrong_prefix):
                malicious_bytes = wrong_prefix + original[1:]
                forged = copy.deepcopy(result["binding"])
                forged["window"]["content_sha256"] = sha(malicious_bytes)
                forged["window"]["id"] = "win." + _sha(_canonical(_identity_payload(forged)))
                forged["binding_sha256"] = _binding_digest(forged)
                issues = validate_parent_window_binding(forged, malicious_bytes)
                self.assertTrue(issues, "invalid UTF-8/CR context was accepted")

    def test_window_validator_rejects_quote_character_count_mismatch(self):
        from core.source_authority.windows import _identity_payload, _canonical, _sha, _binding_digest
        result, content = self.derive()
        self.assertTrue(result["valid"], result)
        forged = copy.deepcopy(result["binding"])
        forged["quote"]["end_char"] += 1
        forged["quote"]["locator"] = (
            "gitblob:" + forged["parent"]["git_blob_sha1"] + "#char="
            + str(forged["quote"]["start_char"]) + ":"
            + str(forged["quote"]["end_char"])
        )
        forged["binding_sha256"] = _binding_digest(forged)
        issues = validate_parent_window_binding(forged, content)
        self.assertTrue(issues, "quote codepoint length and locator disagree")

    def test_actual_larger_than_p1_snapshot_limit_can_derive_small_window(self):
        # 9 MiB raw parent; P1 cannot verify it as one <=8 MiB snapshot.
        self.raw = b"x" * (9 * 1024 * 1024) + "\n".encode() + self.excerpt.encode()
        self.source["source_blob_sha"] = git_blob(self.raw)
        self.file.write_bytes(self.raw)
        result, content = self.derive(max_source_bytes=16 * 1024 * 1024)
        self.assertTrue(result["valid"], result)
        self.assertEqual(sha(self.raw), result["binding"]["parent"]["source_sha256"])
        self.assertEqual(self.excerpt.encode(), content)

    def test_invalid_byte_budget_fails_without_data_leak(self):
        for params in [
            {"max_window_bytes": 0}, {"max_source_bytes": 0},
            {"max_window_bytes": True}, {"max_window_bytes": 1},
            {"left_context_bytes": -1}, {"right_context_bytes": -1},
        ]:
            with self.subTest(params=params):
                result, content = self.derive(**params)
                self.assertFalse(result["valid"])
                self.assertIsNone(content)

    def test_invalid_crlf_file_rejected_without_window(self):
        self.raw = b"prefix\r\n" + self.excerpt.encode()
        self.file.write_bytes(self.raw)
        self.source["source_blob_sha"] = git_blob(self.raw)
        result, content = self.derive()
        self.assertFalse(result["valid"])
        self.assertIsNone(content)
        self.assertTrue(any("CR" in s for s in result["errors"]), result)

    def test_deterministic_binding_and_no_write_to_parent(self):
        one, a = self.derive()
        two, b = self.derive()
        self.assertEqual(one, two)
        self.assertEqual(a, b)
        self.assertEqual(self.raw, self.file.read_bytes())

    def test_binding_schema_rejects_extra_claim_of_authenticity(self):
        result, content = self.derive()
        self.assertTrue(result["valid"], result)
        binding = copy.deepcopy(result["binding"])
        binding["authority"]["edition"] = "authenticated"
        problems = validate_parent_window_binding(binding, content)
        self.assertTrue(problems)
        self.assertTrue(any("schema" in x for x in problems), problems)


if __name__ == "__main__":
    unittest.main()
