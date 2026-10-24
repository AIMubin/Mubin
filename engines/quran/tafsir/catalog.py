"""Fail-closed tafsir bibliography registry for per-verse KSU navigation.

This module does NOT retrieve/parse tafsir text, verify editions or grant reuse
rights. All records are unreviewed bibliographic candidates. P1 graph admission
must be a separate, independently verified future workflow.
"""
from __future__ import annotations
import json
from pathlib import Path
import re
import unicodedata
from typing import Any

from engines.quran.q01.engine import _VERSE_COUNTS

CATALOG_PATH = Path(__file__).with_name("tafsir-catalog-v01.json")
_BASE = "https://quran.ksu.edu.sa/index.php"
_KNOWN = ("tafsir_muyassar","tafsir_saadi","tafsir_baghawi",
          "tafsir_ibn_kathir","tafsir_qurtubi","tafsir_tabari")
_TOP = frozenset(("contract","platform","sources"))
_PLATFORM = frozenset(("id","display_ar","navigation_base","origin_reported","rights_status"))
_SOURCE = frozenset(("id","title_ar","author_ar","edition","source_status",
                     "rights_status","text_ingested","allowed_for_local_quotation",
                     "p1_eligible","link_scope"))
_REF = re.compile(r"([1-9][0-9]{0,2}):([1-9][0-9]{0,2})")


class CatalogError(ValueError):
    """Catalog lacks trustworthy metadata-only structural boundaries."""


def _label(value: Any, *, nullable: bool = False) -> bool:
    if nullable and value is None:
        return True
    if type(value) is not str or not 3 <= len(value) <= 150:
        return False
    if value != value.strip() or not any("\u0621" <= c <= "\u064a" for c in value):
        return False
    return not any(c in value for c in "<>{}[]\r\n\t\x00" + chr(92)) and not any(
        unicodedata.category(c) == "Cf" for c in value
    )


def validate_catalog(data: Any) -> dict[str, Any]:
    """Validate all fields and forbid any claims of qualified tafsir provenance."""
    if type(data) is not dict or set(data) != _TOP:
        raise CatalogError("invalid_catalog_contract")
    if data["contract"] != "mubin-tafsir-metadata-v0.1":
        raise CatalogError("unexpected_catalog_version")
    p = data["platform"]
    if (type(p) is not dict or set(p) != _PLATFORM or
        p.get("id") != "ksu_ayat" or
        p.get("navigation_base") != _BASE or
        p.get("rights_status") != "not_verified" or
        not _label(p.get("display_ar")) or
        type(p.get("origin_reported")) is not str or
        not (10 <= len(p["origin_reported"]) <= 250) or
        "mosshaf.com" not in p["origin_reported"]):
        raise CatalogError("invalid_platform_origin_or_rights")
    rows = data["sources"]
    if type(rows) is not list or len(rows) != len(_KNOWN):
        raise CatalogError("unexpected_bibliography_size")
    for i, item in enumerate(rows):
        if type(item) is not dict or set(item) != _SOURCE:
            raise CatalogError("invalid_bibliography_fields")
        if item.get("id") != _KNOWN[i]:
            raise CatalogError("unexpected_bibliography_identity")
        if not _label(item.get("title_ar")) or not _label(item.get("author_ar"),nullable=True):
            raise CatalogError("invalid_bibliography_label")
        if (item["edition"] is not None or
            item["source_status"] != "metadata_only_unreviewed" or
            item["rights_status"] != "not_verified" or
            item["text_ingested"] is not False or
            item["allowed_for_local_quotation"] is not False or
            item["p1_eligible"] is not False or
            item["link_scope"] != "ksu_navigation_not_book_text"):
            raise CatalogError("forbidden_source_or_rights_promotion")
    return data


def _decode_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise CatalogError("duplicate_json_field")
        result[key] = value
    return result


def _reject_number(value: str):
    raise CatalogError("nonfinite_json_number")


def load_catalog() -> dict[str, Any]:
    """Read metadata only, bounded by 16 KiB, no remote requests."""
    try:
        raw = CATALOG_PATH.read_bytes()
        if not (1 <= len(raw) <= 16384) or raw.startswith(b"\xef\xbb\xbf"):
            raise CatalogError("catalog_size_or_encoding")
        data = json.loads(raw.decode("utf-8","strict"),
                          object_pairs_hook=_decode_pairs,parse_constant=_reject_number)
        return validate_catalog(data)
    except (OSError,ValueError,UnicodeError,RecursionError,OverflowError) as exc:
        raise CatalogError("catalog_unreadable_or_unverified") from exc


def _reference(ref: str) -> tuple[int,int]:
    m = _REF.fullmatch(ref) if type(ref) is str else None
    if m is None:
        raise CatalogError("bad_quran_reference")
    surah,ayah = int(m[1]), int(m[2])
    if not (1 <= surah <= 114 and 1 <= ayah <= _VERSE_COUNTS[surah-1]):
        raise CatalogError("quran_reference_out_of_range")
    return surah, ayah


def ksu_links(ref: str) -> dict[str, str]:
    surah, ayah = _reference(ref)
    link = f"{_BASE}#aya={surah}_{ayah}&m=hafs"
    return {"muyassar":link+"&qaree=husary&trans=ar_mu",
            "choose_tafsir":link}


def catalog_for_ref(ref: str, source_kind: str) -> dict[str,Any]:
    """Metadata response is never P1 evidence or permission to quote tafsir."""
    if type(source_kind) is not str or source_kind not in (
            "unverified_github_mirror", "tanzil_domain_unattested_export"):
        raise CatalogError("reference_source_not_eligible")
    links=ksu_links(ref)
    catalog=load_catalog()
    return {
      "contract":catalog["contract"],
      "reference":ref,
      "platform":catalog["platform"],
      "sources":catalog["sources"],
      "links":links,
      "use_scope":"external_navigation_only",
      "text_import_allowed":False,
      "source_authenticated":False,
      "scholarly_verification":False,
      "scholarly_verified":False,
      "rights_verified":False,
      "redistribution_approved":False,
      "juristic_inference_allowed":False,
      "public_fatwa_authorized":False,
      "edition_verified":False,
      "p1_admitted":False,
      "ai_tafsir_generated":False,
    }
