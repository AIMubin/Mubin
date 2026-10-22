# Quran Engine

Current internal milestone: `Q0.3` **in progress** — internal technical exit distinct from public release. See [Q0.3 engineering exit contract](Q0.3-ENGINEERING-EXIT.md).
Mubin system version remains `0.1.0-alpha`.

## Source-connected components

- [Tafsir Center pinned importer](../../corpus/import_tafsircenter.py) (6,236 verse IDs, five tafsir sources)
- [Quran read-only retrieval](../../corpus/query.py) (no Quran text by default; explicit pinned Tanzil witness required for display, derived text requires developer diagnostic opt-in)
- [Linked SQLite audit](../../corpus/audit_linked.py)
- [Conservative witness difference triage (legacy raw rows)](../../corpus/triage_quran.py)
- [Boundary-aware independent Quran witness analysis](../../corpus/quran_witness_analysis.py)
- [Editorial tafsir-quality audit](../../corpus/audit_tafsir_quality.py)
- [Upstream-to-import byte-exact tafsir comparison](../../corpus/audit_tafsir_upstream.py)
- [Measured real-data witness findings](../../corpus/reviews/q03-quran-witness-analysis.json)
- [11-item manual review queue](../../corpus/reviews/q03-tafsir-review-queue.json)
- [Import/quality workflow](../../.github/workflows/import-quran-tafsir.yml)
- [Q0.2 baseline contracts](../../corpus/Q0.2.md)

## Measured import status

A real staging SQLite artifact has been inspected independently: 6,236 **derived**, unvocalized verse strings and 31,180 nonempty tafsir entries. All five tafsir keys cover every verse ID. Seven al-Tabari entries have only HTML markup; four al-Baghawi texts are exactly 32,767 characters and need source-edition verification. A legacy raw-row comparison found 0/6,236 byte-exact matches. A new analysis of the pinned verbatim Tanzil txt-2 witness identifies 112 first-verse records with prefixed surah-opening basmala (suras 95 and 97 have alternate opening diacritics). Once these *record* prefixes are separated by literal substring boundaries, candidate comparisons across 6,236 ayahs yield 1 exact match, 436 marks-only candidates, 829 alef-variant candidates, 917 additional-script candidates and 4,053 differences not resolved by those simple transforms. These groupings are **not** Quranic equivalence judgments; the data includes 364 derived records with slash artifacts. Additional review of the imported SQLite SHA-256 `a1bd1811ab1b3a4a0373b6499f916f8c379df64ad77fbaf1988e08d34a1814a0` found 364 derived verses with 371 literal `/` marks, for example `2:21` contains `يا/أيها`. These are unacceptable as a canonical display rendering. See [derived text safety review](../../corpus/reviews/q03-derived-quran-observations.json).

**Action-specific hard gates:** Nothing in Q0.3 proves Quranic canonicality, authenticity of any modern tafsir edition, complete tafsir coverage beyond database keys, or authorization to redistribute each edition. Use a pinned, complete, independently checked Quran witness for provisional reading; preserve provenance. **Engineering exit requires reproducible technical evidence, not blanket human scholarly signoff.** Public text display still requires source/witness integrity and rights; novel authoritative scholarly conclusions or editorial reconstructions require their own qualified approvals. See [risk-based assurance](../../docs/RISK_BASED_ASSURANCE.md).

**Fail-closed read path:** `python -m corpus.query 2 21` returns tafsir references but `text=null` when no pinned Tanzil witness is supplied. Pass `--reference corpus-data/reference/tanzil-uthmani.txt` for a pinned witness; `--allow-unverified-derived-text` is reserved for diagnostic use. `python -m corpus.audit_quran_derived` records reconstruction anomalies. Never patch scripture by stripping `/` automatically.

For first-ayah retrieval outside al-Fatihah and al-Tawbah, the pinned witness may carry an unnumbered surah-opening basmala in the same raw record. `corpus.query` now returns that literal opening separately as `opening_basmala` and uses only the unchanged verse substring for `text`; it fails closed on unknown first-verse layouts. Original witness bytes and provenance remain preserved.

## Q0.3 upstream tafsir fidelity audit (local operator report)

The local operator ran `python -m corpus.audit_tafsir_upstream` on a read-only pinned Tafsir Center source and the linked Mubin SQLite. The reported result was **all 31,180 tafsir field values identical** (6,236 per source), with exit code 0 and expected SHA-256 checks. This is **import fidelity**, not byte-wise equality of SQLite database files and not equivalence to a printed edition. The seven al-Tabari entries containing only HTML and four al-Baghawi entries at 32,767 characters already occur upstream. An exact source-side truncation cause is not proven by length alone.

- [Upstream-fidelity evidence summary](../../corpus/reviews/q03-tafsir-upstream-comparison.json) — describes the operator-supplied report; complete machine-generated JSON still resides locally.
- [Printed-edition candidates](../../corpus/reviews/q03-tafsir-edition-candidates.json) — independent bibliographic comparators, **not** upstream edition identities.
- [Baghawi review issue](https://github.com/AIMubin/Mubin/issues/77) and [Tabari review issue](https://github.com/AIMubin/Mubin/issues/78) — editorial verification pending.

No raw imported tafsir strings have been replaced or corrected.

### Q0.3 independent forensic follow-up

The **complete** machine-generated upstream comparison JSON has since been received, inspected and archived unchanged as [primary evidence](../../corpus/reviews/q03-tafsir-upstream-machine-report.json), original file SHA-256 `22e2a0f058d6d168e6a8352365a90780c1f3703da7aebf11d279c533400f602c`. The local Windows test was reported to pass after explicit SQLite connection closure (`Ran 1 test ... OK`); this does not substitute for an independently observed Windows CI run.

- [Seven al-Tabari shared-heading candidates](../../corpus/reviews/q03-tabary-adjacent-headings.json): each markup-only entry has a neighboring tafsir whose introductory heading explicitly cites that ayah. This suggests a **cross-verse indexing/segmentation representation**, not seven wholly lost tafsir passages. Exact commentary boundaries require printed-edition checks. [Reproducible audit tool](../../corpus/audit_tafsir_crossverse.py).
- [Al-Baghawi 4:43 digital comparator](../../corpus/reviews/q03-baghawy-4-43-digital-continuation.json): an independent online transcription continues the narrator citation after the 32,767-character source cutoff. This supports probable upstream truncation in that particular record but is not verified against the same printed edition; there is no approved source mutation or textual completion.

**Editorial source verification remains open.** This is not a claim that every row is complete or that the linked text is a print-edition transcription.
 


## Q0.3 Baghawi four-record cutoff corroboration

A read-only census of all 31,180 linked tafsir entries shows a **source-specific 32767-codepoint ceiling** in Baghawi: exactly four entries equal the ceiling, none longer. In contrast, Tabari has 57 entries above 32767, and Ibn Kathir 13. The four suspicious Baghawi records (4:43, 17:4, 18:10, 33:9) all terminate abruptly. Independently accessible digital tafsir pages from KSU show additional text after each affected source cutoff. This strongly favors **probable upstream digital truncation**, though we have not identified the responsible software operation or verified precise continuation against a matching printed edition.

- [Four digital-continuation evidence cases](../../corpus/reviews/q03-baghawy-four-digital-continuations.json)
- [Five-source text-length distribution](../../corpus/reviews/q03-baghawy-length-ceiling.json)
- [Reproducible read-only length audit](../../corpus/audit_tafsir_length_distribution.py)
- [Metadata-only cutoff/witness alignment](../../corpus/audit_baghawy_cutoff.py)
- [Edition review procedure](../../corpus/reviews/q03-baghawy-edition-verification-runbook.md)

A separately indexed fourth Dar Taybah edition is dated 1417 H (1997), whereas the Waqfeya scan of the earlier edition is 1409 H (1989); never conflate print edition or page numbers. Printed pages, edition identity and permissions **remain unverified**. Original tafsir strings have not been changed.

The corpus-checks GitHub Actions [run 39302590191](https://github.com/AIMubin/Mubin/actions/runs/39302590191) completed successfully: **37/37 tests**. One previously failing synthetic Quran test fixture was corrected to provide the real basmala baseline rather than weakening first-verse validation. This CI result is for test code and synthetic fixtures, not an edition-level scholarly approval.

## Q0.3 print-scanned edition evidence gate (prepared, not closed)

The Waqfeya listing independently identifies the 1409 H / 1989 Dar Taybah eight-volume printed edition. Precise source PDF locators for volumes 2 (4:43), 5 (17:4, 18:10), and 6 (33:9) are now recorded in [q03-baghawy-scan-page-locators.json](../../corpus/reviews/q03-baghawy-scan-page-locators.json). Remote PDF download was unavailable during this review; no printed-page images were examined. The electronic Islamweb reader gives provisional site-pagination leads for 4:43 (volume 2/site page 220) and 17:4 (volume 5/site page 67), but their equivalence to the 1409 H printed pages is unverified.

The [local PDF evidence capture utility](../../corpus/attest_tafsir_print_pdf.py) renders selected PDF pages and records immutable-source and page-image SHA-256, with explicit fail-closed acceptance fields. See [edition runbook](../../corpus/reviews/q03-baghawy-edition-verification-runbook.md). Scanned images and local witness transcriptions remain outside git, under ignored corpus-data.

GitHub Actions [run 39307310854](https://github.com/AIMubin/Mubin/actions/runs/39307310854) passed **39/39 synthetic and structural tests**, including the actual PyMuPDF page-rendering tests. This verifies tooling, **not** the printed-edition review.

## Q0.3 downstream read-path safety: suspected incomplete al-Baghawi

The original Tafsir Center and linked SQLite files remain **unchanged**. However, **4:43, 17:4, 18:10, 33:9**, and any new al-Baghawi entry reaching the suspicious 32,767-character ceiling, are **withheld by default** from tafsir read responses. Ordinary `get_ayah()` sets `displayable=false`, `text=null` and `display_text=null` and identifies `display_status=WITHHELD_PENDING_EDITORIAL_VERIFICATION`. This is not a statement that no interpretation exists in the printed work; it means the current imported entry is suspected incomplete. Every other tafsir is handled independently.

For **authorized local diagnosis only**, an explicit `--allow-flagged-tafsir-text` CLI option (or the corresponding `allow_flagged_tafsir_text=True` internal parameter) permits examination of the original raw text while retaining `DIAGNOSTIC_UNVERIFIED_SOURCE_TEXT` and `scholarly_verification=false`. **Do not expose this override to a public consumer interface.** This flag is not an approved editorial restoration and does not remove copyright restrictions.

The private scanned-page handoff was ZIP-integrity and PNG-SHA verified (8 evidentiary + 9 edition identity images) and visually inspected by an AI assistant; [evidence ledger](../../corpus/reviews/q03-baghawy-assistant-visual-review.json). Vol. 2 copyright page identifies first edition **1409 H / 1989 CE**. The printed folios shown in the selected images are **228–229**, **76–77**, **154–155**, **330–331** for the four cases. The original PDF files themselves were **not** inside the handoff, and page rendering was 120 dpi. In 18:10 the image reads **أتى** where an OCR output read أنى; the 300dpi letter-form and cross-edition alignment question around ثلثمائة/ثلاثمائة remains open.

**Scholarly human review, precise edition-to-source identification for all three volumes, copyright clearance and editorial override approval remain open.** The system version remains `0.1.0-alpha`; these safety changes do not advance the Quran Engine milestone from `Q0.3`.

GitHub Actions [run 39395967179](https://github.com/AIMubin/Mubin/actions/runs/39395967179) passed **41/41 corpus tests on Ubuntu and 41/41 on Windows**, including the four-case suppression and local diagnostic override tests.

## Current policy update — 2026-10-20

The earlier notes above document stages of the evidence campaign, not today's total review status. Four Baghawi printed continuations were visually checked on privately supplied images; the 18:10 high-resolution scan reads `ثلاثمائة` and `أتى`. The private corrected evidence v2 is hash-consistent (19/19), and the four suspect upstream fields remain held back by default. [High-resolution evidence report](../../corpus/reviews/q03-baghawy-18-10-highres-review.json).

[Q0.3 engineering exit conditions](Q0.3-ENGINEERING-EXIT.md) are **now action-specific**: internal technical closure requires reproducible real-data checks and green CI, not a scholarly committee. Source text publication, restoration from a printed edition, authoritative interpretive claims and reproduction rights retain their independent gates. `VERSION.yaml` remains unchanged until technical criteria are measured and recorded.

## Source citations on Tafsir retrieval (2026-10-20)

Every returned tafsir row now includes `source_citation` with the dataset key, a work label, the exact sura:ayah locator, SHA-256 of its imported text field, and explicit `NOT_YET_VERIFIED` edition and `UNKNOWN_UNLESS_SEPARATELY_ESTABLISHED` rights labels. The citation remains visible even when the source's text is quarantined (e.g., the four Baghawi suspected cutoff records), without changing the suppression behavior or mutating the original database. The label identifies the imported Tafsir Center source key, **not** an independently verified printed edition.

These citations aid reproducible use and research; they do not automatically authorize reproducing protected editorial content. See [source-use policy](../../docs/SOURCE_ATTRIBUTION_POLICY.md). The Q0.3 internal engineering qualification scope remains unchanged.
