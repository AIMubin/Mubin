"""P1.1 registry-pin bridge: adversarial tests; not scholarly certification."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from core.source_authority import verify_hadith_cache

ROOT = Path(__file__).resolve().parents[2]
HADITH_REGISTRY = (
    ROOT / "engines" / "hadith" / "qualification" / "H3.9.2"
    / "sources" / "source-registry.json"
)


def git_blob_sha1(payload: bytes) -> str:
    return hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()


class TestHadithPinBridge(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cache = Path(tmp.name) / "source-cache"
        self.cache.mkdir()
        self.raw = "بداية\nهذا نص تجريبي\nنهاية".encode("utf-8")
        self.sid = "openiti:001Example.Work"
        self.source = {
            "source_id": self.sid, "work_id": "001Example.Work",
            "title_ar": "متن تجريبي", "qualification_eligible": True,
            "provider": "OpenITI", "source_repo": "OpenITI/RELEASE",
            "source_path": "data/001Example/001Example.Work/test",
            "repo_ref": "a" * 40, "source_blob_sha": git_blob_sha1(self.raw),
            "version_id": "001Example.Work.test", "format": "OpenITI-mARkdown",
        }
        self.registry = {
            "schema_version": 2, "registry_id": "fixture-locked-registry",
            "license_note": "operator must assess the actual rights",
            "sources": [self.source],
        }
        self.cache_file = self.cache / "openiti__001Example.Work.source"
        self.cache_file.write_bytes(self.raw)

    def verify(self, **kw):
        return verify_hadith_cache(self.registry, self.cache, **kw)

    def test_bytes_match_git_blob_pin_and_sha256_but_no_authority_claim(self):
        r = self.verify()
        self.assertTrue(r["valid"], r)
        self.assertEqual("registry_blob_match_only", r["scope"])
        self.assertEqual("not_authenticated", r["authority"]["edition"])
        self.assertEqual("not_reviewed", r["authority"]["rights"])
        self.assertEqual("not_checked", r["authority"]["entailment"])
        item = r["sources"][0]
        self.assertEqual("registry_blob_matched", item["status"])
        self.assertEqual(git_blob_sha1(self.raw), item["git_blob_sha1"])
        self.assertEqual(hashlib.sha256(self.raw).hexdigest(), item["local_sha256"])
        self.assertEqual(self.source["repo_ref"], item["repo_ref"])
        self.assertEqual(self.source["source_path"], item["source_path"])
        self.assertTrue(item["qualification_eligible"])

    def test_repeatable_and_does_not_modify_registry_or_cache(self):
        before = json.dumps(self.registry, sort_keys=True)
        first = self.verify()
        self.assertEqual(first, self.verify())
        self.assertEqual(before, json.dumps(self.registry, sort_keys=True))
        self.assertEqual(self.raw, self.cache_file.read_bytes())

    def test_tamper_rejected_without_verified_authority(self):
        self.cache_file.write_bytes(self.raw + b"!")
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertEqual("registry_blob_mismatch", r["sources"][0]["status"])
        self.assertEqual("not_authenticated", r["authority"]["edition"])

    def test_missing_cache_fails_closed(self):
        self.cache_file.unlink()
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertEqual("missing_cache_file", r["sources"][0]["status"])

    def test_duplicate_source_id_rejected(self):
        self.registry["sources"].append(dict(self.source))
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertTrue(any("duplicate source_id" in e for e in r["errors"]), r)

    def test_cache_filename_collision_rejected(self):
        # Colon -> double underscore in the already-frozen Hadith cache format.
        self.registry["sources"].append({
            **self.source, "source_id": "openiti:001Example:Work",
            "version_id": "second-version",
        })
        self.registry["sources"][1]["source_id"] = "openiti:001Example__Work"
        self.registry["sources"][0]["source_id"] = "openiti:001Example:Work"
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertTrue(any("cache filename collision" in issue for issue in r["errors"]), r)

    def test_invalid_repository_pin_and_metadata_rejected(self):
        self.source["repo_ref"] = "latest"
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertTrue(any("repo_ref" in e for e in r["errors"]), r)

    def test_traversal_like_source_id_rejected(self):
        self.source["source_id"] = "../escaped"
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertTrue(any("source_id" in e for e in r["errors"]), r)

    def test_source_larger_than_budget_not_read(self):
        with self.cache_file.open("wb") as stream:
            stream.truncate(65)
        r = self.verify(max_source_bytes=64)
        self.assertFalse(r["valid"], r)
        self.assertEqual("size_limit_exceeded", r["sources"][0]["status"])

    def test_total_byte_budget_exceeded_across_sources(self):
        second = {
            **self.source,
            "source_id": "openiti:002Other.Work",
            "work_id": "002Other.Work",
            "version_id": "002Other.Work.test",
        }
        self.registry["sources"].append(second)
        (self.cache / "openiti__002Other.Work.source").write_bytes(self.raw)
        r = self.verify(max_total_bytes=len(self.raw))
        self.assertFalse(r["valid"])
        self.assertEqual("registry_blob_matched", r["sources"][0]["status"])
        self.assertEqual("size_limit_exceeded", r["sources"][1]["status"])

    def test_directory_named_like_source_is_not_read(self):
        self.cache_file.unlink()
        self.cache_file.mkdir()
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertEqual("unsafe_cache_file", r["sources"][0]["status"])

    def test_deep_programmatic_registry_fails_before_file_read(self):
        self.registry["untrusted"] = []
        cursor = self.registry["untrusted"]
        for _ in range(10000):
            item = []
            cursor.append(item)
            cursor = item
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertEqual([], r["sources"])
        self.assertTrue(any("RecursionError" in msg for msg in r["errors"]), r)

    @unittest.skipUnless(hasattr(os, "O_NOFOLLOW"), "requires POSIX no-follow")
    def test_symlink_cache_file_rejected(self):
        target = self.cache / "actual.source"
        target.write_bytes(self.raw)
        self.cache_file.unlink()
        self.cache_file.symlink_to(target)
        r = self.verify()
        self.assertFalse(r["valid"])
        self.assertEqual("unsafe_cache_file", r["sources"][0]["status"])

    def test_selection_skips_ineligible_only_when_explicit(self):
        discovery = {
            **self.source, "source_id": "discovery:000Example.Index",
            "work_id": "000Example.Index",
            "version_id": "000Example.Index.test",
            "qualification_eligible": False,
        }
        self.registry["sources"].append(discovery)
        self.assertFalse(self.verify()["valid"], "all sources should require all cache files")
        r = self.verify(eligible_only=True)
        self.assertTrue(r["valid"], r)
        self.assertEqual(1, r["selection"]["selected_source_count"])
        self.assertEqual(2, r["selection"]["registry_source_count"])
        self.assertEqual(True, r["selection"]["eligible_only"])
        self.assertEqual([self.sid], [s["source_id"] for s in r["sources"]])

    def test_explicit_subset_selection_and_unknown_ids_fail_closed(self):
        second = {
            **self.source, "source_id": "openiti:002Other.Work",
            "work_id": "002Other.Work",
            "version_id": "002Other.Work.test",
        }
        self.registry["sources"].append(second)
        r = self.verify(allowed_source_ids={self.sid})
        self.assertTrue(r["valid"], r)
        self.assertEqual([self.sid], [s["source_id"] for s in r["sources"]])
        self.assertEqual([self.sid], r["selection"]["allowed_source_ids"])
        rejected = self.verify(allowed_source_ids={"openiti:unknown"})
        self.assertFalse(rejected["valid"])
        self.assertTrue(any("unknown" in e for e in rejected["errors"]), rejected)
        empty = self.verify(allowed_source_ids=set())
        self.assertFalse(empty["valid"])
        self.assertTrue(any("empty" in e for e in empty["errors"]), empty)

    def test_eligible_only_with_no_eligible_source_is_error(self):
        self.source["qualification_eligible"] = False
        r = self.verify(eligible_only=True)
        self.assertFalse(r["valid"])
        self.assertTrue(any("empty" in e for e in r["errors"]), r)

    def test_real_frozen_registry_metadata_is_structurally_accepted(self):
        frozen = json.loads(HADITH_REGISTRY.read_text(encoding="utf-8"))
        # This is deliberately a metadata test; cached source files are NOT
        # available to this suite, so no external source verification is claimed.
        self.assertEqual(19, len(frozen["sources"]))
        self.assertEqual(18, sum(s["qualification_eligible"] is True for s in frozen["sources"]))
        from core.source_authority import validate_hadith_registry
        self.assertEqual([], validate_hadith_registry(frozen))

    def test_cli_missing_cache_has_stable_nonzero_exit(self):
        registry_path = self.cache.parent / "registry.json"
        registry_path.write_text(json.dumps(self.registry), encoding="utf-8")
        self.cache_file.unlink()
        run = subprocess.run(
            [sys.executable, "-m", "core.source_authority", str(registry_path),
             str(self.cache), "--json"],
            cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(1, run.returncode, run.stderr)
        obj = json.loads(run.stdout)
        self.assertFalse(obj["valid"])

    def test_cli_deeply_nested_json_is_input_error_not_traceback(self):
        registry_path = self.cache.parent / "invalid.json"
        registry_path.write_text('{"sources":' + "[" * 10000 + "0" + "]" * 10000 + "}", encoding="utf-8")
        run = subprocess.run(
            [sys.executable, "-m", "core.source_authority",
             str(registry_path), str(self.cache)],
            cwd=ROOT, capture_output=True, text=True
        )
        self.assertEqual(2, run.returncode, run.stderr)
        self.assertIn("INPUT_ERROR", run.stderr)
        self.assertNotIn("Traceback", run.stderr)


if __name__ == "__main__":
    unittest.main()
