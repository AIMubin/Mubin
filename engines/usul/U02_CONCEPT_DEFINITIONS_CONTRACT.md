# U0.2.x — Structured Usul Concept Definitions & Scholarly Review Preparation

## Initial contract (Stage: definition-model preparation, research-only)

1. **Concept definition data model**: separate (a) source text, (b) scholarly
   definition, (c) proposed interpretation — three independently versioned
   fields per concept entry; no field may silently overwrite another.
2. **Independent source registry**: every concept binds to work + author +
   edition + locator records with explicit usage-rights status; registry
   entries are append-only.
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

## Acceptance (engineering)

- Data-model module + JSON-schema-style validation + negative tests
- Deterministic manifest with per-entry digests (same canonical rules as
  the Stage-08 graph digest)
- Metadata-only public outputs; private witness text stays local
