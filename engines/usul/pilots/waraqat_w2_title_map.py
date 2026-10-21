"""Independent W2 heading-fingerprint diagnostic, optional to W1 batch success."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.usul.waraqat_w2_heading_map import map_headings


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--secondary-html", type=Path, required=True)
    p.add_argument("--w1-inventory", type=Path, required=True)
    p.add_argument("--report", type=Path, required=True)
    a=p.parse_args()
    try:
        if not a.secondary_html.is_file() or not a.w1_inventory.is_file():
            result,code={"status":"PENDING_SECONDARY_WITNESS_OR_W1_INVENTORY",
                         "source_text_included":False},3
        else:
            if not 0 < a.w1_inventory.stat().st_size <= 300000:
                raise ValueError("W1 inventory missing or oversized")
            report=json.loads(a.w1_inventory.read_text(encoding="utf-8"))
            result=map_headings(a.secondary_html.read_bytes(),report)
            code=0
    except (OSError, UnicodeError, ValueError, KeyError, TypeError) as exc:
        result,code={"status":"FAIL","reason_code":type(exc).__name__,
                     "source_text_included":False},1
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(result,ensure_ascii=False,sort_keys=True,
                                   indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"status":result["status"],
                      "candidate_pairs":result.get("pair_count"),
                      "unresolved":result.get("unresolved_count"),
                      "source_text_included":False},ensure_ascii=True))
    return code


if __name__=="__main__":
    raise SystemExit(main())
