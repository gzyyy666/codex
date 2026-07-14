from __future__ import annotations

import json
import tempfile
import time
from pathlib import Path
import sys

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from ledger_commands import LedgerCommandService


def write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def parsed(raw: str = "note") -> dict:
    return {"id": "pending-1", "date": "2099-01-01", "raw": raw, "body": {"weight": 70.0, "body_fat": None, "waist": None, "sleep": None, "steps": None, "context": "", "bowel_movement": "no", "training_summary": "", "cardio_summary": "", "notes": "body"}, "diet": {"food_summary": "oats", "calories": 1800, "protein": 130, "carbs": 190, "fat": 50, "notes": "diet"}, "training": {"split": "Back", "raw": "", "standardized_summary": "", "notes": "training", "movements": [{"name": "Pull-up", "movement_id": "PULL", "order": 1, "sets": [{"weight": 0, "reps": 10, "sets": 3}], "notes": "strict"}]}}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-save-") as root:
        root = Path(root); tracker = root / "tracker.json"; dictionary = root / "dictionary.json"; backups = root / "backups"
        write(tracker, {"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []})
        write(dictionary, {"version": "1", "movements": [{"movement_id": "PULL", "display_name": "Pull-up", "aliases": ["Pull-up"], "active": True}]})
        service = LedgerCommandService(tracker, dictionary, backups, lambda *_: {})
        created = service.save(parsed())
        assert created["status"] == "CREATED" and created["working_sets"] == 3
        tracker_mtime = tracker.stat().st_mtime_ns; dictionary_mtime = dictionary.stat().st_mtime_ns
        undo_count = len(list(backups.glob("undo_*.json")))
        time.sleep(.02)
        unchanged = service.save(parsed("\n note   \n\n"), "overwrite")
        assert unchanged["status"] == "NO_CHANGES"
        assert tracker.stat().st_mtime_ns == tracker_mtime and dictionary.stat().st_mtime_ns == dictionary_mtime
        assert len(list(backups.glob("undo_*.json"))) == undo_count
        stored = json.loads(tracker.read_text(encoding="utf-8")); body = stored["daily_records"][0]
        no_change = service.update_record("body", body["id"], {"Notes": " body   "})
        assert no_change["status"] == "NO_CHANGES"
        changed = service.update_record("body", body["id"], {"Notes": "changed"})
        assert changed["status"] == "UPDATED"
    print("FITNESS_LEDGER_SAVE_SEMANTICS_OK")


if __name__ == "__main__":
    main()
