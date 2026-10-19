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
