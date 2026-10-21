# W2 Bab al-Amr: three historical byte lengths

State: **PRIVATE REPLAY REQUIRED**. This note documents code-level causes;
it does not amend, silently supersede or recertify earlier private receipts.

Three recorded sizes refer to different representations:

| Representation | Reported bytes | Evidence / code path |
| --- | ---: | --- |
| Stage 06 isolated chapter | 1,702 | HTMLParser adds line breaks on closing block tags, writes UTF-8 bytes |
| Pre-hardening full-book W2 file on Windows | 1,706 | Commit 6dfd5e0 uses Path.write_text(), which translates LF to CRLF on Windows |
| Hardened full-book W2 file | 1,696 | Commit 12d5262 uses Path.write_bytes(), preserving LF UTF-8 serialization |

1706 - 1696 = 10 bytes: compatible with ten LF linefeeds stored as CRLF.
1702 - 1696 = 6 bytes: compatible with Stage06 emitting six extra LF line
separators. These are **mechanistic hypotheses until checked against the
privately frozen HTML**. Byte-length arithmetic is not proof of unchanged
word boundaries or content.

## Replay all three implementations

From the repository root, using the privately pinned W2 source:

    $root = "D:\MubinSources\waraqat"
    python -m engines.usul.pilots.waraqat_w2_representation_audit --raw-html "$root\witness2-original.html" --out "$root\w2-three-representations.audit.json"
    if ($LASTEXITCODE -ne 0) { throw "Three-view representation audit did not pass" }

This script replays Stage06, the 6dfd5e0 content-slicing algorithm plus
Windows write_text newline translation, and the hardened full-book
extractor. It checks historical byte sizes (1702/1706/1696), pinned HTML
SHA-256, identical nonempty lines, unchanged whitespace-delimited tokens,
and equality of all nonwhitespace Unicode codepoints. A merged word
boundary is a FAIL even if the compact strings match. Output JSON contains
only metadata, SHA-256 hashes and boolean results, never original source text.

If successful, record the output SHA-256 and status in a supplemental
metadata-only receipt. Keep previous receipts immutable; PR stays Draft
until explicit approval. No private source, extracted text or raw diffs may
enter GitHub.

If the audit fails, do not call differences formatting-only. Identify whether
the failed property reflects HTML extraction, missing paragraph delimiters,
or storage encoding. The full-book converter strips closing paragraph tags
without adding a separator, which can merge words and MUST NOT be assumed
benign. Add a test before fixing the affected extractor and rerun private
witness extraction and comparison.

All scholarly/rights/semantic qualification flags remain false regardless
of audit outcome.
