# Q0.1 — Primary and adversarial maintainer audit (research-only snapshot lookup)

**Date:** 2026-10-18. **Reviewed implementation HEAD:** `5c10777bafd94446ec6cf6b2d3609321c62a4e35`.
**Base main:** `567e55858a9911a23430ef81f1e41b7a5f26480e`, unchanged.
**PR:** [#73](https://github.com/AIMubin/Mubin/pull/73), **Draft, open, unmerged**.
**Global Mubin version:** `0.1.0-alpha`. Q0.1 is an isolated internal Quran-engine *proposal*, not Q0.1 on main nor a verified scripture corpus.

## Scope and exact boundary

The PR changes exactly ten paths:
- `engines/quran/q01/engine.py`, `__main__.py`, `__init__.py`: a bounded byte-pinned, offline verse-snapshot validator, deterministic `surah:ayah` lookup and literal/query-only mark-insensitive search.
- `engines/quran/fixtures/q01-{manifest,verses}-synthetic.json`: **four INVENTED Arabic testing phrases**, not Quranic text and not usable to answer users' religious questions.
- `schemas/quran-q01-snapshot.schema.json`: strict Draft 2020-12 contracts for untrusted local manifest + corpus.
- `core/tests/test_quran_q01.py`: fail-closed structural, semantic, adversarial and CLI tests.
- `engines/quran/README.md` and `docs/research/QURAN-Q01-SNAPSHOT-INTEGRITY.md`: technical limits, candidate legal sources and next acquisition process.
- `.github/workflows/mubin-quran-q01.yml`: PR and main path filters, all-core test suite and three standalone CLI smoke cases.

No `H3.9.2` test, heldout record, frozen source, Usul/Fiqh rule or source-rights decision was modified. No provider digital Quran file was downloaded or committed.

## Source and rights trust boundaries

The reader accepts **only local bytes the operator already possesses and may use**. A user-supplied SHA-256 manifest is a self-declared commitment; passing its equality check means the supplied corpus was not changed relative to that declaration. It is **not** proof of text authenticity, edition identity, scholarly attestation, publisher custody, copyright/license satisfaction, or correctness of any subsequent Quranic interpretation.

The fixed 114-chapter / 6,236-numbered-verse table is Hafs/Kufan metadata topology; even perfect structural coverage cannot validate the text itself. The full-coverage label is rejected if counts/coverage fail, but not promoted to authenticity on success. All reports have `source_authenticated=false`, `rights_verified=false`, `canonical_corpus_qualified=false`, `eligible_for_religious_ruling=false`. Synthetic fixtures report `synthetic_fixture_only`.

Tanzil's [published terms](https://tanzil.net/docs/Text_License) allow attributed verbatim copies subject to their non-modification and notice requirements; the [King Fahd Quran Complex](https://qurancomplex.gov.sa/en/techquran/dev/) publishes separate Uthmani and Imlaei developer data; [Quran Foundation API terms](https://api-docs.quran.com/legal/developer-terms/) constrain permanent storage/redistribution. **None of these corpora has been ingested.** Do not equate their licensing or versioning. Do not strip, combine, translate, reorder or silently re-encode source Quran text; optional matching normalization is only a transient search-key view. The bismillah handling depends on the chosen official data variant and must be recorded in the source-specific adapter.

## Maintainer code review and threat/falsification coverage

- **Content integrity:** compare SHA-256 of exact supplied corpus-file bytes, no silent UTF8 normalization, no BOM, no JSON NaN/Infinity, duplicate object members, missing/extra fields, unbounded arrays/text, bad Unicode surrogates, C0 controls, bidi override characters or non-Arabic text. A manually changed corpus and updated self-declared hash is deliberately **allowed structurally** but *still remains unverified*.
- **Numbering:** reject duplicate, re-ordered and out-of-surah-bounds keys, leading-zero/ambiguous references and false complete-corpus counts. Absence from a partial snapshot returns `found=false`, not a fabricated verse.
- **Separation:** Quran text stays separate from tafsir, other readings, translations, page guesses and derived rulings. Mixed/extra fields fail. Search returns exact original text and source snapshot metadata; no normalized text can leak as a Quran quotation.
- **Immutability:** `QuranIndex` freezes its source manifest via a copied mapping proxy; caller cannot retitle provenance or status after validating the original bytes.
- **Search:** strict exact-match default; mark-insensitive comparison strips Arabic combining marks only in transient matching. Query consisting solely of diacritics is rejected rather than matching all verses.
- **Safe intake:** bounded per-file reads from actual regular descriptors with O_NOFOLLOW (where available) and O_NONBLOCK, no symlink leaf or FIFO on Linux CI; no huge file/hardcoded release claim. Programmatic subclassed dictionaries are rejected without trusting overloaded equality operators.
- **CLI:** 0 = structurally valid snapshot / executed lookup; 1 = invalid corpus/query; 2 = unsafe/missing file. A successful CLI never attests original source status or grants scholarly authority.
- **Limits explicitly retained:** upstream source acquisition and license are out of scope; parent directory symlink/hardlink trust, filesystem races outside the descriptor, and cross-platform O_NOFOLLOW behavior need separate treatment if a persistent external ingestion service is built. Printed edition or official Quran source is not authenticated by this pilot. The chosen Uthmani/Hafs numbering convention is not a general model of all qira'at.

## Exact GitHub RED → GREEN history

1. **RED before implementation** at `206e3cdde19a4e1139f97aa42c79fb0f386f915f`: [P0 run 39114485832](https://github.com/AIMubin/Mubin/actions/runs/39114485832) failed with **`ModuleNotFoundError: No module named 'engines.quran.q01'`**. Test-only first.
2. **Initial implementation** at `0762a39d1da4c1f04b58d27d46035ed58629d92c`: [Q0.1 run 39114593227](https://github.com/AIMubin/Mubin/actions/runs/39114593227) and [P0 run 39114593156](https://github.com/AIMubin/Mubin/actions/runs/39114593156) **success**, including 20 new Q0.1 tests plus baseline P0 tests.
3. **Maintainer-discovered query/provenance defects; additional RED tests** at `67868a984adfda29cfae23afc0bb655912d1cbd1`: [Q0.1 run 39114718073](https://github.com/AIMubin/Mubin/actions/runs/39114718073) and [P0 run 39114718067](https://github.com/AIMubin/Mubin/actions/runs/39114718067) **failed as expected**: 72 tests, 4 negative subcase failures (three diacritic-only query strings accepted + mutable source manifest).
4. **Repaired implementation** at `5c10777bafd94446ec6cf6b2d3609321c62a4e35`: [Q0.1 run 39114797010](https://github.com/AIMubin/Mubin/actions/runs/39114797010) and [P0 run 39114797041](https://github.com/AIMubin/Mubin/actions/runs/39114797041) **success**. Runner logs confirmed **72/72 cumulative tests** and the three CLI scenarios. Example report: `loaded_verse_count=4`, `scope=synthetic_fixture_only`, `source_authenticated=false`, `rights_verified=false`. Synthetic raw snapshot digest `915c609b88ef03f5330b6d27f33c13fb746801795f391d1813edc07ab21ccbcc`.

**Important:** after this audit-file commit, CI must be rerun at the exact final HEAD; success from the preceding implementation HEAD must not be reused as final-HEAD evidence.

## Approval boundary / next iteration

`codex_review=unavailable` as a secondary independent pass under the previously recorded project-wide quota exhaustion; this is a **maintainer-only engineering review** and must not be advertised as independent AI review. No human Quran-scripture verification has been performed.

**Engineering gate:** structurally sound prototype subject to exact-final-HEAD CI. **Source gate:** no real Quran corpus yet. **Next value milestone:** acquire an exactly licensed and pinned version of a complete Hafs Quran provider dataset, replay numeric/content checks and display verbatim, with provenance/rights evidence, in a *separate* PR. This must not block parallel P1, Hadith or Usul/Fiqh development.

**Merge gate:** keep PR draft until dependent governance checks, exact-HEAD review and scientific source scope are not overstated. No release/version bump or H3.9.2 changes.
