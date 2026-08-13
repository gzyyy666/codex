"""Static genericity and safety assertions for the candidate extension layer."""

from __future__ import annotations

import copy
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from fitness_ledger_core.data_module_engine import DataModuleEngine, ModuleRegistry, stable_hash  # noqa: E402


ENGINE_SOURCE = (PROJECT_ROOT / "fitness_ledger_core" / "data_module_engine.py").read_text(encoding="utf-8")
for forbidden in ("waist_cm", "resting_hr", "body_fat_pct", "if module_id"):
    assert forbidden not in ENGINE_SOURCE, f"module-specific branch leaked into engine: {forbidden}"

registry = ModuleRegistry.from_file(PROJECT_ROOT / "tools" / "fixtures" / "data_modules" / "registry.json")
assert stable_hash({"b": 2, "a": 1}) == stable_hash({"a": 1, "b": 2})
assert [item.module_id for item in registry.all()] == ["waist_cm", "resting_hr"]
assert [item["module_id"] for item in registry.capability_catalog()["modules"]] == ["waist_cm", "resting_hr"]

database = {
    "data_module_records": [{
        "record_id": "orphan-1",
        "module_id": "unknown_module",
        "date": "2026-08-12",
        "value": 1,
        "definition_version": 1,
        "definition_snapshot": {},
        "private": "fixture-only",
    }]
}
engine = DataModuleEngine(registry, PROJECT_ROOT / "data" / "anonymous-candidate.json")
issues = engine.data_check(database)
assert any(issue["issue"] == "orphan module value has no definition" for issue in issues)
try:
    engine.build_cloud_payload(database)
except Exception as exc:
    assert getattr(exc, "code", "") == "MODULE_CLOUD_BLOCKED"
else:
    raise AssertionError("orphan cloud payload was not blocked")

payload = {
    "schema": "fitness-ledger-data-module-cloud-v1",
    "modules": [{"module_id": "waist_cm"}],
    "records": [{"module_id": "waist_cm", "date": "2026-08-12", "value": 82.5}],
    "meta": {},
}
payload["meta"]["collection_hashes"] = {key: stable_hash(payload[key]) for key in ("modules", "records")}
payload["meta"]["payload_hash"] = stable_hash({"modules": payload["modules"], "records": payload["records"]})
assert DataModuleEngine.verify_cloud_payload(payload)["verified"]
broken = copy.deepcopy(payload)
broken["records"][0]["raw_text"] = "private raw"
assert not DataModuleEngine.verify_cloud_payload(broken)["verified"]
print("data_module_static_test: PASS")
