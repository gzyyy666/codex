"""Anonymous contract tests for Analysis Export Request Protocol v1."""
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


def main() -> None:
    request_schema = json.loads((SCHEMA_ROOT / "analysis_export_request_v1.schema.json").read_text(encoding="utf-8"))
    bundle_schema = json.loads((SCHEMA_ROOT / "analysis_export_bundle_v1.schema.json").read_text(encoding="utf-8"))
    assert request_schema["properties"]["raw"] == {"const": False}
    assert set(request_schema["$defs"]["time_range"]["oneOf"][0]["properties"]["mode"]) == {"const"}
    assert bundle_schema["properties"]["safety_flags"]["$ref"] == "#/$defs/safety_flags"

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

    unknown_type = load("01_recent_28_days_body.json")
    unknown_type["datasets"][0]["type"] = "sleep"
    assert_rejected(unknown_type, "UNKNOWN_DATASET_TYPE")

    unknown_field = load("01_recent_28_days_body.json")
    unknown_field["datasets"][0]["fields"] = ["date", "body_fat_percent"]
    assert_rejected(unknown_field, "UNKNOWN_FIELD")

    unknown_time = load("01_recent_28_days_body.json")
    unknown_time["datasets"][0]["time_range"] = {"mode": "last_month"}
    assert_rejected(unknown_time, "UNKNOWN_TIME_MODE")

    unknown_filter = load("03_latest_3_chest_sessions.json")
    unknown_filter["datasets"][0]["filters"]["intensity"] = "hard"
    assert_rejected(unknown_filter, "UNKNOWN_PROPERTY")

    unsupported_filter = load("01_recent_28_days_body.json")
    unsupported_filter["datasets"][0]["filters"]["movement_name"] = "卧推"
    assert_rejected(unsupported_filter, "FILTER_NOT_SUPPORTED_FOR_DATASET")

    notes_without_scope = load("07_training_notes_scope.json")
    notes_without_scope["notes_scope"] = []
    assert_rejected(notes_without_scope, "NOTES_SCOPE_REQUIRED")

    notes_without_dataset = load("01_recent_28_days_body.json")
    notes_without_dataset["notes_scope"] = ["training"]
    assert_rejected(notes_without_dataset, "NOTES_SCOPE_NOT_REQUESTED")

    reversed_dates = load("08_explicit_date_range.json")
    reversed_dates["datasets"][0]["time_range"] = {"mode": "explicit_range", "start": "2026-02-01", "end": "2026-01-01"}
    assert_rejected(reversed_dates, "DATE_RANGE_REVERSED")

    malformed = validate_json('{"request_version":')
    assert not malformed.valid and malformed.errors[0].code == "INVALID_JSON"

    unordered = load("01_recent_28_days_body.json")
    unordered["purpose"] = "  Review body-weight trend over the latest 28 days.  "
    normalized = validate_request(unordered)
    assert normalized.valid
    assert normalized.normalized_request["purpose"] == "Review body-weight trend over the latest 28 days."
    assert normalized.normalized_request["raw"] is False

    print("FITNESS_LEDGER_ANALYSIS_EXPORT_REQUEST_PROTOCOL_OK")


if __name__ == "__main__":
    main()
