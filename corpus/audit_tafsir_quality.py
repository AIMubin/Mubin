"""Find misleading 'nonempty' tafsir entries; never edits the source corpus.

HTML-only records are a demonstrable retrieval gap. Exact 32767-character
boundaries are *possible* truncation, not proof until source comparison.
"""
import argparse
import json
import sqlite3
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

SOURCES = ("tabary", "katheer", "baghawy", "saadi", "moyassar")


class _TextOnly(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)


def plaintext(value):
    parser = _TextOnly()
    parser.feed(value)
    parser.close()
    return "".join(parser.parts).strip()


def audit(path):
    db = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        db.execute("PRAGMA query_only = ON")
        reports = {}
        issues = []
        for source in SOURCES:
            rows = db.execute("SELECT sura,aya,text FROM tafsirs WHERE source=? ORDER BY sura,aya", (source,)).fetchall()
            stats = Counter()
            stats["rows"] = len(rows)
            for sura, aya, content in rows:
                value = content if isinstance(content, str) else ""
                if not value.strip():
                    stats["sql_empty"] += 1
                    issues.append({"source": source, "verse_id": f"{sura}:{aya}", "issue": "SQL_EMPTY"})
                elif not plaintext(value):
                    stats["markup_only"] += 1
                    issues.append({"source": source, "verse_id": f"{sura}:{aya}", "issue": "MARKUP_ONLY"})
                if len(value) == 32767:
                    stats["length_32767"] += 1
                    issues.append({"source": source, "verse_id": f"{sura}:{aya}",
                                   "issue": "POSSIBLE_TRUNCATION_32767"})
                if '<br' in value.lower():
                    stats["contains_br_tag"] += 1
            reports[source] = dict(sorted(stats.items()))
        return {
            "status": "REQUIRES_EDITORIAL_REVIEW" if issues else "NO_HEURISTIC_FLAGS",
            "verified_textual_completeness": False,
            "summary": reports,
            "review_queue": issues,
            "notes": [
                "HTML-only text is empty for plain-text retrieval but may denote continuation across verses.",
                "32767 characters is a truncation indicator, not proof of truncation.",
                "Editor/publisher/volume/page provenance is not attested by this database."
            ]
        }
    finally:
        db.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--database", type=Path, default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--report", type=Path, default=Path("corpus-data/linked/tafsir-quality.json"))
    args = p.parse_args()
    result = audit(args.database)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
