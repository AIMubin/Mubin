"""B02-C.6 synthetic source-window positives and adversarial boundaries."""
from __future__ import annotations

import copy
import hashlib
import json
import unittest

from core.orchestration.hadith_witness_identity import (
    WitnessIdentityError, assess_hadith_witness_identity,
)

MATN = "هذا مثال اصطناعي لتجربة المطابقة النصية ولا يمثل رواية حديثية".encode("utf-8")
ALTERED = "هذا مثال اصطناعي مختلف لتجربة المطابقة النصية ولا يمثل رواية حديثية".encode("utf-8")
PREFIX = b"CONTEXT_START_1234567890"
SUFFIX = b"CONTEXT_END_1234567890"
ISNAD_ONE = b"SYNTHETIC_CHAIN_ONE____"
ISNAD_TWO = b"SYNTHETIC_CHAIN_TWO____"


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def canon(x):
    return json.dumps(x, sort_keys=True, ensure_ascii=False,
                      allow_nan=False, separators=(",", ":")).encode("utf-8")


def span(raw, a, b):
    return {"start_byte": a, "end_byte": b, "sha256": digest(raw[a:b])}


def dataset(second=True, same_work=False, altered=False, coverage=True):
    sources = {
        "source.one": PREFIX + ISNAD_ONE + MATN + SUFFIX,
    }
    if second:
        sources["source.two"] = (
            PREFIX + ISNAD_TWO + (ALTERED if altered else MATN) + SUFFIX)
    registry = {}
    witnesses = []
    for i, (sid, raw) in enumerate(sources.items()):
        prefix = len(PREFIX)
        a = prefix + len(ISNAD_ONE if i == 0 else ISNAD_TWO)
        b = len(raw) - len(SUFFIX)
        work = "work.one" if i == 0 or same_work else "work.two"
        registry[sid] = {
            "source_sha256": digest(raw),
            "work_id": work,
            "version_ref": "version.original",
            "access_scope": "non_holdout",
        }
        witnesses.append({
            "role": "candidate" if i == 0 else "comparison",
            "source_id": sid, "work_id": work,
            "source_sha256": digest(raw),
            "version_ref": "version.original",
            "locator": "synthetic.locator",
            "segment_type": "MATN_CANDIDATE",
            "segment": span(raw, a, b),
            "context": span(raw, 0, len(raw)),
            "isnad": span(raw, prefix, a),
        })
    fragment = copy.deepcopy(witnesses[0]["segment"])
    request = {
        "contract": "mubin-hadith-witness-identity/1.0",
        "case_id": "case.synthetic.001",
        "hsearch_bridge": {
            "link_id": "hl.synthetic.001",
            "classification": "NARRATION_FRAGMENT_CANDIDATE",
            "receipt_sha256": "0" * 64,
        },
        "candidate_fragment": fragment,
        "witnesses": witnesses,
        "open_objection_ids": [],
    }
    bridge = {
        "contract": "mubin-hsearch-witness-bridge/1.0",
        "link_id": "hl.synthetic.001",
        "classification": "NARRATION_FRAGMENT_CANDIDATE",
        "witness_source_sha256": witnesses[0]["source_sha256"],
        "witness_span_sha256": fragment["sha256"],
        "pinned_source_count": 4 if coverage else 3,
        "source_unavailable": [] if coverage else ["source.missing"],
        "candidate_only": True,
        "narration_identity_verified": False,
        "grade_assigned": False,
    }
    raw_bridge = canon(bridge)
    request["hsearch_bridge"]["receipt_sha256"] = digest(raw_bridge)
    return request, registry, sources, raw_bridge


def run(x, reg, sources, bridge, **kwargs):
    def source_read(sid, start, end):
        return sources[sid][start:end]
    return assess_hadith_witness_identity(
        x, source_registry=reg,
        read_span=kwargs.get("read_span", source_read),
        read_bridge=kwargs.get("read_bridge", lambda link: bridge),
    )


class WitnessIdentityTests(unittest.TestCase):
    def test_exact_text_across_distinct_works_is_research_only(self):
        x, reg, sources, bridge = dataset()
        result = run(x, reg, sources, bridge)
        self.assertEqual(result["status"], "EXACT_MATN_CROSS_SOURCE_RESEARCH_ONLY")
        self.assertEqual(result["exact_matn_comparison_matches"], 1)
        self.assertEqual(result["isnad_spans_reported"], 2)
        self.assertFalse(result["raw_source_full_file_hash_recomputed"])
        for k in ("narration_identity_verified", "isnad_authenticated",
                  "hadith_grade_assigned", "scholarly_verified",
                  "scientific_chain_established", "juristic_inference_allowed",
                  "independent_source_families_verified",
                  "segment_boundaries_scholarly_verified", "text_included"):
            self.assertFalse(result[k])
        self.assertNotIn("مثال", json.dumps(result, ensure_ascii=False))

    def test_single_witness_cannot_identify_narration(self):
        x, reg, sources, bridge = dataset(second=False)
        self.assertEqual(run(x, reg, sources, bridge)["status"],
                         "UNDETERMINED")

    def test_same_work_edition_is_not_independent(self):
        x, reg, sources, bridge = dataset(same_work=True)
        self.assertEqual(run(x, reg, sources, bridge)["status"],
                         "UNDETERMINED")

    def test_byte_identical_mirrored_file_not_independent_witness(self):
        x, reg, sources, bridge = dataset()
        sources["source.two"] = sources["source.one"]
        reg["source.two"]["source_sha256"] = digest(sources["source.one"])
        x["witnesses"][1]["source_sha256"] = digest(sources["source.one"])
        for field in ("segment", "context", "isnad"):
            x["witnesses"][1][field] = copy.deepcopy(x["witnesses"][0][field])
        self.assertEqual(run(x, reg, sources, bridge)["status"],
                         "UNDETERMINED")

    def test_quote_label_cannot_point_outside_the_lexical_fragment(self):
        x, reg, sources, bridge = dataset()
        witness = x["witnesses"][0]
        witness["segment_type"] = "QURAN_QUOTE"
        witness["segment"] = witness.pop("isnad")
        with self.assertRaisesRegex(WitnessIdentityError,
                                    "FRAGMENT_OUTSIDE_REPORTED_SEGMENT"):
            run(x, reg, sources, bridge)

    def test_textual_variant_is_not_imagined_exact_match(self):
        x, reg, sources, bridge = dataset(altered=True)
        self.assertEqual(run(x, reg, sources, bridge)["status"],
                         "UNDETERMINED")

    def test_reported_quran_quote_never_becomes_narration(self):
        x, reg, sources, bridge = dataset()
        x["witnesses"][0]["segment_type"] = "QURAN_QUOTE"
        self.assertEqual(run(x, reg, sources, bridge)["status"],
                         "REPORTED_NON_NARRATION_SEGMENT")

    def test_reported_commentary_never_becomes_narration(self):
        x, reg, sources, bridge = dataset()
        x["witnesses"][0]["segment_type"] = "COMMENTARY"
        self.assertEqual(run(x, reg, sources, bridge)["status"],
                         "REPORTED_NON_NARRATION_SEGMENT")

    def test_open_objection_vetoes_identical_matn(self):
        x, reg, sources, bridge = dataset()
        x["open_objection_ids"] = ["obj.isnad.boundary"]
        self.assertEqual(run(x, reg, sources, bridge)["status"], "CONTESTED")

    def test_incomplete_coverage_stays_open(self):
        x, reg, sources, bridge = dataset(coverage=False)
        self.assertEqual(run(x, reg, sources, bridge)["status"],
                         "INCOMPLETE_HSEARCH_COVERAGE")

    def test_unicode_codepoint_offsets_must_not_be_passed_as_bytes(self):
        x, reg, sources, bridge = dataset()
        a = x["witnesses"][0]["segment"]
        a["start_byte"] -= 4
        with self.assertRaisesRegex(WitnessIdentityError,
                                    "WITNESS_SPAN_DIGEST_INVALID"):
            run(x, reg, sources, bridge)

    def test_source_pin_mismatch_rejected(self):
        x, reg, sources, bridge = dataset()
        x["witnesses"][0]["source_sha256"] = "f" * 64
        with self.assertRaisesRegex(WitnessIdentityError, "SOURCE_PIN_MISMATCH"):
            run(x, reg, sources, bridge)

    def test_holdout_source_cannot_enter(self):
        x, reg, sources, bridge = dataset()
        reg["source.two"]["access_scope"] = "holdout"
        with self.assertRaisesRegex(WitnessIdentityError, "SOURCE_PIN_MISMATCH"):
            run(x, reg, sources, bridge)

    def test_duplicate_source_not_independent(self):
        x, reg, sources, bridge = dataset()
        x["witnesses"][1]["source_id"] = x["witnesses"][0]["source_id"]
        with self.assertRaisesRegex(WitnessIdentityError, "DUPLICATE_SOURCE"):
            run(x, reg, sources, bridge)

    def test_two_candidate_spoof_rejected(self):
        x, reg, sources, bridge = dataset()
        x["witnesses"][1]["role"] = "candidate"
        with self.assertRaisesRegex(WitnessIdentityError,
                                    "EXACT_ONE_CANDIDATE_REQUIRED"):
            run(x, reg, sources, bridge)

    def test_isnad_matn_boundary_overlap_rejected(self):
        x, reg, sources, bridge = dataset()
        x["witnesses"][0]["isnad"]["end_byte"] += 1
        with self.assertRaisesRegex(WitnessIdentityError, "ISNAD_MATN_OVERLAP"):
            run(x, reg, sources, bridge)

    def test_context_cannot_be_matn_alone(self):
        x, reg, sources, bridge = dataset()
        x["witnesses"][0]["context"] = copy.deepcopy(
            x["witnesses"][0]["segment"])
        with self.assertRaisesRegex(WitnessIdentityError,
                                    "CONTEXT_INSUFFICIENT"):
            run(x, reg, sources, bridge)

    def test_bridge_digest_mismatch_rejected(self):
        x, reg, sources, bridge = dataset()
        x["hsearch_bridge"]["receipt_sha256"] = "0" * 64
        with self.assertRaisesRegex(WitnessIdentityError,
                                    "BRIDGE_DIGEST_MISMATCH"):
            run(x, reg, sources, bridge)

    def test_bridge_cannot_assert_identified_narration(self):
        x, reg, sources, bridge = dataset()
        b = json.loads(bridge)
        b["narration_identity_verified"] = True
        bridge = canon(b)
        x["hsearch_bridge"]["receipt_sha256"] = digest(bridge)
        with self.assertRaisesRegex(WitnessIdentityError, "BRIDGE_INVALID"):
            run(x, reg, sources, bridge)

    def test_output_never_allows_grade_field_in_request(self):
        x, reg, sources, bridge = dataset()
        x["hadith_grade"] = "SAHIH"
        with self.assertRaisesRegex(WitnessIdentityError, "SCHEMA_INVALID"):
            run(x, reg, sources, bridge)

    def test_read_failure_is_sanitized(self):
        x, reg, sources, bridge = dataset()
        def unsafe_reader(*a):
            raise RuntimeError("D:\\secret\\private.source")
        with self.assertRaisesRegex(WitnessIdentityError,
                                    "^WITNESS_LOCAL_READ_FAILED$"):
            run(x, reg, sources, bridge, read_span=unsafe_reader)

    def test_bridge_reader_error_is_sanitized(self):
        x, reg, sources, bridge = dataset()
        def unsafe_bridge(*a):
            raise RuntimeError("PRIVATE_KEY_LEAK")
        with self.assertRaisesRegex(WitnessIdentityError,
                                    "^WITNESS_BRIDGE_UNAVAILABLE$"):
            run(x, reg, sources, bridge, read_bridge=unsafe_bridge)

    def test_empty_registry_rejects_unpinned_sources(self):
        x, reg, sources, bridge = dataset()
        with self.assertRaisesRegex(WitnessIdentityError, "SOURCE_PIN_MISMATCH"):
            run(x, {}, sources, bridge)

    def test_matn_fragment_outside_mapped_candidate_rejected(self):
        x, reg, sources, bridge = dataset()
        f = x["candidate_fragment"]
        f["start_byte"] = x["witnesses"][0]["isnad"]["start_byte"]
        f["end_byte"] = x["witnesses"][0]["isnad"]["end_byte"]
        f["sha256"] = x["witnesses"][0]["isnad"]["sha256"]
        with self.assertRaisesRegex(WitnessIdentityError,
                                    "FRAGMENT_OUTSIDE_REPORTED_SEGMENT"):
            run(x, reg, sources, bridge)


if __name__ == "__main__":
    unittest.main()
