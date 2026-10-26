# E2E-01.4b.1 — Twenty-four Quran-to-Usul research *candidate* cases

**Project version:** `0.1.0-alpha`. **No human-review gate.**
This milestone produces the **first citation-addressed casebook** for
scientific study of al-Juwayni's `باب الأمر`, NOT gold-standard scholarly
annotations, a verified Arabic-text corpus or a fatwa engine.

## What was verified, and what was not

Eight public online Quran verse pages were inspected for candidate words
whose form could motivate researching `pilot:rule-amr-default`.
The existing `engines.usul.pilots.amr_default` model cites al-Juwayni's
online `الورقات` under `الأمر`; its only source hash covers a **short
excerpt**, not the full text, a publisher's printed edition or rights.

| Verse | Operator-observed candidate word | Public Quran witness |
|---|---|---|
| 2:43 | أَقِيمُوا | https://quran.com/2/43 |
| 2:110 | أَقِيمُوا | https://quran.com/2/110 |
| 4:59 | أَطِيعُوا | https://quran.com/4/59 |
| 5:6 | فَاغْسِلُوا | https://quran.com/5/6 |
| 17:23 | وَقُل | https://quran.com/17/23 |
| 24:56 | أَقِيمُوا | https://quran.com/24/56 |
| 62:9 | فَاسْعَوْا | https://quran.com/62/9 |
| 2:282 | فَاكْتُبُوهُ | https://quran.com/2/282 |

**These are observations from accessible digital readings**, not a
machine-verified exact UTF-8 match against the operator's signed Quran
vault. We have not independently checked any Tafsir text against the
operator's private `sidecar.db`; `tafsir_witnesses=[]`,
`external_verse_digest=null` and `tafsir_connection_attested=false`
are deliberate. Quran.com's public reading page does **not** inherit
rights, edition or scholarly guarantees from Mubin's HMAC ledger.

## The 24 cases and their deliberately limited labels

Each of the eight verse groups creates exactly three variants, always
together in one split:

1. **POSITIVE_CANDIDATE (8):** the reported word is associated with the
   verse citation, but the appropriate result is
   `CANDIDATE_UNVERIFIED`, **NOT** scholarly `SUPPORTED`. Proving
   a command form and whether any contextual `qarīnah` changes its
   interpretation remain separate, uncompleted research tasks.
2. **CONSTRUCTED_NEGATIVE (8):** the word is *deliberately attributed to
   the wrong verse reference*. The contradiction is between the claimed
   word reference and the linked witness, so the expected outcome is
   `REFUTED_REFERENCE_CONFLICT`. Every claimed wrong verse locator is a
   **valid Qur'an coordinate** drawn from the fixed eight-verse cohort;
   malformed/null/out-of-range asserted references or silent mutations of
   the preselected wrong-reference pairing fail the casebook validator,
   rather than earning a false-positive refutation. This is a **provenance counterexample**,
   NOT an independently established negative juristic interpretation.
3. **UNRESOLVED_CONTEXT (8):** no word is asserted, no diverting
   indicators have been independently examined, and the expected result
   is `UNDETERMINED`.

Neither `POSITIVE_CANDIDATE` nor an internally generated expected process
outcome is an independent scientific ground-truth label.
**All** `scientific_gold_label=null`. A zero-error structural score only
shows a well-formed casebook, NOT that an LLM has correctly understood
the Quran or inferred al-Juwayni's rule.

## Development vs holdout

- Development (12 cases, four complete verse groups): **2:43, 2:110,
  4:59, 5:6**.
- Holdout (12 cases, four complete verse groups): **17:23, 24:56,
  62:9, 2:282**.
- A verse's P/N/U variants never appear in different splits.
- **Not source-family-disjoint**: the same public Quran reading site and
  one online al-Waraqat witness underpin all eight verse groups.
  There is no claim of independent-source generalization.
- The holdout is **publicly visible in Git**. It can be frozen at a commit
  and excluded from tuning by protocol, but it is NOT a hidden/blind
  dataset. Model contamination and overfitting remain real limitations.
- The casebook's raw UTF-8 SHA256 appears in the local scorecard. Preserve
  the **exact committed dataset SHA** when comparing future runs.

## Reproducibility

```sh
python -m unittest core.tests.test_e2e_scientific_benchmark -v
python -m engines.e2e.scientific_benchmark --split development
python -m engines.e2e.scientific_benchmark --split holdout
```

The Python module validates all 24 cases, disjoint-verse partition,
realistic verse locator forms, strict existing rule identity, declared
nonverification of text/Tafsir, and locked authority flags. Its simple
process baseline detects fabricated source-reference conflicts and
**abstains from scientific inference**. It does not call an LLM, evaluate
understanding, query real private Quran text, read tafsir, or verify
juristic soundness; those are subsequent independent AI-only scientific
experiments. The old E2E-01.4a metadata evaluator and its 5+6 corpus/sidecar
source behavior stay untouched.

## Next capability — E2E-01.4b.2 (no human reviewer requirement)

For a genuinely evidence-verified case, an independent agent should read
an allowed, fixed Quran witness and its own edition/encoding reference,
pin exact normalized-token and source digests, examine the relevant
tafsir witness and its citation, and emit a **bounded claim** with
explicitly recorded qarīnah scope. A second agent should attempt
reproduction/refutation without access to the first agent's reasoning
or labels. Both may return `UNDETERMINED`; agreement is NOT proof.
Do not score `SUPPORTED` until the actual text witness and
reasoning requirements have been met. There is **no mandatory human
review** in this research pipeline.

All `source_authenticated`, `scholarly_verified`,
`rights_verified`, `publication_allowed`, `p1_admitted`,
`juristic_inference_allowed`, and `public_fatwa_authorized` remain
disabled. Rights and public fatwa authority are separate concerns and
are not granted by automated evaluation.
