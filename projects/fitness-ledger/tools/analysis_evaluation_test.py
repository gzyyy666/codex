"""Anonymous Milestone 2 Data & Evaluation Pipeline tests."""

from __future__ import annotations

import copy
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_evaluation import (  # noqa: E402
    EVALUATION_DATASET_SCHEMA_VERSION,
    EVALUATION_POLICY_VERSION,
    AnonymizedDataProjector,
    EvaluationDatasetV1,
    FoundationEvaluationRunner,
    evaluation_dataset_json_schema,
    evaluation_report_json_schema,
    privacy_audit,
)
from fitness_ledger_core.analysis_foundation import AnalysisRequirementSpecV1, FoundationError, RequirementMapper  # noqa: E402
from fitness_ledger_core.data_catalog import DataCatalogBuilder  # noqa: E402
from fitness_ledger_core.shared_view_models import LedgerViewModels  # noqa: E402
from intelligent_export_core_test import fixture  # noqa: E402


FIXTURE = ROOT / "tools" / "fixtures" / "intelligent_export_evaluation_cases.json"


def expect(code: str, callback) -> None:
    try:
        callback()
    except FoundationError as exc:
        assert exc.code == code, (code, exc.code)
    else:
        raise AssertionError(f"expected {code}")


def test_dataset_contract() -> EvaluationDatasetV1:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    dataset = EvaluationDatasetV1.from_dict(raw)
    assert dataset.schema_version == EVALUATION_DATASET_SCHEMA_VERSION
    assert len(dataset.split("golden")) == 3
    assert len(dataset.split("holdout")) == 3
    assert dataset.dataset_hash == EvaluationDatasetV1.from_dict(dataset.to_dict()).dataset_hash
    assert privacy_audit(raw)["passed"]
    assert "record_id" not in json.dumps(dataset.to_dict(), ensure_ascii=False)
    assert evaluation_dataset_json_schema()["properties"]["cases"]["maxItems"] == 256
    assert evaluation_report_json_schema()["properties"]["policy_version"]["const"] == EVALUATION_POLICY_VERSION
    return dataset


def test_dataset_boundaries() -> None:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    leaked = copy.deepcopy(raw)
    leaked["cases"][1]["user_goal"] = leaked["cases"][0]["user_goal"]
    expect("EVALUATION_DATA_LEAKAGE", lambda: EvaluationDatasetV1.from_dict(leaked))

    private = copy.deepcopy(raw)
    private["cases"][0]["candidate_requirement"]["record_id"] = "record-1"
    assert not privacy_audit(private)["passed"]
    expect("EVALUATION_PRIVACY_VIOLATION", lambda: EvaluationDatasetV1.from_dict(private))

    missing_split = copy.deepcopy(raw)
    for item in missing_split["cases"]:
        item["split"] = "golden"
    expect("EVALUATION_DATASET_INVALID", lambda: EvaluationDatasetV1.from_dict(missing_split))


def test_evaluation_report(dataset: EvaluationDatasetV1) -> None:
    runner = FoundationEvaluationRunner()
    report = runner.run(dataset)
    repeated = runner.run(dataset)
    assert report.to_dict() == repeated.to_dict()
    assert report.total_cases == 6 and report.passed_cases == 6 and report.pass_rate == 1.0
    assert report.by_split["golden"]["pass_rate"] == 1.0
    assert report.by_split["holdout"]["pass_rate"] == 1.0
    assert report.metrics["outcome_accuracy"] == 1.0
    assert report.metrics["evidence_grounding_rate"] == round(5 / 6, 4)
    assert report.metrics["boundary_pass_rate"] == 1.0
    assert report.policy_version == EVALUATION_POLICY_VERSION
    assert len(report.report_id) > len("evaluation:")


def test_candidate_regression_is_detected(dataset: EvaluationDatasetV1) -> None:
    runner = FoundationEvaluationRunner()
    case = dataset.cases[0]
    changed = copy.deepcopy(case.candidate_requirement)
    changed["required_capabilities"] = [{"capability_id": "raw_trace", "reason": "越权候选"}]
    result = runner.evaluate_case(case, changed)
    assert result.passed is False
    assert result.observed_outcome == "rejected"
    assert result.error_code == "RAW_PERMISSION_NOT_GRANTABLE"
    assert result.checks["safe_rejection"] is False


def test_anonymized_data_projector(dataset: EvaluationDatasetV1) -> None:
    case = dataset.cases[0]
    requirement = AnalysisRequirementSpecV1.from_dict(case.candidate_requirement, user_goal=case.user_goal)
    mapping = RequirementMapper().map(requirement)
    with tempfile.TemporaryDirectory(prefix="fitness-ledger-evaluation-data-") as name:
        tracker, dictionary = fixture(Path(name))
        catalog = DataCatalogBuilder(LedgerViewModels(tracker, dictionary)).build()
        projector = AnonymizedDataProjector()
        blocks = projector.build(catalog, mapping)
        assert [item.capability_id for item in blocks] == ["body_history", "diet_macros"]
        serialized = json.dumps([item.to_dict() for item in blocks], ensure_ascii=False)
        assert "body-1" not in serialized and "record_id" not in serialized and "private raw" not in serialized
        package = projector.build_package(requirement, mapping, catalog, case.user_goal, "snapshot:anonymous")
        assert package.raw_included is False and package.notes_scope is None
        assert package.data_blocks == blocks


def main() -> None:
    dataset = test_dataset_contract()
    test_dataset_boundaries()
    test_evaluation_report(dataset)
    test_candidate_regression_is_detected(dataset)
    test_anonymized_data_projector(dataset)
    print("FITNESS_LEDGER_ANALYSIS_EVALUATION_OK")


if __name__ == "__main__":
    main()
