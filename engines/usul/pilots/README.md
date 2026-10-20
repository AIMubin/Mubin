# U0.1 source-backed pilot 01 — al-Waraqat, chapter on commands

**Status:** `SOURCE_ATTRIBUTED_RESEARCH_PILOT`, not juristic verification, no system release impact.

## Why this witness

A short passage under **باب الأمر** of *الورقات في أصول الفقه* attributed to **Imam al-Haramayn al-Juwayni** describes the treatment of the imperative form absent a diverting context, while allowing evidence that changes the interpretive reading.

- Primary public digital witness: https://www.islamicbook.ws/asol/alwrqat.html — section **الأمر**.
- Separate digital comparator: https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/ — section **الأمر**.
- The scanned/printed edition, publishing history and possible textual variants **are not authenticated**. Source metadata describes a *digital witness*, not a verified critical edition.
- Only a **short 21-word quotation** from the primary digital witness is present in [amr_default.py](amr_default.py). Its SHA-256 is over those exact UTF-8 **excerpt bytes**, not over the entire HTML page, authorial work or printed edition. A network-independent test reproduces that excerpt checksum, **not** the historical correctness of the text.
- Attribution is not copyright permission to mirror digital sites, edition scans, annotations or protected publisher material. No book PDF or complete transcription is committed.

## Bounded formalization

The computational rule models this attributed position, not a universal principle accepted by every school:

```text
IF       explicit_command_form = true
AND      diverting_indicator = explicitly false
THEN     default_obligation_candidate = conditionally supported
ELSE IF  diverting_indicator = true: BLOCKED_BY_EXCEPTION
ELSE     UNDETERMINED
```

Inputs are **synthetic scenario assertions** and their evidence IDs refer to a clearly marked Mubin fixture. This is not machine reading of scripture, detecting qarā'in from natural language, inferring a real legal duty, making an authoritative fiqh choice or deciding whether an exception is really absent. In a real source, absence of observed evidence is not the same as evidence of absence; the simulator refuses to assume `false` when a flag is missing.

```bash
python -m pip install -r core/requirements-test.txt
python -m engines.usul.pilots.amr_default
python -m unittest discover -s engines/usul/tests -v
```

Expected scenarios: `CONDITIONALLY_SUPPORTED` for fully declared synthetic facts; `BLOCKED_BY_EXCEPTION` when a diverting indicator is explicitly present; `UNDETERMINED` when the indicator or command-form fact is missing.

The pilot builds a P0 bundle, uses existing strict semantic-binding and source-reference machinery, and outputs book title, section, author, excerpt hash, real witness URL and distinct synthetic-test citations. It never embeds the quotation into the result JSON or claims that real-world evidence has been externally reauthenticated by the offline CLI.

## Gates that stay false

`scholarly_verified=false`, `valid_juristic_ruling=false`, `public_fatwa_authorized=false`, `semantic_equivalence_verified=false`, `witness_externally_revalidated_by_cli=false`. No real legal rule outside this attributed research formalization has been proven sound or applicable. Methodology-sensitive disagreements are preserved; `qiyas` and `tarjih` are unsupported.

## Next measurable improvement

A future source-attestation subsystem can fetch a **licensed pinned witness or private byte-exact copy**, verify exact passage boundaries and source URL against a frozen independent checksum, and bind the witness in a signed provenance ledger. Such a check should upgrade only the **text correspondence** status. It cannot by itself upgrade semantic equivalence or grant publication rights. Avoid opening a general human-review queue just to run these engineering experiments.

## Stage 02 — Evidence-scoped qarinah checks

The new [scoped evidence assessment](../exception_evidence.py) and [four-scenario pilot](scoped_amr_pilot.py) make a critical three-way distinction:

| Assessment | Technical meaning | Pilot consequence |
| --- | --- | --- |
| `PRESENT` | A *synthetic test item* claims a discovered diverting indicator and cites a known P0 evidence ID | `BLOCKED_BY_EXCEPTION` |
| `ABSENT_IN_DECLARED_SCOPE` | Every **listed test-scope item** is marked inspected; a cited P0 evidence ID supports the *synthetic assessment record* | `CONDITIONALLY_SUPPORTED` **inside the simulation only** |
| `NOT_CHECKED` | No inspection has been performed | `UNDETERMINED` |

Even when every *declared* synthetic item has been inspected, this is **not** a proof that the declared set contains all relevant textual/contextual evidence. The code explicitly rejects `real_world` scope assertions and never sets `real_world_absence_verified=true`. P0 `verified` denotes a claim within the input bundle, not independent primary-source verification. Thus the absence claim remains a **bounded research assumption**, not a universal conclusion about `qarā'in`.

Strict mode does not accept direct `true`/`false` values for an exception atom; instead a schema-checked assessment must cite existing P0 evidence and identify a declared, inspected synthetic scope. Incomplete coverage, missing or unverified evidence, contradictory direct facts, duplicate assessments and unrecognized scope kinds are refused with a nonzero CLI exit.

```bash
python -m engines.usul.pilots.scoped_amr_pilot
python -m unittest discover -s engines/usul/tests -v
```

For machine callers, the P0 bridge also accepts an optional assessment JSON array and the flags `--exception-assessments /path/to/array.json --require-semantic-binding --require-evidence-exceptions`. The old `ALLOW_LEGACY_EXPLICIT_FACTS` mode remains for backward-compatible experiments and is **not** evidence-certified. The output preserves the work, section, edition caveat, evidence locator and SHA-256 without reproducing the source passage or granting publication permission.

**No implementation of legal qarīnah detection, semantic comprehension of a source, rule priority, qiyās, tarjīḥ or issuance of fatāwā is claimed.**
