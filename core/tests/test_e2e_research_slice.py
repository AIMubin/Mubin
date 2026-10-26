"""E2E-01.1: genuine synthetic SQLite + signed qualification integration.

Reuses I0.1b's actual operator test fixture (11 sources, private texts), not
a mocked-out unified lookup or current_state. No scripture/keys in Git.
"""
from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from core.tests import test_quran_operator_workspace_i01b as workspace_fixture
from engines.e2e.research_slice import (
    CONTRACT, QUESTION, ResearchSliceError, research_slice, main,
)
from engines.quran.research.private_adapters import PrivateResearchAdapters
from engines.quran.research import qualification as qual
from engines.usul.pilots.amr_default import run_pilot


class E2EResearchSliceTests(unittest.TestCase):
    def setUp(self):
        workspace_fixture.WorkspaceTests.setUp(self)
        # Reuse only its signed SQLite/ledger fixtures, not its HTTP server.
        # Stop the idle server thread before cleanup closes its socket:
        # on Windows the reverse order causes WinError 10038 despite tests
        # reporting OK. E2E-01.1 does not expose an HTTP endpoint.
        self.server.shutdown()
        workspace_fixture.WorkspaceTests.qual_initialize(self)
        self.adapters = PrivateResearchAdapters(
            vault=self.vault, corpus_db=self.corpus, sidecar_db=self.sidecar,
            registry=self.registry, anchor_dir=self.anchor,
            evidence_key=self.evidence_key)

    def output(self, *, reference="2:1", question=QUESTION):
        return research_slice(
            self.adapters, reference, question,
            ledger=self.qual_ledger,
            qualification_anchor_dir=self.qual_anchor,
            qualification_key=self.qual_key, vault=self.vault)

    def test_actual_eleven_source_integration_with_synthetic_sqlite(self):
        out = self.output()
        self.assertEqual(out["contract"], CONTRACT)
        self.assertEqual(out["research_mode"], "metadata_only")
        self.assertEqual(out["quran_retrieval"]["contract"],
                         "mubin-operator-qualified-retrieval-v0.1")
        self.assertEqual(len(out["quran_retrieval"]["sources"]), 11)
        self.assertTrue(all(row["coordinate_present"]
                            for row in out["quran_retrieval"]["sources"]))
        self.assertEqual(len(out["qualification_states"]), 11)
        self.assertEqual(out["usul_analysis"]["pilot"], "waraqat-bab-al-amr")
        self.assertEqual(out["usul_analysis"]["scenario_kind"],
                         "SYNTHETIC_TEST_INPUTS")
        self.assertEqual(len(out["usul_analysis"]["cases"]), 4)
        self.assertFalse(out["research_linkage"]["verse_is_evidence_for_usul_rule"])
        self.assertEqual(out["research_linkage"]["status"], "UNASSESSED")
        self.assertFalse(out["limits"]["source_authenticated"])
        self.assertFalse(out["limits"]["public_fatwa_authorized"])

    def test_determinism_on_unchanged_signed_inputs(self):
        left = json.dumps(self.output(), sort_keys=True, ensure_ascii=False)
        right = json.dumps(self.output(), sort_keys=True, ensure_ascii=False)
        self.assertEqual(left, right)

    def test_no_private_text_or_rule_excerpt_leaked(self):
        text = json.dumps(self.output(), ensure_ascii=False)
        self.assertNotIn(workspace_fixture.PLACEHOLDER, text)
        self.assertNotIn("synthetic-footnote-only", text)
        self.assertNotIn("وصيغته افعل", text)
        self.assertFalse(self.output()["limits"]["text_included"])

    def test_out_of_scope_question_refused_not_answered_with_fixed_pilot(self):
        with self.assertRaisesRegex(
                ResearchSliceError, "E2E_QUESTION_OUT_OF_SCOPE"):
            self.output(question="ما حكم مسألة لا علاقة لها بباب الأمر؟")

    def test_real_signed_ledger_rejection_not_reported_as_unreviewed(self):
        workspace_fixture.WorkspaceTests._record(
            self, "SOURCE_REJECTED")
        out = self.output()
        self.assertEqual(
            out["qualification_states"]["qe_ar_muyassar"]["scholarly"],
            "SOURCE_REJECTED")
        self.assertFalse(out["limits"]["scholarly_verified"])

    def test_ledger_tamper_refused(self):
        self.qual_ledger.write_bytes(b"unsigned-forgery")
        with self.assertRaises(qual.QualificationError):
            self.output()

    def test_evidence_head_change_during_pilot_refused(self):
        def change_mid_pilot():
            result = run_pilot()
            self.mock_evidence.return_value["head_entry_sha256"] = "c" * 64
            return result
        with patch("engines.e2e.research_slice.run_pilot",
                   side_effect=change_mid_pilot):
            with self.assertRaisesRegex(
                    ResearchSliceError, "E2E_EVIDENCE_HEAD_CHANGED"):
                self.output()

    def test_cli_refuses_unavailable_private_paths_without_traceback(self):
        import contextlib
        import io
        fake = str(self.root / "not-found")
        argv = ["--ref", "2:1", "--question", QUESTION]
        for flag in ("vault", "corpus-db", "sidecar-db", "registry",
                     "anchor-dir", "evidence-key", "qualification-ledger",
                     "qualification-anchor-dir", "qualification-key"):
            argv.extend(["--" + flag, fake])
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(argv), 1)
        refused = json.loads(output.getvalue())
        self.assertEqual(refused["status"], "REFUSED")
        self.assertFalse(refused["text_included"])
        self.assertNotIn(fake, output.getvalue())


if __name__ == "__main__":
    unittest.main()
