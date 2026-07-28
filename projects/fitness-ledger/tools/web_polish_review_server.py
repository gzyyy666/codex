from __future__ import annotations

import json
import sys
import tempfile
import threading
from datetime import date, timedelta
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from tools.archive_navigation_test import fixture  # noqa: E402
from web_desktop.backend.analysis_export_protocol import AnonymousFixtureProvider, AnalysisExportProtocolService  # noqa: E402
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
    start = date(2098, 11, 14)
    weights = [
        73.4, 73.2, 73.3, 73.0, 72.9, 73.1, 72.8, 72.7, 72.5, 72.6,
        72.4, 72.2, 72.3, 72.0, 71.9, 72.1, 71.8, 71.7, 71.5, 71.6,
        71.4, 71.2, 71.3, 71.0, 70.9, 71.1, 70.8, 70.7, 70.5, 70.6,
        70.4, 70.2, 70.3, 70.0, 69.9, 70.1, 69.8, 69.7, 69.5, 69.6,
        69.4, 69.2, 69.3, 69.0, 68.9, 69.1, 68.8, 68.7, 68.5, 68.6,
        68.4, 68.2, 68.3, 68.0, 67.9, 68.1,
    ]
    tracker["daily_records"] = [
        {
            "Date": (start + timedelta(days=index)).isoformat(),
            "Weight (kg)": weight,
            "Bowel Movement": "yes",
            "Training": ("Rest", "Back", "Chest", "Legs")[index % 4],
            "Cardio": "walk 20 min" if index % 3 == 0 else "none",
            "Notes": f"Anonymous review day {index + 1}.",
        }
        for index, weight in reversed(list(enumerate(weights)))
    ]


def main() -> None:
    temp = tempfile.TemporaryDirectory(prefix="fitness-ledger-web-polish-review-")
    root = Path(temp.name)
    tracker, dictionary = fixture()
    add_review_rows(tracker, dictionary)
    (root / "tracker.json").write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
    (root / "movement_dictionary.json").write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
    service = LedgerWebService(
        root / "tracker.json",
        root / "movement_dictionary.json",
        root / "backups",
        analysis_export_protocol=AnalysisExportProtocolService(AnonymousFixtureProvider()),
    )
    server = create_server(port=0, service=service)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    print(f"Fitness Ledger anonymous Web Polish review: http://127.0.0.1:{server.server_port}/#movements", flush=True)
    print("Review paths: #body, #movements, #tools?panel=export. Formal data is not loaded.", flush=True)
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
