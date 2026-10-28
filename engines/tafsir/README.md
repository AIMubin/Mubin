# Tafsir Engine — T0.1: linked local-source research retrieval

Mubin system version remains 0.1.0-alpha. T0.1 is a source-linkage engineering slice, not scholarly qualification.

Mubin already has a Q0.3 pinned local corpus database with 6,236 indexed verse keys and 31,180 imported tafsir records across five Tafsir Center keys (see corpus/reviews/q03-engineering-qualification.json). The existing six-title KSU navigation bibliography is metadata-only and distinct. T0.1 reuses corpus.query.get_ayah rather than importing a new corpus.

Every result binds a Quran numeric verse reference to dataset-indexed tafsir entries, with stable evidence IDs, source-record SHA-256, source dataset/key, work and author attribution, quality flags and unknown edition/volume/page. The link asserts dataset indexing, NOT proof that a given printed edition interprets the verse exactly. No interpretive disagreement or juristic conclusion is inferred.

## Private operator commands

    python -m engines.tafsir.t01 2:43 --database corpus-data/linked/quran_tafsir.db

The default produces a metadata-only report; it emits no Quran text and no tafsir body text.

    python -m engines.tafsir.t01 2:43 --database corpus-data/linked/quran_tafsir.db --private-text

Private-text mode prints unverified tafsir body text only for non-held, displayable records. Use it only when that local research use is permitted. Never pipe it into CI, public logs or cloud services. Existing Baghawi review holds and markup-only suppression remain in force; the flag cannot override them.

The CLI requires the exact linked SQLite SHA-256 tracked in corpus/locks/quran-tafsir-q03.json. It hashes the whole file before and after retrieval and refuses SQLite WAL/journal sidecars whose contents are not part of the pinned database digest; there is extra disk I/O, and it does not attest external source custody. The internal _lookup helper permits alternate *synthetic test fixture* pins only, never a production CLI pin bypass.

Unknown edition/volume/page remain null. Work attribution comes from the unreviewed bibliography and must not be mistaken for authenticated printed editions. The upstream SQLite SHA is historical metadata from the Q0.3 record, not independently checked on each lookup.

All authority and redistribution flags stay false: source_authenticated, scholarly_verified, rights_verified, publication_allowed, p1_admitted, juristic_inference_allowed and public_fatwa_authorized. No Tafsir/Fiqh AI model, source rewrite, public API, new corpus download or Quran reconstruction is involved.

## Regression

    python -m unittest core.tests.test_tafsir_t01 corpus.tests.test_query core.tests.test_quran_tafsir_metadata -v

CI exercises synthetic and adversarial paths on Ubuntu and Windows. Actual private-corpus replay occurs on the operator's local vault, outside Git and CI. Future source-work should add independently grounded edition/page locators, structured interpretations and their contexts, then typed connections to Usul and Fiqh.

## T0.2.1–T0.2.2: raw-source candidate segmentation

T0.2 exposes **candidate raw-text segments**, not 61 verified or distinct
exegetical opinions. Its deterministic punctuation splitter does NOT infer
meaning, identify views, distinguish agreement/disagreement, or guarantee
exhaustive segmentation. Metadata remains RULE_EXTRACTED_UNVERIFIED,
interpretation_type=null, and candidate_kind=UNCLASSIFIED_TEXT_SEGMENT.

The T0.1 text field is HTML-stripped display content: its offsets are **not**
offsets into the original imported source row. To avoid falsely grounded
evidence, T0.2's private CLI reads the raw SQLite row from the *same pinned
Q0.3 database*, verifies the database digest before and after reading,
checks raw-text SHA-256 against the T0.1 imported-record digest, and
creates evidence spans in **Unicode codepoint indices of raw imported
text**. Exact UTF-8 SHA-256 fingerprints are retained per span. HTML
markup may be present inside these source-bound spans; no semantic
normalization is claimed. Text-on-hold remains withheld.

By default only safe counts, status and hashed identifiers leave the CLI:

    python -m engines.tafsir.t02_cli 2:43 --database corpus-data/linked/quran_tafsir.db

For permitted **local-only** inspection, explicitly opt in to raw
passages (this prints protected source text and must not be forwarded
to logs, CI or cloud endpoints):

    python -m engines.tafsir.t02_cli 2:43 --database corpus-data/linked/quran_tafsir.db --include-text

A real-world T0.2 candidate count **must be remeasured** after this
raw-text integrity fix; earlier 61 T0.1-display-based segments are a
historical preliminary count, not a validated output of the corrected
T0.2 logic. The local operator should run the default command above
against the actual immutable Q0.3 vault and preserve the metadata-only
receipt outside public source code.

    python -m unittest core.tests.test_tafsir_t01 core.tests.test_tafsir_t02 corpus.tests.test_query core.tests.test_quran_tafsir_metadata -v

No scholarly/source/rights gates are promoted and Mubin stays
0.1.0-alpha. Next product work: meaningful interpretation boundaries,
context and scholar-attributed disagreement **from actual source
passages**, not model comparisons.

## T0.2.3: bounded identification and unresolved relations

The T0.2.3 local pipeline uses only the Q0.3 database pinned via T0.1
and **raw-byte-verified** T0.2 passage records. It identifies lexical
candidates with named-report, anonymous report, narration, or first-person
preference cues, retaining relative passage offsets AND absolute raw-text
codepoint offsets with SHA-256 evidence digests. It does not create
standalone authenticated exegetical opinions, prove a named speaker was
correctly identified, or determine what an author ultimately endorsed.

The author-endorsement cue is strictly a **candidate** and may be wrong
when the passage itself quotes someone else's speech. A specific
statement-to-statement semantic agreement, contradiction, objection or
preference **is not asserted** by these surface cues: all relation pairs
within one passage are recorded as UNDETERMINED. Across different
passages or works, no relation is inferred.

Summary output is text-free by default:

    python -m engines.tafsir.t023_cli 2:43 --database corpus-data/linked/quran_tafsir.db

Protected candidate excerpts can be printed deliberately for allowed
private research with --include-text. Do not log or send those excerpts
to GitHub, CI or cloud services without separate use clearance.

The prior operator's original 2:43 count (61 passages, 65 candidates,
5 undetermined pairs) is a **historical unverified report from the
earlier implementation**. Because the revised logic validates the T0.2
record contract and restricts some broad lexical markers, rerun the
local pinned-vault CLI to establish the new counts; the current CI only
runs synthetic cases.

    python -m unittest core.tests.test_tafsir_t01 core.tests.test_tafsir_t02 core.tests.test_tafsir_t023 corpus.tests.test_query core.tests.test_quran_tafsir_metadata -v

This milestone advances the source-oriented Tafsir engine without
training, comparing, or tuning AI models. Mubin system version remains
0.1.0-alpha, and edition/source/rights/fiqh authority remains unverified.
