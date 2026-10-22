# Usul definition metadata contract — research-only implementation

**Internal component:** `usul-concept-definitions/0.1.1` in PR #81.
**System version:** `0.1.0-alpha`. This is **not** a new qualified Usul U0.2 engine and does not replace the parallel historical PR #67 naming.

## Three **separate**, independently versioned representations

1. `source_observations`: a source-scoped **literal query ID** and concept ID rooted in the frozen U0.2.3 receipt. `observation_status=LEXICAL_ONLY`; **no source strings or lines**.
2. `definition_candidates`: opaque SHA-256 of a **privately maintained candidate text**, a claimed (not established) attribution ID, and an observation ID. `review_status=UNASSESSED`; **no definition prose** in public metadata.
3. `interpretation_candidates`: its own independently versioned opaque text digest and referenced definition candidate IDs. `review_status=UNASSESSED`. The entry is neither a verified scholarly gloss nor an executable rule.

These records are separate collections rather than a single mutable definition object. They cannot overwrite each other. `definition_comparisons` captures the purely administrative label `MULTIPLE_DEFINITIONS`: two candidate digests do **not** demonstrate actual doctrinal disagreement.

## Independent source registry (public metadata only)

Each `sources` entry requires an opaque `work_id`, `claimed_author_id`, `edition_id`, `locator_id`, `witness_id`, frozen `section_sha256`, and its own semantic version. The only accepted rights statuses for this pilot are `NOT_CLEARED` and `RESTRICTED`. Attribution and edition statuses must stay `UNASSESSED`.

**Important:** `claimed_author_id` is an unverified **research claim**, not authenticated authorship. A matching author ID across source/definition records is a structural cross-reference only. The registry does not verify who composed a specific definition; it does not link to a licensed full edition and does not allow quotation.

The current Waraqat/W1 adapter intentionally accepts **one** W1 registry entry, **three** known concept IDs and their literal-query associations, all tied to the public U0.2.3 operator-attested receipt. It does **not** generalize author authentication to new editions, W2, al-Risala, different books, or unrelated sources.

## Immutable reference and append-only contract

`build_definitions(receipt, trusted_receipt_sha256, manifest, previous_manifest=None, trusted_previous_sha256=None)` verifies:

- An **independently supplied** full SHA-256 of the pre-existing U0.2.3 receipt, recalculated canonically from all its fields except `acceptance_receipt_sha256`.
- Six-source-pin acceptance outcome, deterministic local replay claims, W1/W2 tamper rejection, and false scholarly/semantic/rights/fatwa flags.
- Complete coverage of the **three existing receipt concept IDs** and exact `query_id` association, retaining the pinned W1 section hash.
- Strict allowlist of keys, ASCII identifier grammar, bounded collections, semantic versions, digest-only representations and explicit `UNASSESSED` or `LEXICAL_ONLY` labels.
- Referenced concept/observation/author IDs exist in the expected source scope; unauthorized statuses, invented definitions, false attributions, pasted private text or local paths are rejected.
- When an update is proposed, an externally trusted predecessor manifest digest **and the complete predecessor manifest** must be supplied. Every existing entry must remain byte-for-byte identical at the normalized JSON-value level. New versions require **new IDs** and cannot rewrite or delete old entries. A prior digest without the prior manifest does not prove append-only history.

Entries are sorted by their immutable ID before hashing, using existing `engines.usul.concept_rule_catalog.canonical` (sorted JSON keys, compact separators, UTF-8, no NaN). Successful output is a **metadata-only summary**, never input text or a scholarly verdict.

**Limit:** this first schema forbids reattributing or replacing the one pinned W1 source entry. Genuine historical correction, W2 coverage, version migrations and authenticated scholarly statements need new, explicitly reviewed schema versions—not silent in-place changes.

## Privacy-hardening: keyed commitments (0.1.1)

**Security issue closed before using real short definition texts:** a raw
SHA-256 of a short Arabic phrase can be recovered by trying a dictionary of
plausible phrases. A public hash is not encryption. The `0.1.1` draft schema
therefore requires each definition and interpretation candidate to declare
`commitment_scheme`, `commitment_key_id`, and its own
`definition_commitment_sha256` / `interpretation_commitment_sha256` field.

- `SYNTHETIC_SHA256_TEST_VECTOR`: **synthetic test vectors only**, with
  `commitment_key_id: null`. **Never** use this for real text from a
  restricted source.
- `HMAC_SHA256_PRIVATE`: for private real candidate texts, with an opaque
  public **key identifier** (not secret key bytes). The 64-character value
  is an HMAC-SHA256 commitment generated with a secret key stored **off-repo**.
  The schema validates commitment shape, not whether any text is authentic.

The helper `private_text_commitment.py` calculates HMAC from a local file,
with a 32-byte-or-longer key provided as **hex in an environment variable**.
It emits only the digest and scheme; it does not display paths, input content
or key material. Do not commit, paste, log, send, or upload the key, and do
not publish private excerpts or local source files. Protect the key with
appropriate local controls and backup; lost keys prevent independent
recomputation. Public CI runs **only synthetic test vectors**.

A local test command with a **synthetic** example file:

```powershell
# Use locally generated, securely stored 32+ byte secret key; never commit it.
# Set environment variable MUBIN_PRIVATE_HMAC_KEY_HEX securely in the local session.
python -m engines.usul.private_text_commitment --text-file "C:\PRIVATE\synthetic-test-only.txt"
```

Treat the example path as illustrative, not an existing file. The real source
text and key remain private. Neither HMAC verification nor a matching key ID
certifies scholarly attribution, edition authenticity, intellectual property
rights, exact quotation scope, or semantic correctness. Compare candidate
commitments only for exact local byte identity, not to infer doctrinal disputes.

The schema bump is a **breaking draft contract change** from 0.1.0; any
off-branch local manifest must be reviewed and migrated, never silently
accepted as a valid 0.1.1 contract. No public real-text digest is converted
to HMAC without re-reading the original private source and computing a fresh
keyed commitment locally.

## Synthetic demonstration

```bash
python -m engines.usul.concept_definitions \
  --basis-receipt corpus/reviews/u02-waraqat-private-source-acceptance-PASS.json \
  --trusted-basis-sha256 00f0d1c71f55dc226cd6b840decfcdada152a40746a5cdc39b1e4f019c6bf7df \
  --manifest engines/usul/examples/u02-concept-definitions-synthetic.json \
  --out /tmp/mubin-u02-definitions-result.json
python -m unittest discover -s engines/usul/tests -v
```

The fixture contains **three accepted W1 lexical observations** and two **synthetic test-vector definition commitments** for the `concept:amr-term` concept. Digests `synthetic-A`, `synthetic-B` and `synthetic-interpretation` are produced from invented testing strings, **not** actual wordings from al-Waraqat and **not** statements attributable to its author. They must never be labelled as the book's competing definitions.

CLI exit `0`: `U02_DEFINITION_METADATA_CANDIDATES_PASS` (schema and provenance only). Exit `2`: `U02_DEFINITION_METADATA_REJECTED` with a stable reason code. Neither exit code authenticates scholarship.

## Next scientific preparation (not done by this PR)

- Locally acquire/licence the exact edition and establish work/author/edition/locator attribution with independent evidence and reviewer IDs.
- Record private source excerpts and definition transcriptions in a **separately controlled** source store, not a new field in public JSON. Avoid including text in public PR diffs or CI artifacts.
- For each proposed definition: distinguish an exact author quote, a later commentator's gloss, and a model-generated research paraphrase. Keep all three unapproved until reviewed.
- Collect negative evidence and counterexamples. An unresolved tension between candidate formulations is not automatically an attested school or juristic dispute.
- Define a separate scholarly-acceptance workflow for textual variants in the 16 W1/W2 chapters, with human review. Do not change P0, U0.1 executor, Quran Q0.3 or Hadith H3.9.2.

**Always false:** `scholarly_verified`, `redistribution_approved`, `source_support_attested`, `semantic_equivalence_verified`, `juristic_inference_allowed`, `rule_execution_performed`, `public_fatwa_authorized`.
