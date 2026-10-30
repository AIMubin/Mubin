# MUBIN-SYS-B02-C — Resolve missing pinned Usul source node + Fiqh source-reference gap

## Accepted architecture decision

B02-B correctly identified two distinct kernel-level gaps in the 6:145
diagnostic transaction:

1. The existing `usul.evaluate_proposition` only simulates one-step
   rules and does not load the pinned local Waraqat source passages.
2. `fiqh.prepare_case` received source references from Quran, Tafsir,
   and Hadith cue detection, but none tied to a vetted Usul source span.

**This slice fixes only the byte-level evidence ingestion and binding
boundaries**. It does not implement a Usul rule-validity proof, semantic
linkage promotion, juristic opinion attribution, qiyas or tarjih.

## Trusted startup boundary (no source text is committed)

Register `build_engine_registry(..., usul_source_blobs={source_id: bytes},
usul_source_pins={source_id: sha256}, usul_sources_synthetic=False)`.
These are trusted operator inputs. A full-source SHA mismatch refuses
registration; source sizes and count are bounded. Caller-submitted
requests can never insert local paths, override the trusted blob, or
change the source registry.

`usul.bind_source_spans` consumes a small list of pinned original **byte**
spans: `source_id`, `source_sha256`, `start_byte`, `end_byte`,
`span_sha256`, `rule_id`. The adapter verifies full source and span
digests and returns stable `ev.usul.*` evidence handles, never raw text.
The `rule_id` is an unverified research label, not established semantic
attribution or rule correctness.

`fiqh.prepare_case` will link an opinion to an upstream `ev.usul.*`
handle only when provided by an upstream Usul engine execution; it no
longer treats Quran verse IDs, Tafsir passage digests, or Hadith mention
cues as opinion-source evidence. The link **does not** prove attribution,
which remains explicitly `source_claims_verified=false` and
`opinion_source_attribution_verified=false`.

## Mandatory controls on the real 6:145 case

- Reuse the existing frozen local W2/W1 full-source raw bytes and pins
  from the operator vault; byte offsets must be raw-file offsets, not
  newline-normalized decoded-string indices (CRLF/LF safety).
- Preserve `UNDETERMINED` if the source spans cannot be matched or the
  operator has no genuine juristic attribution evidence.
- Source bytes and complete P0 excerpts stay private. Commit only
  metadata receipts after scanning for sensitive fields.
- Execute `run_hsearch` against the four pinned sources separately.
  B01 `detect_tafsir_mentions` is a cue detector, not Hadith identity.
- Recalculate the result through `run_case`, not by editing the old
  `b02c-kernel-receipt`.
- Do not remove the strict candidate rejection, do not assert an issued
  fatwa, and do not update `VERSION.yaml`.

### Engineering check

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s evaluation/integration -v
```

A green CI proves only the integration code path, not correctness of
source edition, interpretation, rule premises or scholarly conclusions.
