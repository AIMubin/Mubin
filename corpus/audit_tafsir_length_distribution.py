"""Read-only per-source text-length distribution audit for tafsir SQLite.

Identifies suspicious source-specific limits; numerical limits are NOT by
themselves proof of truncation, edition identity or missing material.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import sqlite3

SOURCES = ("tabary", "katheer", "baghawy", "saadi", "moyassar")
BOUNDARIES = (32767, 65535)


def analyze(path):
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(path)
    conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only=ON")
        reports = {}
        for source in SOURCES:
            lengths = [row[0] for row in conn.execute(
                "SELECT LENGTH(text) FROM tafsirs WHERE source=?", (source,))]
            if not lengths:
                raise ValueError(f"No tafsir rows for {source}")
            count = Counter(lengths)
            reports[source] = {
                "rows": len(lengths),
                "maximum_codepoints": max(lengths),
                "boundary_counts": {str(x): count[x] for x in BOUNDARIES},
                "above_32767": sum(v for k, v in count.items() if k > 32767),
                "above_65535": sum(v for k, v in count.items() if k > 65535),
            }
        return {
            "status": "DIAGNOSTIC_ONLY",
            "metric": "SQLite LENGTH(text), Unicode codepoints (not UTF-8 bytes)",
            "summary": reports,
            "baghawy_specific_32767_ceiling_observed":
                reports["baghawy"]["maximum_codepoints"] == 32767
                and reports["baghawy"]["boundary_counts"]["32767"] > 0
                and any(reports[s]["above_32767"] > 0 for s in SOURCES if s != "baghawy"),
            "scholarly_verified": False,
            "note": "Source-specific cutoff evidence; the precise upstream software step responsible is unknown.",
        }
    finally:
        conn.close()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--database", type=Path, default=Path("corpus-data/linked/quran_tafsir.db"))
    p.add_argument("--report", type=Path, default=Path("corpus-data/linked/tafsir-length-distribution.json"))
    a = p.parse_args()
    result = analyze(a.database)
    a.report.parent.mkdir(parents=True, exist_ok=True)
    a.report.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
