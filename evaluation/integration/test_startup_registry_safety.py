"""A01/B01 API boundary regressions for invalid Python objects and references.

These tests use no Quran, Hadith or Tafsir source corpus or private files.
"""
from __future__ import annotations

import unittest

from core.contracts import ContractError, EngineRegistry
from core.orchestration import CasePlan, run_case
from core.orchestration.engine_adapters import build_engine_registry


SNAPSHOTS = ("snap.regtest.001",)


def _node(name, ref):
    return {
        "id": name, "engine": "tafsir", "operation": "research_verse",
        "inputs": {"reference": ref}, "depends_on": [],
        "timeout_ms": 1000, "max_results": 3,
    }


class StartupInputTests(unittest.TestCase):
    def test_unhashable_snapshot_members_raise_contract_error(self):
        for bad in (("snap.valid", []), (["snap.bad"],), ({"bad": 1},)):
            with self.subTest(snapshot_type=type(bad[0]).__name__):
                with self.assertRaisesRegex(
                        ContractError, "ADAPTER_SNAPSHOT_CONFIG_INVALID"):
                    build_engine_registry(snapshot_ids=bad)

    def test_registry_rejects_unhashable_engine_at_registration(self):
        registry = EngineRegistry()
        for engine in ([], {}, ["quran"], None):
            with self.subTest(type=type(engine).__name__):
                with self.assertRaisesRegex(
                        ContractError, "REGISTRY_ENGINE_INVALID"):
                    registry.register(engine, ("test_lookup",), lambda req: req)

    def test_registry_rejects_unhashable_lookup_arguments(self):
        registry = EngineRegistry()
        handler = lambda req: req
        registry.register("quran", ("test_lookup",), handler)
        self.assertIs(registry.resolve("quran", "test_lookup"), handler)
        for invalid in ([], {}, ["quran"], None):
            with self.subTest(engine=repr(invalid)):
                with self.assertRaisesRegex(ContractError, "ENGINE_UNAVAILABLE"):
                    registry.resolve(invalid, "test_lookup")
            with self.subTest(operation=repr(invalid)):
                with self.assertRaisesRegex(ContractError, "OPERATION_UNSUPPORTED"):
                    registry.resolve("quran", invalid)

    def test_duplicate_snapshots_still_rejected(self):
        with self.assertRaisesRegex(ContractError, "ADAPTER_SNAPSHOT_CONFIG_INVALID"):
            build_engine_registry(snapshot_ids=("snap.valid", "snap.valid"))

    def test_valid_registry_retains_all_five_engines(self):
        names = set(build_engine_registry(snapshot_ids=SNAPSHOTS).capabilities())
        self.assertEqual(names, {"quran", "tafsir", "hadith", "usul", "fiqh"})


class ReferenceSafetyTests(unittest.IsolatedAsyncioTestCase):
    async def test_oversized_ascii_digit_reference_is_rejected_not_error(self):
        for reference in ("9" * 5000 + ":1", "1:" + "9" * 5000):
            with self.subTest(part=reference[:7]):
                case = CasePlan(
                    "case.regtest.001", "profile.regtest", SNAPSHOTS,
                    (_node("run.tafsir.001", reference),))
                output = await run_case(
                    case, build_engine_registry(snapshot_ids=SNAPSHOTS))
                self.assertEqual(output["status"], "REJECTED")
                self.assertIn("ENGINE_CONTRACT_REJECTED",
                              output["nodes"][0]["result"]["uncertainties"])
                self.assertNotIn("ENGINE_EXECUTION_FAILED", str(output))

    async def test_normal_padded_reference_retains_current_parsing(self):
        case = CasePlan(
            "case.regtest.001", "profile.regtest", SNAPSHOTS,
            (_node("run.tafsir.001", "000001:000001"),))
        output = await run_case(
            case, build_engine_registry(snapshot_ids=SNAPSHOTS))
        # The reference is valid, but no private Tafsir database was provided.
        self.assertEqual(output["status"], "UNAVAILABLE")
        self.assertIn("TAFSIR_DB_UNAVAILABLE",
                      output["nodes"][0]["result"]["uncertainties"])


if __name__ == "__main__":
    unittest.main()
