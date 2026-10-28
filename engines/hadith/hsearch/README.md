# H-Search-01 — source-bound narration-cue search (engineering slice)

## What this does

Local-only research uses the already pinned T0.2 original Tafsir passages
to identify **lexical narration-cue windows**, then searches four explicitly
allowlisted, pinned non-holdout OpenITI source files for matching
**witness-candidate blocks**. A source block is not an independent hadith.
A cue window is not a verified narration. A shared sequence of ten words
is a `CANDIDATE_MATCH`, **not** proof of identical hadith, route, isnad,
hadith grade, or scholar judgment.

- Quran reference → pinned Quran SourceIndex → Tafsir T0.3 →
  T0.2 original-byte-based passage → HadithMention cue →
  pinned source block candidate → conservative, nonauthoritative link.
- Only `non_holdout` items in `AUTHORIZED` from `sources.py` are
  accessed, and only after independent Git blob SHA verification.
- The H3.9.2 qualification benchmark/gold/holdout files are **not** the
  runtime search database. Do not alter frozen qualification manifests.
- No match among the four sources must not be described as proof no
  hadith exists in other books. If any source is unavailable, report
  `SOURCE_UNAVAILABLE` rather than `NO_MATCH`.
- Every matched witness is located to an exact bounded block; the
  **same-file but wrong-block** false positive is explicitly rejected.
- All critical-commentary cues remain
  `UNVERIFIED_CRITICAL_ATTRIBUTION`, with no automated rating.
- No raw text is returned through /api/research, only metadata. Do not
  expose the loopback server via network forwarding.

## Local setup

Place the exact four authorized non-holdout source files into a private
`source-cache` directory, using their existing H3.9.2 cache filenames.
The cache is verified on every run; cache symlinks are forbidden.
Source download is never activated by the HTTP path. Existing
H3.9.2 source-acquisition utilities may be used for the corresponding
non-holdout sources, subject to source terms and cached-byte checks.

Start the existing Quran reader with both --tafsir-db and --hadith-cache,
plus its required pinned Quran --manifest and --source arguments.
The hadith result appears on /research only after explicit opt-in.
Do not run protected book text as GitHub Actions fixtures.

## Test and scope status

- Initial operator run at 2:43 reported 61 Tafsir passages, 62 mention
  windows and 54,599 source blocks; its **original unvalidated logic**
  labeled all 62 links NO_MATCH. The cue detector, witness IDs, match
  boundary and status logic have since been corrected. **Rerun the
  actual private vault before publishing updated counts.**
- The frozen 2:185 case B metadata report identifies 13 shared characters
  between a Tafsir reference and Bayhaqi material. This alone
  **does not satisfy the 10-word automatic candidate-match contract**.
  No source-authenticated positive narration identity is established.
  See the accompanying case-B review assessment; original data remains
  intact for auditability.
- A realistic source-to-source positive needs exact authenticated
  Tafsir mention and independently pinned Hadith witness spans,
  preserved raw text digests and an auditable link. Synthetic positive
  tests prove engineering behavior only, not a live Islamic scholarly
  match. If no real positive is demonstrated, H-Search-01 scientific
  acceptance remains **OPEN**, even when CI passes.

Run synthetic tests:

    python -m unittest core.tests.test_hadith_hsearch01 -v

Mubin overall system version stays 0.1.0-alpha. Source authentication
here means only expected **digital file bytes** match pinned Git blobs,
not an authenticated print edition or established hadith authenticity.

## H-Search-01 raw-offset alignment

Source-bound matching now uses reversible Unicode-codepoint offsets, even
when Arabic harakat, alef shapes, ta marbuta/ha or whitespace differ.
For an eligible ten-whole-token overlap the link stores:

- tafsir_shared_raw_span and hadith_shared_raw_span: [start,end) in each
  independent original raw imported text, **not** normalized text.
- tafsir_shared_raw_sha256 and hadith_shared_raw_sha256: SHA-256 of
  each exact original literal phrase, which may have different bytes.
- folded_phrase_sha256 and folded_word_count: normalized fingerprint and
  ten-token count.
- Pinned tafsir source record ID, Hadith version and Git blob SHA, and
  witness ID/locator. No source text is returned.

A successful raw-offset round-trip is evidence of bounded **lexical
overlap**, not proof that the narrations are identical or that the
compiler endorsed the text. CANDIDATE_MATCH is preserved;
TEXTUALLY_SUPPORTED, grade, scholarly and rights gates are not promoted.
Even a ten-token overlap may be a shared Quran quotation.

Local-operator commands to generate metadata-only receipts from private
Q0.3 and Hadith sources (replace the private cache placeholder):

    python -m engines.hadith.hsearch.replay 2:43 --database corpus-data/linked/quran_tafsir.db --hadith-cache <PRIVATE_SOURCE_CACHE>
    python -m engines.hadith.hsearch.replay 2:185 --database corpus-data/linked/quran_tafsir.db --hadith-cache <PRIVATE_SOURCE_CACHE>

Run 1:7 separately if the operator's previously discovered ten-word
lead requires an independent check. The tool never logs private paths
or source passages, and refuses errors with a bounded code. Preserve
the redacted receipt in the controlled local evidence workspace.

Only report a real positive *lexical alignment* after checking both
independently pinned raw source versions, spans and SHA-256 digests.
It does not close the separate scholarly Hadith identity gate.

The corrected 2:43 operator baseline (61 Tafsir passages, seven
narration-cue windows, 54,599 source candidate blocks, seven NO_MATCH)
must be remeasured on this version. The 2:185 13-character lead alone
still fails the ten-word automatic match requirement.
