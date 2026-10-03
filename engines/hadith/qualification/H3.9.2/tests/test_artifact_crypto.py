from __future__ import annotations

import unittest

from cryptography.exceptions import InvalidTag

from benchmark_campaign.artifact_crypto import decrypt_bytes, encrypt_bytes


class ArtifactCryptoTests(unittest.TestCase):
    def test_authenticated_encryption_round_trip(self):
        plaintext = b"source-bearing benchmark evidence"
        blob = encrypt_bytes(plaintext, "correct horse battery staple for h392")
        self.assertNotEqual(blob, plaintext)
        self.assertEqual(
            decrypt_bytes(blob, "correct horse battery staple for h392"),
            plaintext,
        )

    def test_ciphertext_tamper_fails_authentication(self):
        blob = bytearray(encrypt_bytes(
            b"source-bearing benchmark evidence",
            "correct horse battery staple for h392",
        ))
        blob[-1] ^= 1
        with self.assertRaises(InvalidTag):
            decrypt_bytes(bytes(blob), "correct horse battery staple for h392")

    def test_wrong_passphrase_fails_authentication(self):
        blob = encrypt_bytes(
            b"source-bearing benchmark evidence",
            "correct horse battery staple for h392",
        )
        with self.assertRaises(InvalidTag):
            decrypt_bytes(blob, "different passphrase for h392 evidence")

    def test_short_passphrase_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "at least 20"):
            encrypt_bytes(b"x", "too-short")


if __name__ == "__main__":
    unittest.main()
