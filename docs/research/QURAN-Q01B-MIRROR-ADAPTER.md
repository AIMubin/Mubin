# Q0.1b — Exact-source mirror reader and ephemeral full Quran lookup

**2026-10-18. Research/engineering capability, NOT an authenticated digital mushaf or official Tanzil copy.** Mubin `0.1.0-alpha`; Q0.1/Q0.1b live on open PR branches, not on `main`.

## Full-text candidate source

The primary Tanzil [download page](https://tanzil.net/pub/download/index.php) advertises UTF-8 Quran data **Version 1.1**. Tanzil's [Text License](https://tanzil.net/docs/Text_License) allows **verbatim copies** in applications with visible attribution and link to Tanzil, prohibits changes to the Quran text, and requires including the Tanzil copyright notice in copies. At this stage Mubin has **not** downloaded and cryptographically attested the Tanzil-hosted original for a specific export preset.

For a real full-text *engineering demonstration only*, use the third-party copy at [acfatah/tanzil, immutable commit `052b515f...`](https://github.com/acfatah/tanzil/tree/052b515f3a24dfacbe4cafc3b89f0681a447f462). Its README says **copy of** Tanzil, not a publisher-authorized upstream release. Raw path `data/quran-uthmani.txt`, Git blob `f2f03c415ea50f8493d2058ec67a90257333abe3`, size 1,396,677 bytes (GitHub API). It contains a `sura|aya|Uthmani text` line per 6236 numbered verses with a copyright notice in the unmodified file tail. The apparent Hafs/Kufan count is 114 surahs / 6236 ayahs. A complete count and SHA pin are *file identity and topology only*, not proof of scripture authenticity, license sufficiency for a modified third-party copy, or publisher custody.

**Important rejection:** The independent `nuqayah/quran-text` repo documents intentional Unicode/orthographic changes to Tanzil text (Farsi Yeh, open tanweens, spacing); it must not be described or redistributed as the official verbatim Tanzil copy under Tanzil's unchanged-text terms. The chosen `acfatah` mirror is also not yet independently compared with official Tanzil; that unresolved fact remains in metadata.

## Execution

1. A GitHub Action fetches this exact pinned third-party GitHub file only into the ephemeral runner directory (never into Mubin Git, never uploaded as an artifact).
2. `load_raw` compares the **original bytes** to pinned length, SHA-256 and independently a Git blob SHA-1. The parser validates every consecutive `sura|aya|text` record, 114/6236 topology and the original Tanzil license notice. No text is edited, replaced or rewritten.
3. `get 2:1`, `get 114:6` return exact source Unicode sequences; `find` optionally strips combining marks in *matching only*, never in returned text, source file, or scripture export.
4. All outputs remain `source_authenticated=false`, `official_tanzil_bytes_independently_verified=false`, `rights_verified=false`, `eligible_for_religious_ruling=false`. The term **full** denotes numeric coverage only.

This speeds product engineering without claiming an independent human review or allowing fatwa generation. Actual publication must show a Tanzil link, the required notice and a provenance badge disclosing the mirror. Comparing the mirror's original bytes with an exactly versioned official Tanzil export (including options for basmala, pause/sajdah marks, kashida and verse boundaries) remains a separately audited source acceptance step.

## Reproduction

```bash
python -m engines.quran.q01b --manifest engines/quran/q01b/sources/tanzil-mirror-v1.1.json --source path/to/exact-original-mirror-file --json verify
python -m engines.quran.q01b --manifest engines/quran/q01b/sources/tanzil-mirror-v1.1.json --source path/to/exact-original-mirror-file --json get 2:1
python -m engines.quran.q01b --manifest engines/quran/q01b/sources/tanzil-mirror-v1.1.json --source path/to/exact-original-mirror-file --json find الله --fold-marks --limit 10
```

CLI success is **structural and byte-match success**, not final Islamic scholarship, recitation/rāwī identity, text authenticity, or licensing approval. Keep Tafsir and legal inference entirely separate. Do not ingest the H3.9.2 frozen holdouts and do not change its Schema-31 review contract.
