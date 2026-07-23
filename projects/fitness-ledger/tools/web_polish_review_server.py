from __future__ import annotations

import json
import sys
import tempfile
import threading
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from tools.archive_navigation_test import fixture  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def add_review_rows(tracker: dict, dictionary: dict) -> None:
    dictionary.setdefault("movements", []).append(
        {
            "movement_id": "EXCLUDED_ONLY",
            "display_name": "Excluded Only Press",
            "english_name": "Excluded Only Press",
            "aliases": [],
            "muscle_group": "Chest",
            "active": True,
        }
    )
    tracker.setdefault("training_sessions", []).insert(
        0,
        {
            "id": "session-excluded-only",
            "Date": "2099-01-04",
            "No.": 9,
            "Split": "Chest",
            "Standardized Summary": "Excluded Only Press",
            "Notes": "This instance remains in Training Archive but is excluded from Movement Progress.",
        },
    )
    tracker.setdefault("movements", {})["excluded-only"] = {
        "movement_id": "EXCLUDED_ONLY",
        "name": "Excluded Only Press",
        "history": [
            {
                "id": "history-excluded-only-1",
                "date": "2099-01-04",
                "training_day": 9,
                "order": 1,
                "movement_id": "EXCLUDED_ONLY",
                "sets": [{"weight": 60, "weight_text": "60kg", "reps": 12, "sets": 2}],
                "notes": "Excluded review row.",
                "exclude_from_progress": True,
            }
        ],
    }
    tracker["diet_records"] = [
        {
            "Date": "2099-01-04",
            "Calories (kcal)": 2300,
            "Protein (g)": 160,
            "Carbs (g)": 260,
            "Fat (g)": 72,
            "Food Summary": "Salmon, potatoes, eggs, and fruit.",
            "Notes": "Newest row for color stability review.",
        },
        {
            "Date": "2099-01-03",
            "Calories (kcal)": 2100,
            "Protein (g)": 150,
            "Carbs (g)": 240,
            "Fat (g)": 70,
            "Food Summary": "Rice, beef, eggs, yogurt, and greens.",
            "Notes": "Long enough text to check note contrast and paper tone.",
        },
        {
            "Date": "2099-01-02",
            "Calories (kcal)": 1850,
            "Protein (g)": 130,
            "Carbs (g)": 190,
            "Fat (g)": 55,
            "Food Summary": "Noodles, chicken, vegetables, and milk.",
            "Notes": "Medium length.",
        },
        {
            "Date": "2099-01-01",
            "Calories (kcal)": 1700,
            "Protein (g)": 120,
            "Carbs (g)": 160,
            "Fat (g)": 50,
            "Food Summary": "Oats, milk, fruit, and a small dinner.",
            "Notes": "Short.",
        },
    ]
    tracker["daily_records"] = [
        {
            "Date": "2099-01-08",
            "Weight (kg)": 70.8,
            "Bowel Movement": "yes",
            "Training": "Back",
            "Cardio": "walk 20 min",
            "Notes": "Newest anonymous body record.",
        },
        {
            "Date": "2099-01-07",
            "Weight (kg)": 70.6,
            "Bowel Movement": "yes",
            "Training": "Chest",
            "Cardio": "none",
            "Notes": "Chest day with short notes.",
        },
        {
            "Date": "2099-01-06",
            "Weight (kg)": 70.5,
            "Bowel Movement": "yes",
            "Training": "Legs",
            "Cardio": "bike 30 min",
            "Notes": "Leg day body slip.",
        },
        {
            "Date": "2099-01-05",
            "Weight (kg)": 70.3,
            "Bowel Movement": "yes",
            "Training": "Shoulders",
            "Cardio": "none",
            "Notes": "Shoulder day body slip.",
        },
        {
            "Date": "2099-01-04",
            "Weight (kg)": 70.2,
            "Bowel Movement": "yes",
            "Training": "Arms",
            "Cardio": "run 15 min",
            "Notes": "Arms day body slip.",
        },
        {
            "Date": "2099-01-03",
            "Weight (kg)": 70.1,
            "Bowel Movement": "yes",
            "Training": "Rest",
            "Cardio": "none",
            "Notes": "Rest day body slip.",
        },
    ]


def main() -> None:
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-web-polish-review-")
    root = Path(temp.name)
    tracker, dictionary = fixture()
    add_review_rows(tracker, dictionary)
    (root / "tracker.json").write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
    (root / "movement_dictionary.json").write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
    service = LedgerWebService(root / "tracker.json", root / "movement_dictionary.json", root / "backups")
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Fitness Ledger anonymous Web Polish review: http://127.0.0.1:{server.server_port}/#movements", flush=True)
    print("Review paths: #movements, #training, #diet. Formal data is not loaded.", flush=True)
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
