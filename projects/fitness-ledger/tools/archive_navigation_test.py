from __future__ import annotations

import json
import re
import sys
import tempfile
import threading
import urllib.request
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from fitness_ledger_core.shared_view_models import LedgerViewModels
from web_desktop.backend.server import LedgerWebService, create_server


def fixture() -> tuple[dict, dict]:
    dictionary = {
        "movements": [
            {"movement_id": "CHEST_A", "display_name": "Bench Press", "english_name": "Bench Press", "aliases": ["Incline Bench"], "muscle_group": "Chest", "active": True},
            {"movement_id": "BACK_A", "display_name": "Pull Up", "english_name": "Pull Up", "aliases": ["Chin Up"], "muscle_group": "Back", "active": True},
            {"movement_id": "LEGS_A", "display_name": "Back Squat", "english_name": "Back Squat", "aliases": [], "muscle_group": "Legs", "active": True},
            {"movement_id": "SHOULDER_A", "display_name": "Shoulder Press", "english_name": "Shoulder Press", "aliases": [], "muscle_group": "Shoulders", "active": True},
            {"movement_id": "ARMS_A", "display_name": "Cable Curl", "english_name": "Cable Curl", "aliases": [], "muscle_group": "Arms", "active": True},
            {"movement_id": "CHEST_B", "display_name": "Bench Press", "english_name": "Other Bench", "aliases": ["Bench Variant"], "muscle_group": "Chest", "active": True},
            {"movement_id": "BACK_B", "display_name": "Cable Row", "english_name": "Cable Row", "aliases": [], "muscle_group": "Back", "active": True},
            {"movement_id": "NODATA_A", "display_name": "Legacy Raise", "english_name": "Legacy Raise", "aliases": [], "muscle_group": "Shoulders", "active": True},
        ]
    }

    def session(day: str, no: int, summary: str, notes: str = "") -> dict:
        return {"id": f"session-{no}", "Date": day, "No.": no, "Split": "Full Body", "Standardized Summary": summary, "Notes": notes}

    def history(day: str, no: int, movement: str, order: int, weight=0, reps=8, sets=3, notes: str = "", structured: bool = True) -> dict:
        row = {"id": f"history-{movement or 'unmapped'}-{no}-{order}", "date": day, "training_day": no, "order": order, "sets": [], "notes": notes}
        if movement:
            row["movement_id"] = movement
        if structured:
            row["sets"] = [{"weight": weight, "weight_text": "自重" if weight == 0 else f"{weight}kg", "reps": reps, "sets": sets}]
        return row

    complete_summary = "Bench Press；Pull Up；Back Squat；Shoulder Press；Cable Curl；Bench Variant；Cable Row"
    tracker = {
        "daily_records": [], "diet_records": [],
        "training_sessions": [
            session("2026-07-10", 1, "Bench Press"),
            session("2026-07-12", 2, "Bench Press；Shoulder Press；Cable Row", "Useful session note"),
            session("2026-07-14", 3, complete_summary, "Seven movement archive"),
            session("2026-07-13", 4, "Bench Variant；Incline Bench；Archive Carry"),
            session("2026-07-11", 5, "Archive Carry"),
        ],
        "movements": {
            "chest-a": {"movement_id": "CHEST_A", "name": "Bench Press", "history": [history("2026-07-10", 1, "CHEST_A", 1, 100), history("2026-07-12", 2, "CHEST_A", 1, 105), history("2026-07-14", 3, "CHEST_A", 1, 110, notes="Current chest note")]},
            "back-a": {"movement_id": "BACK_A", "name": "Pull Up", "history": [history("2026-07-14", 3, "BACK_A", 2, 0, reps=10)]},
            "legs-a": {"movement_id": "LEGS_A", "name": "Back Squat", "history": [history("2026-07-14", 3, "LEGS_A", 3, 120, reps=6)]},
            "shoulder-a": {"movement_id": "SHOULDER_A", "name": "Shoulder Press", "history": [history("2026-07-12", 2, "SHOULDER_A", 2, 45), history("2026-07-14", 3, "SHOULDER_A", 4, 50)]},
            "arms-a": {"movement_id": "ARMS_A", "name": "Cable Curl", "history": [history("2026-07-14", 3, "ARMS_A", 5, 20, reps=12)]},
            "chest-b": {"movement_id": "CHEST_B", "name": "Bench Variant", "history": [history("2026-07-13", 4, "CHEST_B", 1, structured=False), history("2026-07-14", 3, "CHEST_B", 6, 90)]},
            "back-b": {"movement_id": "BACK_B", "name": "Cable Row", "history": [history("2026-07-12", 2, "BACK_B", 3, 70), history("2026-07-14", 3, "BACK_B", 7, 75, notes="Keep elbows close")]},
            "nodata-a": {"movement_id": "NODATA_A", "name": "Legacy Raise", "history": [history("2026-07-11", 5, "NODATA_A", 2, structured=False)]},
            "alias": {"name": "Incline Bench", "history": [history("2026-07-13", 4, "", 2, 80)]},
            "unmapped": {"name": "Archive Carry", "history": [history("2026-07-13", 4, "", 3, 16, reps=20, notes="Unmapped but visible"), history("2026-07-11", 5, "", 1, structured=False)]},
        },
        "raw_entries": [],
    }
    return tracker, dictionary


def main() -> None:
    tracker, dictionary = fixture()
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-archive-test-") as temp:
        root = Path(temp)
        (root / "tracker.json").write_text(json.dumps(tracker, ensure_ascii=False), encoding="utf-8")
        (root / "movement_dictionary.json").write_text(json.dumps(dictionary, ensure_ascii=False), encoding="utf-8")
        views = LedgerViewModels(root / "tracker.json", root / "movement_dictionary.json")

        rows = views.training_archive()
        refs = {row["Date"]: row["movement_refs"] for row in rows}
        complete = refs["2026-07-14"]
        assert len(complete) == 7
        assert [ref["movement_id"] for ref in complete] == ["CHEST_A", "BACK_A", "LEGS_A", "SHOULDER_A", "ARMS_A", "CHEST_B", "BACK_B"]
        assert all(ref["is_linkable"] and ref["sets_lines"] for ref in complete)
        assert complete[0]["sets_lines"] == ["110kg × 8 × 3"]
        assert complete[1]["sets_lines"] == ["自重 × 10 × 3"]

        mixed = refs["2026-07-13"]
        assert [ref["movement_id"] for ref in mixed] == ["CHEST_B", "CHEST_A", ""]
        assert [ref["display_name"] for ref in mixed[:2]] == ["Bench Press", "Bench Press"]
        assert mixed[1]["is_linkable"] is True  # exact maintained alias
        assert mixed[2]["display_name"] == "Archive Carry"
        assert mixed[2]["is_linkable"] is False and mixed[2]["sets_lines"]
        assert refs["2026-07-11"][0]["is_linkable"] is False
        assert refs["2026-07-11"][0]["sets_lines"] == []

        previous = views.movement_history_by_id("CHEST_A", before_date="2026-07-14", limit=1)
        assert previous["movement"]["movement_id"] == "CHEST_A"
        assert previous["history"][0]["date"] == "2026-07-12"
        assert previous["history"][0]["sets_lines"] == ["105kg × 8 × 3"]
        assert previous["history"][0]["metrics"]["has_structured_sets"] is True
        assert views.movement_history_by_id("CHEST_A", before_date="2026-07-10")["history"] == []
        no_comparison = views.movement_history_by_id("CHEST_B", before_date="2026-07-14")
        assert no_comparison["history"][0]["date"] == "2026-07-13"
        assert no_comparison["history"][0]["metrics"]["has_structured_sets"] is False
        assert no_comparison["recent_performance"] == []
        one_comparison = views.movement_history_by_id("CHEST_B")
        assert [row["date"] for row in one_comparison["recent_performance"]] == ["2026-07-14"]
        assert one_comparison["recent_performance"][0]["change"]["max_weight"] is None
        all_missing = views.movement_history_by_id("NODATA_A")
        assert all_missing["history"] and all_missing["recent_performance"] == []
        assert views.movement_history_by_id("MISSING")["movement"] is None
        assert views.movement_history_by_id("BACK_A")["history"][0]["sets"][0]["weight_text"] == "自重"

        service = LedgerWebService(root / "tracker.json", root / "movement_dictionary.json", root / "backups")
        server = create_server(port=0, service=service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_port}"
            with urllib.request.urlopen(base + "/", timeout=3) as response:
                assert response.status == 200 and response.headers.get_content_type() == "text/html"
            for asset, content_type in (("/app.js", "text/javascript"), ("/styles.css", "text/css")):
                with urllib.request.urlopen(base + asset, timeout=3) as response:
                    assert response.status == 200 and response.headers.get_content_type() == content_type
            with urllib.request.urlopen(base + "/api/movements?limit=20", timeout=3) as response:
                assert any(item["movement_id"] == "CHEST_A" for item in json.loads(response.read().decode("utf-8")))
            with urllib.request.urlopen(base + "/api/training?limit=20", timeout=3) as response:
                training_payload = json.loads(response.read().decode("utf-8"))
            api_complete = next(row for row in training_payload if row.get("Date") == "2026-07-14")
            assert len(api_complete["movement_refs"]) == 7
            assert api_complete["movement_refs"][3]["movement_id"] == "SHOULDER_A"
            assert api_complete["movement_refs"][6]["movement_id"] == "BACK_B"
            api_unmapped = next(row for row in training_payload if row.get("Date") == "2026-07-13")["movement_refs"][2]
            assert api_unmapped["movement_id"] == "" and api_unmapped["display_name"] == "Archive Carry"
            with urllib.request.urlopen(base + "/api/movement-history?movement_id=CHEST_A&before_date=2026-07-14&limit=1", timeout=3) as response:
                history_payload = json.loads(response.read().decode("utf-8"))
            assert history_payload["movement"]["movement_id"] == "CHEST_A"
            assert history_payload["history"][0]["date"] == "2026-07-12"
            assert history_payload["history"][0]["sets_lines"] == ["105kg × 8 × 3"]
        finally:
            server.shutdown()
            server.server_close()

    app = Path(__file__).resolve().parents[1] / "web_desktop" / "frontend"
    js = (app / "app.js").read_text(encoding="utf-8")
    css = (app / "styles.css").read_text(encoding="utf-8")
    assert "data-select-movement-id" in js and "movement_id=${encodeURIComponent" in js
    assert 'data-select-movement="${' not in js and "dataset.selectMovement)" not in js
    assert "before_date" in js and "setTimeout" in js and "400" in js
    assert "history.pushState" in js and "history.replaceState" in js and "popstate" in js
    assert "openTrainingFromMovement" in js and "data-training-movement-id" in js
    assert "localStorage" not in js
    assert "data-training-date" in js and "data-training-movement-ids" in js
    assert "trainingMovementRow" in js and "Complete movement and set archive" in js
    assert "refs.slice(0,3)" not in js and "training-movement-link" not in js
    assert "currentContext" not in js and "restoreContext" not in js and "restoreScroll" not in js
    assert "No comparable structured data yet" in js and "filter(record=>record.comparable)" in js
    assert "const latest=values.at(-1)||0" not in js
    assert "Recorded without structured sets" not in js[js.rfind("loadMovementFocus=async function"):]
    assert ".movement-group.group-0 .movement-group-art" not in css
    assert re.search(r"\.movement-group\.group-core \.movement-group-art", css)
    assert ".training-movement-row.is-linkable" in css and ".training-movement-link" not in css
    assert "grid-template-columns:repeat(3,minmax(0,1fr))" in css
    assert "layoutTrainingGrid" in js and "grid-auto-flow:row dense" in css
    assert "openSaveModeDialog" in js and 'data-save-mode-choice="append_training"' in js
    assert 'data-save-mode-choice="overwrite"' in js and "save-mode-dialog" in css
    assert "renderPreviousPreview(link,payload.history||[])" in js
    print("FITNESS_LEDGER_ARCHIVE_NAVIGATION_OK")


if __name__ == "__main__":
    main()
