# Usul U0.1 — private admission → Stage04/Stage05 lexical bridge

**Scope:** A read-only, single-operator, internal research bridge. This is
**not** new Usul rule execution, source authenticity, publication clearance,
legal advice, proof of interpretive equivalence, or a Fiqh/fatwa capability.
Mubin remains `0.1.0-alpha`; Usul remains an experimental prototype.

## What this integration actually connects

`corpus/internal_research_ingest.py` (PR #83) stores a hash-addressed private
UTF-8 object, an `internal_only` manifest and a SHA-linked private usage
register. `engines/usul/private_admission_lexical.py` requires:

1. A private intake manifest and usage register whose full chain and stored
   object currently satisfy `is_admitted()`.
2. A matching register entry declaring `source_kind=usul`, matching
   source ID, source/object SHA-256 and intake manifest SHA-256.
3. Intake `visibility=internal_only`, original byte digest equal to its
   separately supplied intake pin, and exact content-addressed object layout.
4. A Stage04 snapshot metadata manifest whose bytes match an **independently
   frozen** manifest SHA-256, whose `source_sha256` matches the admitted
   object and whose `source_url` equals the intake source URL.
5. Stage04's full byte-and-section coverage checks, followed by Stage05's
   exact-literal search, run against the **admitted stored object** rather
   than a caller-supplied arbitrary source file.

The bridge accepts different Stage04 and intake `source_id` namespaces and
records both IDs separately. It does **not** prove edition aliases equivalent:
Stage04's human-readable `edition` and the intake `edition_id` may have
different representations. These claims remain explicitly false.

The result exposes only bounded match counts, source/section/query hashes,
original-byte offsets and metadata IDs. It does **not** return original text,
query literals, source URL, local paths, author or edition. A search with zero
literal hits never establishes absence of a legal `qarīnah`.

## Local operator invocation (no private files committed)

First complete PR #83's operator-reviewed lawful-source intake and independently
freeze a Stage04 snapshot manifest pin outside the submitted document. Put
the source object, register, manifest, query input and report **outside Git**;
keep one trusted writer and restrict filesystem access.

From the Mubin repository root:

~~~powershell
python -m engines.usul.private_admission_lexical `
  --admission-manifest "<PRIVATE_VAULT>/manifests/<INTAKE_ID>-<HASH_PREFIX>.json" `
  --usage-register "<PRIVATE_REGISTER>.jsonl" `
  --snapshot-manifest "<PRIVATE_STAGE04_MANIFEST>.json" `
  --trusted-snapshot-manifest-sha256 "<INDEPENDENTLY_PINNED_STAGE04_MANIFEST_SHA256>" `
  --section-id "pilot:waraqat-bab-amr" `
  --queries "<PRIVATE_QUERY_ARRAY>.json" `
  --report "<PRIVATE_REPORT>.json"
~~~

The query JSON is a bounded array of `{"id": "...", "literal": "...",
"profile": "literal_exact_v1"}` objects. CLI exit codes: **0** for a
metadata-only exact lexical replay, **1** for a refusal, **3** when a required
private input is missing. The CLI prints no private paths or source text; it
writes a fresh metadata report or refusal receipt only to a path outside Git.
**Report destinations must also lie outside the source vault and cannot be
the intake manifest, usage register, Stage04 manifest, query file, admitted
object, or any existing hard link to these inputs.** Results are written
using an atomic same-directory replacement; no input evidence is deliberately
modified, even when a replay is refused. Vault containment checks both lexical
and resolved/canonical paths to reject Windows 8.3 short-name aliases of the
private vault. The real 8.3 regression executes only where the runner's
filesystem has short names enabled; a cross-platform canonicalization test
runs regardless. Always check the current process
exit code, not a cached earlier report.

## Existing al-Waraqat W1/W2 evidence is not silently upgraded

The Stage04 operator receipt records a locally reported UTF-8 export digest
`9ce9de30f1af3ef32b2bf55b0473c9459e0cf530e3b557535744b284c760f4df`
and Stage04 manifest pin
`5bf586787dbb9f84d03fc21c62ee32619b66b474c66a6c890aeb813219f853cf`.
Those records are **historical metadata-only operator evidence**, not
independent GitHub reproduction of the private file, and are not a blanket
admission of either W1 or W2. A local operator must demonstrate the exact
admission/Stage04 byte and URL link using the real restricted files.

The separate W2 `EVIDENCE_RECONCILIATION_FAILED` issue remains open.
Do not rewrite frozen receipts to make this bridge pass. If a stage's source
byte identities differ, refuse that link and handle that discrepancy as a
separate immutable-evidence reconciliation task.

## Test scope and limitations

`python -m unittest discover -s engines/usul/tests -v` includes fully
synthetic cross-module and adversarial tests. GitHub CI validates the code on
Windows and Ubuntu; it does **not** open protected private files, establish
operator declarations as true, validate printed editions or run any fiqh
inference. The register remains SHA-linked but not independently anchored for
malicious rewrite detection; cross-process path swaps and concurrent writers
remain outside the supported single-operator threat model.

`public_fatwa_authorized`, `juristic_inference_allowed`,
`scholarly_verified`, `redistribution_approved`,
`edition_equivalence_verified` and
`semantic_qarinah_detection_verified` always remain `false`.
