from __future__ import annotations

import argparse
import json
import sys
import tempfile
import threading
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from web_desktop.backend.server import LedgerWebService, create_server  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def review_fixture() -> tuple[dict, dict]:
    movement_id = "REVIEW_INCLINE_PRESS"
    partner_id = "REVIEW_PUSHDOWN"
    sessions = []
    cases = [
        ("2026-09-14", 4, [{"segments": [{"weight": 10, "reps": 8}, {"weight": 7.5, "reps": 6}], "sets": 2}], False),
        ("2026-09-12", 3, [{"weight": 90, "reps": 12, "sets": 3}], True),
        ("2026-09-10", 2, [{"weight": 20, "reps": 10, "sets": 2}], False),
        ("2026-09-08", 1, [{"segments": [{"weight": 7.5, "reps": 6}, {"weight": 5, "reps": 8}], "sets": 3}], False),
    ]
    for session_date, day_number, press_sets, is_superset in cases:
        session_id = f"review-session-{session_date}"
        press_instance = f"press-{day_number}"
        movement_items = [{
            "id": press_instance,
            "movement_instance_id": press_instance,
            "movement_id": movement_id,
            "display_name": "Incline Press",
            "date": session_date,
            "training_day": day_number,
            "order": 1,
            "order_in_session": 1,
            "sets": press_sets,
            "training_session_id": session_id,
        }]
        session = {
            "id": session_id,
            "No.": day_number,
            "Date": session_date,
            "Split": "Chest",
            "Standardized Summary": "Incline Press" + ("; Triceps Pushdown" if is_superset else ""),
            "Notes": "Anonymous chart review fixture",
            "movement_items": movement_items,
        }
        if is_superset:
            partner_instance = f"pushdown-{day_number}"
            session["organization_relations"] = [{"id": f"review-superset-{day_number}", "type": "superset", "label": "A", "members": [press_instance, partner_instance]}]
            movement_items.append({
                "id": partner_instance,
                "movement_instance_id": partner_instance,
                "movement_id": partner_id,
                "display_name": "Triceps Pushdown",
                "date": session_date,
                "training_day": day_number,
                "order": 2,
                "order_in_session": 2,
                "sets": [{"weight": 30, "reps": 12, "sets": 3}],
                "training_session_id": session_id,
            })
        sessions.append(session)
    tracker = {
        "daily_records": [],
        "diet_records": [],
        "raw_entries": [],
        "movements": {},
        "training_sessions": sessions,
        "training_organization": {"session_themes": [], "movement_categories": []},
    }
    dictionary = {
        "version": "1.0",
        "movements": [
            {"movement_id": movement_id, "display_name": "Incline Press", "english_name": "Incline Press", "aliases": [], "muscle_group": "Chest", "active": True},
            {"movement_id": partner_id, "display_name": "Triceps Pushdown", "english_name": "Triceps Pushdown", "aliases": [], "muscle_group": "Arms", "active": True},
        ],
    }
    return tracker, dictionary


def main() -> None:
    parser = argparse.ArgumentParser(description="Start an isolated movement chart review with anonymous fixtures.")
    parser.add_argument("--port", type=int, default=0, help="default: allocate an available local port")
    args = parser.parse_args()
    runtime = tempfile.TemporaryDirectory(prefix="fitness-ledger-movement-chart-review-")
    root = Path(runtime.name)
    tracker_data, dictionary_data = review_fixture()
    tracker_file = root / "tracker.json"
    dictionary_file = root / "movement_dictionary.json"
    write_json(tracker_file, tracker_data)
    write_json(dictionary_file, dictionary_data)

    fixture_history = LedgerViewModels(tracker_file, dictionary_file).movement_history_by_id("REVIEW_INCLINE_PRESS")["progress_history"]
    assert [row["metrics"]["volume"] for row in fixture_history] == [250.0, 3240.0, 400.0, 255.0], fixture_history
    assert all(row["metrics"]["has_structured_sets"] for row in fixture_history), fixture_history
    assert fixture_history[1]["organization_relations"][0]["type"] == "superset", fixture_history[1]

    service = LedgerWebService(
        tracker_file,
        dictionary_file,
        root / "backups",
        build_info_override={
            "mode": "ANONYMOUS MOVEMENT CHART REVIEW",
            "status": "PREVIEW",
            "review_fixture": "complex-volume-line-with-superset-exclusion",
            "formal_data_used": False,
            "cloud_mutation": False,
            "mini_publish": False,
        },
    )
    server = create_server("127.0.0.1", args.port, service)
    url = f"http://127.0.0.1:{server.server_address[1]}/#movements"
    print(f"Anonymous movement-chart review: {url}", flush=True)
    print("Review chart: open Incline Press; expected max-weight line 7.5, 20, 10 kg and capacity bars 255, 400, 250 kg-reps.", flush=True)
    print("Hover/click a chart point to inspect both metrics and open its matching Training record.", flush=True)
    print("Review return: enter Incline Press from Movement Progress and Training; the detail back control should restore that exact parent route and scroll position.", flush=True)
    print("A direct detail link without an in-app parent falls back to Movement Progress; Sep 12 superset is excluded from both chart metrics.", flush=True)
    print("This server uses temporary synthetic data only. Stop with Ctrl+C.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        runtime.cleanup()


if __name__ == "__main__":
    main()
