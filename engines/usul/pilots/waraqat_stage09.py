"""U0.1 Stage09 — al-Waraqat research-only typed reference proposal runner.

Does not mutate P0 or issue rulings. Requires a separately pinned exact
Stage08 graph SHA and an existing valid P0 bundle with exact quoted excerpt
and source digest correspondence. Private input bytes stay local.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from engines.usul.typed_evidence_binding import bind_exact_observations

WARAQAT_STAGE08_GRAPH_SHA256 = "72ca6bd80c4e70378dd9d2f1cfc75841024b292d2335479d167add1a8ca6fdb2"
RUNNER = "waraqat-stage09-typed-reference/0.1.0"


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for key in ("stage08-graph", "p0-bundle", "proposals", "report"):
        p.add_argument("--" + key, type=Path, required=True)
    args = p.parse_args()
    try:
        inputs = (args.stage08_graph, args.p0_bundle, args.proposals)
        if not all(f.is_file() for f in inputs):
            result, code = {
                "status": "PENDING_STAGE09_SOURCE_BINDING_INPUTS",
                "scholarly_verified": False, "source_text_included": False,
            }, 3
        else:
            jsons = []
            for file in inputs:
                length = file.stat().st_size
                if not 0 < length <= 2_000_000:
                    raise ValueError("Stage09 input is empty/oversized")
                jsons.append(json.loads(file.read_text(encoding="utf-8")))
            graph, p0_bundle, proposals = jsons
            result = bind_exact_observations(
                graph, WARAQAT_STAGE08_GRAPH_SHA256, p0_bundle, proposals
            )
            result["runner"] = RUNNER
            result["local_source_replay_executed_here"] = False
            code = 0
    except (ValueError, OSError, UnicodeError, KeyError, TypeError) as exc:
        result, code = {
            "status": "FAIL", "reason_code": type(exc).__name__,
            "scholarly_verified": False, "source_text_included": False,
        }, 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({"status": result["status"], "report": str(args.report)},
                     ensure_ascii=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
