"""One-command, fixture-only scenarios for human review of the candidate."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.data_module_engine import DataModuleEngine, ModuleRegistry  # noqa: E402
from ledger_commands import LedgerCommandService  # noqa: E402


REGISTRY_FILE = PROJECT_ROOT / "tools" / "fixtures" / "data_modules" / "registry.json"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-data-module-scenarios-") as temp:
        root = Path(temp)
        tracker = root / "tracker.json"
        dictionary = root / "movement_dictionary.json"
        backups = root / "backups"
        write_json(tracker, {
            "daily_records": [{"Date": "2026-08-12", "Weight (kg)": 70}],
            "diet_records": [],
            "training_sessions": [],
            "movements": {},
            "raw_entries": [],
            "data_module_records": [],
        })
        write_json(dictionary, {"version": "1.0", "movements": []})
        service = LedgerCommandService(tracker, dictionary, backups, lambda *_args: {}, REGISTRY_FILE)

        before = tracker.read_bytes()
        preview = service.data_module_preview("2026-08-12 腰围 82.5 cm")
        assert preview["write_attempted"] is False
        assert tracker.read_bytes() == before

        saved = service.data_module_save(preview, confirmed=True)
        waist_history = service.data_module_history("waist_cm")

        second_preview = service.data_module_preview("2026-08-13 静息心率 62 bpm")
        service.data_module_save(second_preview, confirmed=True)

        registry = ModuleRegistry.from_file(REGISTRY_FILE)
        current, renamed = registry.preview_update(
            "waist_cm",
            {
                "label": "腰围记录",
                "aliases": ["腰围记录", "waist record"],
                "category_id": "extension",
                "status": "retired",
                "capabilities": {"recordable": False},
            },
        )
        retired_registry = registry.clone()
        retired_registry.replace_fixture_definition(renamed)
        retired_engine = DataModuleEngine(retired_registry, tracker, dictionary, backups, service)
        retired_history = retired_engine.history("waist_cm")
        retired_preview = {
            "schema": "fitness-ledger-data-module-preview-v1",
            "status": "preview_ready",
            "write_attempted": False,
            "raw_text": "2026-08-14 腰围 83 cm",
            "candidates": [{
                "module_id": "waist_cm",
                "date": "2026-08-14",
                "value": 83,
                "raw_text": "2026-08-14 腰围 83 cm",
            }],
            "source_fingerprint": retired_engine._fingerprint(),
        }
        try:
            retired_engine.save_preview(retired_preview, confirmed=True)
        except Exception as exc:
            blocked_code = getattr(exc, "code", "UNKNOWN")
        else:
            blocked_code = "NOT_BLOCKED"

        cloud = service.data_module_cloud_payload()
        output = {
            "fixture": "anonymous temporary fixture",
            "formal_write": False,
            "A_preview": {
                "status": preview["status"],
                "write_attempted": preview["write_attempted"],
                "candidate_module_ids": [item["module_id"] for item in preview["candidates"]],
            },
            "B_confirm_history": {
                "save_status": saved["status"],
                "record_id": waist_history["latest"]["record_id"],
                "history_count": len(waist_history["history"]),
            },
            "C_second_module": {
                "module_id": "resting_hr",
                "same_engine": True,
                "record_count": len(service.data_module_export()["records"]),
            },
            "D_schema_evolution": {
                "stable_module_id": current.module_id == renamed.module_id,
                "version_before": current.definition_version,
                "version_after": renamed.definition_version,
                "history_visible_after_retire": bool(retired_history["history"]),
                "new_record_blocked_code": blocked_code,
                "formal_registry_written": False,
            },
            "E_downstream": {
                "normal_export_records": len(service.data_module_export()["records"]),
                "analysis_visible": [item["module_id"] for item in service.data_module_analysis_catalog()["modules"]],
                "analysis_hidden": service.data_module_analysis_catalog()["hidden_module_ids"],
                "cloud_payload_hash": cloud["meta"]["payload_hash"],
                "cloud_network_request_made": cloud["meta"]["network_request_made"],
                "cloud_roundtrip_verified": service.data_module_cloud_verify(cloud)["verified"],
                "mini_renderers": service.data_module_mini_contract()["renderers"],
            },
        }
        assert output["D_schema_evolution"]["stable_module_id"]
        assert output["D_schema_evolution"]["history_visible_after_retire"]
        assert output["D_schema_evolution"]["new_record_blocked_code"] == "MODULE_NOT_RECORDABLE"
        assert output["E_downstream"]["cloud_roundtrip_verified"]
        print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
