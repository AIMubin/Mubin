# U0.2 concept definitions — private W1 operator intake (research only)

**What this tool does:** converts privately held *candidate texts* into a
strict **metadata-only**, versioned W1 concept-definition manifest rooted in
the pre-existing U0.2.3 operator receipt. It does **not** certify that any
candidate is genuinely from al-Waraqat, correctly ascribed to an author,
semantically faithful, or legally reusable.

Implementation: [`waraqat_definition_private_intake.py`](waraqat_definition_private_intake.py)
(and [15 synthetic adversarial tests](../tests/test_waraqat_definition_private_intake.py)).
All real candidate texts must remain off GitHub in an operator-controlled,
**off-repository** directory. The HMAC secret is never stored in public
files. There is no AI-generated authoritative definition here.

## Prerequisites

1. Clone/check out the PR #81 `u02-concept-definitions` branch.
2. Use the historically frozen public receipt
   `corpus/reviews/u02-waraqat-private-source-acceptance-PASS.json`
   (canonical SHA-256 `00f0d1c71f55dc226cd6b840decfcdada152a40746a5cdc39b1e4f019c6bf7df`).
3. Put your original **private research candidate text files** in a
   dedicated folder outside the Git working tree, for example
   `D:\MubinSources\waraqat\definition-intake`. Do not overwrite
   any W1/W2 frozen original bytes. Distinguish quoted source text from
   your *own paraphrase* in private notes; the public schema makes **no
   claim** that it has independently checked that distinction.
4. Prepare a private `intake.json` by copying the **structural example**
   [`u02-private-definition-intake.EXAMPLE.json`](data/u02-private-definition-intake.EXAMPLE.json).
   Edit each relative `private_text_file` to refer to a candidate file
   *inside the private folder*. Each submitted candidate must have an
   immutable ID, one of the **three known concept IDs** and a semantic
   version. **The repository example contains no authentic definitions.**
5. Provision a locally stored random secret key of **at least 32 bytes**
   using your trusted local key-management facility. Arrange for its
   hexadecimal representation to be available to **this one operator
   process** as `MUBIN_PRIVATE_HMAC_KEY_HEX`. Never paste its value into
   chat, GitHub, a script, a PR comment or a tracked file. The HMAC
   `commitment_key_id` is merely an opaque public label; it is **not**
   the secret.

## Private Windows run

From the checked-out repository root:

```powershell
$privateRoot = 'D:\MubinSources\waraqat\definition-intake'

python -m engines.usul.pilots.waraqat_definition_private_intake `
  --private-root "$privateRoot" `
  --private-intake "intake.json" `
  --output-manifest "u02-definition-candidates.json" `
  --output-report "u02-definition-intake-report.json"

if ($LASTEXITCODE -ne 0) {
  throw "Private candidate intake rejected; preserve files for inspection"
}
```

Set the process-scoped secret environment variable through your trusted
local mechanism **before** running this example; it is intentionally not
shown in the command. Clear it promptly after use. Environment variables
are **not** a secure enclave and may be accessible to other privileged
local processes. Avoid enabling shell tracing, logging the environment,
or leaving the key in a persistent PowerShell profile.

Output paths must be **new**, immediate children of the private root
(not inside the repository). Existing output paths and attempts to
overwrite input are rejected. A failed run returns exit 2 and only a
privacy-safe failure status on stdout. Exit 0 returns:

`PRIVATE_CANDIDATES_PREPARED_UNASSESSED`

Files created locally:

- `u02-definition-candidates.json`: strict metadata-only version
  `u02-concept-definitions/0.1.1`. Its **actual** candidate entries use
  `HMAC_SHA256_PRIVATE` and contain only IDs, digest, and public key ID.
- `u02-definition-intake-report.json`: deterministic report from the
  pinned receipt and candidate manifest, with explicit flags
  `scholarly_verified=false`, `source_support_attested=false`,
  `public_fatwa_authorized=false`.

The emitted `report_sha256` covers **the entire final operator report**
except the digest field itself. The original validator-only result is
preserved separately as `definition_validation_report_sha256`. The two
values have different scopes: never treat one as the other's digest.
The canonical JSON serialization uses sorted keys, compact separators,
UTF-8 and `ensure_ascii=False`, matching
`engines.usul.concept_rule_catalog.canonical`.

Path-resolution failures, including symlink loops on Python 3.11, fail
closed with only `PRIVATE_DEFINITION_INTAKE_REJECTED` on stdout;
full private paths and Python traceback messages are never printed.
The private operator is an offline, **single-trusted-user** workflow:
do not let untrusted processes concurrently replace/swap source or
output files in the private directory during intake.

Both files should remain private until independently inspected to ensure
they contain **no private text, paths, keys, personal identifiers or
rights-restricted information**. Do not automatically commit either file.
A public metadata-only manifest can be considered for a subsequent
reviewed PR *only* after a separate disclosure review and confirmation
that revealing the **existence and counts** of the candidates is permitted.

## What exactly gets checked

- Canonical digest of the previously frozen U0.2.3 operator receipt;
  full W1 section pin, three concept/query IDs, and non-promotion flags
- Strict local input schema (no inline text, prose, extra fields,
  unknown identifiers, unbounded lists or path traversal)
- Private candidate files strictly **inside** the supplied private
  directory (resolved symlinks are also checked); each distinct file is
  used at most once; files must be nonempty UTF-8 and under 128 KiB
- HMAC-SHA256 of exact private file bytes using the operator-provisioned
  secret; content is never copied into public outputs
- Cross-references between interpretations and same-concept definition
  candidates; strict `build_definitions` validation with all positive
  scholarly and rights flags disabled
- Output-only-on-success behavior and refusal to overwrite existing files

This is **not** independent evidence that a phrase occurs in a historical
source, or a scientific judgment about the definition. In particular,
connecting a definition file to `concept:amr-term` and the W1 query
`pilot:amr-term` proves only that the **metadata references** match an
existing literal observation. Authentic quotation, attribution, edition,
meaning, provenance rights, and the sixteen W1/W2 variant chapters still
require external review. The algorithm does not turn mere word matches
into a rule of `amr`, `qiyas` or `tarjih`.

## Final local acceptance ledger

Record these without disclosing the input texts:
```ini
private_intake_status = PRIVATE_CANDIDATES_PREPARED_UNASSESSED
receipt_pin_verified = true
definition_records_are_hmac = true
candidate_texts_and_key_remain_private = true
source_authorship_authenticated = false
source_support_attested = false
scholarly_verified = false
redistribution_approved = false
juristic_inference_allowed = false
public_fatwa_authorized = false
```

No additional U0.2 engineering version bump or PR merge is authorized
by a successful local run. Overall Mubin remains `0.1.0-alpha`.
