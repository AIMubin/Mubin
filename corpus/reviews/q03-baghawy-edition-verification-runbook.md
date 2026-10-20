# Q0.3 — Baghawi printed-edition verification

## Boundary between evidence and acceptance

Four Baghawi Tafsir Center records (4:43, 17:4, 18:10, 33:9) each contain exactly 32767 Unicode characters and stop in a non-natural place. The original source database and imported Mubin SQLite have identical text field values. An independent digital witness hosted by KSU contains additional continuation for each of the four. This is strong evidence of source-side digital truncation, NOT printed-edition verification.

Scientific measurements: q03-baghawy-length-ceiling.json, q03-baghawy-four-digital-continuations.json, q03-tafsir-upstream-machine-report.json.

## Printed edition candidate

معالم التنزيل (تفسير البغوي), دار طيبة, 1409 هـ / 1989 م, تحقيق محمد عبد الله النمر، عثمان جمعة ضميرية، سليمان مسلم الحرش, 8 volumes.

Waqfeya catalog: https://waqfeya.net/books/%D9%85%D8%B9%D8%A7%D9%84%D9%85-%D8%A7%D9%84%D8%AA%D9%86%D8%B2%D9%8A%D9%84-%D8%AA%D9%81%D8%B3%D9%8A%D8%B1-%D8%A7%D9%84%D8%A8%D8%BA%D9%88%D9%8A-%D8%B7-%D8%AF%D8%A7%D8%B1-%D8%B7%D9%8A%D8%A8%D8%A9-62a02391d9854b00bceb37bd84e94365

- 4:43: volume 2 — Al Imran to An Nisa.
- 17:4 and 18:10: volume 5 — An Nahl to Al Muminun.
- 33:9: volume 6 — An Nur to Fatir.

PRINTED PAGE NUMBERS HAVE NOT YET BEEN VERIFIED. A different, fourth Dar Taybah edition dated 1417 H / 1997 is indexed by Shamilah; do not merge its page numbers with the 1409 H edition. A KSU Quran verse page number is not a printed Baghawi commentary page number.

## Reviewer tasks

1. Obtain authorized access to the indicated printed volume and its page images; record physical page number, PDF page index, publisher, year, edition, editor, image SHA-256 and neighboring context.
2. Extract a lawful transcription into the ignored corpus-data/editorial directory, not GitHub. Store a witness metadata JSON next to it.
3. Run the following from a Windows 11 local clone (replace directories and page numbers):

    python -m corpus.audit_baghawy_cutoff --database D:\MubinVault\snapshots\run-39267807115\linked\quran_tafsir.db --sura 4 --aya 43 --witness-text-file corpus-data\editorial\baghawy\4-43\candidate.txt --witness-metadata corpus-data\editorial\baghawy\4-43\edition.json --report corpus-data\editorial\baghawy\4-43\alignment.json

Witness edition.json example:

    {
      "source_type": "printed_edition_transcription",
      "work": "معالم التنزيل",
      "source_url": "https://waqfeya.net/books/...",
      "publisher": "دار طيبة",
      "edition": "1409 هـ / 1989 م",
      "volume": "2",
      "page": "ACTUAL PRINTED PAGE NUMBER, TO VERIFY",
      "image_page_sha256": "SHA256 OF RELEVANT PRINTED SCAN",
      "verified_by_reviewer": false
    }

4. Examine the original text ending and the continuation in the identified pages. Record whether passage and footnote boundaries align; a diagnostic suffix match alone does not establish source identity.
5. Retain original data unmodified. A corrected view requires a reversible editorial overlay with approval and separate licensing evidence. Do not invent missing tafsir or copy an edited publication without applicable rights.

## Acceptance criteria

For each of the four entries: identify the actual printed edition and page(s); show independent continuation beyond the exact cutoff; verify full per-ayah paragraph boundaries; record reviewer and rights decision; preserve provenance and original text.

The four KSU digital continuations and the statistical 32767 boundary DO NOT close this printed-edition gate.

## Local PDF scan attestation (Q0.3, prepared)

Independent catalogue: https://waqfeya.net/books/معالم-التنزيل-تفسير-البغوي-ط-دار-طيبة-62a02391d9854b00bceb37bd84e94365

Printed pages have **not yet been inspected**. Download locators are archived in [q03-baghawy-scan-page-locators.json](q03-baghawy-scan-page-locators.json). PDF volume sources: https://archive.org/download/FP3457/malimt2.pdf (volume 2); https://archive.org/download/FP3457/malimt5.pdf (volume 5); https://archive.org/download/FP3457/malimt6.pdf (volume 6).

Use a local Windows machine with PyMuPDF 1.26.x to capture selected PDF **page indices** into an ignored corpus-data directory:

    python -m pip install "PyMuPDF>=1.26,<1.27"
    python -m corpus.attest_tafsir_print_pdf --pdf D:\MubinEditions\malimt2.pdf --verse-id 4:43 --volume 2 --pages 1,2 --edition-metadata corpus-data\editorial\baghawy\vol2\edition.json --out-dir corpus-data\editorial\baghawy\vol2\pages

The indices 1,2 are COMMAND PLACEHOLDERS, not actual identified pages. The JSON metadata needs work, publisher, publication_year, edition, scan_url; capture produces PDF SHA-256, PNG page hashes, render version and per-page metadata. It intentionally leaves printed pagination, edition identity, paragraph boundary review, rights approval, and scholarly verification false.

The external digital index Islamweb indicates volume 2 / site page 220 for verse 4:43 and volume 5 / site page 67 for 17:4. **These are candidate finding aids, not verified printed page numbers of the Dar Taybah 1409 scan.** No source text or scans are approved for public commit. Review rendered pages locally and record printed folio/page, source-imprint confirmation and reviewer acceptance separately.

## Q0.3 follow-up: high-resolution verification of al-Kahf 18:10

The initial private image handoff contained 120-dpi rendered pages 154–155 of the vol.5 candidate scan, from which an AI visual review read `فلما أتى الملك الخبر` (where archive OCR read `أنى`). The letter form in `ثلثمائة/ثلاثمائة` is **not yet securely adjudicated**, and the normalised textual witness does not have a unique suffix alignment; do not mark it VERIFIED.

The print-scanning tool now permits 300-dpi renders (bounded 96–360 dpi). This must be a fresh render **from the original PDF**, not image upscaling. On the user's Windows system, run the following after updating the repository:

~~~powershell
python -m corpus.attest_tafsir_print_pdf `
  --pdf "D:\MubinEditions\malimt5.pdf" `
  --verse-id "18:10" --volume 5 --pages "154,155" --dpi 300 `
  --edition-metadata "corpus-data\editorial\baghawy\18-10\edition.json" `
  --out-dir "corpus-data\editorial\baghawy\18-10\print-proof-300dpi"
~~~

The destination must not already exist. Verify the original PDF SHA-256 `a9191af575d27ca9b959d06a537ca02ac18fa6ec84e0516906a5490e5ab7692f` against the local scanned volume before proceeding. Return only the two newly rendered PNGs, their full SHA-256 values, and the metadata JSON for private visual review. Do not commit images or copyrighted text to GitHub.

Human reviewer signs off separately on the exact number spelling, edition imprint and paragraph boundaries; CLI output cannot assert scholarly or redistribution approval.
