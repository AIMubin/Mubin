# I0.1c.1 — Pinned Snapshot Operator Workspace (experimental)

**Scope:** opt-in loopback-only metadata workspace over an independently copied
corpus+sidecar snapshot. This is **not** a public Quran/Tafsir text endpoint, a
license or scholarly attestation. Mubin global version is `0.1.0-alpha`.

## Security and lifecycle contract

1. The operator starts the existing workspace CLI with `--pinned-snapshot`.
   Before listening, startup runs **full** R0.1a vault, registry and HMAC
   verification and resolves the current I0.1c Snapshot (full corpus and
   sidecar SHA-256). Source, sidecar **and campaign receipt** digests must match the last authenticated
   registry payload, and its HMAC head must be unchanged.
2. The process pins exact two database paths, their full-content hashes and
   filesystem identities. An initial bad/mismatched snapshot fails closed.
   The pointer must use a **full** revision identifier (`r` plus 64 lowercase
   hexadecimal characters); a human-readable eight-character abbreviation
   is not a valid on-disk Revision ID. A new `LATEST.json` alone does **not** move already-open operator sessions:
   the process remains on its original revision until restarted. If the
   **evidence head** or observed original/snapshot file identities change,
   requests are refused rather than silently switching to Revision B.
3. Every HTTP request revalidates file identity `dev/ino/size/mtime_ns/ctime_ns/
   nlink`, recomputes the **small** hash-linked evidence JSONL chain, verifies
   the independently keyed HMAC head anchor, and requires the pinned head and
   SHA-256 metadata (including the campaign receipt digest). The R0.1d qualification ledger is **independently
   authenticated on every lookup/state request** by the existing APIs; it
   is not cached. Every successful HTTP response is re-guarded before send.
4. There is **no per-request full hash** of the original corpus (15.9MB) or
   sidecar (223MB), and no per-request full hash of the pinned databases.
   The existing I0.1a/R0.1c metadata contracts and `text_included=false`
   enforcement remain intact; no body, secret or path appears in responses.
5. The filesystem identity guard is an **operator-trust optimization**:
   it does not detect intentionally restored filesystem metadata or hostile
   modifications made by an administrator with direct storage control.
   This is not cryptographic WORM. Restart/re-pin is required for a changed
   evidence head. Concurrent publishers still require external coordination.
6. Failures remain `409 REFUSED` with stable refusal codes. The original
   workspace is unchanged **without** `--pinned-snapshot`; existing clients
   must opt into the accelerated trust contract explicitly.

## Operator-local startup

Use the same ten private path parameters as I0.1b (never put actual paths,
keys or local vault content in repository issues or CI):

```sh
python -m engines.quran.research.workspace --pinned-snapshot \
  --vault "$VAULT" --corpus-db "$ORIGINAL_CORPUS_DB" \
  --sidecar-db "$ORIGINAL_SIDECAR_DB" \
  --registry "$EVIDENCE_REGISTRY" --anchor-dir "$EVIDENCE_ANCHORS" \
  --evidence-key "$EVIDENCE_KEY" \
  --qualification-ledger "$QUALIFICATION_LEDGER" \
  --qualification-anchor-dir "$QUALIFICATION_ANCHORS" \
  --qualification-key "$QUALIFICATION_KEY" --port 8765
```

On Windows, use the equivalent PowerShell invocation with your local
private paths. The server only binds `127.0.0.1`. No text routes are added.

## Benchmark: full localhost HTTP request/response, not direct SQLite

Once the real-vault operator has started the pinned workspace and its normal
qualification ledger has been initialized, run locally:

```sh
python -m qa.benchmark_pinned_workspace_i01c1 \
  --origin http://127.0.0.1:8765 --ref 2:1 --warmup 5 --samples 60
```

The harness returns `p50_ms`, `p95_ms`, `p99_ms` and mean elapsed time for
**complete loopback HTTP responses** (including the server qualification
checks); startup verification, real browser rendering and network overhead
beyond loopback are explicitly excluded. Record both cold startup validation
time (separately) and warm response p50/p95 on the real operator machine.
Browser developer tools may be used for complementary navigation/render
measurement; these numbers are **not** browser measurements.

**Evidence boundary:** the CI harness uses only invented synthetic SQLite
placeholders and independently signed test HMAC fixtures. No real Quran/Tafsir
bytes, operator HMAC keys, local vault paths or text permits enter CI.
Observed p50/p95 on synthetic CI must NEVER be passed off as production
performance.

## Verification

```sh
python -m unittest core.tests.test_quran_operator_workspace_i01b core.tests.test_quran_pinned_workspace_i01c1 -v
```

Scenarios include old I0.1b backward compatibility, successful metadata
lookup over genuinely published synthetic snapshots, prohibition on per-request
bulk rehash, bad Origin/private-text route refusal, original/snapshot file
mutation refusal, forged registry content retaining a stale head, receipt provenance
mismatch, qualification
corruption refusal, and Revision A pinning despite a new LATEST pointer.

All authority gates remain `false`: `source_authenticated`,
`scholarly_verified`, `rights_verified`, `publication_allowed`,
`juristic_inference_allowed`, `public_fatwa_authorized`.
