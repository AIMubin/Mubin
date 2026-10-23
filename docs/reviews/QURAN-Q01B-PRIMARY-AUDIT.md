# Q0.1b — Maintainer-first primary source and adversarial audit

**Date:** 2026-10-18.
**Reviewed implementation HEAD:** `97b9e662b1744a60c74c2bb29bc2c4cb2745aff1`.
**Dependency:** Q0.1b [PR #74](https://github.com/AIMubin/Mubin/pull/74) is stacked on still-unmerged [Q0.1 PR #73](https://github.com/AIMubin/Mubin/pull/73) at `2bd3e164c7a2f6d294da19bb5509418489ff7a80`. Global version is `0.1.0-alpha`; no main merge/release and no H3.9.2 holdout changes.

## Material advance — genuine 6236-row engineering source

For the first time the Q0.1 parser is exercised against a complete Quran-text candidate, not just invented Arabic test strings. CI retrieves **exact original bytes** into temporary GitHub Actions runner storage, never into this Git repository or a downloadable Actions artifact, from:

- Non-official GitHub mirror `acfatah/tanzil`, immutable source commit `052b515f3a24dfacbe4cafc3b89f0681a447f462`;
- `data/quran-uthmani.txt`, Git blob SHA-1 `f2f03c415ea50f8493d2058ec67a90257333abe3`;
- exact 1,396,677 bytes, locally enumerated 6,236 `surah|ayah|verbatim-text` rows;
- exact SHA-256 `f64fe7657dbe2e185e9995e14f7a67ee6cf1a30773f39184883d7a763d70fb19`.

Both raw SHA-256 (external data identity, independently recomputed by GitHub runner) and Git blob SHA-1 over the same original bytes are checked before opening the in-memory index. Also verify strict 114-surah/6,236-ayah Hafs/Kufan coordinate topology, no duplicates/out-of-order records, original Tanzil footer license text in the **unmodified raw file**, exact text lookup, and query-only combining-mark search.

**This is a mirrored candidate, not Tanzil publisher authentication.** [Tanzil official download](https://tanzil.net/pub/download/index.php) and [terms](https://tanzil.net/docs/Text_License) establish announced v1.1 availability and requirements to copy the text verbatim, credit Tanzil, link to Tanzil and preserve the copyright notice. We were **unable to download and attest the precisely configured original Tanzil export bytes directly** during this stage. Third-party `acfatah` states its copy is from Tanzil but that assertion is not proof of unmodified original. Another investigated project, `nuqayah/quran-text`, explicitly documents orthographic changes, and is **not** treated as an original unmodified Tanzil copy.

The permitted use of the **specific third-party mirror** (including its fidelity to Tanzil non-change terms) remains independently unreviewed. `rights_verified=false`; `source_authenticated=false`; `official_tanzil_bytes_independently_verified=false`; `eligible_for_religious_ruling=false` are fixed in every validation, get and find report. Passing checksum or complete numeric coverage does not elevate them.

## Security/integrity review

- **No hidden online runtime:** The Python CLI only reads explicitly supplied local regular files with a per-file byte budget. The **separate** CI workflow uses an exact immutable raw.githubusercontent.com commit URL and time/size-bounded HTTPS curl download into runner temporary storage. It never pushes or checks in Quran source bytes. Use per-source and per-purpose rights inspection before any public full-text redistribution.
- **No permissive corpus conversion:** The file is neither rewritten as a new Quran JSON corpus nor normalized in persistent storage. Line ending and BOM deviations are rejected. Search folding is an in-memory comparison only, with the retrieved Unicode text exactly as stored.
- **Fail-closed authenticity claims:** External mirror identity, immutable commit, Git blob ID, SHA-256, size, expected reading and coverage are pinned. Attempted rights/source promotion and manifest extra fields fail. Tampering cannot pass by updating a self-declared SHA-256 alone because the Git blob is independently fixed in implementation.
- **Security regressions:** Symlinks/nonregular/oversized input, malformed source lines, duplicate/out-of-order verses, illegal coordinates, injected source notes, query-only Arabic diacritics, unsafe Unicode strings, fake complete-coverage and wrong SHA/commit/URL fail. Manifest exposed to caller is immutable.
- **Residual constraints:** Leaf symlink checks and read-through-open descriptor do not establish a global trusted file system, remote repository custodianship, stable official release, legal redistribution permission, scripture authenticity, or full tafsir/fiqh verification. Python does not independently validate Arabic grapheme correctness. A deliberate network attack causing download failure simply closes this CI gate; no source is silently substituted.

## RED → GREEN GitHub audit trail

1. **TDD RED before implementation:** test-only commit `4f7701b692242c3c0d7254031987405f467e26ee`, [P0 run 39123317781](https://github.com/AIMubin/Mubin/actions/runs/39123317781) failed with expected `ModuleNotFoundError: engines.quran.q01b` (73 tests, one import error).
2. **First implementation** `3b2f3838a4f4d6703e70a584a6513fa673a435e7`, [Q0.1b run 39123425912](https://github.com/AIMubin/Mubin/actions/runs/39123425912): 88 tests, two test failures and one reader input error; both Q0.1 and P0 CI also failed due to shared core tests. Root causes were Path subclass handling, acceptance of extra blank lines in synthetic input, and a false negative test assumption about appending a valid verse to a partial fixture.
3. **Correction** `6853ece02732f56d5843b54848690444cce576a3`: [Q0.1b run 39123527520](https://github.com/AIMubin/Mubin/actions/runs/39123527520) failed one newly introduced partial-fixture extension test because its Python literal contained a backslash+n rather than newline. The test harness expected syntactically valid raw lines, so this was corrected without reducing any real-source pin/coverage gate.
4. **Repaired HEAD `97b9e662b1744a60c74c2bb29bc2c4cb2745aff1`:** [Q0.1b run 39123594230](https://github.com/AIMubin/Mubin/actions/runs/39123594230), [Q0.1 run 39123594182](https://github.com/AIMubin/Mubin/actions/runs/39123594182), [P0 run 39123594217](https://github.com/AIMubin/Mubin/actions/runs/39123594217), all **success**. Q0.1b executes **89/89 cumulative tests**, successfully downloads the real 1,396,677-byte mirror source at pinned GitHub commit and independently confirms SHA-256, prints exact 114 / 6,236 index coverage, retrieves `2:1` (with source's original basmala prefix) and `114:6` with original Unicode text.

The final audit-doc commit **requires new exact-head CI checks**; preceding successes may not be reused to assert final HEAD green.

## Authority boundary and unblock rule

`codex_review=unavailable` for this cycle due to previous documented quota exhaustion. Additional threat-model and reproducible failures above are a **maintainer-only** engineering review, not independent scientific certification.

**No human or AI scholarly approval, fatwa authority, or text-source legal permission has been inferred.** The actual source not being independently verified does not prevent parallel work on search, UI, tafsir source boundaries or P1 receipts; it only blocks calling a publicly redistributed source authoritative.

Next Q0.1c: independently retrieve the precisely configured *official* Tanzil release (or an independently authenticated King Fahd Quran Complex export), record the official source checksum and usage rights for intended operations, run source-to-source collision/variant diagnostics, and use a separate allowlist to promote source authority **without changing the original bytes**. Any Quranic interpretation must stay distinct from plain verse lookup.
