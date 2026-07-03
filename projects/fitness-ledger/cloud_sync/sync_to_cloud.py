from __future__ import annotations
import argparse
import json
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

if __name__ == "__main__": main()
