from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from .core import canonical_json_bytes, load_json, sha256_bytes, sha256_file, write_json

SCHEMA_VERSION = 1
ALGORITHM = "AES-256-GCM"
KEY_BYTES = 32


def sealed_gold_path(root: Path, benchmark_id: str) -> Path:
    return root / "sealed-holdout" / f"{benchmark_id}.gold.aesgcm.json"


def generate_holdout_key(path: Path) -> dict[str, Any]:
    """Generate a 256-bit sealing key. The key must never be committed with the campaign."""
    if path.exists():
        raise FileExistsError(f"refusing to overwrite holdout key: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    key = AESGCM.generate_key(bit_length=256)
    encoded = base64.urlsafe_b64encode(key).decode("ascii")
    path.write_text(encoded + "\n", encoding="ascii")
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass
    return {"path": str(path), "key_id": key_id(key), "bytes": len(key)}


def load_holdout_key(path: Path) -> bytes:
    raw = path.read_text(encoding="ascii").strip()
    try:
        key = base64.urlsafe_b64decode(raw.encode("ascii"))
    except Exception as exc:
        raise ValueError("invalid holdout key encoding") from exc
    if len(key) != KEY_BYTES:
        raise ValueError(f"holdout key must decode to {KEY_BYTES} bytes")
    return key


def key_id(key: bytes) -> str:
    return sha256_bytes(key)[:16]


def _aad(campaign_id: str, benchmark_id: str) -> bytes:
    return f"mubin:{campaign_id}:{benchmark_id}:sealed-holdout-gold:v1".encode("utf-8")


def _public_binding(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": str(record["case_id"]),
        "content_fingerprint": str(record["content_fingerprint"]),
        "source_ids": sorted(str(x) for x in record.get("source_ids", [])),
        "family_id": str(record.get("family_id", "")),
        "gold_status": str(record.get("gold_status", "")),
        "answer_provenance_sha256": (
            sha256_bytes(canonical_json_bytes(record["answer_provenance"]))
            if isinstance(record.get("answer_provenance"), dict) else None
        ),
    }


def _public_binding_sha256(record: dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(_public_binding(record)))


def public_holdout_index(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted((_public_binding(r) for r in rows), key=lambda x: x["case_id"])


def public_index_sha256(rows: list[dict[str, Any]]) -> str:
    return sha256_bytes(canonical_json_bytes(public_holdout_index(rows)))


def _secret_records(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    secret = []
    for r in rows:
        payload = r.get("payload")
        if not isinstance(payload, dict) or "gold" not in payload:
            raise ValueError(f"holdout record {r.get('case_id')!r} has no plaintext gold to seal")
        secret.append({
            "case_id": str(r["case_id"]),
            "public_binding_sha256": _public_binding_sha256(r),
            "gold": payload["gold"],
        })
    return sorted(secret, key=lambda x: x["case_id"])


def sanitize_holdout_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    sanitized = []
    for r in rows:
        x = json.loads(json.dumps(r, ensure_ascii=False))
        payload = x.get("payload")
        if not isinstance(payload, dict) or "input" not in payload or "gold" not in payload:
            raise ValueError(f"holdout record {r.get('case_id')!r} must contain input+gold before sealing")
        payload.pop("gold", None)
        payload["gold_sealed"] = True
        x["payload"] = payload
        sanitized.append(x)
    return sanitized


def seal_holdout_rows(root: Path, campaign_id: str, benchmark_id: str,
                      rows: list[dict[str, Any]], key: bytes) -> dict[str, Any]:
    """Encrypt holdout gold and return sanitized public rows plus seal metadata.

    Existing stores are immutable. An identical re-run with the same key is accepted only
    when decryption proves the stored secret payload is byte-equivalent canonically.
    """
    if len(key) != KEY_BYTES:
        raise ValueError("invalid holdout key length")
    path = sealed_gold_path(root, benchmark_id)
    secret = {
        "schema_version": SCHEMA_VERSION,
        "campaign_id": campaign_id,
        "benchmark_id": benchmark_id,
        "records": _secret_records(rows),
    }
    plaintext = canonical_json_bytes(secret)
    aad = _aad(campaign_id, benchmark_id)

    if path.exists():
        prior = decrypt_holdout_store(path, key, campaign_id, benchmark_id)
        if canonical_json_bytes(prior) != plaintext:
            raise FileExistsError(f"sealed holdout already exists with different gold: {path}")
    else:
        nonce = os.urandom(12)
        ciphertext = AESGCM(key).encrypt(nonce, plaintext, aad)
        wrapper = {
            "schema_version": SCHEMA_VERSION,
            "algorithm": ALGORITHM,
            "campaign_id": campaign_id,
            "benchmark_id": benchmark_id,
            "key_id": key_id(key),
            "aad_b64": base64.b64encode(aad).decode("ascii"),
            "nonce_b64": base64.b64encode(nonce).decode("ascii"),
            "ciphertext_b64": base64.b64encode(ciphertext).decode("ascii"),
            "holdout_count": len(rows),
            "public_index_sha256": public_index_sha256(rows),
        }
        write_json(path, wrapper)

    public_rows = sanitize_holdout_rows(rows)
    return {
        "public_rows": public_rows,
        "sealed_path": path,
        "sealed_sha256": sha256_file(path),
        "key_id": key_id(key),
        "holdout_count": len(rows),
        "public_index_sha256": public_index_sha256(public_rows),
    }


def decrypt_holdout_store(path: Path, key: bytes, campaign_id: str, benchmark_id: str) -> dict[str, Any]:
    wrapper = load_json(path)
    if wrapper.get("schema_version") != SCHEMA_VERSION or wrapper.get("algorithm") != ALGORITHM:
        raise ValueError("unsupported sealed holdout format")
    if wrapper.get("campaign_id") != campaign_id or wrapper.get("benchmark_id") != benchmark_id:
        raise ValueError("sealed holdout identity mismatch")
    if wrapper.get("key_id") != key_id(key):
        raise ValueError("holdout key does not match sealed store")
    try:
        aad = base64.b64decode(wrapper["aad_b64"])
        nonce = base64.b64decode(wrapper["nonce_b64"])
        ciphertext = base64.b64decode(wrapper["ciphertext_b64"])
        plaintext = AESGCM(key).decrypt(nonce, ciphertext, aad)
    except Exception as exc:
        raise ValueError("sealed holdout authentication/decryption failed") from exc
    expected_aad = _aad(campaign_id, benchmark_id)
    if aad != expected_aad:
        raise ValueError("sealed holdout AAD mismatch")
    obj = json.loads(plaintext.decode("utf-8"))
    if obj.get("campaign_id") != campaign_id or obj.get("benchmark_id") != benchmark_id:
        raise ValueError("decrypted holdout identity mismatch")
    return obj


def validate_public_seal_binding(root: Path, campaign_id: str, benchmark_id: str,
                                 public_rows: list[dict[str, Any]]) -> list[str]:
    """Validate what can be checked without the secret key."""
    path = sealed_gold_path(root, benchmark_id)
    if not path.exists():
        return ["sealed holdout store missing"]
    try:
        wrapper = load_json(path)
    except Exception as exc:
        return [f"sealed holdout store unreadable: {exc}"]
    errors: list[str] = []
    if wrapper.get("schema_version") != SCHEMA_VERSION:
        errors.append("sealed holdout schema version mismatch")
    if wrapper.get("algorithm") != ALGORITHM:
        errors.append("sealed holdout algorithm mismatch")
    if wrapper.get("campaign_id") != campaign_id or wrapper.get("benchmark_id") != benchmark_id:
        errors.append("sealed holdout identity mismatch")
    if wrapper.get("holdout_count") != len(public_rows):
        errors.append("sealed holdout count mismatch")
    if wrapper.get("public_index_sha256") != public_index_sha256(public_rows):
        errors.append("sealed holdout public index mismatch")
    for field in ("nonce_b64", "ciphertext_b64", "aad_b64", "key_id"):
        if not isinstance(wrapper.get(field), str) or not wrapper.get(field):
            errors.append(f"sealed holdout missing {field}")
    return errors


def decrypt_gold_map(root: Path, campaign_id: str, benchmark_id: str,
                     public_rows: list[dict[str, Any]], key: bytes) -> dict[str, Any]:
    path = sealed_gold_path(root, benchmark_id)
    obj = decrypt_holdout_store(path, key, campaign_id, benchmark_id)
    records = obj.get("records")
    if not isinstance(records, list):
        raise ValueError("sealed holdout records are invalid")
    expected_binding = {str(r["case_id"]): _public_binding_sha256(r) for r in public_rows}
    actual_binding = {str(r.get("case_id")): str(r.get("public_binding_sha256")) for r in records}
    if actual_binding != expected_binding:
        raise ValueError("sealed gold does not bind to the current public holdout records")
    gold_map: dict[str, Any] = {}
    public_by_case = {str(r["case_id"]): r for r in public_rows}
    for r in records:
        cid = str(r.get("case_id"))
        if cid in gold_map:
            raise ValueError(f"duplicate case_id inside sealed holdout: {cid}")
        if "gold" not in r:
            raise ValueError(f"sealed holdout gold missing for {cid}")
        gold = r["gold"]
        public = public_by_case.get(cid)
        if isinstance(public, dict) and public.get("gold_status") == "source_attributed":
            ap = public.get("answer_provenance")
            if not isinstance(ap, dict):
                raise ValueError(f"source_attributed holdout missing answer_provenance: {cid}")
            supports = ap.get("supports")
            if not isinstance(supports, list) or not supports:
                raise ValueError(f"source_attributed holdout missing supports: {cid}")
            normalized_supports = [
                {
                    "source_id": s.get("source_id"),
                    "support_text": s.get("support_text"),
                    "support_text_sha256": s.get("support_text_sha256"),
                    "source_excerpt_sha256": s.get("source_excerpt_sha256"),
                }
                for s in supports if isinstance(s, dict)
            ]
            expected_gold_binding = sha256_bytes(canonical_json_bytes({
                "gold": gold,
                "supports": normalized_supports,
                "mode": ap.get("mode"),
            }))
            if ap.get("gold_binding_sha256") != expected_gold_binding:
                raise ValueError(f"source_attributed holdout gold binding mismatch: {cid}")
        gold_map[cid] = gold
    if set(gold_map) != set(expected_binding):
        raise ValueError("sealed holdout case set mismatch")
    return gold_map


def sealed_store_descriptor(root: Path, campaign_id: str, benchmark_id: str,
                            public_rows: list[dict[str, Any]]) -> dict[str, Any]:
    path = sealed_gold_path(root, benchmark_id)
    wrapper = load_json(path)
    return {
        "benchmark_id": benchmark_id,
        "path": str(path.relative_to(root)),
        "sha256": sha256_file(path),
        "algorithm": wrapper.get("algorithm"),
        "key_id": wrapper.get("key_id"),
        "holdout_count": wrapper.get("holdout_count"),
        "public_index_sha256": wrapper.get("public_index_sha256"),
        "binding_verified_without_key": not validate_public_seal_binding(root, campaign_id, benchmark_id, public_rows),
    }
