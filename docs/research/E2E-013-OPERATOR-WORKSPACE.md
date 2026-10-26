# E2E-01.3 — Integrated Research View in the Existing Operator Workspace

**Product version:** `0.1.0-alpha`. This is an operator-local research aid,
not a scholarly verdict, legal clearance, or public fatwa interface.

## What changed

One additional view **inside the existing** loopback-bound
`engines.quran.research.workspace` process. No new server, database,
public API, frontend framework, JS runtime, queue or governance layer.

- `GET /research?ref=2:43` renders an Arabic, RTL, server-generated
  **metadata-only** page listing the qualified Quran/tafsir source records,
  the four actual synthetic al-Waraqat pilot case statuses, and gaps and
  research uncertainty. A link is visible on the existing home page.
- `GET /api/research?ref=2:43` returns the existing E2E-01.1/01.2 JSON
  contract, not a separately reimplemented result. Both routes use
  `research_slice`, which calls signed `operator_lookup` and checks
  evidence and qualification heads before and after Usul execution.
- `--pinned-snapshot` uses the **same existing** I0.1c.1 pinned session
  for research as for `/api/lookup`; request guards run before and after
  the research computation and never hash the large files per request.
- All dynamic HTML fields are HTML-escaped. No client-side JS or inline
  CSS is needed; the original restrictive CSP, Origin, Host, Sec-Fetch-Site
  and loopback-only checks apply to both new routes. Responses use
  `Cache-Control: no-store`.

## Operator observation — optional startup-only JSON

By default there is **no** semantic relation asserted. The research page
says `UNASSESSED`. To show an E2E-01.2 proposal, the local operator can
provide an *optional* JSON file **outside the vault** with the same
`build_linkage` input fields defined in
`docs/research/E2E-012-SEMANTIC-LINKAGE.md`:

```sh
python -m engines.quran.research.workspace \
  --vault "$VAULT" --corpus-db "$CORPUS_DB" --sidecar-db "$SIDECAR_DB" \
  --registry "$EVIDENCE_REGISTRY" --anchor-dir "$EVIDENCE_ANCHORS" \
  --evidence-key "$EVIDENCE_KEY" \
  --qualification-ledger "$QUALIFICATION_LEDGER" \
  --qualification-anchor-dir "$QUALIFICATION_ANCHORS" \
  --qualification-key "$QUALIFICATION_KEY" \
  --pinned-snapshot --research-observation-file "$OPERATOR_CANDIDATE_JSON" \
  --port 8765
```

The optional file is UTF-8 JSON, at most 8192 bytes, not a symlink, outside
the private vault, read **once at server start** and validated using the
existing E2E-01.2 rule and scope checks. It is **not** a remotely writable
annotation API. The proposal appears only on the specified verse reference;
all other references remain `UNASSESSED`. On every research request
the proposal's claimed evidence head is compared with the authenticated
retrieval head and a real retrieved source coordinate must exist; mismatch
returns HTTP 409 `REFUSED`. Restart the server to update or remove the
local proposal file. Do not store keys, protected text, Quran/tafsir bodies
or private reviewer decisions in that JSON file.

## Semantics displayed

Three distinct concepts must never be conflated:

1. **Retrieved metadata**: actual source IDs, coordinate-presence indicators
   and verified-ledger scholarly and rights decision states. These show
   authenticated system records, not scholarly certification.
2. **Operator observations**: researcher-entered Arabic word, position and
   counts of reportedly inspected, uninspected and positive-indicator
   sources. The code does NOT inspect the actual Quran or Tafsir verse bytes
   or independently authenticate that morphological relation.
3. **Proposed relationship**: always `PROPOSED_NOT_CERTIFIED`, never
   scholarly accepted or legally binding. NOT_OBSERVED_IN_SCOPE does not
   mean absence of `qarīnah`.

No protected source text, footnotes, excerpts or local secret paths are
rendered. Input source-specific notes may contain user-entered text in
the operator-only JSON report; the server-rendered HTML deliberately omits
these notes, and the input is restricted to a local operator-controlled file.

## Tests and acceptance

```sh
python -m unittest \
  core.tests.test_e2e_research_slice \
  core.tests.test_semantic_linkage \
  core.tests.test_e2e_workspace_e013 -v
```

The tests exercise the actual local HTTP routes over synthetic SQLite,
real signed synthetic qualification ledger and pilot, HTML escaping,
non-leaking private-text contract, false authority flags, source-candidate
head binding, out-of-scope candidate filtering, invalid references,
cross-Origin refusal, damaged-ledger refusal and pinned-session steady-state
no-bulk-hash behavior. CI does NOT include real private source materials.

## Next

**E2E-01.4** is a substantive **scientific** evaluation of verse–rule
linkage accuracy, supporting/opposing source witnesses, uncertain/blocked
cases, false-positive links and methodological limitations. We should not
build additional infrastructure or declare a scholarly result on account
of this UI. Parallel `H-Search-01` remains a separate research-capability
track.

All source, rights, scholarly, publication, juristic and fatwa gates
remain `false`.
