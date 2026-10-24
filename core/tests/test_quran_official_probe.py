"""Official-domain Q0.1e-a probe: no text dissemination or authority promotion."""
from __future__ import annotations
import unittest
from unittest.mock import patch
from qa.quran_official_probe import run_probe, PRESET, OFFICIAL_URL, probe_source_bytes

MIRROR = b"1|1|\xd8\xb3\xd9\x8e\xd9\x84\xd8\xa7\xd9\x85\n"
SOURCE = b"1|1|\xd8\xb3\xd9\x8e\xd9\x84\xd8\xa7\xd9\x85\n"


def stub_result(**overrides):
    r={"comparison":"byte_identical","candidate_verse_count":6236,
       "candidate_sha256":"a"*64,"differing_verse_count":0,
       "differing_refs":[],"source_authenticated":True,
       "candidate_publisher_provenance_verified":True,"rights_verified":True}
    r.update(overrides)
    return r


class OfficialSourceProbeTests(unittest.TestCase):
    def test_explicit_stable_preset_and_one_official_host(self):
        self.assertEqual("https://tanzil.net/pub/download/index.php",OFFICIAL_URL)
        self.assertEqual("uthmani",PRESET["quranType"])
        self.assertEqual("txt-2",PRESET["outType"])
        self.assertEqual("true",PRESET["agree"])
        self.assertNotIn("stanween",PRESET)
        self.assertEqual({"marks","sajdah","rub","tatweel"},
                         set(PRESET)-{"quranType","outType","agree"})

    def test_no_success_from_html_or_http_error(self):
        for reason in ("<html>Not a Quran download</html>".encode(),"", "error"):
            with self.subTest(reason=reason):
                def fetcher(method):
                    if reason=="error": raise OSError("network down")
                    return reason
                report=run_probe(b"manifest",MIRROR,fetcher=fetcher)
                self.assertEqual("unavailable_or_invalid",report["outcome"])
                self.assertFalse(report["source_authenticated"])
                self.assertFalse(report["eligible_for_religious_ruling"])
                self.assertFalse(report["rights_verified"])
                self.assertNotIn("source_text",report)

    def test_compares_two_different_byte_sources_without_promotion(self):
        fetch_calls=[]
        def fetcher(method):
            fetch_calls.append(method)
            if method=="GET":raise OSError("GET unavailable")
            return SOURCE
        with patch("qa.quran_official_probe.compare_raw", return_value=stub_result()):
            report=run_probe(b"manifest",MIRROR,fetcher=fetcher)
        self.assertEqual(["GET","POST"],fetch_calls)
        self.assertEqual("comparison_available_not_authenticated",report["outcome"])
        self.assertEqual("byte_identical",report["comparison"])
        for key in ("source_authenticated","official_candidate_attested",
                    "candidate_publisher_provenance_verified","rights_verified",
                    "eligible_for_religious_ruling"):
            self.assertIs(report[key],False,key)
        self.assertNotIn("verse_text",report)
        self.assertNotIn("source_text",report)

    def test_invalid_comparison_returns_no_source_claim(self):
        with patch("qa.quran_official_probe.compare_raw",side_effect=ValueError("bad candidates")):
            x=run_probe(b"manifest",MIRROR,fetcher=lambda _:SOURCE)
        self.assertEqual("unavailable_or_invalid",x["outcome"])
        self.assertFalse(x["source_authenticated"])
        self.assertNotIn("text",str(x))

    def test_fake_compare_with_unsafe_label_is_rejected(self):
        with patch("qa.quran_official_probe.compare_raw",
                   return_value=stub_result(comparison="authenticated_official")):
            x=run_probe(b"manifest",MIRROR,fetcher=lambda _:SOURCE)
        self.assertEqual("unavailable_or_invalid",x["outcome"])
        self.assertFalse(x["source_authenticated"])

    def test_no_laundered_untrusted_difference_reference(self):
        invalid = [
            stub_result(candidate_sha256="z" * 64),
            stub_result(differing_verse_count=True),
            stub_result(differing_verse_count=-1),
            stub_result(differing_verse_count=1, differing_refs=["2:1", "2:2"]),
            stub_result(differing_verse_count=1, differing_refs=["some secret text"]),
            stub_result(differing_verse_count=1, differing_refs=["2:1<script>"]),
            stub_result(differing_verse_count=1, differing_refs=["2:1", "2:2"] * 12),
        ]
        for fake in invalid:
            with self.subTest(fake=fake):
                with patch("qa.quran_official_probe.compare_raw", return_value=fake):
                    report=run_probe(b"manifest",MIRROR,fetcher=lambda _:SOURCE)
                self.assertEqual("unavailable_or_invalid",report["outcome"])
                self.assertFalse(report["source_authenticated"])

    def test_all_qualification_flags_remain_false_even_on_comparison_success(self):
        with patch("qa.quran_official_probe.compare_raw",return_value=stub_result()):
            response=run_probe(b"manifest",MIRROR,fetcher=lambda _:SOURCE)
        self.assertEqual("comparison_available_not_authenticated",response["outcome"])
        for key in ("source_authenticated","official_candidate_attested",
                    "candidate_publisher_provenance_verified","rights_verified",
                    "redistribution_approved","scholarly_verified",
                    "juristic_inference_allowed","public_fatwa_authorized",
                    "eligible_for_religious_ruling",
                    "candidate_raw_persisted_or_published"):
            self.assertIs(response[key],False,key)
        self.assertIs(response["retrieved_over_official_domain_https"],False)

    def test_get_and_post_are_only_supported_fetch_modes(self):
        from qa.quran_official_probe import _fetch
        with self.assertRaises(ValueError):
            _fetch("DELETE")

    def test_no_redirect_and_fixed_host_are_explicit(self):
        from pathlib import Path
        from qa import quran_official_probe as module
        code=Path(module.__file__).read_text(encoding="utf-8")
        self.assertIn("class NoRedirect",code)
        self.assertIn("urllib.request.build_opener(NoRedirect)",code)
        self.assertIn("resp.geturl() != url",code)
        self.assertNotIn("os.system(",code)
        self.assertNotIn("subprocess.run(",code)

    def test_reader_bytes_untouched(self):
        with patch("qa.quran_official_probe.compare_raw",return_value=stub_result()) as c:
            run_probe(b"manifest",MIRROR,fetcher=lambda _:SOURCE)
        self.assertEqual(SOURCE,c.call_args.args[2])
        self.assertEqual(MIRROR,c.call_args.args[1])

    def test_probe_source_bytes_rejects_html_binary_injection(self):
        for val in (b"<html>bad</html>", b"\x00binary", b"", b"1|1|\n", b"x"*4194305):
            with self.subTest(sample=val[:12]):
                self.assertFalse(probe_source_bytes(val))

if __name__=="__main__":unittest.main()
