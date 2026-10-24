# Q0.1f engineering extraction — evidence and limits

**Extraction origin:** the former mixed-scope [PR #76](https://github.com/AIMubin/Mubin/pull/76) contained bibliographic metadata, Q0.1e, official-domain probes, Chrome E2E, private-sidecar and corpus-import work. This extraction cherry-picks **no** unrelated original history; files are selectively recreated on current main after #89 and #90 merged.

## Review checklist

- Metadata contract is strict and rejects fabricated editions, text imports, rights claims, P1 admission and unknown fields.
- JSON parsing is bounded to 16 KiB with duplicate-key detection; no remote catalog requests.
- Runtime loader verifies original Q0.1b byte-pinned mirror (and disallows synthetic material) before returning a navigation-only catalog; no display or claim of a scholarly verification.
- Browser uses `textContent`, no `innerHTML`/HTML interpolation, no embedded iframe or automatic KSU fetch; external URLs must exactly match the KSU fragment template.
- User-facing labels distinguish Quranic source bytes, candidate bibliography, and AI analysis disabled. Any KSU site visit is a **user-triggered external navigation**.
- Adversarial tests cover unknown/extra source claims, illegal references, duplicate JSON keys, external domain injection, and synthetic-source HTTP denial.
- Source rights, publisher authenticity, book editions, the historical Q0.3 corpus, and theological interpretation are **outside scope**.

**Review/CI result:** pending latest extracted-HEAD workflow and independent code review. This file does not reuse or promote the original #76 historical approval statements.
