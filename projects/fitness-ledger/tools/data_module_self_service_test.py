"""Full self-service persistence, restart, negative, and genericity candidate test."""

from __future__ import annotations

import hashlib
import json
import secrets
import subprocess
import sys
import tempfile
from unittest.mock import patch
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore, DataModuleError, DataModuleEngine, ModuleDefinition, ModuleRegistry  # noqa: E402
from ledger_commands import LedgerCommandError, LedgerCommandService  # noqa: E402


REGISTRY_FILE = PROJECT_ROOT / "tools" / "fixtures" / "data_modules" / "registry.json"


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    tracker = root / "tracker.json"
    dictionary = root / "movement_dictionary.json"
    backups = root / "backups"
    store = root / "data_module_definitions.json"
    write_json(tracker, {"daily_records": [{"Date": "2026-08-12", "Weight (kg)": 70}], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": [], "data_module_records": []})
    write_json(dictionary, {"version": "1.0", "movements": []})
    DataModuleDefinitionStore.initialize(store, REGISTRY_FILE, backup_dir=backups / "definitions")
    return tracker, dictionary, backups, store


def service(paths: tuple[Path, Path, Path, Path]) -> LedgerCommandService:
    tracker, dictionary, backups, store = paths
    return LedgerCommandService(tracker, dictionary, backups, lambda *_args: {}, store)


def save_definition(commands: LedgerCommandService, preview: dict) -> dict:
    assert preview["write_attempted"] is False
    return commands.data_module_definition_save(preview, confirmed=True)


def phase_a(root: Path) -> dict:
    paths = fixture(root)
    commands = service(paths)
    _tracker, _dictionary, _backups, store_path = paths
    category_token = secrets.token_hex(5)
    category_label = f"Runtime Category {category_token}"
    category_id = f"runtime_category_{category_token}"
    module_token = secrets.token_hex(5)
    label_a = f"Runtime Metric {module_token} A"
    alias_a = f"runtime alias {module_token} a"
    label_b = f"Runtime Metric {module_token} B"
    alias_b = f"runtime alias {module_token} b"

    before_store = store_path.read_bytes()
    category_preview = commands.data_module_definition_preview({"kind": "category", "action": "create", "values": {"category_id": category_id, "label": category_label, "order": 800}})
    assert store_path.read_bytes() == before_store
    save_definition(commands, category_preview)

    category_update = commands.data_module_definition_preview({
        "kind": "category",
        "action": "update",
        "category_id": category_id,
        "changes": {"category_id": category_id, "label": f"Renamed {category_label}", "order": 801, "presentation": {"template": "extension", "semantic": "summary"}},
    })
    save_definition(commands, category_update)
    updated_category = next(item for item in commands.data_module_catalog()["categories"] if item["category_id"] == category_id)
    assert updated_category["definition_version"] == 2
    assert len(updated_category["definition_history"]) == 1
    assert updated_category["label"].startswith("Renamed")
    try:
        commands.data_module_definition_preview({"kind": "category", "action": "update", "category_id": category_id, "changes": {"category_id": "different_category"}})
    except Exception as exc:
        assert getattr(exc, "code", "") == "CATEGORY_ID_IMMUTABLE"
    else:
        raise AssertionError("category ID was mutable")

    try:
        commands.data_module_definition_preview({"kind": "category", "action": "create", "values": {"category_id": category_id, "label": "Duplicate"}})
    except Exception as exc:
        assert getattr(exc, "code", "") == "CATEGORY_ID_DUPLICATE"
    else:
        raise AssertionError("duplicate category was not rejected")

    common = {"category_id": category_id, "data_type": "quantity", "actual_unit": "bpm", "display_unit": "bpm", "minimum": 20, "maximum": 240, "renderer": "single_metric", "section": "extension", "slot": "summary", "order": 810}
    module_a_preview = commands.data_module_definition_preview({"kind": "module", "action": "create", "values": {**common, "label": label_a, "aliases": [alias_a]}})
    assert module_a_preview["write_attempted"] is False
    module_a_id = next(item["module_id"] for item in module_a_preview["after"]["modules"] if item["label"] == label_a)
    save_definition(commands, module_a_preview)
    module_a_definition = next(item for item in commands.data_module_catalog()["modules"] if item["module_id"] == module_a_id)
    assert module_a_definition["capabilities"] == {
        "recordable": True,
        "queryable": True,
        "history_enabled": True,
        "exportable": True,
        "analysis_visible": False,
        "cloud_syncable": False,
        "mini_program_visible": False,
    }
    try:
        commands.data_module_definition_preview({"kind": "module", "action": "update", "module_id": module_a_id, "changes": {"module_id": "different_module"}})
    except Exception as exc:
        assert getattr(exc, "code", "") == "MODULE_ID_IMMUTABLE"
    else:
        raise AssertionError("module ID was mutable")
    try:
        commands.data_module_definition_preview({"kind": "module", "action": "update", "module_id": module_a_id, "changes": {"actual_unit": "ms"}})
    except Exception as exc:
        assert getattr(exc, "code", "") == "MODULE_ACTUAL_UNIT_MIGRATION_REQUIRED"
    else:
        raise AssertionError("actual unit changed without migration gate")
    module_b_preview = commands.data_module_definition_preview({"kind": "module", "action": "create", "values": {**common, "label": label_b, "aliases": [alias_b], "renderer": "metric_history", "capabilities": {"analysis_visible": True, "cloud_syncable": True, "mini_program_visible": True}}})
    module_b_id = next(item["module_id"] for item in module_b_preview["after"]["modules"] if item["label"] == label_b)
    save_definition(commands, module_b_preview)

    try:
        commands.data_module_definition_preview({"kind": "module", "action": "create", "values": {**common, "label": "Collision", "aliases": [alias_a]}})
    except Exception as exc:
        assert getattr(exc, "code", "") == "MODULE_ALIAS_CONFLICT"
    else:
        raise AssertionError("duplicate alias was not rejected")
    negative_store_baseline = store_path.read_bytes()
    for bad_values, expected in [
        ({**common, "label": "Bad Range", "minimum": 300, "maximum": 20}, "MODULE_VALIDATION_RANGE_INVALID"),
        ({**common, "label": "Bad Unit", "actual_unit": "bpm?"}, "MODULE_UNIT_INVALID"),
        ({**common, "label": "Bad Behaviour", "recording_kind": "session"}, "MODULE_RECORDING_BEHAVIOR_NOT_IMPLEMENTED"),
        ({**common, "label": "Bad Renderer", "renderer": "freeform"}, "MODULE_RENDERER_UNSUPPORTED"),
        ({**common, "label": "Bad Placement", "slot": "unknown"}, "MODULE_PRESENTATION_INVALID"),
        ({**common, "label": "Coordinate Placement", "presentation": {"x": 10}}, "MODULE_PRESENTATION_INVALID"),
    ]:
        try:
            commands.data_module_definition_preview({"kind": "module", "action": "create", "values": bad_values})
        except Exception as exc:
            assert getattr(exc, "code", "") == expected, (expected, getattr(exc, "code", ""))
        else:
            raise AssertionError(f"negative definition case was not rejected: {expected}")
        assert store_path.read_bytes() == negative_store_baseline

    record_preview = commands.data_module_preview(f"2026-08-12 {alias_a} 58 bpm")
    assert record_preview["write_attempted"] is False
    commands.data_module_save(record_preview, confirmed=True)
    module_a = commands.data_module_catalog()["modules"]
    module_a_record = commands.data_module_history(module_a_id)["latest"]
    rename_preview = commands.data_module_definition_preview({"kind": "module", "action": "update", "module_id": module_a_id, "changes": {"label": f"Renamed {label_a}", "aliases": [f"new {alias_a}"], "category_id": "extension", "renderer": "metric_history", "slot": "history", "order": 820}})
    save_definition(commands, rename_preview)
    retired_preview = commands.data_module_definition_preview({"kind": "module", "action": "retire", "module_id": module_a_id})
    save_definition(commands, retired_preview)
    retired_engine = commands.data_module_engine()
    assert retired_engine.history(module_a_id)["history"]
    retired_record_preview = {"schema": "fitness-ledger-data-module-preview-v1", "status": "preview_ready", "write_attempted": False, "raw_text": "2026-08-13 new 59", "candidates": [{"module_id": module_a_id, "date": "2026-08-13", "value": 59}], "source_fingerprint": retired_engine._fingerprint()}
    try:
        retired_engine.save_preview(retired_record_preview, confirmed=True)
    except DataModuleError as exc:
        assert exc.code == "MODULE_NOT_RECORDABLE"
    else:
        raise AssertionError("retired module accepted a new record")

    retire_category = commands.data_module_definition_preview({"kind": "category", "action": "retire", "category_id": category_id})
    save_definition(commands, retire_category)
    try:
        commands.data_module_definition_preview({"kind": "module", "action": "create", "values": {**common, "label": "Blocked by retired category", "category_id": category_id}})
    except Exception as exc:
        assert getattr(exc, "code", "") == "CATEGORY_NOT_RECORDABLE"
    else:
        raise AssertionError("module creation was allowed in a retired category")
    save_definition(commands, commands.data_module_definition_preview({"kind": "category", "action": "re_enable", "category_id": category_id}))

    valid_payload = json.loads(store_path.read_text(encoding="utf-8"))
    valid_payload["modules"].append({"module_id": "invalid module id", "label": "Corrupt module"})
    corrupt_isolated = root / "partially_corrupt_definitions.json"
    write_json(corrupt_isolated, valid_payload)
    isolated_categories, isolated_modules, isolated_issues = DataModuleDefinitionStore(corrupt_isolated).load(strict=False)
    assert category_id in {item.category_id for item in isolated_categories.all()}
    assert module_b_id in {item.module_id for item in isolated_modules.all()}
    assert any(issue["issue"] == "MODULE_ID_INVALID" for issue in isolated_issues)
    fully_corrupt = root / "fully_corrupt_definitions.json"
    fully_corrupt.write_text("{not-json", encoding="utf-8")
    _empty_categories, _empty_modules, corrupt_issues = DataModuleDefinitionStore(fully_corrupt).load(strict=False)
    assert any(issue["issue"] == "DEFINITION_STORE_CORRUPT" for issue in corrupt_issues)
    try:
        DataModuleDefinitionStore(fully_corrupt).load(strict=True)
    except DataModuleError as exc:
        assert exc.code == "DEFINITION_STORE_CORRUPT"
    else:
        raise AssertionError("strict corruption detection did not fail")

    rollback_baseline = store_path.read_bytes()
    rollback_preview = commands.data_module_definition_preview({"kind": "module", "action": "update", "module_id": module_b_id, "changes": {"label": f"Rollback Probe {module_b_id}"}})
    try:
        with patch("fitness_ledger_core.data_module_engine._write_json_atomic", side_effect=OSError("simulated definition write failure")):
            commands.data_module_definition_save(rollback_preview, confirmed=True)
    except LedgerCommandError as exc:
        assert exc.code == "DEFINITION_SAVE_FAILED"
    else:
        raise AssertionError("simulated definition write failure was not raised")
    assert store_path.read_bytes() == rollback_baseline

    cloud = commands.data_module_cloud_payload()
    assert module_a_id not in {item["module_id"] for item in cloud["modules"]}
    assert module_b_id in {item["module_id"] for item in cloud["modules"]}
    assert commands.data_module_cloud_verify(cloud)["verified"]
    assert module_b_id in {item["module_id"] for item in commands.data_module_mini_contract()["modules"]}
    return {"store": str(store_path), "category_id": category_id, "category_label": category_label, "module_a_id": module_a_id, "module_b_id": module_b_id, "label_a": label_a, "alias_a": alias_a, "alias_b": alias_b, "record_id": module_a_record["record_id"], "source_hash": hashlib.sha256(store_path.read_bytes()).hexdigest()}


def phase_b(root: Path, expected: dict) -> dict:
    paths = (root / "tracker.json", root / "movement_dictionary.json", root / "backups", root / "data_module_definitions.json")
    commands = service(paths)
    catalog = commands.data_module_catalog()
    assert expected["category_id"] in {item["category_id"] for item in catalog["categories"]}
    renamed = next(item for item in catalog["modules"] if item["module_id"] == expected["module_a_id"])
    assert renamed["label"].startswith("Renamed")
    assert renamed["presentation"]["slot"] == "history"
    assert commands.data_module_history(expected["module_a_id"])["latest"]["record_id"] == expected["record_id"]
    new_preview = commands.data_module_preview(f"2026-08-13 {expected['alias_b']} 61 bpm")
    commands.data_module_save(new_preview, confirmed=True)
    assert commands.data_module_history(expected["module_b_id"])["latest"]["value"] == 61
    return {"persisted": True, "module_count": len(catalog["modules"]), "record_count": len(commands.data_module_export()["records"]), "new_alias_recognized": True}


def main() -> None:
    if len(sys.argv) == 3:
        phase, root = sys.argv[1], Path(sys.argv[2])
        result = phase_a(root) if phase == "a" else phase_b(root, json.loads((root / "phase_a.json").read_text(encoding="utf-8")))
        if phase == "a":
            (root / "phase_a.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False))
        return
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-self-service-") as temp:
        root = Path(temp)
        phase_a_process = subprocess.run([sys.executable, str(Path(__file__)), "a", str(root)], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        phase_b_process = subprocess.run([sys.executable, str(Path(__file__)), "b", str(root)], cwd=PROJECT_ROOT, capture_output=True, text=True, check=True)
        phase_a_result = json.loads(phase_a_process.stdout)
        phase_b_result = json.loads(phase_b_process.stdout)
        assert phase_b_result["persisted"]
        print(json.dumps({"process_a": phase_a_result, "process_b": phase_b_result, "process_restart": True, "process_ids_distinct": True}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
