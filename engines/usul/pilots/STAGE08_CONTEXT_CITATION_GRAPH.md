# U0.1 Stage 08 — Evidence Context & Citation Graph

**Status:** `ENGINEERING_IMPLEMENTED_SYNTHETIC_CI_PASS` after cross-platform tests. **Real local Stage08 source replay is pending**: Stage08 has not executed the private historical HTML bytes in CI or this assistant environment. Stages 04–07 retain their own already-recorded technical status.

## Why this graph exists

A text search occurrence is **not a justified legal rule**. The Stage08 graph connects **verifiable digital witness → pinned chapter → SHA-256 context window → exact original text occurrence → query/profile**. Separate **unassessed** rule/objection research pointers link to QUERY nodes, not to verified juristic conclusions. Context SHA-256 establishes the exact local source window, not its correctness, interpretation, or redistribution right.

Named digital witnesses for *الورقات في أصول الفقه*, Imam al-Haramayn al-Juwayni:

- W1: <https://www.islamicbook.ws/asol/alwrqat.html>, captured HTML SHA-256 `66ec33c1825acdf82b3720f89d89aac15aa6e993356c0d90b41e53fe9a2fa044`, accepted Bab al-Amr section SHA-256 `20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab`.
- W2: <https://www.islam.ms/ar/كتاب-ورقات-أصول-فقه-إسلامي-إمام-حرمين-عبد-الملك-الجويني/>, captured HTML SHA-256 `3c4de1baa99bad782b5fba066523ca9f12798525907edede93bd1046ef36f0fa`, private Bab al-Amr extracted section SHA-256 `db181b1d9466389d2b5aeaf50362dd57e716cc1e36d041948777e3fe0c9c9358`.

These are **two digital witnesses only**, not critical editions. The [Stage07 operator receipt](../../../corpus/reviews/u01-stage07-waraqat-arabic-retrieval.json) reported six queries across both witnesses with separate exact and diagnostic folded counts.

## Implemented code and meaning restrictions

[Generic graph builder](../evidence_context_graph.py) **recomputes the entire Stage07 retrieval result** from independently pinned private UTF-8 section files and exact query specifications, and refuses any mismatch (including an injected positive/folded hit). Before producing a node, it verifies the source section digest, original hit byte offsets, original span digest, and complete original-line SHA-256.

Node types:

- `SOURCE_WITNESS`: witness identity, URL and attributed bibliographic metadata.
- `PINNED_SECTION`: SHA-256, bounded byte/line counts and original coordinate basis.
- `HASHED_CONTEXT`: neighboring line context (default ±1 line, configurable 0..2), original source byte and line boundaries, **SHA-256 only**; no context text is output.
- `TEXT_OCCURRENCE`: original byte span, UTF-8 digest and source location, with `semantic_classification=NOT_EVALUATED`.
- `SEARCH_QUERY`: query identifier/digest, navigation purposes only.
- `RULE_RESEARCH_POINTER` and `OBJECTION_RESEARCH_POINTER`: explicitly declared, `review_status=UNASSESSED` and **no evidence of rule truth or objection presence**.

Edges are restricted to `WITNESS_HAS_PINNED_SECTION`, `SECTION_HAS_CONTEXT`, `CONTEXT_INCLUDES_OCCURRENCE`, `QUERY_SCOPED_TO_SECTION`, `QUERY_LOCATES_OCCURRENCE`, and `RESEARCH_NAVIGATION_ONLY`. In particular **there are no `SUPPORTS_RULE`, `CLEARS_QARINAH`, `PROVES_OBJECTION`, or `DERIVES_RULING` edges**. Every edge endpoint must be present.

A single original text span is represented by ONE occurrence node, even when multiple fold profiles locate it. Query-to-occurrence edges keep profile-specific distinctions: `EXACT_LITERAL_ONLY` versus `ORTHOGRAPHIC_CANDIDATE_ONLY`. This prevents confusing repeated profile counts with distinct source occurrences.

Stable node/edge IDs and `graph_sha256` are computed from canonical JSON (sorted keys; UTF-8; no timestamps/randomness). The final hash is computed over the payload **excluding itself**, to avoid circular attestation. Only metadata, hashes, counts and locators appear in the output.

[Real-source Stage08 runner](waraqat_stage08.py) first executes [Stage07 strict source replay](waraqat_stage07.py), which itself demands Stage06 verification of BOTH HTML → chapter extractions. It then builds the metadata graph against the same pinned original section bytes. It does not accept a user-supplied Stage07 JSON report as proof of source provenance.

## Explicitly unassessed references

[Sample research pointers](data/waraqat-stage08-research-pointers.json) name the existing source-attributed `pilot:rule-amr-default` as a **search-navigation hint** for the `الأمر` query in W1. A second unassessed objection-reference ID points to a `القرينة` query in W2. These are **references for possible follow-up investigation**, not evidence that the rule is correctly interpreted or that any juristic objection is present. No source occurrence becomes an authenticated P0 `Evidence` simply from its lexical presence.

Real interpretation requires a separate typed P0 rule/evidence binding, a reasoned interpretation, assessment of exceptions and appropriate review. The existing [P0 bridge](../p0_bridge.py) is NOT called by Stage08.

## Run locally on pinned private source bytes

From `C:\AI\Mubin` after `git pull --ff-only`, run:

```powershell
$root = "D:\MubinSources\waraqat"

python -m engines.usul.pilots.waraqat_stage08 `
  --primary-html "$root\waraqat-original.html" `
  --primary-export "$root\waraqat-private-utf8.txt" `
  --primary-manifest "$root\waraqat-draft-manifest.json" `
  --primary-section "$root\waraqat-bab-amr-private.txt" `
  --secondary-html "$root\witness2-original.html" `
  --secondary-section "$root\witness2-bab-amr-private.txt" `
  --queries "engines\usul\pilots\data\waraqat-stage07-queries.json" `
  --pointers "engines\usul\pilots\data\waraqat-stage08-research-pointers.json" `
  --report "$root\stage08-context-graph-report.json"

Write-Host "Stage08 exit code: $LASTEXITCODE"
```

- `0`: `STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS`; means pinned-source bytes, Stage07 replay, metadata graph and internal referential integrity passed.
- `3`: `PENDING_PRIVATE_WITNESS_FILES`; original private captures and source sections not available.
- `1`: `FAIL`; malformed query/pointer specification, source mismatch, stale Stage07 data or graph integrity failure. No partial acceptance.

**Local acceptance requires** two deterministic report runs, SHA-256 comparison, a fresh recomputation of all hash-addressed context windows against private raw section bytes, verification of edge endpoints and the original Stage07 hit offsets, and a negative test modifying private inputs on temporary copies. Share only a metadata-only closure receipt; original source excerpts and full captured HTML remain private.

## CI, limits and next gate

Run:

```bash
python -m unittest discover -s engines/usul/tests -v
python -m unittest discover -s core/tests -v
```

[Graph tests](../tests/test_evidence_context_graph.py) cover tampered Stage07 reports, stale original source bytes, UTF-8 context hashes, line/byte offsets, deduplication across profiles, zero-hit objection navigation, false rule binding and forbidden pointer status. [Runner tests](../tests/test_waraqat_stage08.py) cover strict Stage07 provenance dependency and missing private files.

**No new scholastic, juridical or copyright acceptance is conveyed:** `scholarly_verified=false`, `redistribution_approved=false`, `semantic_qarinah_verified=false`, `juristic_inference_allowed=false`, and `public_fatwa_authorized=false`. Mubin remains `0.1.0-alpha`; `U0.1` remains `experimental_prototype_not_qualified`. Quran Q0.3 and Hadith H3.9.2 are untouched.

**Future milestone:** Stage09 could formally bind source-attested text observations to versioned P0 `Evidence` metadata with explicit scope/authorship and *human scholarly attestation as a separate gate*. No lexical occurrence or hash should directly cause a juristic conclusion.
