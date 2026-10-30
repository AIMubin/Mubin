"""B02-C: trusted raw Usul bytes -> narrow source handles -> Fiqh RESEARCH_ONLY."""
from __future__ import annotations

import hashlib
import json
import unittest

from core.contracts import ContractError
from core.orchestration import CasePlan, run_case
from core.orchestration.engine_adapters import build_engine_registry

RAW = "قاعدة اختبار أصولية اصطناعية خالية من اعتماد فقهي".encode("utf-8")
SOURCE_ID = "usul.fixture.source"
FULL_SHA = hashlib.sha256(RAW).hexdigest()
SPAN_SHA = hashlib.sha256(RAW[:18]).hexdigest()
SNAPSHOTS = ("snap.b02c.001",)


def n(name, engine, operation, inputs, depends_on=()):
    return {"id": name, "engine": engine, "operation": operation,
            "inputs": inputs, "depends_on": list(depends_on),
            "timeout_ms": 1500, "max_results": 24}


def span(full_sha=FULL_SHA, span_sha=SPAN_SHA, start=0, end=18):
    return {"source_id": SOURCE_ID, "source_sha256": full_sha,
            "span_sha256": span_sha, "rule_id": "rule.example",
            "start_byte": start, "end_byte": end}


def configured(**kwargs):
    return build_engine_registry(
        snapshot_ids=SNAPSHOTS,
        usul_source_blobs={SOURCE_ID: RAW},
        usul_source_pins={SOURCE_ID: FULL_SHA},
        usul_sources_synthetic=True, **kwargs)


def plan(*nodes):
    return CasePlan("case.b02c.001", "method.example", SNAPSHOTS, tuple(nodes))


class SourceBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def test_pinned_usul_spans_emit_only_metadata(self):
        result = await run_case(plan(n("run.usul.001", "usul",
                           "bind_source_spans", {"spans": [span()]})), configured())
        self.assertEqual(result["status"], "OK")
        item = result["nodes"][0]["result"]
        self.assertTrue(item["evidence_refs"][0].startswith("ev.usul."))
        self.assertEqual(item["findings"][0]["source_sha256"], FULL_SHA)
        self.assertFalse(item["findings"][0]["opinion_attributed"])
        self.assertIn("SOURCE_BYTE_FIDELITY_ONLY_NO_JURISTIC_ATTRIBUTION",
                      item["uncertainties"])
        self.assertNotIn("قاعدة", json.dumps(result, ensure_ascii=False))

    async def test_unconfigured_sources_unavailable_not_no_match(self):
        reg = build_engine_registry(snapshot_ids=SNAPSHOTS)
        result = await run_case(plan(n("run.usul.001", "usul",
                           "bind_source_spans", {"spans": [span()]})), reg)
        self.assertEqual(result["status"], "UNAVAILABLE")

    async def test_wrong_span_digest_refused(self):
        result = await run_case(plan(n("run.usul.001", "usul",
                           "bind_source_spans", {"spans": [span(span_sha="0"*64)]})), configured())
        self.assertEqual(result["status"], "REJECTED")

    async def test_wrong_full_source_digest_refused(self):
        result = await run_case(plan(n("run.usul.001", "usul",
                           "bind_source_spans", {"spans": [span(full_sha="0"*64)]})), configured())
        self.assertEqual(result["status"], "REJECTED")

    async def test_invalid_byte_boundary_refused(self):
        result = await run_case(plan(n("run.usul.001", "usul",
                           "bind_source_spans", {"spans": [span(start=2, end=1)]})), configured())
        self.assertEqual(result["status"], "REJECTED")

    async def test_foreign_source_id_refused(self):
        s = span()
        s["source_id"] = "source.untrusted"
        result = await run_case(plan(n("run.usul.001", "usul",
                           "bind_source_spans", {"spans": [s]})), configured())
        self.assertEqual(result["status"], "REJECTED")

    async def test_duplicate_span_refused(self):
        result = await run_case(plan(n("run.usul.001", "usul",
                           "bind_source_spans", {"spans": [span(), span()]})), configured())
        self.assertEqual(result["status"], "REJECTED")

    async def test_usul_to_fiqh_bound_source_not_fatwa(self):
        expected_ref = f"ev.usul.{FULL_SHA[:24]}.0.18.{SPAN_SHA[:24]}"
        report = await run_case(plan(
            n("run.usul.001", "usul", "bind_source_spans", {"spans": [span()]}),
            n("run.fiqh.001", "fiqh", "prepare_case", {
                "question": "حالة اصطناعية",
                "opinions": [{"opinion_id": "op.synthetic", "source_ref": expected_ref}],
            }, ["run.usul.001"])), configured())
        entry = report["nodes"][1]["result"]
        self.assertEqual(entry["status"], "UNDETERMINED")  # synthetic is nonqualifying
        self.assertIn("SYNTHETIC_UPSTREAM_PRESENT", entry["uncertainties"])
        self.assertIn("SOURCE_SPAN_MATCH_NOT_OPINION_ATTRIBUTION", entry["uncertainties"])
        self.assertFalse(entry["findings"])
        self.assertEqual(report["status"], "PARTIAL")

    async def test_tafsir_only_evidence_cannot_link_fiqh_opinion(self):
        # Any stage other than the trusted Usul span adapter is NOT an opinion source.
        # The bridge cannot infer opinion attribution from verse locators or mention cues.
        reg = build_engine_registry(snapshot_ids=SNAPSHOTS)
        report = await run_case(plan(n("run.fiqh.001", "fiqh", "prepare_case", {
            "question": "اصطناعي", "opinions": [
                {"opinion_id": "op.synthetic", "source_ref": "ev.quran.1.1.fake"}],
        })), reg)
        self.assertEqual(report["status"], "UNDETERMINED")
        self.assertIn("OPINION_SOURCE_NOT_IN_UPSTREAM_EVIDENCE",
                      report["nodes"][0]["result"]["uncertainties"])

    def test_registry_declines_unpinned_bytes(self):
        with self.assertRaises(ContractError):
            build_engine_registry(snapshot_ids=SNAPSHOTS,
                                 usul_source_blobs={SOURCE_ID: RAW},
                                 usul_source_pins={SOURCE_ID: "0"*64})

    def test_registry_declines_source_paths_and_missing_pins(self):
        with self.assertRaises(ContractError):
            build_engine_registry(snapshot_ids=SNAPSHOTS,
                                 usul_source_blobs={SOURCE_ID: "C:\\private\\waraqat.txt"},
                                 usul_source_pins={SOURCE_ID: FULL_SHA})
        with self.assertRaises(ContractError):
            build_engine_registry(snapshot_ids=SNAPSHOTS,
                                 usul_source_blobs={SOURCE_ID: RAW})

if __name__ == "__main__":
    unittest.main()
