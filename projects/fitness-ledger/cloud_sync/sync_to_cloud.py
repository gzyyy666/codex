from __future__ import annotations
import argparse
import json
from datetime import datetime
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the prepared Fitness Ledger cloud payload.")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.dry_run: raise SystemExit("Only --dry-run is supported until a cloud provider is explicitly selected.")
    path = PROJECT_DIR / "cloud_sync" / "out" / "fitness_ledger_cloud_payload.json"
    if not path.exists(): raise SystemExit("Build the payload first with build_cloud_payload.py.")
    payload = json.loads(path.read_text(encoding="utf-8"))
    print("DRY RUN: no network request was made.")
    for name, rows in payload.items(): print(f"{name}: {len(rows)}")
    report = {
        "status": "validated_local_payload",
        "network_request_made": False,
        "validated_at": datetime.now().replace(microsecond=0).isoformat(),
        "payload": str(path),
        "collections": {name: len(rows) for name, rows in payload.items()},
        "warnings": ["CloudBase provider and environment are not configured."],
    }
    report_path = path.with_name("fitness_ledger_cloud_sync_report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"report: {report_path}")

if __name__ == "__main__": main()
