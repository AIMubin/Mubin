# E2E-01.4b.2 — First local witness-scoped AI/critic trial (2:43)

**Status:** experimental, source-scoped, **AI-only**, no human review requirement.
This is a scientific-evidence *trial contract*, not a claim that the first
independent LLM-versus-LLM trial has already been run.

## What we can cite now

The source-addressed case `AMR-01-P` concerns Quran **2:43** and the
candidate substring **أَقِيمُوا**. Publicly accessible independent
reference **locations** (not downloaded/byte-authenticated snapshots):

- Quran verse reading and Arabic Uthmani display:
  https://quran.com/2/43
- Quran.com Sa'di tafsir for 2:43:
  https://quran.com/ar/2%3A43/tafsirs/ar-tafseer-al-saddi
- Quran.com al-Tabari tafsir for 2:43:
  https://quran.com/ur/2%3A43/tafsirs/ar-tafsir-al-tabari
- An independent exposition of al-Waraqat's باب الأمر, naming
  **وَأَقِيمُوا الصَّلَاةَ [البقرة: 43]** as a worked example:
  https://www.alukah.net/alomar/1/29223/
- The Mubin pilot's online al-Waraqat excerpt:
  https://www.islamicbook.ws/asol/alwrqat.html
- A secondary al-Waraqat digital reading:
  https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/

The fact that an exposition uses 2:43 as an example makes this case a
**more meaningful candidate** than an arbitrary verse lookup. It does
**not** establish Quran edition custody, tafsir interpretation correctness,
absence of qarā'in, or a Mubin-certified obligation conclusion. A tafsir
host and an Usul commentary are not independent Quran textual witnesses.
Treat these as bibliographic leads, not as frozen byte-verified source files.

## New executable capability

`engines/e2e/witness_science.py` accepts three **operator-local** JSON
objects: a local witness packet, an evaluator AI report and an independent
critic AI report. No model provider, secret or protected Quran/Tafsir text
is committed. It never downloads sources or calls a model by itself.

Witness packet is a JSON object:

```json
{
  "case_id": "AMR-01-P",
  "reference": "2:43",
  "witnesses": [
    {"id": "v", "role": "verse", "url": "https://quran.com/2/43",
     "family": "quran-reading", "text": "OPERATOR_LOCAL_TEXT_NOT_GIT",
     "sha256": "64_lowercase_hex_from_exact_UTF8"},
    {"id": "t", "role": "tafsir", "url": "https://quran.com/ar/2%3A43/tafsirs/ar-tafseer-al-saddi",
     "family": "tafsir-digital", "text": "OPERATOR_LOCAL_TEXT_NOT_GIT",
     "sha256": "64_lowercase_hex_from_exact_UTF8"},
    {"id": "u", "role": "usul", "url": "https://www.islamicbook.ws/asol/alwrqat.html",
     "family": "usul-digital", "text": "OPERATOR_LOCAL_TEXT_NOT_GIT",
     "sha256": "64_lowercase_hex_from_exact_UTF8"}
  ]
}
```

The `text` placeholders above are NOT canonical Quran/Tafsir quotations.
Use only source text an operator is legally permitted to process. Hash must
be `sha256(text.encode('utf-8')).hexdigest()`. The verifier hashes the
**actual submitted UTF-8 bytes** and checks exact substring presence of
the candidate word, without changing Uthmani orthography or conflating a
substring check with Arabic morphology. The output never contains these
text bodies. Both hashes and source URLs in the packet remain *operator
claims*; passing local hash checks does **not** authenticate upstream custody.

Evaluator and critic each receive the **same packet**, in separate sessions,
without seeing each other's result. They output bounded JSON of this form:

```json
{
  "role": "evaluator",
  "model_id": "MODEL_A",
  "provider": "PROVIDER_A",
  "run_id": "RUN_A_UNIQUE",
  "packet_sha256": "SHA256_OF_CANONICAL_JSON_PACKET",
  "decision": "SUPPORTED",
  "evidence_ids": ["v", "t", "u"]
}
```

Critic has `role=critic` with a different provider, model and run ID.
Choose `SUPPORTED`, `REFUTED`, or `UNDETERMINED` as **model
hypotheses**, not official rulings. Models should examine the Quran
coordinate/token, tafsir argument and the al-Waraqat rule, explicitly test
whether any qarīnah was actually checked, and abstain otherwise. The
run contract checks unique declared model/provider/run IDs and citations,
but cannot independently prove distinct training data, model execution or
epistemic independence.

A generated trial is evaluated with:

```sh
python -m engines.e2e.witness_science \
  --case AMR-01-P \
  --packet /private/operator/2-43-witness.json \
  --evaluator /private/operator/evaluator.json \
  --critic /private/operator/critic.json
```

Only local source-hash consistency, matching citation IDs and distinct
model declarations are automatically validated. Results are one of
`UNDETERMINED`, `AI_DISAGREEMENT` or
`AI_AGREEMENT_UNCERTIFIED`. **Never** `SUPPORTED` as a system-verified
scientific claim. Missing witness types, a missing exact candidate
substring or repeating the same model forces abstention or refusal as
appropriate. Tampered text/digest or a hallucinatory citation is refused.

## Important acceptance criteria and honest omissions

- CI tests are purely synthetic: no sacred scripture has been invented,
  modified, stored, uploaded or represented as canonical in tests.
- The implementation does not use the connected private vault or a live
  model provider. **Real AI independent reports have not been executed**
  in this change. This code makes such a run reproducible and auditable,
  not retroactively performed.
- The public URLs above are leads verified from public browsing, but
  their text **has not been frozen and signed into the Mubin R0.1a vault**.
- No automatic qarinah absence is asserted. A model agreement on the
  same case is never a scientific accuracy score and cannot change
  `source_authenticated`, `scholarly_verified`,
  `publication_allowed`, `juristic_inference_allowed`,
  `public_fatwa_authorized` or `p1_admitted`.
- The next real execution step is to obtain a permitted pinned primary
  witness and two independently executed AI reports in an operator-local
  environment, re-score 2:43, then extend *only after that* to 24 cases.

No mandatory human review; no new governance or signing service.
