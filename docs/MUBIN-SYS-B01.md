# MUBIN-SYS-B01 — Real-code engine bridges, controlled research-only Fiqh

This incremental Wave B entry uses **existing engine functions**, not mock engine
handlers. Test data may still be synthetic; the bridge is not evidence that the
underlying corpus is authentic or that Mubin's five-engine real-source goal has
passed.

## Five operations

| Engine | Allowlisted operation | Actual existing implementation | Limit |
|---|---|---|---|
| Quran | `lookup_verse` | `QuranIndex.get` over an externally supplied SHA-pinned local snapshot | metadata digest/coordinate only, no canonical authentication |
| Tafsir | `research_verse` | `unified_research_query` T0.3, chained T0.1/T0.2/T0.2.3 | metadata/candidates; requires pinned local DB |
| Hadith | `detect_tafsir_mentions` | T0.1/T0.2 raw verification + H-Search `detect_all` | lexical narration cues **not** isnad/grade or source-wide search |
| Usul | `evaluate_proposition` | U0.1 `evaluate` one-step rule executor | engineering simulation, NOT qiyas/tarjih |
| Fiqh | `prepare_case` | F0.1 `FiqhCase`, `JuristicOpinion`, `prepare_research` | structured candidate assembly; never authorizes a juristic conclusion |

Configured `snapshot_ids` are operator-declared case pins and must match the
request exactly. The QuranIndex verifies its supplied corpus digest; the Tafsir
reader independently verifies its pinned SQLite source. A matching token does
not verify edition authenticity. No request can inject arbitrary filesystem
paths or raw Tafsir passages.

## Runner result plumbing

A dependent node receives a sealed `_upstream` list assembled from validated
direct dependency receipts: `engine`, `status`, `evidence_refs` and the
`synthetic` flag. The plan is forbidden from supplying this key itself.
Only upstream `OK` and `NO_MATCH` complete dependencies; all other
states block the dependent node. Source verse references also propagate;
Fiqh refuses to combine different Quran coordinates as one finding. Fiqh refuses to promote opinions not bound to
a directly upstream evidence reference. A fully successful *technical* Usul
simulation does not qualify the simulated rule as scholarly valid.

The current `run_case` remains per-case bounded and has no cross-process
transactional durability. Sync adapters use `asyncio.to_thread`: cancellation
cannot forcibly terminate a blocked Python thread. Production resource
isolation, durable resume, and true source-backed full E2E remain later gates.

## Verify

```bash
python -m pip install -r core/requirements-test.txt
python -m unittest discover -s evaluation/integration -v
```

## Not yet delivered

- No external source corpus bundled; real-source runtime must be tested by an
  operator using local pinned sources and independent receipts.
- Hadith H-Search candidate detection is **not** authenticated narration grading.
- No Fiqh rule synthesis, real qiyas, tarjih, or fatwa.
- No complete real-source five-engine chain. No H3.9.2 gold promotion.
- No rights/approval review in the internal engineering gate; separate release
  process applies when public publication is proposed.
