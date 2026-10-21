# U0.1 Full Waraqat Batch Coverage — chapter-first engineering

Status: ENGINEERING_SYNTHETIC_BATCH_READY after successful cross-platform CI. Real original-book W1 run is PENDING. Twenty chapters in synthetic tests do NOT prove 20 chapters in the historical W1 snapshot.

## What this replaces

The frozen W1 HTML pin is 66ec33c1825acdf82b3720f89d89aac15aa6e993356c0d90b41e53fe9a2fa044 and its UTF-8 full export pin is 9ce9de30f1af3ef32b2bf55b0473c9459e0cf530e3b557535744b284c760f4df. One [full-book inventory](../waraqat_batch.py) reads these exact sources ONCE instead of repeating Stage04 through Stage09 for each heading.

- Detect ALL literal h5 boundaries and fail closed on unexpected h5 syntax. Determine real chapter count from actual pinned HTML, never from synthetic fixtures.
- Map each heading to exact original UTF-8 byte/line coordinates. Partition entire source export: prelude plus each chapter through the end, no gaps/overlaps.
- Preserve the old Bab al-Amr golden bytes [3735,4967), 22 lines, SHA-256 20879bade7a4a831a0020e1bae51806ca015d7803be42fdb44e580a9055581ab.
- Reuse existing Stage07 Arabic retrieval and Stage08 hash-only context graph for each chapter in isolated temporary private files. No source book text is committed or returned in reports.
- A failed individual chapter is SECTION_PROCESSING_FAILED; other valid chapters continue. A failed original HTML/export root digest stops ALL processing.
- W2 is explicitly SECOND_WITNESS_COMPARISON_NOT_RUN in this pass. No W2 alignment is inferred. That independent mapping must not block clean W1 results.

## Run locally with privately pinned W1

From the project root on Windows after checking for local changes, run:

~~~powershell
cd C:\AI\Mubin
git status --short
git pull --ff-only
$root = "D:\MubinSources\waraqat"
python -m engines.usul.pilots.waraqat_full_book_batch --primary-html "$root\waraqat-original.html" --primary-export "$root\waraqat-private-utf8.txt" --queries "engines\usul\pilots\data\waraqat-stage07-queries.json" --inventory "$root\waraqat-full-w1-inventory.json" --report "$root\waraqat-full-w1-batch.json"
Write-Host "Batch exit code: $LASTEXITCODE"
~~~

The inventory JSON reports heading ordinals/hashes, every exact source byte/line range and SHA-256, full partition coverage and canonical inventory digest. The batch JSON reports per-section PASS/FAIL, exact and folded match counts, graph digests, W2 pending status and explicitly unassessed interpretation. Neither output contains original section text, source HTML, full book export or search strings.

## Independent real-source closure criteria

- Root W1 HTML and export digests verified independently.
- Every heading counted, order verified, end-boundaries exact, all source bytes covered once, legacy Bab al-Amr unchanged.
- Every section digest recomputed from the original export, a sample of occurrence positions and context digests independently recomputed; no private text leaked.
- Two successive CLI runs produce byte-identical JSON; errors are not concealed.
- Do not publish full source bytes. Commit only reviewed metadata-only closure details after an actual local run. Public CI uses synthetic data only; it cannot certify the private real-book chapter count or printed-edition accuracy.

## Work lanes

A. W1 whole book: inventory + indexing + context graphs, gate independently.

B. W2 whole book: separate HTML heading inventory and explicit section alignment. Missing W2 or an unresolved difference yields comparison pending without blocking W1.

C. Stage09 typed references: optional research lane, not a source indexing blocker.

D. Scholarship/rights: independent publication gate for semantic/legal conclusions and original edition text.

Run tests with python -m unittest discover -s engines/usul/tests -v and python -m unittest discover -s core/tests -v.

Keep project system version 0.1.0-alpha, Usul U0.1 experimental_prototype_not_qualified, Quran Q0.3 and frozen Hadith H3.9.2 unchanged. The limited public metadata preview remains independent of chapter research.
