# Q0.1f — Metadata-only Tafsir bibliography and optional KSU linkouts

**Scope:** Arabic reference discovery and manual external navigation in the existing Q0.1c localhost Quran reader. No tafsir book text is stored, downloaded, embedded, or authenticated. This feature does not supersede Q0.3 Quran source work. System version stays `0.1.0-alpha`.

## Source registry

`engines/quran/tafsir/tafsir-catalog-v01.json` lists **six unreviewed candidates**, without edition claims: التفسير الميسر، السعدي، البغوي، ابن كثير، القرطبي، الطبري. `schemas/quran-tafsir-source-v01.schema.json` and `engines/quran/tafsir/catalog.py` reject extra fields and all promotions. Every source has:

- `edition=null`, `source_status=metadata_only_unreviewed`, `rights_status=not_verified`.
- `text_ingested=false`, `allowed_for_local_quotation=false`, `p1_eligible=false`.
- `link_scope=ksu_navigation_not_book_text`.

The registry contains only names/attributions as **candidate bibliographic metadata**, not verified links between exact print editions and digital content. The KSU platform metadata describes its reported origin in mosshaf.com; Mubin has not independently verified that provenance, licensing, or displayed edition.

## Safe read-only navigation

After the reader loads an **original, fully byte-pinned Q0.1b mirror file**, `GET /api/tafsir-catalog?ref=2%3A1` returns metadata for a numbered verse in the *loaded* index and two external addresses at the fixed `https://quran.ksu.edu.sa/index.php` origin:

- `#aya=2_1&m=hafs`: open the verse and choose tafsir at KSU.
- `#aya=2_1&m=hafs&qaree=husary&trans=ar_mu`: open the verse with the example interpretation option.

The browser does **not** preload or crawl KSU; it displays six unverified titles via `textContent` and supplies optional links requiring a deliberate click, `target=_blank`, `rel=noopener noreferrer`, and `referrerPolicy=no-referrer`. KSU navigation/fragments can change independently; this feature does not guarantee third-party navigation outcomes.

The API denies synthetic and unknown sources with HTTP 403, invalid references with HTTP 400, and absent coordinates with HTTP 404. Only `unverified_github_mirror` sources accepted by the existing Q0.1b pinned-manifest validation are eligible. **This is eligibility for navigation metadata, not authenticity or scientific source admission.** Q0.1e's experimental official-domain adapter is intentionally excluded from this PR.

## Explicitly not authorized

`source_authenticated=false`, `rights_verified=false`, `redistribution_approved=false`, `scholarly_verified=false`, `juristic_inference_allowed=false`, `public_fatwa_authorized=false`.

No tafsir texts, private sidecars, private corpus import, AI-generated tafsir, inference into P1 or Fiqh, Q0.1e domain probe, browser Chrome E2E, or H3.9.2 holdout modifications. Linking to a scholarly work does not qualify its text or justify attributing interpretations to an unverified edition.

## Engineering qualification

Synthetic tests validate the catalog schema, rejection of authority-laundering fields, malformed KSU references and synthetic-source HTTP denial on both Windows and Ubuntu. A dedicated Ubuntu workflow downloads the previously pinned **unverified mirror** to the ephemeral CI runner (not Git), checks the SHA/verse topology through Q0.1b, then queries the localhost metadata endpoint for `2:1` and validates the six bibliographic entries, read-only navigation links, and false qualification flags. CI does **not** click KSU or certify publisher custody.

Independent review and final exact-HEAD CI must be recorded at the PR after execution, not inferred from earlier old-branch audit documents.
