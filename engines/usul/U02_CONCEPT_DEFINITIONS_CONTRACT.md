# U0.2.x — Structured Usul Concept Definitions & Scholarly Review Preparation

## Initial contract (Stage: definition-model preparation, research-only)

1. **Concept definition data model**: separate (a) source text, (b) scholarly
   definition, (c) proposed interpretation — three independently versioned **metadata collections** (source observation,
   unassessed definition candidate, unassessed interpretation candidate).
   Private text is not an inline public field; no collection may overwrite another.
2. **Independent source registry**: every concept binds to work + author +
   edition + locator records with explicit usage-rights status; registry
   entries are append-only by externally pinned predecessor manifest; the
   source/author/edition identities are unverified attribution claims.
3. **Multiple competing definitions** per concept are first-class records;
   disagreement between witnesses is recorded as MULTIPLE_DEFINITIONS, not
   as a fixed scholarly dispute.
4. **Negative tests**: unattributed definitions, contradictory definitions,
   and misattributed definitions must be refused or marked UNASSESSED — never
   auto-promoted.
5. **Limited candidate set**: باب الأمر candidate definitions prepared for
   later scholarly review; original witnesses stay private/local.
6. **Separate scholarly acceptance plan**: software acceptance gates (this
   repo) remain independent from any scholarly sign-off process.

## Non-goals

No fiqh inference engine. No executable rule promotion from proposed
definitions. No public redistribution of witness text.

## Implementation on this branch

The [definition metadata validator](concept_definitions.py),
[negative regression suite](tests/test_concept_definitions.py),
[synthetic metadata fixture](examples/u02-concept-definitions-synthetic.json),
and [complete implementation/limitation guide](U02_CONCEPT_DEFINITIONS_IMPLEMENTATION.md)
implement the **bounded initial W1 adapter**. The fixture's two example
'definitions' are hashed synthetic markers, never quotations or confirmed
competing statements from the author. A successful result means only that
metadata contracts and the pinned U0.2.3 receipt agree.

## Acceptance (engineering)

- Data-model module + JSON-schema-style validation + negative tests
- Deterministic manifest with per-entry digests (same canonical rules as
  the Stage-08 graph digest)
- Metadata-only public outputs; private witness text stays local

## Private text commitments (draft schema 0.1.1)

Direct public SHA-256 fingerprints of short genuine source definitions are
**not acceptable**: adversaries can guess short texts and compare hashes.
The model now distinguishes `SYNTHETIC_SHA256_TEST_VECTOR` (invented CI
data, never private source text) from `HMAC_SHA256_PRIVATE` commitments
computed off-repository using a secret key. Each commitment includes only
an opaque `commitment_key_id` (no secret), a digest, and an `UNASSESSED`
status. Text, HMAC key and local paths must remain private. The public
validator cannot independently attest the truth of a private commitment.

See [privacy implementation and operator cautions](U02_CONCEPT_DEFINITIONS_IMPLEMENTATION.md)
and [local HMAC helper](private_text_commitment.py). This draft schema change
is intentionally non-backward-compatible and must not silently upgrade
prior 0.1.0 manifests.
