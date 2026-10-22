"""The private HMAC commitment tool uses only synthetic in-memory data."""
import hashlib
import hmac
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from engines.usul.private_text_commitment import (
    MAX_BYTES, make_private_commitment,
)


class PrivateCommitmentTests(unittest.TestCase):
    def test_hmac_matches_independent_stdlib_implementation(self):
        key = bytes(range(32))
        source = b"synthetic-public-test-only"
        got = make_private_commitment(source, key)
        self.assertEqual(got, hmac.new(key, source, hashlib.sha256).hexdigest())
        self.assertEqual(len(got), 64)
        self.assertNotEqual(got, hashlib.sha256(source).hexdigest())

    def test_same_key_and_bytes_are_deterministic(self):
        key = b"Z" * 32
        self.assertEqual(make_private_commitment(b"synthetic", key),
                         make_private_commitment(b"synthetic", key))

    def test_different_keys_change_commitment(self):
        self.assertNotEqual(make_private_commitment(b"synthetic", b"a"*32),
                            make_private_commitment(b"synthetic", b"b"*32))

    def test_empty_text_is_refused(self):
        with self.assertRaisesRegex(ValueError, "PRIVATE_TEXT_BOUNDS_INVALID"):
            make_private_commitment(b"", b"a"*32)

    def test_short_key_is_refused(self):
        with self.assertRaisesRegex(ValueError, "PRIVATE_HMAC_KEY_TOO_SHORT"):
            make_private_commitment(b"synthetic", b"small")

    def test_oversized_text_is_refused(self):
        with self.assertRaisesRegex(ValueError, "PRIVATE_TEXT_BOUNDS_INVALID"):
            make_private_commitment(b"a" * (MAX_BYTES + 1), b"a"*32)

    def test_cli_uses_env_not_cli_key_or_inline_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "private-synthetic.txt"
            src.write_bytes(b"synthetic-cli-private-text")
            env = dict(os.environ)
            env["MUBIN_PRIVATE_HMAC_KEY_HEX"] = ("01" * 32)
            r = subprocess.run([
                sys.executable, "-m", "engines.usul.private_text_commitment",
                "--text-file", str(src),
            ], capture_output=True, text=True, env=env,
                cwd=Path(__file__).resolve().parents[3])
            self.assertEqual(r.returncode, 0, r.stderr)
            report = json.loads(r.stdout)
            self.assertEqual(report["commitment_scheme"], "HMAC_SHA256_PRIVATE")
            self.assertEqual(len(report["commitment_sha256"]), 64)
            self.assertFalse(report["source_text_included"])
            self.assertNotIn("synthetic-cli-private-text", r.stdout)
            self.assertNotIn(str(src), r.stdout)
            self.assertNotIn("010101", r.stdout)

    def test_cli_fails_without_key_without_exposing_private_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "synthetic.txt"
            src.write_bytes(b"synthetic-private-sensitive-test")
            env = dict(os.environ)
            env.pop("MUBIN_PRIVATE_HMAC_KEY_HEX", None)
            r = subprocess.run([
                sys.executable, "-m", "engines.usul.private_text_commitment",
                "--text-file", str(src),
            ], capture_output=True, text=True, env=env,
                cwd=Path(__file__).resolve().parents[3])
            self.assertEqual(r.returncode, 2)
            self.assertEqual(json.loads(r.stdout)["status"],
                             "PRIVATE_COMMITMENT_REJECTED")
            self.assertNotIn("synthetic-private-sensitive-test", r.stdout+r.stderr)


if __name__ == "__main__":
    unittest.main()
