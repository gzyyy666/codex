"""Write a Review Evidence package from an existing structured artifact.

This utility intentionally refuses to infer missing runtime stages from
Markdown.  The real acceptance runner supplies the structured results; this
wrapper is only for already projected artifacts or an explicit blocked state.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.intelligent_export_review_evidence import assemble_bundle, write_review_index


def _blocked(reason: str) -> dict:
    return {
        "review_schema_version": "fitness-ledger-review-evidence-v1.0",
        "review_status": "blocked",
        "request_evidence": [],
        "stability_evidence": [],
        "integrity_audit": {"passed": False, "blocking_integrity_codes": ["REVIEW_EXECUTION_IDS_MISSING"], "reason": reason},
        "privacy_audit": {"passed": True, "violations": []},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="")
    ap.add_argument("--output", default="")
    args = ap.parse_args()
    output = Path(args.output) if args.output else Path(tempfile.gettempdir()) / ("fitness-ledger-intelligent-export-review-" + datetime.now().strftime("%Y%m%d-%H%M%S"))
    output.mkdir(parents=True, exist_ok=True)
    raw = json.loads(Path(args.results).read_text(encoding="utf-8")) if args.results else None
    if isinstance(raw, dict) and "request_evidence" in raw and "stability_evidence" in raw:
        bundle = assemble_bundle(raw.get("request_evidence", []), raw.get("stability_evidence", []))
    else:
        bundle = _blocked("No structured runtime Review Evidence was supplied; Markdown inference is not allowed.")
    (output / "summary.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "integrity-audit.json").write_text(json.dumps(bundle["integrity_audit"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "privacy-audit.json").write_text(json.dumps(bundle["privacy_audit"], ensure_ascii=False, indent=2), encoding="utf-8")
    (output / "README.md").write_text("# Intelligent Export Review Evidence\n\n仅接受结构化 Review Evidence；不从 Markdown 反向猜测 Intent、候选、Selection 或 Execution。\n", encoding="utf-8")
    write_review_index(bundle, output)
    print(str(output))


if __name__ == "__main__":
    main()
