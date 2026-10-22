# U0.2 pilot 03 — strict real-source W1/W2 lexical concept anchoring

**Scope:** metadata-only, private-operator source replay. Not a qualification
of an Usul rule, source edition, semantic equivalence or Fiqh.

Previous U0.2 synthetic tests show only that the *contracts* behave
deterministically. This pilot connects those contracts to the existing
**historically frozen** Stage08 graph of the two al-Waraqat digital
witnesses, without sending source HTML, text exports or excerpts to GitHub.

## Established public historical pins (U0.1 receipt)

- Stage08 graph SHA-256:
  `72ca6bd80c4e70378dd9d2f1cfc75841024b292d2335479d167add1a8ca6fdb2`.
- W1 باب الأمر section SHA-256:
  `20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab`.
- W2 Stage06 باب الأمر section SHA-256:
  `db181b1d9466389d2b5aeaf50362dd57e716cc1e36d041948777e3fe0c9c9358`.
- Historical Stage08 graph: **53 nodes, 87 edges**, including one
  `RULE_RESEARCH_POINTER`, one `OBJECTION_RESEARCH_POINTER`,
  and twelve `SEARCH_QUERY` nodes.
- Stage07 receipt W1 exact literal counts:
  `pilot:amr-term=6`, `pilot:qarinah-term=1`,
  `pilot:wujub-term=1`.

The pins belong to the cited **captured digital sources**, not verified
printed scholarly editions. Matching them proves the local reproduction
of that captured state; it does not authenticate the contents.

## New operator chain

`engines/usul/pilots/waraqat_u02_real_bridge.py` executes, in order:

1. Existing `waraqat_stage08.replay_and_graph` (which first executes
   strict Stage07 → Stage06 verification of both original HTML files and
   derived private sections).
2. Verify the **independently frozen historical** Stage08 graph SHA,
   both source-section hashes, runner flags, and 53/87 inventory.
3. Recompute the U0.2.0 catalog using that Stage08 graph and
   `waraqat-u02-catalog-candidates.json`.
4. Bind **every** proposed concept to an existing source-scoped Stage08
   query and unique byte-addressed occurrence nodes, explicitly
   preserving `EXACT_LITERAL_ONLY` vs folded diagnostic classification.
5. Require each research query's exact match count to equal the frozen
   Stage07 receipt count, and output *only* IDs, SHA-256, source scopes,
   classifications and no-authority flags.

The existing Stage08 **rule research pointer** is attached only to the
`pilot:amr-term` query in W1. The separate qarinah and wujub *concept*
anchors bind their own W1 **literal query observations**. These are
three lexical observations, **not proof that the text endorses the proposed
`amr → wujub` rule or clears any qarinah**.

The candidate manifest has deliberately explicit `UNASSESSED` statuses.
No meaning/content gloss is asserted. No automatically inferred definition
is committed. This pilot is not a semantic definition-validation system.

## Execution on local private Windows machine

In the repository root after `git pull --ff-only` on PR #80's branch:

```powershell
$root = "D:\MubinSources\waraqat"

python -m engines.usul.pilots.waraqat_u02_real_bridge `
  --primary-html "$root\waraqat-original.html" `
  --primary-export "$root\waraqat-private-utf8.txt" `
  --primary-manifest "$root\waraqat-draft-manifest.json" `
  --primary-section "$root\waraqat-bab-amr-private.txt" `
  --secondary-html "$root\witness2-original.html" `
  --secondary-section "$root\witness2-bab-amr-private.txt" `
  --report "$root\u02-waraqat-real-lexical-catalog.json"

if ($LASTEXITCODE -ne 0) {
    throw "Private U0.2 provenance bridge did not pass"
}
```

Default `--queries`, `--pointers`, `--catalog-manifest` and
`--lexical-manifest` are **committed metadata-only fixtures** under
`engines/usul/pilots/data/`; supplying alternative metadata is allowed
but the strict historical graph pin and legacy source pins must still
match, so unreviewed changes in Stage08 inputs fail closed.

- Exit `0`: `U02_WARAQAT_PINNED_CATALOG_PASS`. The report is
  research metadata, **not** a new scholarship/authorization gate.
- Exit `3`: `PENDING_PRIVATE_WITNESS_FILES`, no source promotion.
- Exit `1`: `U02_WARAQAT_PINNED_CATALOG_FAILED`.
  Investigate mismatch without modifying historical U0.1 pins.

## Local acceptance required before PR qualification

- Execute the private replay **twice** and compare the reports' complete
  SHA-256 and content, not only their `status` values.
- Confirm all 3 exact lexical links exist in the expected W1 source:
  `6/1/1`, with original occurrence hashes and stable source IDs;
  do **not** quote the private source lines in the public receipt.
- Recompute all 3 query occurrence counts from the private section
  independently, and compare to the Stage07 receipt.
- Verify Stage08 53/87 and the frozen SHA. Flip a temporary copy of
  a private HTML or section and confirm failure rather than false PASS.
- Ensure output JSON contains **no private source text**, HTML,
  raw excerpts, line context or local private paths.
- Archive only a metadata-only result with operator-attested replay
  hashes and limitations, separately from the original private report.
- Leave PR #80 Draft until source replay is attested and engineering
  review is complete; do not merge automatically.

## Automated CI coverage

`tests/test_waraqat_u02_real_bridge.py` builds actual Stage07 and
Stage08 components from temporary, **synthetic** Arabic witness files and
tests the U0.2 bridge with synthetic patched source pins. That test
does **not** pretend to have the private W1/W2 HTML. The real operator
uses the **unaltered** frozen W1/W2 and Stage08 constants.

```bash
python -m unittest discover -s engines/usul/tests -v
```

Mubin system stays `0.1.0-alpha`. Hadith H3.9.2 and Quran Q0.3
are unchanged; all `scholarly_verified`, `redistribution_approved`,
`semantic_equivalence_verified` and `public_fatwa_authorized`
authorizations remain `false`. No Fiqh engine or operative
`qiyas`/`tarjih` was introduced.
