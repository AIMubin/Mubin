"""S0.1 metadata-only Shamela catalog validator.

Only human-inspected *public bibliography*, no automated fetch, corpus bytes,
legal clearance or publisher authenticity. Never use this in H3.9.2 holdouts.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

SCHEMA_PATH = (
    Path(__file__).resolve().parents[2] / "schemas"
    / "shamela-bibliographic-catalog.schema.json"
)
MAX_ENTRIES = 256
MAX_CATALOG_BYTES = 1024 * 1024
_ID = re.compile(r"^shamela:book:([1-9][0-9]{0,8})$")
_BOOK = re.compile(r"^https://shamela\.ws/book/([1-9][0-9]{0,8})$")
_PAGE = re.compile(r"^https://shamela\.ws/book/([1-9][0-9]{0,8})/([1-9][0-9]{0,8})$")


def _serialized(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8", "strict")


def validate_shamela_catalog(catalog: Any) -> list[str]:
    """Return bounded errors for an offline catalog; no acquisition side effects.

    A passing catalog has rights_status=unverified, has no source bytes or
    excerpt hashes, and must not be interpreted as an authority attestation.
    Schema and origin checks are both necessary; neither authenticates an
    externally supplied record or guarantees stable Shamela page URLs.
    """
    if not isinstance(catalog, dict):
        return ["catalog: JSON object required"]
    entries = catalog.get("entries")
    if isinstance(entries, list) and len(entries) > MAX_ENTRIES:
        return [f"catalog: exceeds {MAX_ENTRIES} entries"]
    # Keep adversarial programmatic values bounded BEFORE whole-object JSON
    # serialization or jsonschema's potentially huge diagnostic value echo.
    text_limits = {
        "source_id": 40, "discipline": 20, "work_title": 200,
        "author_display": 300, "edition_display": 500,
        "editor_display": 300, "publisher_display": 300,
        "volume_description": 100, "pagination_status": 50,
        "book_url": 100, "sample_page_url": 120, "rights_status": 40,
        "edition_verification": 50, "text_acquisition_status": 40,
        "notes": 4096,
    }
    significant = (
        "work_title", "author_display", "edition_display",
        "editor_display", "publisher_display", "volume_description", "notes",
    )
    allowed = set(text_limits) | {"book_id", "review_flags"}
    unknown_root = set(catalog) - {"catalog_version", "scope", "acquisition", "entries"}
    if unknown_root:
        return ["catalog: unknown top-level metadata field"]
    for field, max_length in (("catalog_version", 20), ("scope", 100)):
        if field in catalog:
            value = catalog[field]
            if not isinstance(value, str) or len(value) > max_length:
                return [f"catalog: invalid JSON {field}"]
    acquisition = catalog.get("acquisition")
    if isinstance(acquisition, dict):
        known = {"method", "database_inspected", "text_acquired", "rights_verified"}
        if any(not isinstance(k, str) or k not in known for k in acquisition):
            return ["catalog: unknown acquisition metadata field"]
        if "method" in acquisition and (
            not isinstance(acquisition["method"], str)
            or len(acquisition["method"]) > 80
        ):
            return ["catalog: invalid JSON acquisition method"]
        for key in ("database_inspected", "text_acquired", "rights_verified"):
            if key in acquisition and type(acquisition[key]) is not bool:
                return [f"catalog: invalid JSON acquisition {key}"]
    elif acquisition is not None:
        return ["catalog: invalid JSON acquisition shape"]
    if isinstance(entries, list):
        for i, row in enumerate(entries):
            if not isinstance(row, dict):
                return [f"catalog: invalid JSON entry shape at {i}"]
            for field in row:
                if not isinstance(field, str) or field not in allowed:
                    return [f"catalog: unknown metadata field {str(field)[:100]} at {i}"]
            for field, cap in text_limits.items():
                if field in row:
                    value = row[field]
                    if not isinstance(value, str):
                        return [f"catalog: invalid JSON text field {field} at {i}"]
                    if len(value) > cap:
                        return [f"catalog: {field} exceeds field size limit at {i}"]
                    if field in significant and not value.strip():
                        return [f"catalog: {field} cannot be whitespace-only at {i}"]
            if "review_flags" in row:
                flags = row["review_flags"]
                if not isinstance(flags, list) or len(flags) > 16 or any(
                    not isinstance(flag, str) or len(flag) > 100 for flag in flags
                ):
                    return [f"catalog: invalid JSON review_flags at {i}"]
    try:
        raw = _serialized(catalog)
    except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError) as exc:
        return [f"catalog: invalid JSON/UTF-8 serialization ({type(exc).__name__})"]
    if len(raw) > MAX_CATALOG_BYTES:
        return [f"catalog: JSON size exceeds {MAX_CATALOG_BYTES} bytes"]

    try:
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        errors = [
            "schema " + "/".join(str(part) for part in item.absolute_path)
            + ": " + item.message[:512]
            for item in Draft202012Validator(schema).iter_errors(catalog)
        ]
    except (ValueError, TypeError, UnicodeError, RecursionError, OSError) as exc:
        return [f"catalog: schema validation unavailable ({type(exc).__name__})"]
    if errors:
        return sorted(set(errors))[:100]

    seen_ids: set[str] = set()
    seen_book_ids: set[int] = set()
    seen_pages: set[str] = set()
    for position, item in enumerate(entries):
        name = f"entries[{position}]"
        book_id = item["book_id"]
        source_id = item["source_id"]
        # Python bool is a subclass of int; a book id must be a genuine int.
        if type(book_id) is not int:
            errors.append(f"{name}.book_id must be an integer, not bool")
            continue
        wanted_id = f"shamela:book:{book_id}"
        wanted_book_url = f"https://shamela.ws/book/{book_id}"
        wanted_page_prefix = wanted_book_url + "/"
        if _ID.fullmatch(source_id) is None or source_id != wanted_id:
            errors.append(f"{name}.source_id differs from canonical book_id")
        if _BOOK.fullmatch(item["book_url"]) is None or item["book_url"] != wanted_book_url:
            errors.append(f"{name}.book_url differs from canonical book_id")
        match = _PAGE.fullmatch(item["sample_page_url"])
        if match is None or item["sample_page_url"] != wanted_page_prefix + (match.group(2) if match else ""):
            errors.append(f"{name}.sample_page_url differs from canonical book_id")
        if book_id in seen_book_ids:
            errors.append(f"{name}: duplicate book_id {book_id}")
        if source_id in seen_ids:
            errors.append(f"{name}: duplicate source_id {source_id}")
        if item["sample_page_url"] in seen_pages:
            errors.append(f"{name}: duplicate sample_page_url")
        seen_book_ids.add(book_id)
        seen_ids.add(source_id)
        seen_pages.add(item["sample_page_url"])
    return sorted(set(errors))[:100]


def assess_shamela_catalog(catalog: Any) -> dict[str, Any]:
    """Safe metadata-only summary. No corpus text or individual record echoed."""
    issues = validate_shamela_catalog(catalog)
    report = {
        "valid": not issues,
        "scope": "shamela_bibliographic_metadata_only",
        "assurance": "observed_catalog_metadata_only",
        "rights_assurance": "unverified",
        "content_acquisition": "not_performed",
        "entry_count": 0,
        "catalog_sha256": None,
        "errors": issues,
    }
    if not issues:
        report["entry_count"] = len(catalog["entries"])
        report["catalog_sha256"] = hashlib.sha256(_serialized(catalog)).hexdigest()
    return report
