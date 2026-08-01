"""Regression coverage for the formal read-only movement projection."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fitness_ledger_core.formal_readonly_data_source import FormalReadOnlyDataSource


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    configured = os.environ.get("FITNESS_LEDGER_FORMAL_DIR", "").strip()
    if not configured:
        raise RuntimeError("FITNESS_LEDGER_FORMAL_DIR is required")
    data_root = Path(configured).expanduser().resolve() / "data"
    tracker = data_root / "tracker.json"
    dictionary = data_root / "movement_dictionary.json"
    before = (_sha256(tracker), _sha256(dictionary))

    provider = FormalReadOnlyDataSource(tracker, dictionary)
    request = {
        "request_version": "1.1",
        "purpose": "Verify formal movement projection",
        "datasets": [
            {
                "dataset_id": "movement_progress_01",
                "type": "movement_progress",
                "time_range": {"mode": "all_available"},
                "filters": {
                    "movement_selector": {
                        "kind": "movement_id",
                        "value": "BACK_001",
                    }
                },
                "fields": [
                    "date",
                    "movement_id",
                    "movement_name",
                    "body_part",
                    "variant",
                    "order",
                    "sets",
                ],
                "notes_scope": "movement",
            }
        ],
        "raw": False,
        "output": {"formats": ["json"]},
    }
    bundle = provider.materialize(request)
    assert bundle["manifest"]["record_count"] == 13
    assert all(item["movement_id"] == "BACK_001" for item in bundle["records"])
    assert (_sha256(tracker), _sha256(dictionary)) == before
    print("FORMAL_READONLY_EXPORT_BINDING_OK")


if __name__ == "__main__":
    main()
