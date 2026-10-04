from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from benchmark_campaign.readiness import (
    _adapter_command,
    _build_canary_fixture,
    _diagnostic_from_stderr,
    _load_bound_offline_report,
    _validate_canary_output,
    run_live_readiness,
)


class ReadinessGateTests(unittest.TestCase):
    def test_curator_canary_fixture_is_full_evidence_surface_without_holdout(self):
        with tempfile.TemporaryDirectory() as d:
            index_dir, task_path, task = _build_canary_fixture(
                Path(d), "curator", "classification"
            )
            rows = [
                json.loads(line)
                for line in (index_dir / "segments.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            self.assertEqual(len(rows), 12)
            self.assertEqual(len(task["allowed_source_pool"]), 12)
            self.assertEqual(task["partition"], "non_holdout")
            self.assertEqual(task["task_type"], "classification")
            self.assertEqual(task["benchmark_id"], "transmission-language")
            self.assertIn("heard_from", task["allowed_labels"])
            self.assertIn("did_not_meet", task["allowed_labels"])
            self.assertNotIn("candidate_input", task)
            self.assertTrue(task_path.exists())

    def test_verifier_canary_fixture_exercises_multilabel_contract(self):
        with tempfile.TemporaryDirectory() as d:
            _, _, task = _build_canary_fixture(
                Path(d), "verifier", "multilabel"
            )
            self.assertEqual(task["task_type"], "multilabel")
            self.assertEqual(task["benchmark_id"], "external-critical-commentary")
            self.assertIn("continuity_negative", task["allowed_labels"])
            self.assertIn("non_encounter", task["allowed_labels"])
            self.assertIsInstance(task["candidate_input"], dict)

    def test_curator_canary_output_requires_expected_candidate_gold(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.jsonl"
            good = {
                "task_id": "readiness:curator:classification",
                "status": "candidate",
                "candidate": {
                    "payload": {
                        "input": {"question": "q"},
                        "gold": {"label": "heard_from"},
                    },
                    "answer_provenance": {
                        "supports": [
                            {
                                "source_id": "readiness-source-01",
                                "support_text": "heard_from",
                            }
                        ]
                    },
                },
            }
            path.write_text(json.dumps(good) + "\n", encoding="utf-8")
            self.assertIsNone(
                _validate_canary_output("curator", "classification", path)
            )

            good["candidate"]["payload"]["gold"] = {"label": "did_not_meet"}
            path.write_text(json.dumps(good) + "\n", encoding="utf-8")
            self.assertEqual(
                _validate_canary_output("curator", "classification", path),
                "canary_semantic_mismatch",
            )

    def test_verifier_multilabel_canary_is_order_insensitive_but_exact(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.jsonl"
            row = {
                "task_id": "readiness:verifier:multilabel",
                "status": "candidate",
                "answer": {
                    "gold": {"labels": ["non_encounter", "continuity_negative"]},
                    "supports": [
                        {
                            "source_id": "readiness-source-01",
                            "support_text": "non_encounter continuity_negative",
                        }
                    ],
                },
            }
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            self.assertIsNone(
                _validate_canary_output("verifier", "multilabel", path)
            )

            row["answer"]["gold"] = {"labels": ["non_encounter"]}
            path.write_text(json.dumps(row) + "\n", encoding="utf-8")
            self.assertEqual(
                _validate_canary_output("verifier", "multilabel", path),
                "canary_semantic_mismatch",
            )

    def test_no_candidate_is_not_enough_for_live_readiness(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "out.jsonl"
            path.write_text(
                json.dumps({
                    "task_id": "readiness:curator:classification",
                    "status": "no_candidate",
                    "reason": "insufficient",
                }) + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _validate_canary_output("curator", "classification", path),
                "canary_no_candidate",
            )

    def test_diagnostic_extraction_ignores_arbitrary_stderr(self):
        stderr = (
            "provider detail that must not be promoted\n"
            "MUBIN_DIAGNOSTIC:connection_failed\n"
            "more arbitrary text\n"
        )
        self.assertEqual(
            _diagnostic_from_stderr(stderr),
            "connection_failed",
        )
        self.assertIsNone(_diagnostic_from_stderr("arbitrary only"))

    def test_offline_report_must_match_current_github_sha(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "offline.json"
            path.write_text(
                json.dumps({
                    "schema_version": 1,
                    "campaign_id": "H3.9.2",
                    "kind": "offline_readiness_gate",
                    "github_sha": "a" * 40,
                    "offline_protocol": {"passed": True},
                    "passed": True,
                }) + "\n",
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"GITHUB_SHA": "a" * 40}, clear=False):
                loaded = _load_bound_offline_report(path)
            self.assertTrue(loaded["passed"])

            with patch.dict(os.environ, {"GITHUB_SHA": "b" * 40}, clear=False):
                with self.assertRaisesRegex(ValueError, "current GitHub SHA"):
                    _load_bound_offline_report(path)

            data = json.loads(path.read_text(encoding="utf-8"))
            data["github_sha"] = None
            path.write_text(json.dumps(data) + "\n", encoding="utf-8")
            with patch.dict(os.environ, {"GITHUB_SHA": "a" * 40}, clear=False):
                with self.assertRaisesRegex(ValueError, "current GitHub SHA"):
                    _load_bound_offline_report(path)

    def test_live_readiness_runs_full_matrix_without_exposing_provider_identity(self):
        offline = {
            "offline_protocol": {
                "compile": "pass",
                "tests": "pass",
                "tests_run": 1,
                "failures": 0,
                "errors": 0,
                "skipped": 0,
                "passed": True,
            }
        }
        env = {
            "MUBIN_READINESS_CURATOR_ENDPOINT": "https://curator.secret.example/v1",
            "MUBIN_READINESS_CURATOR_MODEL_REF": "curator-secret-model",
            "MUBIN_READINESS_CURATOR_API_KEY": "curator-secret-key",
            "MUBIN_READINESS_VERIFIER_ENDPOINT": "https://verifier.secret.example/v1",
            "MUBIN_READINESS_VERIFIER_MODEL_REF": "verifier-secret-model",
            "MUBIN_READINESS_VERIFIER_API_KEY": "verifier-secret-key",
        }

        def fake_canary(
            root, role, task_type, endpoint, model_ref, api_key,
            auth_style, json_mode, live_timeout,
        ):
            return {
                "role": role,
                "task_type": task_type,
                "passed": True,
                "diagnostic": None,
                "duration_ms": 1,
            }

        with patch.dict(os.environ, env, clear=False), patch(
            "benchmark_campaign.readiness._run_live_canary",
            side_effect=fake_canary,
        ) as run:
            report = run_live_readiness(
                Path("/campaign"),
                offline,
                "bearer",
                "bearer",
                "json_object",
                "json_object",
                300,
            )

        self.assertTrue(report["ready"])
        self.assertEqual(run.call_count, 4)
        self.assertEqual(
            {(x["role"], x["task_type"]) for x in report["live_canaries"]},
            {
                ("curator", "classification"),
                ("curator", "multilabel"),
                ("verifier", "classification"),
                ("verifier", "multilabel"),
            },
        )
        serialized = json.dumps(report)
        for secret in env.values():
            self.assertNotIn(secret, serialized)

    def test_canary_command_matches_production_streaming_surface(self):
        root = Path("/campaign")
        cmd = _adapter_command(
            root,
            "curator",
            "https://example.test/v1",
            "bearer",
            "json_object",
            Path("/tmp/task.jsonl"),
            Path("/tmp/out.jsonl"),
            Path("/tmp/index"),
            300,
        )
        self.assertIn("--stream", cmd)
        self.assertIn("--json-mode", cmd)
        self.assertIn("json_object", cmd)
        self.assertIn("--max-evidence-sources", cmd)
        self.assertIn("12", cmd)
        self.assertIn("--max-excerpt-chars", cmd)
        self.assertIn("1800", cmd)
        self.assertNotIn("--completion-budget", cmd)
        self.assertNotIn("--reasoning-effort", cmd)


if __name__ == "__main__":
    unittest.main()
