from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from cloud_sync.build_cloud_payload import build_optional_data_module_collections, resolve_source_files
from cloud_sync.sync_to_cloud import validate_payload
from fitness_ledger_core.cloud_payload import build_cloud_payload
from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore, DataModuleEngine
from fitness_ledger_core.shared_view_models import LedgerViewModels


def main() -> None:
    tracker, dictionary = resolve_source_files()
    registry = PROJECT / "tools" / "fixtures" / "data_modules" / "registry.json"
    old_registry = os.environ.get("FITNESS_LEDGER_DATA_MODULE_REGISTRY")
    try:
        os.environ["FITNESS_LEDGER_DATA_MODULE_REGISTRY"] = str(registry)
        extension = build_optional_data_module_collections(tracker, dictionary)
        assert extension is not None
        assert set(extension) == {"fl_data_modules", "fl_data_module_records", "fl_data_module_contract"}
        assert {item["module_id"] for item in extension["fl_data_modules"]} == {"waist_cm", "resting_hr"}
        assert extension["fl_data_module_contract"][0]["schema"] == "fitness-ledger-mini-module-contract-v1"
        payload = build_cloud_payload(
            LedgerViewModels(tracker, dictionary),
            data_module_collections=extension,
        )
        assert payload["fl_meta"][0]["extensions"] == ["data-modules-v1"]
        serialized = json.dumps(payload, ensure_ascii=False).lower()
        assert '"raw_text"' not in serialized
        assert '"source_raw_hash"' not in serialized
        assert '"private"' not in serialized
        with tempfile.TemporaryDirectory(prefix="fitness-ledger-mini-extension-") as temp:
            temp_tracker = Path(temp) / "tracker.json"
            tracker_payload = json.loads(tracker.read_text(encoding="utf-8"))
            tracker_payload["data_module_records"] = [{
                "record_id": "waist-1",
                "module_id": "waist_cm",
                "category_id": "body",
                "record_kind": "scalar",
                "date": "2026-08-12",
                "value": 82.5,
                "actual_unit": "cm",
                "definition_version": 1,
                "definition_snapshot": {"secret": "must-not-leave"},
                "source_raw_hash": "secret-hash",
                "raw_text": "腰围 82.5 cm",
                "private": "private note",
                "notes": "private note",
            }]
            temp_tracker.write_text(json.dumps(tracker_payload, ensure_ascii=False), encoding="utf-8")
            store = DataModuleDefinitionStore(registry)
            categories, modules, issues = store.load(strict=True)
            mini = DataModuleEngine(modules, temp_tracker, dictionary, category_registry=categories, definition_issues=issues).build_mini_program_contract()
            mini_text = json.dumps(mini, ensure_ascii=False).lower()
            assert "secret-hash" not in mini_text and "private note" not in mini_text and "definition_snapshot" not in mini_text
            assert mini["modules"][0]["history"][0]["value"] == 82.5
        subprocess.run([sys.executable, str(PROJECT / "cloud_sync" / "build_cloud_payload.py")], check=True, env=os.environ.copy())
        report = validate_payload()
        assert report["status"] == "DRY_RUN"
        assert report["network_request_made"] is False
        print("FITNESS_LEDGER_DATA_MODULE_CLOUD_EXTENSION_OK")
    finally:
        if old_registry is None:
            os.environ.pop("FITNESS_LEDGER_DATA_MODULE_REGISTRY", None)
        else:
            os.environ["FITNESS_LEDGER_DATA_MODULE_REGISTRY"] = old_registry


if __name__ == "__main__":
    main()
