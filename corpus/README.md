# Mubin corpus acquisition (foundation)

This directory defines a **source registry** and a **local-file ingestion tool**. It does not claim that any Quran, tafsir, hadith, fiqh, or mushaf corpus has already been downloaded, authenticated, or verified.

## Acquisition rules

1. Keep original source bytes immutable and content-addressed with SHA-256.
2. Preserve source, edition, textual recension, rights, acquisition URL, date, and citations.
3. Keep Quran canonical text separate from normalized search tokens. Never silently normalize, correct, or regenerate canonical Quran verses.
4. Model mushaf page images as edition / riwayah / page; model Quran text as riwayah / surah / ayah / text-version. Cross-map explicitly.
5. Tafsir paragraphs require book / author / editor or print edition / volume / page / ayah range, with multiple interpretations kept distinct.
6. A public-domain original does not automatically clear copyright on a modern edited edition, translation, typesetting, annotations, or scans.
7. Importing to a private staging area is not the same as permission to reproduce or redistribute. Use rights-aware publication decisions, but allow metadata and official remote references while approvals are pending.
8. Do not defeat rate limits, access controls, authentication, or third-party prohibitions on mirroring.

## Workflow

Download a source from its official or authorized location, record its exact edition, then:

```bash
python corpus/import_local.py ./downloaded-source.txt \
  --root ./corpus-data \
  --source-id tanzil-uthmani \
  --edition "Publisher release identifier" \
  --source-url "https://tanzil.net/download/" \
  --rights "CC BY 3.0; verbatim-only; attribution required" \
  --visibility review_pending
```

Keep `corpus-data/` outside git. Hash validation only proves byte integrity, **not** textual religious accuracy. A second verification phase must check surah/ayah counts, authoritative references, edition identity, variants, and manual scholarly review before setting `verification_status=VERIFIED`. For Quran, demand 114 surahs and 6,236 verses **for the selected standard verse-numbering convention**; ensure bismillah conventions are explicit. Do not use this count alone to authenticate text.

## Acquisition priorities

P0: verified Quran text (Hafs baseline), source metadata, canonical verse identifiers.
P1: official mushaf editions and page/ayah mappings; Tafsir Ibn Kathir, al-Tabari, al-Qurtubi, al-Sa'di, al-Baghawi, al-Tahrir wa al-Tanwir, al-Tafsir al-Muyassar — as **distinct sourced editions**, not blindly copied from unspecified websites.
P2: qira'at/riwayat, asbab al-nuzul, nasikh-mansukh, ulum al-Quran, Arabic lexica; then hadith corpora/isnad apparatus and usul/fiqh works across madhahib. Material of uncertain distribution status gets metadata + citations or official links until an authorized copy is available.

## Operational status

Registry scaffold and importers: implemented. A real pinned Tafsir Center download was imported in GitHub Actions and independently inspected from user-supplied staging SQLite (source DB SHA-256 `a1bd1811ab1b3a4a0373b6499f916f8c379df64ad77fbaf1988e08d34a1814a0`). Coverage: 6,236 derived Quran verses and 31,180 non-NULL tafsir entries across five sources. A prior Tanzil comparison found 0 byte-exact verse matches; diagnostic categories are **not yet established**. The staging Quran text is **not** an authenticated verbatim Uthmani witness. Editorial audit identified seven al-Tabari HTML-only entries and four al-Baghawi 32,767-character truncation candidates; see [review queue](reviews/q03-tafsir-review-queue.json). Independent edition checking and scholarly verification remain pending. GitHub Actions artifacts expire after 30 days and are not permanent storage. Rights status remains under review; publication is not approved.

Q0.3 tools: `python -m corpus.audit_tafsir_quality`, `python -m corpus.triage_quran --reference corpus-data/reference/tanzil-uthmani.txt` and `python -m corpus.query 1 1 --reference corpus-data/reference/tanzil-uthmani.txt`. All diagnostics preserve original files; classification does **not** establish scriptural equivalence.

## Q0.3 derived-text display safeguard

Direct inspection of the linked SQLite release revealed **364 verse records containing 371 literal slash characters**, including `2:21` rendered `يا/أيها`. The importer's joined-word strings are *not* suitable as Quranic display text. Read operations now return `text=null` by default without a pinned Tanzil witness; diagnostic access to unverified derived text requires `--allow-unverified-derived-text`. This is separate from the outstanding independent scholarly approval and license review. [Audit record](reviews/q03-derived-quran-observations.json).
