"""Anonymous contract and v1.1 closure tests for the request protocol."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_export_request import validate_json, validate_request

SCHEMA_ROOT = ROOT / "schemas"
EXAMPLE_ROOT = ROOT / "docs" / "experiments" / "evidence" / "analysis_export_request_examples"


def load(name: str) -> dict:
    return json.loads((EXAMPLE_ROOT / name).read_text(encoding="utf-8"))


def assert_rejected(value: dict, code: str) -> None:
    result = validate_request(value)
    assert not result.valid, result.to_dict()
    assert code in {item.code for item in result.errors}, result.to_dict()


def base_request() -> dict:
    return load("01_recent_28_days_body.json")


def test_schema_contract() -> None:
    request_schema = json.loads((SCHEMA_ROOT / "analysis_export_request_v1.schema.json").read_text(encoding="utf-8"))
    bundle_schema = json.loads((SCHEMA_ROOT / "analysis_export_bundle_v1.schema.json").read_text(encoding="utf-8"))
    assert request_schema["properties"]["request_version"] == {"const": "1.1"}
    assert request_schema["properties"]["raw"] == {"const": False}
    assert request_schema["additionalProperties"] is False
    assert {item["$ref"] for item in request_schema["properties"]["datasets"]["items"]["oneOf"]} == {
        "#/$defs/body_dataset",
        "#/$defs/diet_dataset",
        "#/$defs/training_dataset",
        "#/$defs/movement_dataset",
    }
    selector_defs = request_schema["$defs"]["movement_selector"]["oneOf"]
    assert [item["properties"]["kind"]["const"] for item in selector_defs] == [
        "movement_id", "movement_name", "body_part"
    ]
    assert selector_defs[0]["properties"]["value"]["pattern"] == "^[A-Za-z0-9_.:-]+$"
    assert request_schema["$defs"]["movement_dataset"]["properties"]["set_roles"]["items"]["enum"] == [
        "top", "working", "backoff"
    ]
    assert bundle_schema["properties"]["request"]["$ref"] == "analysis_export_request_v1.schema.json"
    assert bundle_schema["properties"]["safety_flags"]["$ref"] == "#/$defs/safety_flags"


def test_examples() -> None:
    names = sorted(path.name for path in EXAMPLE_ROOT.glob("*.json"))
    assert len(names) == 10, names
    for name in names[:9]:
        result = validate_request(load(name))
        assert result.valid, (name, result.to_dict())
        assert result.normalized_request["raw"] is False
        assert result.preview["execution"] == {"executor_called": False, "formal_data_written": False}
    raw = validate_request(load("10_raw_unauthorized.json"))
    assert not raw.valid
    assert any(item.code == "RAW_PERMISSION_REQUIRED" for item in raw.errors)
    assert raw.preview["raw"] == {"requested": True, "allowed": False, "status": "rejected"}


def test_v11_closure_regressions() -> None:
    # 1. Every dataset has a stable, unique identifier.
    request = base_request()
    request["datasets"].append({
        "dataset_id": "diet_recent",
        "type": "diet",
        "time_range": {"mode": "recent_days", "days": 7},
        "filters": {},
        "fields": ["date", "calories_kcal"],
    })
    assert validate_request(request).valid
    duplicate = base_request()
    duplicate["datasets"].append(dict(duplicate["datasets"][0]))
    assert_rejected(duplicate, "DUPLICATE_DATASET_ID")

    # 2. The dependency must target a training dataset and supports each match.
    dependency = base_request()
    dependency["datasets"][0]["dataset_id"] = "training_target"
    dependency["datasets"][0]["type"] = "training"
    dependency["datasets"][0]["time_range"] = {"mode": "recent_days", "days": 3}
    dependency["datasets"][0]["filters"] = {"split": "chest"}
    dependency["datasets"][0]["fields"] = ["date", "split"]
    dependency["datasets"].append({
        "dataset_id": "diet_before_training",
        "type": "diet",
        "time_range": {
            "mode": "days_before_target_session", "days_before": 3,
            "target_dataset_id": "training_target", "match_mode": "each_matching_session",
            "include_target_session_day": False,
        },
        "filters": {}, "fields": ["date", "calories_kcal"],
    })
    assert validate_request(dependency).valid
    explicit_target = load("02_recent_14_days_diet.json")
    explicit_target["datasets"][0]["time_range"] = {
        "mode": "days_before_target_session", "days_before": 1,
        "target_date": "2026-07-15", "match_mode": "single_latest_matching_session",
        "include_target_session_day": True,
    }
    assert validate_request(explicit_target).valid
    both_targets = json.loads(json.dumps(explicit_target))
    both_targets["datasets"][0]["time_range"]["target_dataset_id"] = "training_target"
    assert_rejected(both_targets, "TARGET_REFERENCE_EXCLUSIVE")
    date_each = json.loads(json.dumps(explicit_target))
    date_each["datasets"][0]["time_range"]["match_mode"] = "each_matching_session"
    assert_rejected(date_each, "MATCH_MODE_REQUIRES_DATASET")

    bad_target = json.loads(json.dumps(dependency))
    bad_target["datasets"][1]["time_range"]["target_dataset_id"] = "missing_training"
    assert_rejected(bad_target, "UNKNOWN_TARGET_DATASET")
    non_training_target = json.loads(json.dumps(dependency))
    non_training_target["datasets"][0]["type"] = "diet"
    non_training_target["datasets"][0]["filters"] = {}
    assert_rejected(non_training_target, "TARGET_DATASET_NOT_TRAINING")

    # 3. A single selector is authoritative; legacy parallel keys are rejected.
    movement = load("04_movement_progress_known_name.json")
    assert validate_request(movement).valid
    legacy_filter = json.loads(json.dumps(movement))
    legacy_filter["datasets"][0]["filters"]["movement_name"] = "bench_press"
    assert_rejected(legacy_filter, "UNKNOWN_PROPERTY")
    for kind in ("movement_id", "movement_name", "body_part"):
        selected = json.loads(json.dumps(movement))
        selected["datasets"][0]["filters"]["movement_selector"] = {"kind": kind, "value": "chest"}
        assert validate_request(selected).valid

    # 4. Set-role labels are constrained to the three protocol roles.
    roles = json.loads(json.dumps(movement))
    roles["datasets"][0]["set_roles"] = ["top", "working", "backoff"]
    assert validate_request(roles).valid
    bad_role = json.loads(json.dumps(roles))
    bad_role["datasets"][0]["set_roles"] = ["warmup"]
    assert_rejected(bad_role, "UNKNOWN_SET_ROLE")
    non_movement_roles = base_request()
    non_movement_roles["datasets"][0]["set_roles"] = ["top"]
    assert_rejected(non_movement_roles, "UNKNOWN_PROPERTY")

    # 5. Per-dataset notes_scope is the only authoritative Notes expression.
    notes = load("07_training_notes_scope.json")
    assert validate_request(notes).valid
    old_notes = json.loads(json.dumps(notes))
    old_notes["datasets"][0]["include_notes"] = True
    assert_rejected(old_notes, "UNKNOWN_PROPERTY")
    top_notes = json.loads(json.dumps(notes))
    top_notes["notes_scope"] = ["training"]
    assert_rejected(top_notes, "UNKNOWN_PROPERTY")
    wrong_notes = json.loads(json.dumps(notes))
    wrong_notes["datasets"][0]["notes_scope"] = "diet"
    assert_rejected(wrong_notes, "NOTES_SCOPE_DATASET_MISMATCH")

    # 6. latest_matching_sessions is deliberately restricted to session datasets.
    latest_diet = base_request()
    latest_diet["datasets"][0]["type"] = "diet"
    latest_diet["datasets"][0]["time_range"] = {"mode": "latest_matching_sessions", "sessions": 3}
    latest_diet["datasets"][0]["fields"] = ["date", "calories_kcal"]
    assert_rejected(latest_diet, "TIME_MODE_NOT_SUPPORTED_FOR_DATASET")

    # 7. V3's explicit all-history scope is supported by every data domain.
    all_history = load("04_movement_progress_known_name.json")
    all_history["datasets"][0]["time_range"] = {"mode": "all_available"}
    assert validate_request(all_history).valid
    all_body = base_request()
    all_body["datasets"][0]["time_range"] = {"mode": "all_available"}
    assert validate_request(all_body).valid

    # 8. Raw remains closed even when every other field is valid.
    raw = base_request()
    raw["raw"] = True
    assert_rejected(raw, "RAW_PERMISSION_REQUIRED")


def test_boundary_rules() -> None:
    unknown_type = base_request(); unknown_type["datasets"][0]["type"] = "sleep"
    assert_rejected(unknown_type, "UNKNOWN_DATASET_TYPE")
    unknown_field = base_request(); unknown_field["datasets"][0]["fields"] = ["date", "body_fat_percent"]
    assert_rejected(unknown_field, "UNKNOWN_FIELD")
    unknown_time = base_request(); unknown_time["datasets"][0]["time_range"] = {"mode": "last_month"}
    assert_rejected(unknown_time, "UNKNOWN_TIME_MODE")
    unknown_filter = load("03_latest_3_chest_sessions.json"); unknown_filter["datasets"][0]["filters"]["intensity"] = "hard"
    assert_rejected(unknown_filter, "UNKNOWN_PROPERTY")
    unsupported_filter = base_request(); unsupported_filter["datasets"][0]["filters"]["movement_name"] = "bench_press"
    assert_rejected(unsupported_filter, "UNKNOWN_PROPERTY")
    reversed_dates = load("08_explicit_date_range.json")
    reversed_dates["datasets"][0]["time_range"] = {"mode": "explicit_range", "start": "2026-02-01", "end": "2026-01-01"}
    assert_rejected(reversed_dates, "DATE_RANGE_REVERSED")
    bad_days = base_request(); bad_days["datasets"][0]["time_range"]["days"] = 0
    assert_rejected(bad_days, "INTEGER_OUT_OF_RANGE")
    bad_selector = load("04_movement_progress_known_name.json")
    bad_selector["datasets"][0]["filters"]["movement_selector"] = {"kind": "movement_id", "value": "bad id"}
    assert_rejected(bad_selector, "INVALID_MOVEMENT_ID")
    bad_output = base_request(); bad_output["output"]["formats"] = ["csv"]
    assert_rejected(bad_output, "UNKNOWN_OUTPUT_FORMAT")
    malformed = validate_json('{"request_version":')
    assert not malformed.valid and malformed.errors[0].code == "INVALID_JSON"
    unordered = base_request(); unordered["purpose"] = "  Review body-weight trend over the latest 28 days.  "
    normalized = validate_request(unordered)
    assert normalized.valid
    assert normalized.normalized_request["purpose"] == "Review body-weight trend over the latest 28 days."
    assert normalized.normalized_request["raw"] is False


def main() -> None:
    test_schema_contract()
    test_examples()
    test_v11_closure_regressions()
    test_boundary_rules()
    print("FITNESS_LEDGER_ANALYSIS_EXPORT_REQUEST_PROTOCOL_V11_OK")


if __name__ == "__main__":
    main()
