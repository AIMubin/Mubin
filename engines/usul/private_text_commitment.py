"""Create HMAC-SHA256 commitments for privately stored candidate texts.

Never uploads or prints text, key material, or local source paths. The
operator must independently manage and preserve the secret key offline.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
from pathlib import Path

MAX_BYTES = 131072


def make_private_commitment(source_bytes: bytes, key: bytes) -> str:
    if type(source_bytes) is not bytes or not (0 < len(source_bytes) <= MAX_BYTES):
        raise ValueError("PRIVATE_TEXT_BOUNDS_INVALID")
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("PRIVATE_HMAC_KEY_TOO_SHORT")
    return hmac.new(key, source_bytes, hashlib.sha256).hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--text-file", type=Path, required=True)
    p.add_argument("--secret-hex-env", default="MUBIN_PRIVATE_HMAC_KEY_HEX")
    a = p.parse_args()
    try:
        if not a.secret_hex_env.isidentifier():
            raise ValueError("KEY_ENV_NAME_INVALID")
        value = os.environ.get(a.secret_hex_env, "")
        if len(value) < 64 or len(value) % 2 or len(value) > 256:
            raise ValueError("PRIVATE_HMAC_KEY_INVALID")
        try:
            key = bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError("PRIVATE_HMAC_KEY_INVALID") from exc
        if not a.text_file.is_file() or a.text_file.stat().st_size > MAX_BYTES:
            raise ValueError("PRIVATE_TEXT_FILE_INVALID")
        commitment = make_private_commitment(a.text_file.read_bytes(), key)
        result = {
            "commitment_scheme": "HMAC_SHA256_PRIVATE",
            "commitment_sha256": commitment,
            "source_text_included": False,
            "private_path_included": False,
        }
        status = 0
    except (ValueError, OSError, UnicodeError):
        result = {"status": "PRIVATE_COMMITMENT_REJECTED",
                  "source_text_included": False, "private_path_included": False}
        status = 2
    print(json.dumps(result, sort_keys=True))
    return status


if __name__ == "__main__":
    raise SystemExit(main())
