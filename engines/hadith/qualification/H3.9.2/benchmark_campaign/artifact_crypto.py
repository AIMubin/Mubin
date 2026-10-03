from __future__ import annotations

import argparse
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt


MAGIC = b"MUBIN-H392-AESGCM-1\x00"
SALT_SIZE = 16
NONCE_SIZE = 12
KEY_SIZE = 32
SCRYPT_N = 2**15
SCRYPT_R = 8
SCRYPT_P = 1


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    if not isinstance(passphrase, str) or len(passphrase) < 20:
        raise ValueError("artifact passphrase must contain at least 20 characters")
    return Scrypt(
        salt=salt,
        length=KEY_SIZE,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
    ).derive(passphrase.encode("utf-8"))


def encrypt_bytes(plaintext: bytes, passphrase: str) -> bytes:
    salt = secrets.token_bytes(SALT_SIZE)
    nonce = secrets.token_bytes(NONCE_SIZE)
    key = _derive_key(passphrase, salt)
    aad = MAGIC + salt
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
    return MAGIC + salt + nonce + ciphertext


def decrypt_bytes(blob: bytes, passphrase: str) -> bytes:
    prefix = len(MAGIC)
    minimum = prefix + SALT_SIZE + NONCE_SIZE + 16
    if len(blob) < minimum or blob[:prefix] != MAGIC:
        raise ValueError("invalid H3.9.2 encrypted artifact format")
    salt = blob[prefix:prefix + SALT_SIZE]
    nonce_start = prefix + SALT_SIZE
    nonce = blob[nonce_start:nonce_start + NONCE_SIZE]
    ciphertext = blob[nonce_start + NONCE_SIZE:]
    key = _derive_key(passphrase, salt)
    return AESGCM(key).decrypt(nonce, ciphertext, MAGIC + salt)


def encrypt_file(input_path: Path, output_path: Path, passphrase: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(encrypt_bytes(input_path.read_bytes(), passphrase))


def decrypt_file(input_path: Path, output_path: Path, passphrase: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(decrypt_bytes(input_path.read_bytes(), passphrase))


def _passphrase_from_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None:
        raise ValueError(f"required passphrase environment variable is unset: {name}")
    return value


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Authenticated encryption for H3.9.2 source-bearing artifacts")
    sub = p.add_subparsers(dest="command", required=True)
    for command in ("encrypt", "decrypt"):
        sp = sub.add_parser(command)
        sp.add_argument("--input", type=Path, required=True)
        sp.add_argument("--output", type=Path, required=True)
        sp.add_argument("--passphrase-env", required=True)
    return p


def main() -> int:
    args = _parser().parse_args()
    passphrase = _passphrase_from_env(args.passphrase_env)
    if args.command == "encrypt":
        encrypt_file(args.input, args.output, passphrase)
    else:
        decrypt_file(args.input, args.output, passphrase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
