from __future__ import annotations
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))
from fitness_ledger_core.cloud_payload import build_cloud_payload
from fitness_ledger_core.shared_view_models import LedgerViewModels

def main() -> Path:
    views = LedgerViewModels(PROJECT_DIR / "data" / "tracker.json", PROJECT_DIR / "data" / "movement_dictionary.json")
    payload = build_cloud_payload(views)
    output = PROJECT_DIR / "cloud_sync" / "out" / "fitness_ledger_cloud_payload.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(output)
    for name, rows in payload.items(): print(f"{name}: {len(rows)}")
    return output

if __name__ == "__main__": main()
