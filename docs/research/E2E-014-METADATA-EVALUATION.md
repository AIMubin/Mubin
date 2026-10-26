# E2E-01.4a — Eight-group metadata evaluation (engineering evidence only)

**Version:** Mubin `0.1.0-alpha`. This milestone is **not** a scholarly
certification and does not grant any new authority, rights or publication.

## Actual scope

Runs an offline, operator-local evaluation over one or more verse
coordinates with the **existing** E2E research slice, signed qualification
ledger and original read-only corpus/sidecar SQLite databases. No new
service, governance system, external connection or authoritative engine.

The eight checks are:

1. `coordinate_accuracy`: each returned `coordinate_present` is compared
   to **independently queried** SQLite row existence for that exact verse,
   using the correct family. **For every evaluated reference**, all eleven\n   distinct source identities and their correct adapter families must be\n   present in the response; a complete first reference cannot conceal\n   missing or duplicated sources for another reference. QuranEnc/quran uses `corpus_entries`; the
   TafsirCenter sidecar uses its five Tafsir tables plus
   `QuranTafseer`, which has distinct column names. A false coordinate
   can be **correct**: do not assume all eleven sources contain every ref.
2. `source_completeness`: checks all five manifest Corpus IDs, all six
   allowlisted Sidecar table names, independently observed physical tables,
   the union of all eleven source IDs, and no duplicate identities. The
   *unified* list is expected to contain both families.
3. `qualification_consistency`: validates the **signed** ledger and
   recomputes the existing source/evidence-head matching, sticky-denial
   states and stale-decision flags against the *qualified operator result*.
   This is policy consistency, **not** independent scholarly review.
4. `gap_completeness`: validates gap declarations against actual
   unreviewed scholarly/rights states, the unauthenticated edition and
   missing hadith search. Rejected sources are not automatically treated
   as unreviewed.
5. `abstention`: checks explicit undetermined clauses, an unapproved
   verse-to-Usul link, and an unpromoted synthetic pilot.
6. `authority_flags`: checks every required locked flag is **explicitly
   false**, not simply absent, and rights stay `legal_review_pending`.
7. `determinism`: compares a second complete research slice result using
   canonical JSON serialization under stable source and ledger inputs.
8. `source_provenance`: checks each declared adapter family by exact
   allowlisted source identity. `QuranTafseer` is a Sidecar table even
   though its name does not start with `tafsir_`.

All groups must contain passing checks for `all_passed=true`. There is no
`critical-only` shortcut. Broken signatures, inaccessible SQLite,
missing metadata or invalid evaluation scope fail closed.

## Repeatable test command (synthetic only)

```sh
python -m pip install -r core/requirements-test.txt
python -m unittest core.tests.test_e2e_evaluation -v
```

This CI fixture reuses E2E-01.1's synthetic SQLite and real HMAC signed
qualification ledger; only the original R0.1a **expensive vault verifier**
is mocked, not the source lookups or qualification policy. Tests require
real DB-negative coordinates, independent sidecar/corpus catalogs, signed
reject states, detection of a deliberately falsified row-presence indicator,
incomplete catalog and missing/duplicated rows on a second reference,\n   authority flag promotion and refusal for forged ledger,
as well as no private text/secret leakage. The corpus, Tafsir and keys used
in tests are **invented**. This does NOT reproduce the operator's real
vault report or constitute human review.

Operator-supplied prior `28/31` was not a verified test baseline in Git;
the old E2E evaluation branch had an undefined function, wrong function
call shapes, always-present assumption, misidentified `QuranTafseer`,
unqualified ledger comparison, vacuous/noncritical success shortcut, and
a synthetic fixture incompatible with real path and receipt verification.
The corrective implementation must be assessed by its actual CI results;
do not claim inherited passing checks for deleted or replaced code.

## Limits and next scientific evaluation

The report says **cannot_automate** for scholarly authenticity of verse or
tafsir interpretation, edition or custody, rights or redistribution,
juristic soundness, P1 admissibility and **truth of the semantic
verse-to-rule relationship**. Two green automated evaluators do not by themselves establish
scholarly authenticity. The next AI-only research stage uses a bounded,
source-linked casebook and independent AI evaluator/critic attempts to
verify Quran/Tafsir/al-Waraqat witnesses and test positive, incorrect
and unresolved relations. No human-review gate is required to progress
this research. If source witnesses are unavailable, unauthenticated or
inconclusive, classify the case `UNDETERMINED`; never promote model
consensus into certification. See [E2E-01.4b.1](E2E-014B1-AMR-CASEBOOK.md).
Scientific, source-authenticity, rights, public-use and fatwa authority
remain separate from engineering or AI research milestones.

All `source_authenticated`, `scholarly_verified`, `rights_verified`,
`publication_allowed`, `juristic_inference_allowed`,
`public_fatwa_authorized`, and `p1_admitted` remain false.
