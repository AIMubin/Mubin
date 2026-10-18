# Quran Engine — Q0.1 verse snapshot lookup (draft, not qualified)

System-wide `Mubin` release stays `0.1.0-alpha`. The main branch currently advertises `Q0.0`; Q0.1 lives in a separate PR until merged and verified.

The Q0.1 code reads a **caller-supplied, raw-SHA-256-pinned, UTF-8 JSON verse snapshot** and supports stable numbered verse lookup and bounded substring search. No live network calls, scraped Quran text, tafsir, training corpora or rights claims are included. The committed four-entry fixture contains **invented Arabic test phrases**; it is **not** Quranic text. Do not display it to end users as scripture.

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s core/tests -p 'test_quran_q01.py' -v
python -m engines.quran.q01 --manifest engines/quran/fixtures/q01-manifest-synthetic.json --corpus engines/quran/fixtures/q01-verses-synthetic.json --json verify
python -m engines.quran.q01 --manifest engines/quran/fixtures/q01-manifest-synthetic.json --corpus engines/quran/fixtures/q01-verses-synthetic.json --json get 1:1
python -m engines.quran.q01 --manifest engines/quran/fixtures/q01-manifest-synthetic.json --corpus engines/quran/fixtures/q01-verses-synthetic.json --json find 'سلام' --match arabic_marks_insensitive
```

Exit 0 = internally valid snapshot/query completed; 1 = invalid corpus or argument; 2 = inaccessible/unsafe input. **None grants edition/authenticity/permission status.** A checksum computed from an arbitrary malicious copy can be made internally consistent; independent provenance is a separate P1 gate. Use the same file bytes and official pinned provider release for meaningful external validation.

See `docs/research/QURAN-Q01-SNAPSHOT-INTEGRITY.md` for source candidates, licensing, scope, and future ingestion.
