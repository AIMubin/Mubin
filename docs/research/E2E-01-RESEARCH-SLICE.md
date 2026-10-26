# Mubin E2E-01.1 — First bounded cross-engine research demonstration

**System release:** `0.1.0-alpha`. Engineering integration only, **not** a
scholarly or legal interpretation.

## User-visible capability delivered

Given **exactly** the Arabic research question
`دلالة صيغة الأمر والقرائن المؤثرة فيه` and a verse locator such as
`2:1`, the new `engines/e2e/research_slice.py` composes **existing**
components in one JSON response:

- I0.1a `operator_lookup` (internally calls R0.1c `unified_lookup`) returns
  genuine metadata retrieval from corpus+tafsir SQLite source families, and
  checks the HMAC evidence head plus the signed two-axis R0.1d
  qualification ledger before and after each lookup.
- U0.1 `amr_default.run_pilot` supplies the existing attributed
  *al-Waraqat*, chapter `الأمر`, metadata and the **actual four**
  synthetic scenario outcomes (not merely their names).
- The result exposes source review states, gaps, unknowns, and locked
  authority flags. Both the evidence and qualification head are checked
  once more after the Usul pilot to prevent a mixed-epoch result.

**Scientific honesty:** retrieving a verse coordinate is NOT proof that
the verse illustrates an imperative, constitutes evidence for al-Juwayni's
rule, or supports a valid legal conclusion. `2:1` is explicitly a
synthetic demonstration lookup, not a claimed imperative example.
`research_linkage.status=UNASSESSED`,
`verse_is_evidence_for_usul_rule=false`, and
`synthetic_scenarios_are_real_case_evidence=false`.
There is no hadith search and no semantic/fiqh inference in E2E-01.1.
Other questions are refused rather than answered with the unrelated,
hard-coded pilot.

## Operator-only CLI, default no text

```sh
python -m engines.e2e \
  --ref 2:1 \
  --question "دلالة صيغة الأمر والقرائن المؤثرة فيه" \
  --vault "$VAULT" --corpus-db "$CORPUS_DB" \
  --sidecar-db "$SIDECAR_DB" --registry "$EVIDENCE_REGISTRY" \
  --anchor-dir "$EVIDENCE_ANCHOR_DIR" --evidence-key "$EVIDENCE_KEY" \
  --qualification-ledger "$QUALIFICATION_LEDGER" \
  --qualification-anchor-dir "$QUALIFICATION_ANCHOR_DIR" \
  --qualification-key "$QUALIFICATION_KEY"
```

Paths above are operator-local environment variables. Do not commit vault,
Quran or Tafsir text, production HMAC keys, signed qualification decisions,
or private source excerpts. The command emits a single JSON document or a
`REFUSED` JSON with non-leaking reason code and nonzero exit. Windows legacy
console output uses safe escaped Unicode.

## Independent acceptance tests

```sh
python -m pip install -r core/requirements-test.txt
python -m unittest core.tests.test_e2e_research_slice -v
```

The synthetic fixture creates actual corpus + sidecar SQLite stores,
instantiates actual `PrivateResearchAdapters`, initializes a real signed
R0.1d ledger, executes the real operator retrieval and real al-Waraqat
pilot, and tests deterministic source-scoped output, absence of private text,
unrelated-question refusal, signed rejection state, corrupted ledger
refusal, evidence-head mutation and safe CLI failure. The R0.1a original
vault verifier is mocked **only for the synthetic fixture**, not the
application's retrieval or qualification logic. Ubuntu/Windows CI runs
these tests offline and includes no real private source content.

## Next scientific steps — no new infrastructure

**E2E-01.2:** Select one independently sourced real imperative verse
candidate, bind its *specific* verse/tafsir witness and relevant Usul
rule citation with explicit traceable relationship evidence, and present
positive/blocked/undetermined outcomes without assuming absence of
`qarā'in`. This must be real-science progress, not a new abstract
governance schema.

**E2E-01.3:** Reuse the existing loopback operator workspace to display
the integrated result; do not create a second front-end.

**E2E-01.4:** Independently evaluate relation quality, attribution,
and false positive/negative links; CI is not a scholarly accuracy score.

**H-Search-01** starts as a parallel metadata-first Hadith retrieval lane,
not a blocker to the first Usul/Quran integration. The 158 frozen H3.9.2
human adjudications remain untouched.

All source authentication, scholarly approval, rights, publication,
juristic inference and public fatwa gates remain disabled.
