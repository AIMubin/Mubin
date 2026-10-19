# Tafsir Center — private source sidecar (not a Mubin release)

The [Tafsir Center tafsir-mcp-data dataset](https://huggingface.co/datasets/tafsircenter/tafsir-mcp-data) distributes an original SQLite `quran.db` database (~214 MB according to its repository documentation). This private importer **keeps the exact database unchanged** and validates SHA-256 `10e61f615ab5e6a3440e8ecc8ba1dc2273d12cd9048752760fe53a44d191cc27` (published in their own data_loader.py). It then uses read-only SQLite to verify the five classical Arabic tafsir tables, a trilingual concise tafsir table, surah metadata, word-rasm, qira'at, and reasons of revelation; no raw content is copied to a public GitHub artifact.

The data has [LICENSE-DATA marked CC BY 4.0](https://github.com/tafsircenter/tafsir-mcp/blob/main/LICENSE-DATA) but [DATA_SOURCES.md](https://github.com/tafsircenter/tafsir-mcp/blob/main/DATA_SOURCES.md) also says commercial redistribution needs permission. These statements should be reconciled by the Mubin legal team. **This inconsistency does not block authorized internal research ingestion**; it does block an automatic claim that *Mubin has public redistribution clearance*.

Local use, on a private host: download the `quran.db` dataset file outside the public repo, check its source identity, then:

```bash
python -m qa.tafsircenter_sidecar_v01 --file /private/mubin/tafsircenter/quran.db
```

This is a **separate byte-identical sidecar**; it is not merged into the 5-source private corpus SQLite created by `qa.corpus_ingest_v01`, so neither its original schema nor tafsir text gets silently normalized. Query it with `sqlite3.connect('file:...?...mode=ro', uri=True)` in a later scoped retrieval adapter, and preserve provenance separately from QuranEnc and Tanzil. The script prints source checksums, row counts, and a research-only receipt; it never prints tafsir content.

The GitHub Actions job [Mubin Tafsir Center private sidecar verification](https://github.com/AIMubin/Mubin/actions) attempts a one-time read-only full download into runner-local storage, computes the digest and checks the database, then discards it. If this network transfer fails, other project CI and parallel engine builds are unaffected; the job's status must not be misreported as a successful import.

**Not done by this sidecar:** qualify a tafsir edition as independently verified in Mubin, resolve legal release terms, publish a fatwa, claim an alternate mushaf/qira'ah has been independently validated, or add it to P1 Gold.
