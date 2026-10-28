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
