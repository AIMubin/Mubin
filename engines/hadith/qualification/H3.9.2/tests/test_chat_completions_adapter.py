from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.chat_completions import (
    AdapterDiagnosticError,
    RetrievalIndex,
    MAX_RESPONSE_BYTES,
    _NoRedirect,
    _call_chat,
    _curator_row,
    _extract_message_content,
    _strip_json_fence,
    _supports_from_model,
    _system_prompt,
    _validate_base_url,
    _verifier_row,
)
from benchmark_campaign.core import dump_jsonl


class ChatCompletionsAdapterTests(unittest.TestCase):
    def _index(self, root: Path) -> RetrievalIndex:
        index = root / "index"
        index.mkdir()
        rows = [
            {
                "source_id": "s1",
                "source_blob_sha": "a" * 40,
                "segment_id": "seg-1",
                "locator": f"gitblob:{'a' * 40}#char=0:40",
                "char_start": 0,
                "char_end": 40,
                "text": "قال الإمام سمع من شيخه وهذا نص ثابت",
                "text_sha256": "1" * 64,
            },
            {
                "source_id": "s2",
                "source_blob_sha": "b" * 40,
                "segment_id": "seg-2",
                "locator": f"gitblob:{'b' * 40}#char=100:145",
                "char_start": 100,
                "char_end": 145,
                "text": "وفي الطريق الآخر ثبت أنه سمع من الشيخ نفسه",
                "text_sha256": "2" * 64,
            },
            {
                "source_id": "s2",
                "source_blob_sha": "b" * 40,
                "segment_id": "seg-3",
                "locator": f"gitblob:{'b' * 40}#char=200:238",
                "char_start": 200,
                "char_end": 238,
                "text": "نص بعيد لا علاقة له بموضوع السماع",
                "text_sha256": "3" * 64,
            },
        ]
        dump_jsonl(index / "segments.jsonl", rows)
        return RetrievalIndex(index)

    def _task(self):
        anchor_text = "قال الإمام سمع من شيخه وهذا نص ثابت"
        return {
            "task_id": "b1:non_holdout:s1:0001",
            "benchmark_id": "b1",
            "risk_tier": 1,
            "task_type": "classification",
            "allowed_labels": ["yes", "no"],
            "retrieval_terms": ["سمع من"],
            "anchor_source_id": "s1",
            "allowed_source_pool": ["s1", "s2"],
            "anchor_segment": {
                "source_id": "s1",
                "source_blob_sha": "a" * 40,
                "segment_id": "seg-1",
                "locator": f"gitblob:{'a' * 40}#char=0:{len(anchor_text)}",
                "char_start": 0,
                "char_end": len(anchor_text),
                "text": anchor_text,
                "text_sha256": "1" * 64,
            },
        }

    def test_retrieval_is_source_diverse_and_anchor_first(self):
        with tempfile.TemporaryDirectory() as d:
            idx = self._index(Path(d))
            evidence = idx.evidence_for_task(self._task(), 12, 1800)
            self.assertEqual(evidence[0]["source_id"], "s1")
            self.assertEqual([x["source_id"] for x in evidence], ["s1", "s2"])
            self.assertIn("سمع", evidence[1]["excerpt"])
            self.assertTrue(evidence[1]["locator"].startswith("gitblob:" + "b" * 40))

    def test_base_url_rejects_credentials_query_and_non_https(self):
        for value in (
            "http://example.test/v1",
            "https://user:pass@example.test/v1",
            "https://example.test/v1?token=secret",
            "https://example.test/v1#fragment",
        ):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _validate_base_url(value)
        self.assertEqual(
            _validate_base_url("https://example.test/api/v1/"),
            "https://example.test/api/v1",
        )

    def test_redirect_handler_is_fail_closed(self):
        handler = _NoRedirect()
        self.assertIsNone(
            handler.redirect_request(None, None, 302, "Found", {}, "https://other.test/")
        )

    def test_model_response_size_is_capped(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self, size):
                return b"x" * (MAX_RESPONSE_BYTES + 1)

        class FakeOpener:
            def open(self, req, timeout):
                return FakeResponse()

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
            with self.assertRaisesRegex(ValueError, "response exceeds size limit"):
                _call_chat(
                    "https://example.test/v1",
                    "secret",
                    "bearer",
                    "model-x",
                    "system",
                    "user",
                    10,
                    0.0,
                    128,
                    "off",
                )

    def test_http_status_is_reduced_to_safe_diagnostic_code(self):
        import urllib.error
        with patch(
            "adapters.chat_completions.urllib.request.build_opener"
        ) as build:
            opener = build.return_value
            opener.open.side_effect = urllib.error.HTTPError(
                "https://example.test/v1/chat/completions",
                401,
                "details not exposed",
                {},
                None,
            )
            with self.assertRaises(AdapterDiagnosticError) as ctx:
                _call_chat(
                    "https://example.test/v1",
                    "secret",
                    "bearer",
                    "model-x",
                    "system",
                    "user",
                    10,
                    0.0,
                    128,
                    "off",
                )
            self.assertEqual(ctx.exception.code, "http_401")
            self.assertNotIn("details not exposed", str(ctx.exception))

    def test_connection_failure_is_reduced_to_safe_diagnostic_code(self):
        import urllib.error
        with patch(
            "adapters.chat_completions.urllib.request.build_opener"
        ) as build:
            opener = build.return_value
            opener.open.side_effect = urllib.error.URLError("sensitive transport detail")
            with self.assertRaises(AdapterDiagnosticError) as ctx:
                _call_chat(
                    "https://example.test/v1",
                    "secret",
                    "bearer",
                    "model-x",
                    "system",
                    "user",
                    10,
                    0.0,
                    128,
                    "off",
                )
            self.assertEqual(ctx.exception.code, "connection_failed")
            self.assertNotIn("sensitive transport detail", str(ctx.exception))

    def test_support_mapping_requires_verbatim_retrieved_evidence(self):
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:10",
            "excerpt": "سمع من شيخه",
        }]
        with self.assertRaisesRegex(ValueError, "verbatim"):
            _supports_from_model(
                [{"evidence_id": "E01", "support_text": "نص غير موجود"}],
                evidence,
            )

    def test_curator_adapter_constructs_deterministic_record_fields(self):
        task = self._task()
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:20",
            "excerpt": "قال الإمام سمع من شيخه",
        }]
        row = _curator_row(task, {
            "status": "candidate",
            "family_id": "narrator-pair-x",
            "input": {"question": "هل ثبت السماع؟"},
            "gold": {"label": "yes"},
            "mode": "direct_extract",
            "verbatim_answer": "سمع من شيخه",
            "supports": [{"evidence_id": "E01", "support_text": "سمع من شيخه"}],
        }, evidence)
        candidate = row["candidate"]
        self.assertEqual(candidate["benchmark_id"], "b1")
        self.assertEqual(candidate["anchor_source_id"], "s1")
        self.assertFalse(candidate["synthetic"])
        self.assertEqual(candidate["payload"]["gold"], {"label": "yes"})
        self.assertEqual(candidate["source_refs"][0]["locator"], evidence[0]["locator"])

    def test_verifier_adapter_maps_only_blind_evidence(self):
        task = self._task()
        task["candidate_input"] = {"question": "هل ثبت السماع؟"}
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:20",
            "excerpt": "قال الإمام سمع من شيخه",
        }]
        row = _verifier_row(task, {
            "status": "candidate",
            "gold": {"label": "yes"},
            "supports": [{"evidence_id": "E01", "support_text": "سمع من شيخه"}],
        }, evidence)
        self.assertEqual(row["answer"]["gold"], {"label": "yes"})
        self.assertNotIn("candidate", row)

    def test_system_prompt_marks_sources_as_untrusted_data(self):
        prompt = _system_prompt("curator", "contract")
        self.assertIn("untrusted DATA", prompt)
        self.assertIn("Do not use memory", prompt)
        self.assertIn("no_candidate", prompt)

    def test_json_fence_and_content_extraction_are_tolerant(self):
        fence = chr(96) * 3
        raw = fence + "json\n" + json.dumps({"status": "no_candidate"}) + "\n" + fence
        self.assertEqual(
            json.loads(_strip_json_fence(raw))["status"],
            "no_candidate",
        )
        self.assertEqual(
            _extract_message_content({
                "choices": [{"message": {"content": [{"text": "{\"x\":1}"}]}}]
            }),
            "{\"x\":1}",
        )


if __name__ == "__main__":
    unittest.main()
