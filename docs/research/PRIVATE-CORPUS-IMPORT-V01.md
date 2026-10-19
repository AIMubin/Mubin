# Mubin — Research corpus import, stage 1 (internal; not a release)

**Policy:** import now for internal research under a legal review in progress. Do **not** treat collection or structural verification as permission to publish, an authenticated tafsir edition, or P1 gold/authoritative evidence.

### Data actually targeted in the first automated full import

- **Tanzil Quran Uthmani 1.1**: one exact externally observed HTTPS export, full 6,236 verses, preserving every original codepoint and copyright footer. Pinned SHA-256 `7f30c647331a61100ebf24a80507dc0fcdd9f2df97f1312b5b2dfcb982a7f326`. Hafs/Kufan numbering only. Does not establish other qira'at or prints.
- **QuranEnc.com**: four distinct full Arabic editions, each 6,236 keyed explanations with footnotes: Al-Muyassar (`1.0.0`), Al-Mukhtasar (`1.0.0`), Al-Yaseer (`1.0.22`), An-Nafahat al-Makkiyyah (`1.0.0`). Packages sourced from `m-alhamry/Quran-text-assets` pinned Git commit `698f8bbdb5f8a892e978d4e95a750b92406dc418`; immutable gzip bytes verified against SHA-256, compressed/decompressed size, edition and complete coordinates. **The mirror's package hashes do not independently certify official QuranEnc provenance**; retain exact upstream version/footnotes/attribution and legal-review status.
- Repository import contract: `research/corpora/import-sources-v01.json`. Actual text/footnotes stay only in a SQLite DB **outside the Git checkout**, or in a disposable GitHub runner. The public repository contains importer code, tests, source metadata and source hashes, never unreviewed corpora, raw downloads, corpus archives or database artifacts.

### How to run locally without waiting for legal publication approval

Checkout the PR #76 stack. Choose an **access-restricted private directory outside the repository** and run:

```bash
umask 077
python -m qa.corpus_ingest_v01 \
  --manifest research/corpora/import-sources-v01.json \
  --input-dir /private/mubin/source-archives \
  --output-db /private/mubin/corpora.sqlite3 \
  --download
```

The script downloads each file by an allowlisted HTTPS endpoint, verifies exact pinned raw bytes, rejects a changed source, validates the 114-surah / 6,236-entry maps, creates one immutable SQLite snapshot, and prints **counts and SHA only**, without any excerpt. It never overwrites existing output. Change the output path for each ingestion generation and record its receipt. Do not expose this SQLite file through the public Quran reader or GitHub artifacts.

For incomplete network access, import only the available *previously fetched* pinned files with `--allow-partial` (omit `--download`). The report names missing sources; it never claims that all corpora were imported. The CI reference run uses **all five** and fails closed if any download, source hash or structural check fails. Actual rights evaluation is a **separate publication gate**; it is not a prerequisite for data indexing and search engineering.

### Next acquisition queues running in parallel

1. **King Fahd Glorious Quran Printing Complex** official developer downloads: Hafs text variations, separately verified reading/edition profiles, `Tafseer Muyassar` official dataset (7.51 MB; published SHA-1 `5f533113c2f54f32eded734bb49e6a5837965722` and MD5 `5601682965e32f4dd6992c7600fdccc3`), and `Muyassar Ghareeb`. Every orthography / reading is its **own** file/version/sha and coordinate scheme; not interchangeable with the existing Hafs text.
2. **Tafsir Center / tafsir-mcp**: database distributed with its own CC BY 4.0 attribution statement, code MIT; published `quran.db` expected SHA-256 `10e61f615ab5e6a3440e8ecc8ba1dc2273d12cd9048752760fe53a44d191cc27`, about 214 MB, including classical tafsirs, word data, qira'at and asbab al-nuzul. Import only after validating full schema, provenance and separate source/license notice; do not pretend those data are independent scholarly approvals from Mubin.
3. **Additional classical editions (Tabari, Ibn Kathir, Baghawi, Qurtubi, Saadi)**: select versioned sources independently, record editorial edition and scholarly origin; catalog entries and a book title are *not* source content, and derived webpage scrape is not permission by itself. Legal team resolves reuse/publication policy in parallel.

### Governance and data-use boundaries

- `research_internal_unpublished` / `legal_review_pending` is an operational state, **not** a judgment that internal copying or any use is legally permitted in every jurisdiction. Follow organizational legal-team guidance and source terms; take down any source they flag. The importer is reusable for inputs the organization is authorized to hold.
- Preserve raw file bytes, content, footnotes, source transcripts/attribution in their original edition; derived search tokens/indexes remain separate and never overwrite the quoted text.
- All source rows are marked `publication_enabled=0`, `source_authenticated=0`, `p1_admitted=0`. P1 ingestion and religious ruling qualification remain different procedures. Formal release requires publisher/source permissions where applicable, edition/provenance validation and scholarly authority checks.
- No Hadith H3.9.2 Schema-31 files, reserved holdouts, human signoffs, public main branch, or system version changes.

**Initial source documentation:** [Tanzil license](https://tanzil.net/docs/Text_License), [QuranEnc terms](https://quranenc.com/en/home/api/), [QuranEnc versioned archive](https://github.com/m-alhamry/Quran-text-assets), [King Fahd developer portal](https://qurancomplex.gov.sa/en/techquran/dev/), [Tafsir Center repo/license](https://github.com/tafsircenter/tafsir-mcp).
