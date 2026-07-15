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
            {"movement_id": "CHEST_B", "display_name": "Bench Press", "english_name": "Other Bench", "aliases": ["Bench Variant"], "muscle_group": "Chest", "active": True},
            {"movement_id": "BACK_A", "display_name": "Pull Up", "english_name": "Pull Up", "aliases": ["Chin Up"], "muscle_group": "Back", "active": True},
        ]
    }
    def session(day: str, no: int, movement: str) -> dict:
        return {"id": f"session-{no}", "Date": day, "No.": no, "Split": "Chest", "Standardized Summary": "Bench Press", "Notes": ""}
    def history(day: str, no: int, movement: str, weight, reps=8) -> dict:
        return {"id": f"history-{movement}-{no}", "movement_id": movement, "date": day, "training_day": no, "order": 1, "sets": [{"weight": weight, "weight_text": "自重" if weight == 0 else f"{weight}kg", "reps": reps, "sets": 3}], "notes": "long note must not enter preview"}
    tracker = {
        "daily_records": [], "diet_records": [],
        "training_sessions": [session("2026-07-10", 1, "CHEST_A"), session("2026-07-12", 2, "CHEST_A"), session("2026-07-14", 3, "CHEST_A"), session("2026-07-13", 4, "CHEST_B")],
        "movements": {
            "a": {"movement_id": "CHEST_A", "history": [history("2026-07-10", 1, "CHEST_A", 100), history("2026-07-12", 2, "CHEST_A", 105), history("2026-07-14", 3, "CHEST_A", 110)]},
            "b": {"movement_id": "CHEST_B", "history": [history("2026-07-13", 4, "CHEST_B", 90)]},
            "back": {"movement_id": "BACK_A", "history": [history("2026-07-11", 5, "BACK_A", 0, 10)]},
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
        assert refs["2026-07-10"][0]["movement_id"] == "CHEST_A"
        assert refs["2026-07-13"][0]["movement_id"] == "CHEST_B"
        assert refs["2026-07-13"][0]["display_name"] == "Bench Press"
        assert {ref["movement_id"] for ref in refs["2026-07-13"]} == {"CHEST_B"}

        previous = views.movement_history_by_id("CHEST_A", before_date="2026-07-14", limit=1)
        assert previous["movement"]["movement_id"] == "CHEST_A"
        assert previous["history"][0]["date"] == "2026-07-12"
        assert views.movement_history_by_id("CHEST_A", before_date="2026-07-10")["history"] == []
        assert views.movement_history_by_id("CHEST_B", before_date="2026-07-14")["history"][0]["date"] == "2026-07-13"
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
            assert any(row["movement_refs"][0]["movement_id"] == "CHEST_B" for row in training_payload if row.get("Date") == "2026-07-13")
            with urllib.request.urlopen(base + "/api/movement-history?movement_id=CHEST_A&before_date=2026-07-14&limit=1", timeout=3) as response:
                history_payload = json.loads(response.read().decode("utf-8"))
            assert history_payload["movement"]["movement_id"] == "CHEST_A"
            assert history_payload["history"][0]["date"] == "2026-07-12"
        finally:
            server.shutdown()
            server.server_close()

    app = Path(__file__).resolve().parents[1] / "web_desktop" / "frontend"
    js = (app / "app.js").read_text(encoding="utf-8")
    css = (app / "styles.css").read_text(encoding="utf-8")
    assert "data-select-movement-id" in js and "movement_id=${encodeURIComponent" in js
    assert "before_date" in js and "setTimeout" in js and "400" in js
    assert "history.pushState" in js and "history.replaceState" in js and "popstate" in js
    assert "openTrainingFromMovement" in js and "data-training-movement-id" in js
    assert "localStorage" not in js
    assert "data-training-date" in js and "data-training-movement-ids" in js
    assert ".movement-group.group-0 .movement-group-art" not in css
    assert re.search(r"\.movement-group\.group-core \.movement-group-art", css)
    print("FITNESS_LEDGER_ARCHIVE_NAVIGATION_OK")


if __name__ == "__main__":
    main()
