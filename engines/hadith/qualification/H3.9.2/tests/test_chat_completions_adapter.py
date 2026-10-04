from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from adapters.chat_completions import (
    AdapterDiagnosticError,
    ModelContractError,
    RetrievalIndex,
    MAX_RESPONSE_BYTES,
    _NoRedirect,
    _call_chat,
    _curator_row,
    _empty_output_diagnostic,
    _extract_finish_reason,
    _extract_message_content,
    _gold_contract_code,
    _has_reasoning_content,
    _parse_completion_budget,
    _parse_model_json_object,
    parse_args,
    _strip_json_fence,
    _supports_from_model,
    _system_prompt,
    _user_prompt,
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
                    "max_tokens",
                    None,
                    "off",
                )
            self.assertEqual(ctx.exception.code, "response_too_large")

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
                    "max_tokens",
                    None,
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
                    "max_tokens",
                    None,
                    "off",
                )
            self.assertEqual(ctx.exception.code, "connection_failed")
            self.assertNotIn("sensitive transport detail", str(ctx.exception))

    def test_wrapped_timeout_is_reduced_to_endpoint_timeout(self):
        import urllib.error
        with patch(
            "adapters.chat_completions.urllib.request.build_opener"
        ) as build:
            opener = build.return_value
            opener.open.side_effect = urllib.error.URLError(
                TimeoutError("sensitive timeout detail")
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
                    "max_tokens",
                    None,
                    "off",
                )
            self.assertEqual(ctx.exception.code, "endpoint_timeout")
            self.assertNotIn("sensitive timeout detail", str(ctx.exception))

    def test_read_stage_disconnect_is_reduced_to_connection_failed(self):
        import http.client

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self, size):
                raise http.client.IncompleteRead(b"partial", 100)

        class FakeOpener:
            def open(self, req, timeout):
                return FakeResponse()

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
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
                    "max_tokens",
                    None,
                    "off",
                )
            self.assertEqual(ctx.exception.code, "connection_failed")

    def test_read_stage_connection_reset_is_reduced_to_connection_failed(self):
        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self, size):
                raise ConnectionResetError("sensitive socket detail")

        class FakeOpener:
            def open(self, req, timeout):
                return FakeResponse()

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
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
                    "max_tokens",
                    None,
                    "off",
                )
            self.assertEqual(ctx.exception.code, "connection_failed")
            self.assertNotIn("sensitive socket detail", str(ctx.exception))

    def test_reference_adapter_defaults_to_native_inference_and_600_second_timeout(self):
        argv = [
            "chat_completions.py",
            "--input", "in.jsonl",
            "--output", "out.jsonl",
            "--index", "index",
            "--contract", "contract.md",
            "--base-url", "https://example.test/v1",
        ]
        with patch("sys.argv", argv):
            args = parse_args()
        self.assertEqual(args.timeout, 600)
        self.assertEqual(args.completion_budget, "auto")
        self.assertEqual(args.reasoning_effort, "provider_default")
        self.assertFalse(args.stream)

    def test_streaming_transport_reconstructs_final_content_without_reasoning_text(self):
        captured = {}

        class FakeResponse:
            def __init__(self):
                self.lines = iter([
                    b'data: {"choices":[{"delta":{"reasoning_content":"private reasoning"}}]}\n',
                    b'\n',
                    b'data: {"choices":[{"delta":{"content":"{\\"status\\":\\"no_"}}]}\n',
                    b'\n',
                    b'data: {"choices":[{"delta":{"content":"candidate\\",\\"reason\\":\\"x\\"}"},"finish_reason":"stop"}]}\n',
                    b'\n',
                    b'data: [DONE]\n',
                    b'\n',
                ])
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def readline(self, size):
                return next(self.lines, b"")

        class FakeOpener:
            def open(self, req, timeout):
                captured["payload"] = json.loads(req.data.decode("utf-8"))
                captured["accept"] = req.headers.get("Accept")
                return FakeResponse()

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
            response = _call_chat(
                "https://example.test/v1", "secret", "bearer", "model-x",
                "system", "user", 10, 0.0, None, "max_tokens", None,
                "json_object", stream=True,
            )
        self.assertTrue(captured["payload"]["stream"])
        self.assertEqual(captured["accept"], "text/event-stream")
        self.assertEqual(
            _extract_message_content(response),
            '{"status":"no_candidate","reason":"x"}',
        )
        self.assertEqual(_extract_finish_reason(response), "stop")
        self.assertTrue(_has_reasoning_content(response))
        self.assertNotIn(
            "private reasoning",
            json.dumps(response, ensure_ascii=False),
        )

    def test_streaming_transport_stops_reading_immediately_after_done_event(self):
        class FakeResponse:
            def __init__(self):
                self.lines = iter([
                    b'data: {"choices":[{"delta":{"content":"{}"}}]}\n',
                    b'\n',
                    b'data: [DONE]\n',
                    b'\n',
                ])
                self.calls = 0
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def readline(self, size):
                self.calls += 1
                if self.calls > 4:
                    raise AssertionError("stream parser read past DONE")
                return next(self.lines, b"")

        response = FakeResponse()

        class FakeOpener:
            def open(self, req, timeout):
                return response

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
            parsed = _call_chat(
                "https://example.test/v1", "secret", "bearer", "model-x",
                "system", "user", 10, 0.0, None, "max_tokens", None,
                "off", stream=True,
            )
        self.assertEqual(_extract_message_content(parsed), "{}")
        self.assertEqual(response.calls, 4)

    def test_streaming_transport_treats_unfinished_eof_as_connection_failure(self):
        class FakeResponse:
            def __init__(self):
                self.lines = iter([
                    b'data: {"choices":[{"delta":{"content":"{\\"status\\":"}}]}\n',
                    b'\n',
                ])
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def readline(self, size):
                return next(self.lines, b"")

        class FakeOpener:
            def open(self, req, timeout):
                return FakeResponse()

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
            with self.assertRaises(AdapterDiagnosticError) as ctx:
                _call_chat(
                    "https://example.test/v1", "secret", "bearer", "model-x",
                    "system", "user", 10, 0.0, None, "max_tokens", None,
                    "json_object", stream=True,
                )
        self.assertEqual(ctx.exception.code, "connection_failed")

    def test_streaming_transport_accepts_finish_reason_without_done_sentinel(self):
        class FakeResponse:
            def __init__(self):
                self.lines = iter([
                    b'data: {"choices":[{"delta":{"content":"{}"},"finish_reason":"stop"}]}\n',
                    b'\n',
                ])
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def readline(self, size):
                return next(self.lines, b"")

        class FakeOpener:
            def open(self, req, timeout):
                return FakeResponse()

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
            response = _call_chat(
                "https://example.test/v1", "secret", "bearer", "model-x",
                "system", "user", 10, 0.0, None, "max_tokens", None,
                "off", stream=True,
            )
        self.assertEqual(_extract_message_content(response), "{}")
        self.assertEqual(_extract_finish_reason(response), "stop")

    def test_completion_budget_parser_accepts_auto_or_unbounded_positive_integer(self):
        self.assertIsNone(_parse_completion_budget("auto"))
        self.assertIsNone(_parse_completion_budget(" AUTO "))
        self.assertEqual(_parse_completion_budget("8192"), 8192)
        self.assertEqual(_parse_completion_budget("1000000"), 1000000)
        for value in ("0", "-1", "8k", ""):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    _parse_completion_budget(value)

    def test_auto_completion_budget_omits_token_cap_and_reasoning_control(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self, size):
                return b'{"choices":[{"message":{"content":"{}"}}]}'

        class FakeOpener:
            def open(self, req, timeout):
                captured["payload"] = json.loads(req.data.decode("utf-8"))
                return FakeResponse()

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
            _call_chat(
                "https://example.test/v1", "secret", "bearer", "model-x",
                "system", "user", 10, 0.0, None, "max_tokens", None, "off",
            )
        payload = captured["payload"]
        self.assertNotIn("max_tokens", payload)
        self.assertNotIn("max_completion_tokens", payload)
        self.assertNotIn("reasoning_effort", payload)

    def test_explicit_completion_budget_uses_selected_field_and_reasoning_effort(self):
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                return False
            def read(self, size):
                return b'{"choices":[{"message":{"content":"{}"}}]}'

        class FakeOpener:
            def open(self, req, timeout):
                captured["payload"] = json.loads(req.data.decode("utf-8"))
                return FakeResponse()

        with patch(
            "adapters.chat_completions.urllib.request.build_opener",
            return_value=FakeOpener(),
        ):
            _call_chat(
                "https://example.test/v1", "secret", "bearer", "model-x",
                "system", "user", 10, 0.0, 32768,
                "max_completion_tokens", "low", "json_object",
            )
        payload = captured["payload"]
        self.assertEqual(payload["max_completion_tokens"], 32768)
        self.assertNotIn("max_tokens", payload)
        self.assertEqual(payload["reasoning_effort"], "low")
        self.assertEqual(payload["response_format"], {"type": "json_object"})

    def test_model_json_parser_accepts_direct_object(self):
        obj, mode = _parse_model_json_object('{"status":"no_candidate","reason":"x"}')
        self.assertEqual(obj["status"], "no_candidate")
        self.assertEqual(mode, "direct_json")

    def test_model_json_parser_accepts_single_fenced_object(self):
        fence = chr(96) * 3
        raw = fence + "json\n{\"status\":\"no_candidate\",\"reason\":\"x\"}\n" + fence
        obj, mode = _parse_model_json_object(raw)
        self.assertEqual(obj["status"], "no_candidate")
        self.assertEqual(mode, "single_fenced_json")

    def test_model_json_parser_accepts_one_embedded_object_only(self):
        raw = 'Preface text. {"status":"no_candidate","reason":"x"} End text.'
        obj, mode = _parse_model_json_object(raw)
        self.assertEqual(obj["status"], "no_candidate")
        self.assertEqual(mode, "single_embedded_json")

    def test_model_json_parser_nested_object_is_not_ambiguous(self):
        raw = 'Result: {"status":"candidate","gold":{"label":"yes"},"supports":[]}'
        obj, mode = _parse_model_json_object(raw)
        self.assertEqual(obj["gold"], {"label": "yes"})
        self.assertEqual(mode, "single_embedded_json")

    def test_model_json_parser_rejects_multiple_top_level_objects(self):
        raw = '{"status":"no_candidate"} text {"status":"no_candidate"}'
        with self.assertRaises(AdapterDiagnosticError) as ctx:
            _parse_model_json_object(raw)
        self.assertEqual(ctx.exception.code, "model_output_ambiguous_json")

    def test_model_json_parser_rejects_array_even_if_it_contains_object(self):
        raw = '[{"status":"no_candidate"}]'
        with self.assertRaises(AdapterDiagnosticError) as ctx:
            _parse_model_json_object(raw)
        self.assertEqual(ctx.exception.code, "model_output_not_object")

    def test_model_json_parser_rejects_structured_payload_outside_embedded_object(self):
        raw = '[metadata] {"status":"no_candidate"}'
        with self.assertRaises(AdapterDiagnosticError) as ctx:
            _parse_model_json_object(raw)
        self.assertEqual(ctx.exception.code, "model_output_ambiguous_json")

    def test_model_json_parser_rejects_malformed_single_object(self):
        raw = 'Result: {"status":"no_candidate",}'
        with self.assertRaises(AdapterDiagnosticError) as ctx:
            _parse_model_json_object(raw)
        self.assertEqual(ctx.exception.code, "model_output_invalid_json")

    def test_model_json_parser_rejects_nonstandard_constants(self):
        for raw in (
            '{"status":"no_candidate","reason":"x","extra":NaN}',
            '{"status":"no_candidate","reason":"x","extra":Infinity}',
            '{"status":"no_candidate","reason":"x","extra":-Infinity}',
            'Result: {"status":"no_candidate","reason":"x","extra":NaN}',
        ):
            with self.subTest(raw=raw):
                with self.assertRaises(AdapterDiagnosticError) as ctx:
                    _parse_model_json_object(raw)
                self.assertEqual(ctx.exception.code, "model_output_invalid_json")

    def test_model_json_parser_distinguishes_missing_and_unbalanced_objects(self):
        with self.assertRaises(AdapterDiagnosticError) as ctx:
            _parse_model_json_object("plain text only")
        self.assertEqual(ctx.exception.code, "model_output_no_json_object")
        with self.assertRaises(AdapterDiagnosticError) as ctx:
            _parse_model_json_object('Result: {"status":"no_candidate"')
        self.assertEqual(ctx.exception.code, "model_output_unbalanced_json")

    def test_response_metadata_helpers_are_content_safe(self):
        response = {
            "choices": [{
                "finish_reason": "length",
                "message": {"content": "", "reasoning_content": "private reasoning"},
            }]
        }
        self.assertEqual(_extract_finish_reason(response), "length")
        self.assertTrue(_has_reasoning_content(response))

    def test_empty_output_diagnostic_prefers_truncation_signal(self):
        self.assertEqual(
            _empty_output_diagnostic("length", True),
            "model_output_truncated",
        )
        self.assertEqual(
            _empty_output_diagnostic(None, True),
            "model_output_reasoning_only",
        )
        self.assertEqual(
            _empty_output_diagnostic(None, False),
            "model_output_empty",
        )

    def test_support_mapping_requires_verbatim_retrieved_evidence(self):
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:10",
            "excerpt": "سمع من شيخه",
        }]
        with self.assertRaises(ModelContractError) as ctx:
            _supports_from_model(
                [{"evidence_id": "E01", "support_text": "نص غير موجود"}],
                evidence,
            )
        self.assertEqual(ctx.exception.code, "contract_support_not_verbatim")
        self.assertIn("verbatim", str(ctx.exception))

    def test_support_contract_diagnostics_are_bounded_and_content_safe(self):
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:10",
            "excerpt": "سمع من شيخه",
        }]
        cases = [
            (None, "contract_supports_missing"),
            ([42], "contract_support_item_invalid"),
            ([{"evidence_id": 1, "support_text": "x"}], "contract_evidence_id_invalid"),
            ([{"evidence_id": "EXFIL", "support_text": "x"}], "contract_evidence_id_invalid"),
            ([{"evidence_id": "E01", "support_text": ""}], "contract_support_text_missing"),
        ]
        for value, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(ModelContractError) as ctx:
                    _supports_from_model(value, evidence)
                self.assertEqual(ctx.exception.code, code)
                self.assertNotIn("EXFIL", ctx.exception.code)

    def test_multiple_literal_supports_from_same_source_are_allowed(self):
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:40",
            "excerpt": "قال الإمام سمع من شيخه وهذا نص ثابت",
        }]
        supports = _supports_from_model([
            {"evidence_id": "E01", "support_text": "قال الإمام"},
            {"evidence_id": "E01", "support_text": "سمع من شيخه"},
        ], evidence)
        self.assertEqual(len(supports), 2)
        self.assertEqual({x["source_id"] for x in supports}, {"s1"})

    def test_no_candidate_reason_is_required_not_repaired(self):
        task = self._task()
        with self.assertRaises(ModelContractError) as ctx:
            _curator_row(task, {"status": "no_candidate"}, [])
        self.assertEqual(ctx.exception.code, "contract_reason_missing")

        verifier_task = self._task()
        verifier_task["candidate_input"] = {"question": "q"}
        with self.assertRaises(ModelContractError) as ctx:
            _verifier_row(verifier_task, {"status": "no_candidate", "reason": ""}, [])
        self.assertEqual(ctx.exception.code, "contract_reason_missing")

    def test_multilabel_gold_rejects_type_coercion(self):
        task = self._task()
        task["task_type"] = "multilabel"
        task["allowed_labels"] = ["1", "yes"]
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:20",
            "excerpt": "قال الإمام سمع من شيخه",
        }]
        obj = {
            "status": "candidate",
            "family_id": "family-x",
            "input": {"question": "q"},
            "gold": {"labels": [1]},
            "mode": "direct_extract",
            "verbatim_answer": "سمع من شيخه",
            "supports": [{"evidence_id": "E01", "support_text": "سمع من شيخه"}],
        }
        with self.assertRaises(ModelContractError) as ctx:
            _curator_row(task, obj, evidence)
        self.assertEqual(ctx.exception.code, "contract_gold_label_type_invalid")

    def test_curator_contract_diagnostics_identify_semantic_failure_class(self):
        task = self._task()
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:20",
            "excerpt": "قال الإمام سمع من شيخه",
        }]
        base = {
            "status": "candidate",
            "family_id": "family-x",
            "input": {"question": "هل ثبت السماع؟"},
            "gold": {"label": "yes"},
            "mode": "direct_extract",
            "verbatim_answer": "سمع من شيخه",
            "supports": [{"evidence_id": "E01", "support_text": "سمع من شيخه"}],
        }
        mutations = [
            ({"status": "unexpected"}, "contract_status_invalid"),
            ({"gold": {"label": "other"}}, "contract_gold_label_outside_contract"),
            ({"family_id": ""}, "contract_family_id_missing"),
            ({"family_id": " family-x "}, "contract_family_id_invalid"),
            ({"input": None}, "contract_input_missing"),
            ({"mode": "other"}, "contract_mode_invalid"),
            ({"mode": []}, "contract_mode_invalid"),
            ({"mode": {}}, "contract_mode_invalid"),
            ({"verbatim_answer": ""}, "contract_verbatim_missing"),
            ({"verbatim_answer": "غير موجود"}, "contract_verbatim_not_supported"),
        ]
        for change, code in mutations:
            with self.subTest(code=code):
                obj = dict(base)
                obj.update(change)
                with self.assertRaises(ModelContractError) as ctx:
                    _curator_row(task, obj, evidence)
                self.assertEqual(ctx.exception.code, code)

    def test_gold_diagnostics_distinguish_shape_type_duplicates_and_vocabulary(self):
        classification = {
            "task_type": "classification",
            "allowed_labels": ["yes", "no"],
        }
        self.assertEqual(
            _gold_contract_code([], classification),
            "contract_gold_not_object",
        )
        self.assertEqual(
            _gold_contract_code({"label": 1}, classification),
            "contract_gold_label_type_invalid",
        )
        self.assertEqual(
            _gold_contract_code({"label": "maybe"}, classification),
            "contract_gold_label_outside_contract",
        )

        multilabel = {
            "task_type": "multilabel",
            "allowed_labels": ["a", "b"],
        }
        self.assertEqual(
            _gold_contract_code({"label": "a"}, multilabel),
            "contract_gold_labels_missing",
        )
        self.assertEqual(
            _gold_contract_code({"labels": [1]}, multilabel),
            "contract_gold_label_type_invalid",
        )
        self.assertEqual(
            _gold_contract_code({"labels": ["a", "a"]}, multilabel),
            "contract_gold_labels_duplicate",
        )
        self.assertEqual(
            _gold_contract_code({"labels": ["c"]}, multilabel),
            "contract_gold_label_outside_contract",
        )

    def test_curator_row_keeps_unique_source_refs_with_multiple_same_source_supports(self):
        task = self._task()
        evidence = [{
            "evidence_id": "E01",
            "source_id": "s1",
            "locator": "gitblob:" + "a" * 40 + "#char=0:40",
            "excerpt": "قال الإمام سمع من شيخه وهذا نص ثابت",
        }]
        row = _curator_row(task, {
            "status": "candidate",
            "family_id": "family-x",
            "input": {"question": "هل ثبت السماع؟"},
            "gold": {"label": "yes"},
            "mode": "direct_extract",
            "verbatim_answer": "سمع من شيخه",
            "supports": [
                {"evidence_id": "E01", "support_text": "قال الإمام"},
                {"evidence_id": "E01", "support_text": "سمع من شيخه"},
            ],
        }, evidence)
        self.assertEqual(len(row["candidate"]["source_refs"]), 1)
        self.assertEqual(
            len(row["candidate"]["answer_provenance"]["supports"]),
            2,
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

    def test_curator_prompt_keeps_task_metadata_out_of_candidate_input(self):
        task = self._task()
        prompt = _user_prompt("curator", task, [])
        self.assertIn("end-user benchmark question/input", prompt)
        self.assertIn("allowed_labels", prompt)
        self.assertIn("Do not copy task metadata", prompt)
        self.assertIn("Multiple support_text spans may cite the same evidence/source", prompt)

    def test_verifier_prompt_states_exact_multilabel_gold_shape(self):
        task = self._task()
        task["task_type"] = "multilabel"
        task["allowed_labels"] = ["a", "b"]
        task["candidate_input"] = {"question": "q"}
        prompt = _user_prompt("verifier", task, [])
        self.assertIn("multilabel uses a non-empty gold.labels array", prompt)
        self.assertIn("exact strings from task.allowed_labels", prompt)

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
