"""B02-C.2 malicious metadata cannot be promoted to source or juristic proof."""
from __future__ import annotations
import copy
import unittest
from qa.check_b02c2_replay import ReplayError, verify_fiqh, verify_source_handles

def make_source():
    full, span = "a"*64, "b"*64
    handle = "ev.usul." + full[:24] + ".0.12." + span[:24]
    source = {
        "kind": "USUL_RAW_SOURCE_SPAN", "source_sha256": full,
        "span_sha256": span, "start_byte": 0, "end_byte": 12,
        "source_authenticated": False, "source_semantics_verified": False,
        "opinion_attributed": False, "synthetic_fixture": False,
        "source_text_included": False, "rule_id": "rule.001",
    }
    findings = []
    for i in range(4):
        s=copy.deepcopy(source)
        s["start_byte"]=i*20
        s["end_byte"]=i*20+12
        s["rule_id"]="rule.001" if i < 2 else "rule.002"
        s["source_sha256"]="a"*64 if i < 2 else "c"*64
        findings.append(s)
    refs=[f"ev.usul.{f['source_sha256'][:24]}.{f['start_byte']}.{f['end_byte']}.{f['span_sha256'][:24]}" for f in findings]
    return {"findings":findings, "evidence_refs":refs}


class ReplayGateTests(unittest.TestCase):
    def test_valid_synthetic_handles_still_do_not_authenticate(self):
        x=make_source()
        verify_source_handles(x, {"a"*64,"c"*64})

    def test_mismatch_handle_refused(self):
        x=make_source()
        x["evidence_refs"][0]="ev.usul.unverified"
        with self.assertRaises(ReplayError):
            verify_source_handles(x, {"a"*64,"c"*64})

    def test_false_source_authentication_refused(self):
        x=make_source()
        x["findings"][1]["source_authenticated"]=True
        with self.assertRaises(ReplayError):
            verify_source_handles(x, {"a"*64,"c"*64})

    def test_unknown_manifest_source_digest_refused(self):
        x=make_source()
        with self.assertRaises(ReplayError):
            verify_source_handles(x, {"d"*64,"c"*64})

    def test_duplicate_byte_bound_ref_refused(self):
        x=make_source()
        x["evidence_refs"][1]=x["evidence_refs"][0]
        with self.assertRaises(ReplayError):
            verify_source_handles(x, {"a"*64,"c"*64})

    def test_juristic_conclusion_not_promotable(self):
        basic={
            "status":"PARTIAL", "uncertainties":[
                "USUL_APPLICATION_NOT_EXECUTED",
                "SOURCE_SPAN_MATCH_NOT_OPINION_ATTRIBUTION"],
            "evidence_refs":["ev.usul.a","ev.usul.b"],
            "findings":[{"case_id":"case.001", "opinion_refs":["op.a","op.b"],
                         "linked_evidence_count":2,"authority":"RESEARCH_ONLY",
                         "juristic_conclusion":None,"source_claims_verified":False,
                         "opinion_source_attribution_verified":False}],
        }
        verify_fiqh(basic,["ev.usul.a","ev.usul.b"],
                    set(basic["evidence_refs"]),case_id="case.001")
        forged=copy.deepcopy(basic)
        forged["findings"][0]["juristic_conclusion"]="approved"
        with self.assertRaises(ReplayError):
            verify_fiqh(forged,["ev.usul.a","ev.usul.b"],
                        set(basic["evidence_refs"]),case_id="case.001")

if __name__ == "__main__":
    unittest.main()
