# Q0.1e-b — Direct, exact-byte, **unattested** Tanzil-domain localhost reader

**Engineering pilot only.** Built on Mubin main `3d0f7a22028ad6b9844f66881ec243c79f2f65f4`; relies on merged Q0.1e-a fixed-host bounded HTTPS GET probe, Q0.1d format parser, Q0.1c localhost HTTP reader, and Q0.1f six-title Tafsir bibliography. This is *not* an authenticated Quran release, a certified edition or a new inference/tafsir engine. System stays `0.1.0-alpha`.

## Operator workflow

```bash
python -m engines.quran.q01e --port 8765
```

The command fetches the specified HTTPS Tanzil preset **once**, holds response bytes in memory, and checks an **exact previously observed SHA-256** (`7f30c647331a61100ebf24a80507dc0fcdd9f2df97f1312b5b2dfcb982a7f326`), structural 114 chapters/6,236 verses, preserved source notice, LF/UTF-8 and numbered original lines. There is **no automatic fallback** to an altered response, another host or an unpinned mirror. If unavailable or different, the reader exits without opening its HTTP socket; the CLI does not print the response text or raw transport exception.

On success, open **http://127.0.0.1:8765/** locally. It binds only 127.0.0.1, refuses nonlocal Host/Origin and writes no source file. The Q0.1c reader reconstructs the Q0.1e SourceIndex **from the same exact pinned original bytes** *before binding*, then compares the records and metadata. A forged SourceIndex with a mislabeled `source_kind`, invented rights or changed verse cannot authorize the server. The display text is the unchanged string parsed from source bytes; folded search affects matching only.

For the Tanzil-domain candidate, `GET /api/status` identifies `source_kind=tanzil_domain_unattested_export` with `display_provenance=observed_tanzil_domain_unattested`. The existing Q0.1f `GET /api/tafsir-catalog?ref=2%3A1` is eligible to return **metadata only** for six titles and optional *user-click* KSU links. The endpoint is not available to synthetic or unqualified sources. It does not import Tafsir text or promise the identity of a printed edition. The browser distinguishes a pinned domain observation from an unauthenticated GitHub mirror; both are **unverified**.

## Trust separation

- **Identity of bytes:** strict SHA-256 equality with an earlier HTTPS-domain observation; this does not independently attest publisher custody or a scholarly approved Mushaf.
- **Content topology:** valid numbered records and identical text for 6,236 verses compared with the pinned GitHub mirror in Q0.1e-a; differences in raw full-file bytes remain, and no automatic adoption of a changed response is allowed.
- **External tafsir navigation:** six unreviewed bibliographic candidates; `edition=null`, `text_ingested=false`, `rights_verified=false`, `p1_eligible=false`. KSU is opened on deliberate click and may record the user's external visit.
- **AI interpretation and rulings:** disabled. The reader never turns a bibliographic match into P1 or Fiqh authority.

Status flags remain **false**: `source_authenticated`, `official_tanzil_bytes_independently_verified`, `scholarly_verified`, `rights_verified`, `redistribution_approved`, `juristic_inference_allowed`, `public_fatwa_authorized`, `eligible_for_religious_ruling`.

## Verification

Cross-platform unit/integration tests exercise a **full-sized artificial 6,236-row fixture** instead of fetching or storing Quranic text in Git. Cases include byte drift, missing copyright, forged SourceIndex/rights metadata, invalid Host and references, six-source bibliography and response security headers. Dedicated Ubuntu CI runs the full core test suite. An additional advisory-only CI step may attempt the real HTTPS source, validate pinned bytes in memory, start localhost HTTP, and query both Quran status and Tafsir metadata. **The advisory step is nonblocking:** its result must be checked explicitly; workflow-level green is not proof of live domain success or canonical source authority.

Q0.1e-b does not change Q0.3, H3.9.2 holdouts, Usul/Fiqh gates or any private TafsirCenter/SQLite/corpus imports. Rights and release decisions remain separate.
