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
