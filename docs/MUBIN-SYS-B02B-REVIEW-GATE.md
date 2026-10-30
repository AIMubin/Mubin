# B02-B handoff metadata CI — reviewer-owned integrity checks

This small CI applies the maintainer findings on PR #129 without modifying
private source receipts, the frozen Hadith H3.9.2 qualification material,
engine runtime or system version.

It checks the eight-file `research/b02b/` package, most critically:
- `preserved_candidate` is not `selected_case`; strict selection rejected.
- 232 tests = 230 passed + 2 skipped + 0 failed (actual sums are checked).
- P0 projection passes `verify_redacted_projection` and has **zero**
  engine bindings (Usul-scoped topology, not cross-engine inference).
- Five-node `run_case` receipt passes the engine-result wire schema,
  uses matching source snapshots, and matches the diagnostic summary.
- Hadith is explicitly cue-only; Usul has no verified source handles;
  Fiqh is UNDETERMINED with no juristic conclusion.
- Historical F0.0 gaps are marked historical; current F0.1 scaffold is
  not misrepresented as a complete Fiqh engine.

No raw private source, workflow credentials, or external model calls are
used by CI. It cannot reproduce the operator-only 6:145 source ingest,
the full four-source H-Search run or semantic AI rationale receipts.
Only matching committed metadata is asserted. This is a correct, narrow
gate for a metadata-only research pull request.

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest qa.tests.test_b02b_handoff -v
python qa/check_b02b_handoff.py
```

On a code-only branch without a `research/b02b/` package, the workflow
runs the negative tests and then skips the handoff check using
`--if-present`. It checks the real package as soon as the branch includes
those files. A mandatory review requires this job green at the exact
final PR head before merge.
