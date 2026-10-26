# E2E-01.2 — Operator-observed semantic relation candidate (research only)

## What this stage *actually* accomplishes

E2E-01.1 already retrieves a verse coordinate across the pinned Quran/tafsir
metadata sources with an authenticated evidence head and signed R0.1d
qualification state. E2E-01.2 lets the operator *record a candidate* that
a particular observed Arabic imperative token may be relevant to the
existing al-Waraqat `pilot:rule-amr-default`.

The optional `linkage_observation` argument to
`engines.e2e.research_slice.research_slice` verifies that the candidate
reference equals the queried verse, its declared `evidence_head_sha256`
equals the **actually attested** retrieval head, and at least one pinned
source has that coordinate present. It then returns the record in the same
research JSON, without opening protected text or creating a new backend.
The previously published E2E-01.1 response is unchanged when no
observation is given.

**What is NOT verified:** the code does not independently fetch or hash
the purported Arabic verse witness, establish that `أَقِيمُوا` is really
present at the reported token position, establish the morphology or
semantic relevance of the verse to al-Juwayni's modeled rule, or find
or refute any diverting `qarīnah` in a real source. `verse_text_sha256`
is a syntactically valid *operator-supplied claim*, not an independently
recomputed digest. The source/word/position/notes are operator observations.
Never label such an E2E result as a proved Quran-to-Usul inference.

The only accepted `rule_id` and expression are the existing
`pilot:rule-amr-default` and its matching `example_bundle` rule;
arbitrary caller-supplied rules are refused, not silently given the authority
of al-Waraqat. The relationship is **PROPOSED_NOT_CERTIFIED** regardless
of input and every scholarly/rights/publication/juristic/fatwa flag remains
false.

## Indicator scope

`assess_indicator_scope` accepts exactly three bounded, nonoverlapping
lists from the **operator**: `sources_examined`, `indicators_found`,
`sources_not_examined`. It derives the case from the lists; the caller
cannot claim `PRESENT` while reporting zero findings, or invent a positive
finding without claiming any examined source.

- `PRESENT`: one or more alleged positive observations and at least one
  declared examined source; not independent detection.
- `NOT_OBSERVED_IN_SCOPE`: some declared examined sources with no positive
  observation. NEVER a proof of universal absence.
- `NOT_EXAMINED`: zero examined sources and no reported findings.

All three retain `absence_not_confirmed=true`, since this code does not
certify absence. A legitimate positive observation is **not** equivalent to
a verified scholarly diverting indicator.

## Evaluation

```sh
python -m pip install -r core/requirements-test.txt
python -m unittest core.tests.test_e2e_research_slice core.tests.test_semantic_linkage -v
```

The added tests cover syntactically invalid verse/digests, a wrong rule,
inconsistent indicator records and scope overlap, immutable false gates,
and the **actual signed E2E retrieval** against a synthetic SQLite fixture,
including successful binding for synthetic `2:43`, a changed evidence head,
a mismatched coordinate and a missing coordinate. E2E-01.1 and
E2E-01.2 remain open to independent scientific evaluation. No restricted
Quran, Tafsir or Hadith body text, signing secret, or real operator vault
enters CI.

## The real-source check that must precede scientific promotion

For each proposed verse-to-rule connection, an authorized operator must
re-read the actual SHA-pinned witness, check exact token boundaries,
record the passage reference, compare the relevant commentary and check
which sources were *actually* examined for diverting indicators. A separately
reproducible source-observation receipt (without republishing protected text)
is required before claiming byte correspondence.

**Do not jump from this bounded recorder straight to a verified
`Verse → Tafsir → Usul → outcome` scientific conclusion.** That step
requires independently evidenced text association and a negative/positive/
undetermined case evaluation. The following E2E-01.3 work may render
`PROPOSED_NOT_CERTIFIED` in the existing operator workspace, but it
must not visually represent it as a verified research conclusion.

System version remains `0.1.0-alpha`, separate from subsystem milestones.
