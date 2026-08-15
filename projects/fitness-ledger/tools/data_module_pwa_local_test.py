from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1]
if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from mobile_viewer.app import create_app  # noqa: E402
from mobile_viewer.data_access import LedgerDataAccess  # noqa: E402


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-pwa-modules-") as temp:
        root = Path(temp)
        tracker = root / "tracker.json"
        dictionary = root / "movement_dictionary.json"
        registry = root / "data_module_definitions.json"
        write_json(tracker, {
            "daily_records": [],
            "diet_records": [],
            "training_sessions": [],
            "movements": {},
            "raw_entries": [],
            "data_module_records": [{
                "record_id": "waist-1",
                "module_id": "waist_cm",
                "category_id": "body",
                "record_kind": "scalar",
                "date": "2026-08-15",
                "value": 82.5,
                "actual_unit": "cm",
                "definition_version": 1,
                "definition_snapshot": {},
                "source_raw_hash": "must-not-leak",
                "raw_text": "private input",
                "notes": "private note",
            }],
        })
        write_json(dictionary, {"version": "1.0", "movements": []})
        registry.write_bytes((PROJECT / "tools" / "fixtures" / "data_modules" / "registry.json").read_bytes())

        app = create_app(LedgerDataAccess(tracker, dictionary), registry)
        client = app.test_client()
        response = client.get("/api/pwa/read?action=dataModules")
        assert response.status_code == 200
        payload = response.get_json()
        assert payload["ok"] is True
        contract = payload["data"]
        assert contract["schema"] == "fitness-ledger-mini-module-contract-v1"
        waist = next(item for item in contract["modules"] if item["module_id"] == "waist_cm")
        assert waist["latest"]["value"] == 82.5
        serialized = json.dumps(contract, ensure_ascii=False)
        for forbidden in ("must-not-leak", "private input", "private note", "definition_snapshot"):
            assert forbidden not in serialized

        page = client.get("/pwa/")
        assert page.status_code == 200
        assert b"data-modules.js?v=20260815-01" in page.data
        local_config = client.get("/pwa/config.js")
        assert local_config.status_code == 200
        assert b"requireWebAuth: false" in local_config.data
        assert b"apiBaseUrl: '/api'" in local_config.data
        print("DATA_MODULE_PWA_LOCAL_OK")


if __name__ == "__main__":
    main()
