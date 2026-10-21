# U0.1 Stage 08 — Evidence Context & Citation Graph

**Status:** `STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS` **reported by the private Windows operator** and documented in [the Stage08 metadata-only closure receipt](../../../corpus/reviews/u01-stage08-waraqat-context-graph.json). This closes the locally attested technical source-to-context graph workflow; **public CI only reruns synthetic fixtures**, not the separately retained historical HTML captures. No scholarly, legal, edition or rights verification is implied.

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


## 2026-10-21 — real-source graph closure and independently verified CI

The [Stage08 metadata-only review receipt](../../../corpus/reviews/u01-stage08-waraqat-context-graph.json), committed in [`753bebb`](https://github.com/AIMubin/Mubin/commit/753bebb1e7ce8d780c24ee3f815dc6090d62db6f), records successful **local** `STAGE08_DUAL_SOURCE_CONTEXT_GRAPH_PASS` following strict W1/W2 Stage07 replay with both HTML→section derivations rechecked.

| Reported original-source graph measure | Count |
| --- | ---: |
| Nodes | **53** |
| Edges | **87** |
| Unique `TEXT_OCCURRENCE` | **22** |
| `HASHED_CONTEXT` | **13** |
| `SEARCH_QUERY` | **12** |
| `QUERY_LOCATES_OCCURRENCE` links from exact literal matches | **12** |
| `QUERY_LOCATES_OCCURRENCE` links from folded candidates | **24** |
| Unassessed rule/objection pointers | **2** |

All **13/13 context windows** and **22/22 source-positioned occurrences** were reportedly re-hashed against exact private UTF-8 sections; all **87/87 edge endpoints** resolved with no cross-witness crossing. The two research navigation pointers remained `UNASSESSED`, and the graph did not create legal support/proof edges.

- Canonical logical-graph SHA-256: `72ca6bd80c4e70378dd9d2f1cfc75841024b292d2335479d167add1a8ca6fdb2` (computed over canonical payload **excluding** `graph_sha256` and runner-added fields).
- Private final-report SHA-256: `939380a4c191495269abc7db2d4a9c027e976daf9e57ed1f7225f0744e994231`; two local reports were byte-identical. **These two SHA-256s intentionally differ.**
- [Usul code baseline `2388797`](https://github.com/AIMubin/Mubin/commit/238879784a8a463682a5d4955d87984b912426b0) passed [CI 39553023684](https://github.com/AIMubin/Mubin/actions/runs/39553023684) **173/173 tests on both Windows and Ubuntu**.
- The Stage08 review-only commit `753bebb` passed [Corpus CI 39556898598](https://github.com/AIMubin/Mubin/actions/runs/39556898598), **62/62 tests on both OSes**. The `usul-checks` workflow was not triggered on the `corpus/reviews`-only change, as expected from path filters.
- **Negative-test evidence is tiered:** the receipt records a private CLI missing-file check (exit 3) and W1 section byte flip (exit 1). Other HTML mutation and graph-integrity cases were covered by committed synthetic tests. Do not describe all variants as individually executed against both private HTML captures during Stage08.

This locally reported PASS is a *byte-traceability and graph referential-integrity* milestone only. It does not qualify published witness editions, prove same meaning across source variants, detect semantic `qarā'in`, authenticate applied P0 rules, or permit a fatwa. `scholarly_verified=false`, `redistribution_approved=false`, `semantic_qarinah_verified=false`, `juristic_inference_allowed=false`, `rule_support_attested=false`, and `objection_presence_attested=false` remain in force.

**Next independently scoped research milestone:** `U0.1 Stage09 — Typed Evidence Binding & Provenance Contracts`: a non-promotional, versioned bridge between source-anchored observations and P0 evidence identifiers, with separate scholarly/interpretive attestation and strict rejection of direct inferred rule support.
