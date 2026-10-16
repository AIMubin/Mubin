# S0.1 — Shamela feasibility study (bibliography-first, zero text ingestion)

**Date:** 2026-10-16  
**Project:** Mubin system \`0.1.0-alpha\`; this \`S0.1\` is a source-inventory experiment, **not** the overall system release or a qualified engine.  
**Decision:** PROCEED with offline bibliographic metadata pilot; HOLD all automated source text acquisition, embedding, RAG indexing, training, sharing, P1 receipts and Hadith qualification until explicit per-edition gates.

## What was actually verified on the official site

- https://shamela.ws/#categories describes about 8,000 books and 40 categories; the Hadith, Tafsir and Usul categories are relevant, but category counts are not an audit of distinct licensed editions.
- https://shamela.ws/page/download supplies Windows/macOS/Linux application downloads and describes a portable \`database\` directory. It does NOT document a supported machine-readable extraction API, DB file format, rights permission or reproducible data download SHA-256 on the page inspected. The official link documents an available full \`database\` bundle, **not permission to redistribute its contents**.
- Book pages expose publisher, editor, claimed printing/edition, site-reported print pagination, chapter/topic index and human-readable page routes. At least one visited passage page shows text and separated footnotes; **this text was not copied to the repo**.
- The human-visible route \`/book/{book_id}/{route_id}\` is an internal website locator, not an authenticated stable paragraph ID or printed page. For instance \`https://shamela.ws/book/8180/114\` displays a different printed page number. Never infer \`printed_page=114\` from its path. Nor does the presence of a "copy paragraph link" UI prove an official automated export endpoint.

### Three deliberately edition-specific candidates

| Domain | Official book ID | Bibliographic identity on inspected page | Main research risk |
| --- | --- | --- | --- |
| Hadith | [1681](https://shamela.ws/book/1681) | al-Bukhari, Sahih al-Bukhari; al-Sultaniyya, Bulaq 1311H; subsequent photographed reprint with supplementary numbering and editorial notes | Multiple editions/numbering conventions and supplemental notes must not be merged into a single immutable text identity |
| Tafsir | [7798](https://shamela.ws/book/7798) | al-Tabari, Jami al-Bayan; ed. Abdullah al-Turki, Dar Hajar 1422H/2001, 26 volumes including indexes | The catalog header claims freshly entered text from al-Turki, while the longer carried-over description also discusses an earlier text with pagination subsequently matched to Hajar. **Flag for independent editorial reconciliation**, not silent correction |
| Usul | [8180](https://shamela.ws/book/8180) | al-Shafi'i, al-Risala; critical edition and commentary by Ahmad Muhammad Shakir, al-Halabi, first ed. 1357H/1938, 601 pages | The page states additions and corrections from the editor's supplement were inserted at their original positions in the e-text; do not claim exact original manuscript/edition equivalence |

Sample **human-browsing only** URLs: https://shamela.ws/book/1681/9 , https://shamela.ws/book/7798/1 , https://shamela.ws/book/8180/114 . None establishes byte offset, text SHA, scholarly grade or reproducible frozen source.

### Fact vs inference vs unknown

| Claim | Status |
| --- | --- |
| These three site book pages and their reported bibliographies exist and are currently browsable | Observed public-site metadata |
| Printed page numbering is claimed in these page descriptions | Observed *claim by the site*, not externally collated |
| A portable desktop \`database\` folder is described in official documentation | Observed |
| Database storage uses a particular SQL engine or preserves paragraph IDs across versions | **Not verified**; do not assert |
| The official site exposes a stable public API, bulk download format, rate limits or scraping permission | **Not verified**; no crawler is included |
| All electronic text bytes match their declared printed editions | **Not verified** |
| Metadata can be promoted to P1 \`source_sha256\` evidence / Hadith grade | **False inference**; metadata != bytes or scholarly authority |
| Free public reading or availability of installation/data files grants right to reproduce, transform, redistribute or train | **Not established** |
| Source rights can be judged from the original author death year alone | **Incorrect** for modern textual editions, transcriptions and editorial annotations |

## Implemented S0.1 boundary

- \`research/shamela/pilot-catalog.json\`: only three manually recorded bibliographic entries, official book URLs, human-readable passage URLs, edition warnings, and explicit \`rights_status=unverified\`, \`edition_verification=bibliographic_claim_only\`, \`text_acquisition_status=not_acquired\`.
- \`schemas/shamela-bibliographic-catalog.schema.json\`: strict additional-properties rejection, rights and acquisition constants, no unknown text/hash/span/license/qualification fields, byte and entry caps.
- \`core/source_catalog/shamela.py\`: offline schema/ID/link matching validator. Checks that each book's \`shamela:book:ID\` agrees with \`book_id\` and both official links; detects duplicate source/book/page identifiers. Its \`catalog_sha256\` fingerprints the operator-entered JSON only, **not any book**.
- \`core/source_catalog/__main__.py\`: deterministic local command. Exit 0 for valid metadata, 1 for syntactically valid but invalid catalog, 2 for unreadable/malformed CLI input. No HTTP library and no source-text acquisition path.

Run from the repository root:

\`\`\`bash
python -m pip install -r core/requirements-test.txt
python -m core.source_catalog research/shamela/pilot-catalog.json --json
python -m unittest discover -s core/tests -v
\`\`\`

Passing says only that **the catalog structure and declared restrictions are internally valid**. There is no source-provider signature and no attested publisher. The catalog JSON is not a substitute for an external legal review, signed release manifest or content source registry.

## Gates for S0.2, before any text acquisition

1. **Rights matrix by work and edition:** independently document permitted read, local reproduction, automated bulk extraction, transformation, attribution, research evaluation, public display, redistribution and model-training rights. Record authorization provenance or remain HOLD. A site's "free" status is not a blanket permission.
2. **Supported acquisition route:** verify whether the official application/data distribution provides an authorized offline format, stable revision identity, checksums and explicit permission; do not reverse-engineer confidential mechanisms or build a crawler without permission.
3. **Exact edition comparison:** independent specialist review of all catalog contradictions/annotations and explicit treatment of mixed editorial contributions, variant texts and edition-specific numbering.
4. **Structural and source mapping:** sample only an approved nonholdout book/edition, confirm that its local paragraph/page/footnote IDs survive export; compare exact Unicode, headings and footnotes separately. Record absolute UTF-8 byte offsets **only after raw source bytes are legally obtained and cryptographically pinned**.
5. **Cryptographic custody and partition gate:** if authorized raw texts become available, record independent SHA-256, license evidence and versioned snapshot custody; never silently merge Shamela with OpenITI IDs or H3.9.2 frozen source registry. Preserve source-/family-disjoint holdouts and human scholarly adjudication.
6. **Research gate:** 3-books × (metadata consistency, per-edition rights, stable locators, textual non-normalization, extraction reproducibility, cross-edition disagreement) measurable matrix. If any criterion remains unknown, report \`not_demonstrated\` instead of \`passed\`.

**No-go until the gate:** do not bulk download, mirror the site, scrape text, insert source text into git, compute fabricated SHA-256 from page URLs, or feed unlicensed text into LLM training/RAG. A comparative citation may link to the publisher page without claiming content possession.

## Relationship to existing Mubin modules

S0.1 has no imports from frozen Hadith Factory and does not mutate \`engines/hadith/qualification/H3.9.2/\`. Its \`shamela:book:ID\` is only a proposed local catalog ID, not an H3 source ID or canonical book/edition URI. In P1.1, verification requires already-existing exact UTF-8 bytes and a pinned source registry, and P0/P1 inferential receipts remain structural/local only. S0.1 **cannot** produce those receipts.

Separate bibliography, licensing, edition/source pins, textual spans, and scholarly validation as independent assurance layers. Source-provider agreement is corroboration for an **exact, independently established edition**, not by itself proof of authenticity or a license.
