"""Anonymous-only contract tests for AnalysisExportMaterializer."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_export_materializer import (  # noqa: E402
    AnonymousFixtureMaterializer,
    MaterializationError,
)
from fitness_ledger_core.analysis_export_request import validate_request  # noqa: E402


FIXTURE_DIR = ROOT / "tools" / "fixtures" / "analysis_export_anonymous"


def load_json(name: str):
    return json.loads((FIXTURE_DIR / name).read_text(encoding="utf-8"))


def assert_schema(value: dict, name: str) -> None:
    """Exercise the committed schema's required/closed/constant contract.

    The project runtime intentionally has no third-party JSON Schema package;
    these assertions use the committed schema as the source of truth for the
    closed object keys and required fields, then check all v1.1 constants and
    generated record shapes needed by this stage.
    """
    schema = json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))
    assert set(value) == set(schema["required"])
    if name == "analysis_export_request_v1.schema.json":
        assert value["request_version"] == schema["properties"]["request_version"]["const"]
        assert value["raw"] is schema["properties"]["raw"]["const"]
        assert 1 <= len(value["datasets"]) <= 8
        for dataset in value["datasets"]:
            assert set(dataset) <= {"dataset_id", "type", "time_range", "filters", "fields", "notes_scope", "set_roles"}
            definition = schema["$defs"][{"body": "body_dataset", "diet": "diet_dataset", "training": "training_dataset", "movement_progress": "movement_dataset"}[dataset["type"]]]
            assert set(dataset) >= set(definition["required"])
            assert dataset["type"] == definition["properties"]["type"]["const"]
            assert dataset["fields"]
        assert value["output"]["formats"] and len(set(value["output"]["formats"])) == len(value["output"]["formats"])
    else:
        assert value["bundle_version"] == schema["properties"]["bundle_version"]["const"]
        manifest_schema = schema["$defs"]["manifest"]
        assert set(value["manifest"]) == set(manifest_schema["required"])
        assert set(value["safety_flags"]) == set(schema["$defs"]["safety_flags"]["required"])
        assert value["safety_flags"] == {"raw_included": False, "executor_called": False, "formal_data_written": False}
        assert isinstance(value["records"], list)


def test_all_valid_request_fixtures_pass_frozen_validator() -> None:
    for name, request in load_json("requests.json").items():
        result = validate_request(request)
        assert result.valid, (name, result.errors)
        assert result.normalized_request is not None
        assert_schema(request, "analysis_export_request_v1.schema.json")


def test_rejected_raw_and_unsupported_operation_fail_before_materialization() -> None:
    materializer = AnonymousFixtureMaterializer(FIXTURE_DIR / "fixture.json")
    for name, request in load_json("rejected_requests.json").items():
        result = validate_request(request)
        assert not result.valid, name
        try:
            materializer.materialize(request)
        except MaterializationError as error:
            assert error.validation is not None
        else:
            raise AssertionError(f"{name} was materialized")


def test_movement_name_ambiguity_requires_resolution() -> None:
    materializer = AnonymousFixtureMaterializer(FIXTURE_DIR / "fixture.json")
    request = load_json("resolution_requests.json")["movement_name_ambiguous"]
    validation = validate_request(request)
    assert validation.valid
    try:
        materializer.materialize(request)
    except MaterializationError as error:
        assert error.code == "MOVEMENT_RESOLUTION_REQUIRED"
        assert {item["movement_id"] for item in error.candidates} == {
            "m_synthetic_press_alt",
            "m_synthetic_press_variant",
        }
    else:
        raise AssertionError("Ambiguous movement name was silently materialized")


def test_four_time_modes_and_relation_are_deterministic() -> None:
    materializer = AnonymousFixtureMaterializer(FIXTURE_DIR / "fixture.json")
    requests = load_json("requests.json")
    bundle = materializer.materialize(requests["body_recent_28"])
    assert bundle["manifest"]["record_count"] == 28
    assert materializer.materialize(requests["diet_recent_14"])["manifest"]["record_count"] == 14
    assert materializer.materialize(requests["training_latest_3_chest"])["manifest"]["record_count"] == 3
    relation = materializer.materialize(requests["diet_before_each_chest"])
    diet_records = [row for row in relation["records"] if row["dataset_id"] == "diet_before_chest"]
    assert len(diet_records) == 9
    assert {row["relation"]["target_session_date"] for row in diet_records} == {"2099-12-18", "2099-12-24", "2099-12-28"}
    target_day = materializer.materialize(requests["diet_target_date_include"])
    assert [row["date"] for row in target_day["records"]] == ["2099-12-21", "2099-12-22", "2099-12-23", "2099-12-24"]
    excluded = {row["date"] for row in diet_records}
    assert "2099-12-18" not in excluded and "2099-12-24" not in excluded and "2099-12-28" not in excluded


def test_selectors_set_roles_notes_and_missing_values() -> None:
    materializer = AnonymousFixtureMaterializer(FIXTURE_DIR / "fixture.json")
    requests = load_json("requests.json")
    movement = materializer.materialize(requests["movement_latest_3_id"])
    for record in movement["records"]:
        assert {item["role"] for item in record["sets"]} == {"top", "working", "backoff"}
        assert record["notes"]
    assert materializer.materialize(requests["movement_name_selector"])["manifest"]["record_count"] == 3
    assert materializer.materialize(requests["movement_body_part_selector"])["manifest"]["record_count"] == 3
    missing = materializer.materialize(requests["missing_field"])
    record = missing["records"][0]
    assert record["weight_kg"] is None and record["cardio_summary"] is None
    assert any("weight_kg" in item for item in missing["missing_information"])
    assert any("cardio_summary" in item for item in missing["missing_information"])
    diet = materializer.materialize(requests["diet_recent_14"])
    assert any(record.get("notes") is None for record in diet["records"])
    assert not any("Notes scope" in item for item in diet["missing_information"])
    empty = materializer.materialize(requests["empty_intersection"])
    assert empty["records"] == []
    assert empty["quality_profile"]["status"] == "empty_selection"
    assert any("empty selection" in item for item in empty["warnings"])


def test_progress_exclusions_match_website_visibility_without_hiding_training() -> None:
    fixture = load_json("fixture.json")
    fixture["movement_catalog"] = [dict(item) for item in fixture["movement_catalog"]]
    fixture["datasets"] = {key: [dict(row) for row in rows] for key, rows in fixture["datasets"].items()}
    next(
        item for item in fixture["movement_catalog"] if item["movement_id"] == "m_synthetic_fly"
    )["exclude_from_progress"] = True
    for row in fixture["datasets"]["movement_progress"]:
        if row["date"] == "2099-12-24" and row["movement_id"] == "m_synthetic_press":
            row["exclude_from_progress"] = True

    request = {
        "request_version": "1.1",
        "purpose": "Verify progress-only exclusion semantics",
        "datasets": [
            {
                "dataset_id": "chest_training",
                "type": "training",
                "time_range": {"mode": "explicit_range", "start": "2099-12-10", "end": "2099-12-28"},
                "filters": {"body_part": "chest"},
                "fields": ["date", "split", "standardized_summary"],
                "notes_scope": "training",
            },
            {
                "dataset_id": "chest_progress",
                "type": "movement_progress",
                "time_range": {"mode": "explicit_range", "start": "2099-12-10", "end": "2099-12-28"},
                "filters": {"movement_selector": {"kind": "body_part", "value": "chest"}},
                "fields": ["date", "movement_id", "movement_name", "sets"],
                "notes_scope": "movement",
            },
        ],
        "raw": False,
        "output": {"formats": ["json", "markdown"]},
    }
    validation = validate_request(request)
    assert validation.valid, validation.errors
    bundle = AnonymousFixtureMaterializer(fixture).materialize(request)
    training = [row for row in bundle["records"] if row["dataset_id"] == "chest_training"]
    progress = [row for row in bundle["records"] if row["dataset_id"] == "chest_progress"]
    assert len(training) == 4
    assert len(progress) == 3
    progress_quality = next(item for item in bundle["quality_profile"]["datasets"] if item["dataset_id"] == "chest_progress")
    assert progress_quality["excluded_record_count"] == 2
    assert progress_quality["excluded_movement_count"] == 2
    assert {item["movement_id"] for item in progress_quality["excluded_movements"]} == {
        "m_synthetic_press",
        "m_synthetic_fly",
    }
    assert bundle["quality_profile"]["progress_exclusions"] == {
        "excluded_record_count": 2,
        "excluded_movement_count": 2,
    }
    markdown = AnonymousFixtureMaterializer.export_markdown(bundle)
    assert "Progress exclusions" in markdown
    assert "training/day-level records remain available" in markdown

    excluded_only_request = {
        "request_version": "1.1",
        "purpose": "Verify a fully excluded movement remains distinguishable from missing data",
        "datasets": [{
            "dataset_id": "excluded_fly_progress",
            "type": "movement_progress",
            "time_range": {"mode": "explicit_range", "start": "2099-12-10", "end": "2099-12-28"},
            "filters": {"movement_selector": {"kind": "movement_id", "value": "m_synthetic_fly"}},
            "fields": ["date", "movement_id", "sets"],
        }],
        "raw": False,
        "output": {"formats": ["json"]},
    }
    excluded_only = AnonymousFixtureMaterializer(fixture).materialize(excluded_only_request)
    assert excluded_only["records"] == []
    assert excluded_only["missing_information"] == []
    assert excluded_only["warnings"] == []
    assert excluded_only["quality_profile"]["status"] == "empty_after_progress_exclusion"


def test_combo_bundle_schema_exports_and_safety_are_reproducible() -> None:
    materializer = AnonymousFixtureMaterializer(FIXTURE_DIR / "fixture.json")
    request = load_json("requests.json")["combo_notes"]
    bundle_one, exports_one = materializer.materialize_with_exports(request)
    bundle_two, exports_two = materializer.materialize_with_exports(request)
    assert bundle_one == bundle_two
    assert exports_one == exports_two
    assert_schema(bundle_one, "analysis_export_bundle_v1.schema.json")
    assert set(exports_one) == {"json", "markdown"}
    assert json.loads(exports_one["json"]) == bundle_one
    assert "synthetic note body 02" in exports_one["markdown"]
    assert bundle_one["provenance"]["request_schema_version"] == "1.1"
    assert bundle_one["provenance"]["materializer_version"]
    assert bundle_one["provenance"]["fixture_version"] == "anonymous-fixture-v1"
    assert bundle_one["provenance"]["counts"]["validated_request_count"] == 1
    assert bundle_one["provenance"]["counts"]["candidate_record_count"] >= bundle_one["provenance"]["counts"]["resolved_record_count"]
    assert bundle_one["provenance"]["counts"]["materialized_record_count"] == len(bundle_one["records"])
    assert bundle_one["provenance"]["counts"]["exported_artifact_count"] == 2
    assert bundle_one["safety_flags"] == {"raw_included": False, "executor_called": False, "formal_data_written": False}
    assert bundle_one["request"]["raw"] is False


def main() -> None:
    test_all_valid_request_fixtures_pass_frozen_validator()
    test_rejected_raw_and_unsupported_operation_fail_before_materialization()
    test_movement_name_ambiguity_requires_resolution()
    test_four_time_modes_and_relation_are_deterministic()
    test_selectors_set_roles_notes_and_missing_values()
    test_progress_exclusions_match_website_visibility_without_hiding_training()
    test_combo_bundle_schema_exports_and_safety_are_reproducible()
    print("FITNESS_LEDGER_ANALYSIS_EXPORT_MATERIALIZER_OK")


if __name__ == "__main__":
    main()
