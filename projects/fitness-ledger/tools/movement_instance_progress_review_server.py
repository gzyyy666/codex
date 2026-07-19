from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402

REVIEW_RAW = """2099-01-05
weight: 70.0
bowel: yes
calories: 1900
protein: 140
carbs: 200
fat: 60
training: chest
1. Bench Press
100kg x 8 x 3
2. Bench Press
60kg x 12 x 2
3. Mystery Movement
bodyweight x 10 x 2
cardio:
none
diet:
anonymous review meal
notes:
Instance-level progress review fixture.
"""


def write_fixture(root: Path) -> None:
    (root / "tracker.json").write_text(json.dumps({
        "daily_records": [], "diet_records": [], "training_sessions": [],
        "movements": {}, "raw_entries": [],
    }, ensure_ascii=False), encoding="utf-8")
    (root / "movement_dictionary.json").write_text(json.dumps({
        "version": "1.0", "movements": [{
            "movement_id": "CHEST_001", "display_name": "Bench Press",
            "english_name": "Bench Press", "aliases": ["Bench Press"],
            "muscle_group": "Chest", "active": True,
        }],
    }, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-instance-progress-review-")
    root = Path(temp.name)
    write_fixture(root)
    service = LedgerWebService(root / "tracker.json", root / "movement_dictionary.json", root / "backups")
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Fitness Ledger anonymous instance-progress review: http://127.0.0.1:{server.server_port}/#quick", flush=True)
    print("Review flow:", flush=True)
    print("1. Parse & Review the sample below.", flush=True)
    print("2. Keep the first Bench Press included; turn off the second Bench Press.", flush=True)
    print("3. Choose the raw-only option for Mystery Movement.", flush=True)
    print("4. Confirm & Save; open Training and verify both Bench Press instances remain.", flush=True)
    print("5. Toggle the second instance back on from the Training archive.", flush=True)
    print("6. Open Bench Press trajectory, edit the first history row, and test the same switch.", flush=True)
    print("Daily Entry sample:", flush=True)
    print(REVIEW_RAW, flush=True)
    try:
        thread.join()
    except KeyboardInterrupt:
        pass
    finally:
        server.shutdown()
        server.server_close()
        temp.cleanup()


if __name__ == "__main__":
    main()
