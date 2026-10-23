# U0.1 Stage09 — Typed Evidence Binding (research-only)

**Status:** engineering prototype with synthetic tests, **not** qualified historical P0 evidence and **not required for the public metadata preview**.

## Contract

[Typed exact-byte binding](../typed_evidence_binding.py) and [al-Waraqat Stage09 runner](waraqat_stage09.py) join an EXACT original-byte occurrence from a Stage08 graph with a specifically existing P0 Evidence record **only after separate SHA identities are checked**:

1. The original Stage08 graph canonical SHA-256 matches an independently frozen anchor. For the private al-Waraqat source, the frozen anchor is 72ca6bd80c4e70378dd9d2f1cfc75841024b292d2335479d167add1a8ca6fdb2.
2. The source record of a structurally validated P0 bundle identifies the exact same SECTION by SHA-256 and work title, not merely the same named book or an unrelated edition.
3. The declared P0 Evidence excerpt SHA-256 equals the occurrence's original-byte SHA-256. The occurrence must have an EXACT_LITERAL_ONLY locator edge. Folded candidates, absent matches and unpinned material **cannot be silently promoted**.

Outputs carry status STAGE09_TYPED_REFERENCE_PROPOSALS_PASS with each binding explicitly PROPOSED_EXACT_BYTE_LINK_UNASSESSED. Neither P0 Evidence.verification_status nor its excerpt text are output or changed. No rules are executed. All interpretation, scholarly review, fatwa and rights flags remain false.

**Important:** A P0 bundle's own internal verified label is metadata; it does NOT authenticate an edition or a scholarly conclusion. A SHA match is proof of a bounded declared byte correspondence, not proof of source meaning or legal applicability.

## Inputs and local invocation

To attempt a private al-Waraqat run, the operator must already have:
- The **full private Stage08 JSON graph** from the pinned two-witness workflow.
- An independently authored, structurally valid P0 bundle with the exact chapter SHA as P0 Source.content_sha256 and the actual quoted occurrence as a P0 Evidence excerpt.
- A list of proposals with exactly: id, occurrence_id, p0_source_id, p0_evidence_id, relationship=EXACT_BYTE_CITATION_PROPOSAL, review_status=UNASSESSED.

All identifier fields must be genuine known local references. Synthetic placeholders never prove real evidence correspondence.

~~~powershell
python -m engines.usul.pilots.waraqat_stage09 --stage08-graph "D:\MubinSources\waraqat\stage08-context-graph-report.json" --p0-bundle "D:\MubinSources\waraqat\stage09-private-p0-bundle.json" --proposals "D:\MubinSources\waraqat\stage09-reference-proposals.json" --report "D:\MubinSources\waraqat\stage09-proposal-report.json"
~~~

Exit 0: STAGE09_TYPED_REFERENCE_PROPOSALS_PASS (byte-level research reference proposal, not a juridical decision).
Exit 3: PENDING_STAGE09_SOURCE_BINDING_INPUTS (private graph/P0 inputs not supplied).
Exit 1: FAIL/REFUSED (bad source/graph pin, mismatching quote, unrecognized or candidate-only occurrence, malformed P0/proposal data, or unsafe output destination).

### Protected inputs and metadata-only report

The Stage09 runner now rejects input and report paths inside any Git worktree, as
well as symlink/reparse redirections. The report destination must **not** equal
or hardlink to the Stage08 graph, P0 bundle or proposal input. It may overwrite
only a previous Stage09 report carrying its recognized `report_kind` and
`runner` markers; an unrelated existing file is protected.

Reports are written through a same-directory temporary file with fsync and
atomic replacement. On a safe destination, the current refusal or missing-input
status replaces the previous Stage09 status, preventing stale PASS reports.
The command prints only status/reason metadata, not filenames or private text.
These checks assume **one trusted local writer**; they do not defend against
an adversary replacing directory entries concurrently.

**Important prerequisite for W1:** A successful Stage05 lexical replay alone
does not construct a valid P0 bundle or a Stage08 exact-occurrence proposal.
Select real Stage08 `TEXT_OCCURRENCE` identifiers and already-existing P0
Source/Evidence records; verify matching section and excerpt digests and the
independently pinned Stage08 canonical graph hash. Keep all source and P0
inputs outside Git. Mark every proposal `UNASSESSED`; no rule execution or
scholarly/fiqh/publishing authorization follows from Stage09.

[Synthetic byte-binding tests](../tests/test_typed_evidence_binding.py) use the project’s synthetic P0 demo bundle and original-byte fixture; [runner tests](../tests/test_waraqat_stage09.py) enforce the frozen Stage08 public receipt digest.

## Launch bottleneck removed

The public [metadata preview](../../../docs/index.html) and its [independent release CI](../../../.github/workflows/public-preview.yml) are decoupled from Stage09 and from incomplete Hadith/Fiqh and protected Quran/Tafsir text-publication gates. Only **publication of those additional features** needs their separate verified prerequisites.

U0.1 remains experimental_prototype_not_qualified. Mubin system remains 0.1.0-alpha; Q0.3 and frozen H3.9.2 are unchanged.
