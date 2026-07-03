from __future__ import annotations

import json
import shutil
import sys
import tempfile
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from web_desktop.backend.server import LedgerWebService, create_server


def fetch(url: str) -> tuple[int, str, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=3) as response:
            return response.status, response.headers.get_content_type(), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get_content_type(), exc.read()


def post(url: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def main() -> None:
    project_data = PROJECT_DIR / "data"
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-web-test-") as temp:
        temp_dir = Path(temp)
        data_file = temp_dir / "tracker.json"
        dictionary_file = temp_dir / "movement_dictionary.json"
        backup_dir = temp_dir / "backups"
        shutil.copy2(project_data / "tracker.json", data_file)
        shutil.copy2(project_data / "movement_dictionary.json", dictionary_file)
        dictionary = json.loads(dictionary_file.read_text(encoding="utf-8"))
        inactive = next(item for item in dictionary["movements"] if item.get("active", True))
        inactive["active"] = False
        dictionary_file.write_text(json.dumps(dictionary, ensure_ascii=False, indent=2), encoding="utf-8")
        service = LedgerWebService(data_file, dictionary_file, backup_dir)
        server = create_server(port=0, service=service)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            for endpoint in ("/api/health", "/api/capabilities", "/api/today", "/api/recent", "/api/body", "/api/diet", "/api/training", "/api/movements", "/api/dictionary"):
                status, content_type, body = fetch(base + endpoint)
                assert status == 200, (endpoint, status)
                assert content_type == "application/json", (endpoint, content_type)
                json.loads(body.decode("utf-8"))

            capabilities = json.loads(fetch(base + "/api/capabilities")[2].decode("utf-8"))
            assert capabilities["parse"] is True
            assert capabilities["save"] is True
            assert capabilities["dictionary_admin"] is True
            movements = json.loads(fetch(base + "/api/movements?limit=200")[2].decode("utf-8"))
            assert inactive["movement_id"] not in {item["movement_id"] for item in movements}
            history = json.loads(
                fetch(base + f"/api/movement-history?name={urllib.parse.quote(inactive['display_name'])}")[2].decode("utf-8")
            )
            assert history["movement"] is None

            status, created = post(
                base + "/api/dictionary/create",
                {
                    "display_name": "测试推举",
                    "english_name": "Test Press",
                    "aliases": ["测试器械推举"],
                    "muscle_group": "Chest",
                    "category": "Strength",
                    "equipment": "Machine",
                    "notes": "Temporary integration test.",
                },
            )
            assert status == 200, created
            test_id = created["definition"]["movement_id"]
            status, updated = post(
                base + "/api/dictionary/update",
                {
                    "movement_id": test_id,
                    "definition": {
                        **created["definition"],
                        "aliases": ["测试器械推举", "测试胸推"],
                        "muscle_group": "Chest",
                    },
                },
            )
            assert status == 200, updated
            assert "测试胸推" in updated["definition"]["aliases"]
            status, toggled = post(base + "/api/dictionary/active", {"movement_id": test_id, "active": False})
            assert status == 200 and toggled["active"] is False
            movements = json.loads(fetch(base + "/api/movements?limit=500")[2].decode("utf-8"))
            assert test_id not in {item["movement_id"] for item in movements}

            inactive_raw = """2099-08-16
weight: 70.1
bowel: no
calories: 1750
protein: 125
carbs: 180
fat: 50
training: chest
1. 测试胸推
30kg x 12 x 3
cardio:
none
diet:
breakfast: oats
notes:
Inactive dictionary write test.
"""
            status, parsed_inactive = post(base + "/api/parse", {"raw": inactive_raw})
            assert status == 200, parsed_inactive
            assert parsed_inactive["review"]["training"]["movements"][0]["movement_id"] == test_id
            status, saved_inactive = post(
                base + "/api/save",
                {"review_id": parsed_inactive["review_id"], "review": parsed_inactive["review"]},
            )
            assert status == 200, saved_inactive
            stored = json.loads(data_file.read_text(encoding="utf-8"))
            test_movement = next(item for item in stored["movements"].values() if item.get("movement_id") == test_id)
            assert any(item.get("date") == "2099-08-16" for item in test_movement["history"])
            status, deleted = post(
                base + "/api/dictionary/delete",
                {"movement_id": test_id, "confirmation": "测试推举"},
            )
            assert status == 200 and deleted["deleted_history"] == 1
            stored = json.loads(data_file.read_text(encoding="utf-8"))
            assert not any(item.get("movement_id") == test_id for item in stored["movements"].values())
            assert any(item.get("date") == "2099-08-16" and item.get("text") == inactive_raw.strip() for item in stored["raw_entries"])

            status, content_type, body = fetch(base + "/")
            assert status == 200
            assert content_type == "text/html"
            assert b"Fitness Ledger Web" in body

            raw = """2099-08-15
weight: 70.2
bowel: no
calories: 1800
protein: 130
carbs: 190
fat: 52
training: back
1. Pull-up
bodyweight x 10 x 2
cardio:
none
diet:
breakfast: oats
notes:
Web shared service test.
"""
            status, parsed = post(base + "/api/parse", {"raw": raw})
            assert status == 200, parsed
            assert parsed["review"]["raw"] == raw.strip()
            assert parsed["review_id"]

            status, saved = post(
                base + "/api/save",
                {"review_id": parsed["review_id"], "review": parsed["review"]},
            )
            assert status == 200, saved
            assert saved["ok"] is True
            stored = json.loads(data_file.read_text(encoding="utf-8"))
            assert any(item.get("date") == "2099-08-15" and item.get("text") == raw.strip() for item in stored["raw_entries"])
            assert list(backup_dir.glob("undo_tracker_*.json"))
            assert list(backup_dir.glob("undo_dictionary_*.json"))

            status, duplicate = post(base + "/api/parse", {"raw": raw})
            assert status == 200
            status, conflict = post(
                base + "/api/save",
                {"review_id": duplicate["review_id"], "review": duplicate["review"]},
            )
            assert status == 409, conflict
            assert conflict["code"] == "duplicate_date"
        finally:
            server.shutdown()
            server.server_close()
    print("FITNESS_LEDGER_WEB_SHARED_WRITE_OK")


if __name__ == "__main__":
    main()
