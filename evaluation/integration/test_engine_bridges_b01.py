"""B01: exercise real engine functions using clearly synthetic pinned test sources."""
from __future__ import annotations

import asyncio
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from core.contracts import ContractError
from core.orchestration import CasePlan, PlanError, run_case
from core.orchestration.engine_adapters import build_engine_registry
from engines.quran.q01.engine import load_snapshot

ROOT = Path(__file__).resolve().parents[2]
FIX = ROOT / "engines/quran/fixtures"
TEXT = ("قال رسول الله: قصة اصطناعية طويلة لامتحان اكتشاف إشارة "
        "الرواية والتحقق من إحداثيات المقطع فقط.")
SHA = hashlib.sha256(TEXT.encode("utf-8")).hexdigest()
EVIDENCE = f"tafsir:tafsir_tabari:2:43:{SHA}"


def node(name, engine, op, data, deps=()):
    return {"id": name, "engine": engine, "operation": op, "inputs": data,
            "depends_on": list(deps), "timeout_ms": 5000, "max_results": 20}


def model():
    return {
        "schema_version": "0.1.0", "methodology_id": "profile.research",
        "facts": [{"atom": "fact.one", "truth": "true",
                   "source_evidence_ids": ["ev.test"]}],
        "rules": [{"id": "rule.one", "methodology_id": "profile.research",
                   "rule_kind": "propositional_demo",
                   "if_all": [{"atom": "fact.one", "truth": "true"}],
                   "unless_any": [], "then": {"atom": "candidate.one", "truth": "true"},
                   "source_evidence_ids": ["ev.test"]}],
        "objections": [],
    }


class EngineBridgeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db = Path(self.temp.name) / "original_source.db"
        con = sqlite3.connect(self.db)
        con.execute("CREATE TABLE tafsirs(source TEXT, sura INTEGER, aya INTEGER, text TEXT)")
        con.execute("INSERT INTO tafsirs VALUES(?, ?, ?, ?)", ("tabari", 2, 43, TEXT))
        con.commit()
        con.close()
        db_hash = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.lookup = {
            "contract": "mubin-tafsir-t01-v1", "quran_reference": "2:43",
            "tafsir_count": 1,
            "corpus": {
                "linked_database_pin_matched": True,
                "linked_sqlite_sha256": db_hash,
                "original_upstream_sqlite_sha256_declared": "0" * 64,
                "source_dataset": "synthetic",
            },
            "tafsirs": [{
                "work_id": "tafsir_tabari", "work_title_ar": "جامع البيان",
                "author_ar": "محمد بن جرير الطبري",
                "dataset_source_key": "tabari",
                "display_status": "SOURCE_TEXT_UNVERIFIED_EDITION",
                "edition_authenticated": False, "quality_flags": [],
                "evidence_id": EVIDENCE, "imported_record_sha256": SHA,
                "verse_locator": "2:43", "text": TEXT,
                "text_access": "LOCAL_RESEARCH", "source_dataset": "synthetic",
            }],
        }
        def fake_metadata(db, ref, *, include_private_text=False):
            if ref != "2:43":
                raise ValueError("TEST_REFERENCE_NOT_AVAILABLE")
            return dict(self.lookup)
        # Only the metadata intake is stubbed. T0.2, T0.2.3 and H-Search
        # still validate the original SQLite row and apply existing algorithms.
        patchers = [
            patch("engines.tafsir.t03.lookup_verse", side_effect=fake_metadata),
            patch("engines.tafsir.t01.lookup_verse", side_effect=fake_metadata),
        ]
        for patcher in patchers:
            patcher.start()
            self.addCleanup(patcher.stop)
        manifest = json.loads((FIX / "q01-manifest-synthetic.json").read_bytes())
        corpus = json.loads((FIX / "q01-verses-synthetic.json").read_bytes())
        # Extend the existing synthetic snapshot with the *same* coordinate
        # used by the Tafsir and Hadith fixtures. No authentic Quran text.
        corpus["verses"].append({
            "surah": 2, "ayah": 43, "text": "بيانات اصطناعية للاختبار فقط"})
        raw = (json.dumps(corpus, sort_keys=True, ensure_ascii=True,
                          separators=(",", ":")) + "\\n").encode("utf-8")
        manifest["raw_sha256"] = hashlib.sha256(raw).hexdigest()
        manifest["declared_verse_count"] = len(corpus["verses"])
        self.quran = load_snapshot(json.dumps(manifest).encode("utf-8"), raw)
        self.ids = ("snap.synthetic.quran", "snap.synthetic.tafsir")
        self.registry = build_engine_registry(
            snapshot_ids=self.ids, quran_index=self.quran, tafsir_db=self.db)

    def case(self, *nodes, ids=None, case_id="case.synthetic"):
        return CasePlan(case_id, "profile.research",
                        self.ids if ids is None else ids, tuple(nodes), 4)

    async def test_all_five_run_actual_code_no_fatwa(self):
        entries = (
            node("n.quran", "quran", "lookup_verse", {"reference": "2:43"}),
            node("n.tafsir", "tafsir", "research_verse", {"reference": "2:43"}),
            node("n.hadith", "hadith", "detect_tafsir_mentions", {"reference": "2:43"}),
            node("n.usul", "usul", "evaluate_proposition", {"model": model()}),
            node("n.fiqh", "fiqh", "prepare_case", {
                "question": "مسألة اختبار اصطناعي",
                "opinions": [{"opinion_id": "op.synthetic", "source_ref": EVIDENCE}],
            }, deps=("n.quran", "n.tafsir", "n.hadith", "n.usul")),
        )
        result = await run_case(self.case(*entries), self.registry)
        by = {x["node_id"]: x["result"] for x in result["nodes"]}
        self.assertEqual(by["n.quran"]["status"], "OK")
        self.assertEqual(by["n.tafsir"]["status"], "OK")
        self.assertEqual(by["n.hadith"]["status"], "OK")
        self.assertEqual(by["n.usul"]["status"], "OK")
        self.assertEqual(by["n.fiqh"]["status"], "UNDETERMINED")
        self.assertEqual(result["status"], "PARTIAL")
        self.assertTrue(by["n.quran"]["findings"][0]["synthetic_fixture"])
        self.assertFalse(by["n.tafsir"]["findings"][0]["scholarly_verified"])
        self.assertFalse(by["n.hadith"]["findings"][0]["grade_assigned"])
        self.assertIn("SYNTHETIC_UPSTREAM_PRESENT", by["n.fiqh"]["uncertainties"])
        self.assertNotIn(TEXT, json.dumps(result, ensure_ascii=False))
        self.assertNotIn("public_fatwa_authorized", json.dumps(result))

    async def test_unavailable_tafsir_is_not_no_match(self):
        r = build_engine_registry(snapshot_ids=self.ids, quran_index=self.quran)
        report = await run_case(self.case(node("n.tafsir", "tafsir",
                                              "research_verse", {"reference": "2:43"})), r)
        self.assertEqual(report["status"], "UNAVAILABLE")

    async def test_wrong_source_pin_refused(self):
        report = await run_case(self.case(
            node("n.quran", "quran", "lookup_verse", {"reference": "1:1"}),
            ids=("snap.fake",)), self.registry)
        self.assertEqual(report["nodes"][0]["result"]["status"], "REJECTED")

    async def test_quran_missing_verse_not_synthetic_hit(self):
        report = await run_case(self.case(
            node("n.quran", "quran", "lookup_verse", {"reference": "2:44"})), self.registry)
        self.assertEqual(report["status"], "NO_MATCH")

    async def test_hadith_no_cue_does_not_claim_hadith_absence(self):
        with patch("engines.hadith.hsearch.mention.detect_all", return_value=[]):
            report = await run_case(self.case(
                node("n.hadith", "hadith", "detect_tafsir_mentions",
                     {"reference": "2:43"})), self.registry)
        self.assertEqual(report["status"], "NO_MATCH")
        self.assertIn("NO_NARRATION_CUE_IN_SCOPED_TAFSIR",
                      report["nodes"][0]["result"]["uncertainties"])

    async def test_cross_engine_mismatched_reference_blocks_fiqh(self):
        report = await run_case(self.case(
            node("n.quran", "quran", "lookup_verse", {"reference": "1:1"}),
            node("n.tafsir", "tafsir", "research_verse", {"reference": "2:43"}),
            node("n.fiqh", "fiqh", "prepare_case", {
                "question": "مسألة اصطناعية",
                "opinions": [{"opinion_id": "op.synthetic", "source_ref": EVIDENCE}],
            }, ("n.quran", "n.tafsir"))), self.registry)
        fiqh = report["nodes"][-1]["result"]
        self.assertEqual(fiqh["status"], "UNDETERMINED")
        self.assertIn("CROSS_ENGINE_REFERENCE_MISMATCH", fiqh["uncertainties"])

    async def test_fiqh_unbound_opinion_cannot_qualify(self):
        data = {"question": "مسألة اصطناعية",
                "opinions": [{"opinion_id": "op.synthetic", "source_ref": "ev.unbound"}]}
        report = await run_case(self.case(
            node("n.tafsir", "tafsir", "research_verse", {"reference": "2:43"}),
            node("n.fiqh", "fiqh", "prepare_case", data, ("n.tafsir",))), self.registry)
        out = report["nodes"][1]["result"]
        self.assertEqual(out["status"], "UNDETERMINED")
        self.assertIn("OPINION_SOURCE_NOT_IN_UPSTREAM_EVIDENCE", out["uncertainties"])

    async def test_mismatch_profile_does_not_execute_usul(self):
        broken = model()
        broken["methodology_id"] = "profile.other"
        report = await run_case(self.case(node(
            "n.usul", "usul", "evaluate_proposition", {"model": broken})), self.registry)
        self.assertEqual(report["status"], "REJECTED")

    async def test_cannot_request_unregistered_operation(self):
        report = await run_case(self.case(node(
            "n.quran", "quran", "publish_fatwa", {})), self.registry)
        self.assertEqual(report["status"], "REJECTED")

    async def test_fiqh_halts_when_upstream_engine_unavailable(self):
        r = build_engine_registry(snapshot_ids=self.ids)
        report = await run_case(self.case(
            node("n.tafsir", "tafsir", "research_verse", {"reference": "2:43"}),
            node("n.fiqh", "fiqh", "prepare_case", {
                "question": "اختبار", "opinions": []
            }, ("n.tafsir",))), r)
        self.assertEqual(report["nodes"][1]["result"]["status"], "UNDETERMINED")
        self.assertIn("DEPENDENCY_NOT_OK", report["nodes"][1]["result"]["uncertainties"])

    def test_never_accept_untrusted_path_from_request(self):
        with self.assertRaises(ContractError):
            build_engine_registry(snapshot_ids=self.ids, tafsir_db="/tmp/untrusted")

if __name__ == "__main__":
    unittest.main()
