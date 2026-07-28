"""Milestone 1 Foundation Contract tests using anonymous hand-written fixtures."""

from __future__ import annotations

import json
import sys
from datetime import date
from types import SimpleNamespace
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from fitness_ledger_core.analysis_foundation import (  # noqa: E402
    AnalysisRequirementSpecV1,
    AnalysisTrace,
    CapabilityRegistryV1,
    FoundationError,
    GPTAnalysisPackage,
    HumanCorrection,
    PackageDataBlock,
    RequirementMapper,
    foundation_contract_schema,
    foundation_error_info,
)


def expect(code: str, callback) -> None:
    try:
        callback()
    except FoundationError as exc:
        assert exc.code == code, (code, exc.code)
    else:
        raise AssertionError(f"expected {code}")


def requirement_payload(**changes):
    payload = {
        "schema_version": "fitness-ledger-analysis-requirement-v1",
        "analysis_goal": "评估最近体重变化",
        "questions_to_answer": ["体重趋势如何？"],
        "required_capabilities": [{"capability_id": "body_history", "reason": "用户明确提到体重变化"}],
        "optional_capabilities": [],
        "preferred_time_window": {"kind": "recent", "label": "最近"},
        "derived_metrics": [{"name": "体重变化趋势", "reason": "帮助回答体重趋势问题"}],
        "missing_information": [],
        "clarifications": [],
        "evidence": [{"text": "最近体重变化", "source": "user_goal"}],
        "gpt_prompt_outline": ["先概括数据覆盖", "回答体重趋势并标记不确定性"],
    }
    payload.update(changes)
    return payload


def test_registry() -> None:
    registry = CapabilityRegistryV1()
    assert registry.schema_version == "fitness-ledger-capability-registry-v1"
    assert set(registry.ids) == {"body_history", "diet_macros", "training_context", "movement_progress", "notes_context", "raw_trace"}
    assert registry.require("movement_progress").source_contracts == ("DataCatalogBuilder.module:movement_history", "MovementResolver", "IntentCompiler.dimension:movement_progress", "AnalysisExportCommandParser.movement_scope")
    assert registry.require("raw_trace").model_selectable is False
    public = registry.to_dict()
    assert all("field_id" not in json.dumps(item, ensure_ascii=False) for item in public["capabilities"])
    assert "record_id" not in json.dumps(public, ensure_ascii=False)
    assert set(CapabilityRegistryV1.json_schema()["properties"]) == {"schema_version", "capabilities"}
    assert CapabilityRegistryV1.json_schema()["properties"]["capabilities"]["items"]["type"] == "object"


def test_requirement_schema_and_boundaries() -> None:
    requirement = AnalysisRequirementSpecV1.from_dict(requirement_payload(), user_goal="分析最近体重变化")
    assert requirement.to_dict()["preferred_time_window"] == {"kind": "recent", "label": "最近"}
    assert "user_goal" not in requirement.to_dict()
    assert "field_id" not in json.dumps(requirement.to_dict(), ensure_ascii=False)
    expect("SCHEMA_INVALID", lambda: AnalysisRequirementSpecV1.from_dict({**requirement_payload(), "field_id": "Weight (kg)"}, user_goal="分析最近体重变化"))
    expect("FORMAL_DATE_FORBIDDEN", lambda: AnalysisRequirementSpecV1.from_dict({**requirement_payload(), "preferred_time_window": {"kind": "explicit_user_phrase", "label": "2026-07-24"}}, user_goal="分析最近体重变化"))
    expect("FORMAL_DATE_FORBIDDEN", lambda: AnalysisRequirementSpecV1.from_dict({**requirement_payload(), "preferred_time_window": {"kind": "explicit_user_phrase", "label": "2026年7月24日"}}, user_goal="分析最近体重变化"))
    expect("EVIDENCE_NOT_GROUNDED", lambda: AnalysisRequirementSpecV1.from_dict({**requirement_payload(), "evidence": [{"text": "今天做了深蹲并且膝盖疼", "source": "user_goal"}]}, user_goal="分析最近体重变化"))
    expect("EVIDENCE_NOT_GROUNDED", lambda: AnalysisRequirementSpecV1.from_dict({**requirement_payload(), "evidence": [{"text": "最近体重变化", "source": "tracker"}]}, user_goal="分析最近体重变化"))


def test_mapping_permissions() -> None:
    mapper = RequirementMapper()
    mapped = mapper.map(AnalysisRequirementSpecV1.from_dict(requirement_payload(), user_goal="分析最近体重变化"))
    assert [item.capability_id for item in mapped.mapped_capabilities] == ["body_history"]
    assert mapped.date_resolution_status == "deferred_to_date_range_resolver_and_user_confirmation"
    assert mapped.raw_permission_status == "not_granted"
    assert mapped.notes_scope_status == "not_selected"
    assert "field_ids" not in mapped.to_dict() and "record_ids" not in mapped.to_dict() and "export_plan" not in mapped.to_dict()
    catalog = SimpleNamespace(date_range={"start": "2026-07-01", "end": "2026-07-15"})
    assert mapper.resolve_confirmed_date_candidates(AnalysisRequirementSpecV1.from_dict(requirement_payload(), user_goal="分析最近体重变化"), "分析最近体重变化", catalog, confirmed=False) == []
    candidates = mapper.resolve_confirmed_date_candidates(AnalysisRequirementSpecV1.from_dict(requirement_payload(), user_goal="分析最近体重变化"), "分析最近体重变化", catalog, confirmed=True, today=date(2026, 7, 15))
    assert candidates and candidates[0]["resolved_start"] == "2026-07-01" and candidates[0]["resolved_end"] == "2026-07-15"
    expect("UNKNOWN_CAPABILITY", lambda: mapper.map(AnalysisRequirementSpecV1.from_dict(requirement_payload(required_capabilities=[{"capability_id": "not-in-registry", "reason": "未知"}]), user_goal="分析最近体重变化")))
    expect("RAW_PERMISSION_NOT_GRANTABLE", lambda: mapper.map(AnalysisRequirementSpecV1.from_dict(requirement_payload(required_capabilities=[{"capability_id": "raw_trace", "reason": "用户没有明确授权，但模型想要原文"}]), user_goal="分析最近体重变化")))
    notes = mapper.map(AnalysisRequirementSpecV1.from_dict(requirement_payload(required_capabilities=[{"capability_id": "notes_context", "reason": "用户提到备注"}]), user_goal="分析最近体重变化和备注"))
    assert notes.notes_scope_status == "requires_user_confirmation"
    assert notes.mapped_capabilities[0].requires_user_confirmation is True


def test_gpt_package_boundary() -> None:
    mapper = RequirementMapper()
    requirement = AnalysisRequirementSpecV1.from_dict(requirement_payload(), user_goal="分析最近体重变化")
    mapping = mapper.map(requirement)
    package = GPTAnalysisPackage.build(requirement, mapping, "分析最近体重变化", "snapshot:anonymous", [PackageDataBlock("body_history", "DataCatalogBuilder.module:body", ["有可用体重历史"])])
    assert package.raw_included is False and package.notes_scope is None
    assert package.confirmed_time_window is None
    round_trip = GPTAnalysisPackage.from_dict(package.to_dict())
    assert round_trip.package_id == package.package_id
    expect("RAW_PERMISSION_NOT_GRANTABLE", lambda: GPTAnalysisPackage.from_dict({**package.to_dict(), "raw_included": True}))
    expect("NOTES_SCOPE_REQUIRES_CONFIRMATION", lambda: GPTAnalysisPackage.from_dict({**package.to_dict(), "notes_scope": "training"}))
    expect("NOTES_SCOPE_REQUIRES_CONFIRMATION", lambda: GPTAnalysisPackage.build(requirement, mapper.map(AnalysisRequirementSpecV1.from_dict(requirement_payload(required_capabilities=[{"capability_id": "notes_context", "reason": "用户提到备注"}]), user_goal="分析最近体重变化和备注")), "分析最近体重变化和备注", "snapshot:anonymous"))


def test_trace_and_human_correction() -> None:
    trace = AnalysisTrace.proposed("candidate:anonymous")
    validated = trace.transition("VALIDATED", {"ok": True})
    pending = validated.transition("PENDING_REVIEW")
    approved_correction = HumanCorrection.from_dict({"schema_version": "fitness-ledger-human-correction-v1", "correction_id": "correction:1", "candidate_id": "candidate:anonymous", "decision": "APPROVED", "reason": "范围与证据通过", "edited_fields": {}})
    approved = pending.apply_human_correction(approved_correction, {"ok": True})
    assert [event.status for event in approved.events] == ["PROPOSED", "VALIDATED", "PENDING_REVIEW", "APPROVED"]
    assert AnalysisTrace.from_dict(approved.to_dict()).status == "APPROVED"
    edited_correction = HumanCorrection.from_dict({"schema_version": "fitness-ledger-human-correction-v1", "correction_id": "correction:2", "candidate_id": "candidate:anonymous", "decision": "EDITED", "reason": "缩小问题范围", "edited_fields": {"questions_to_answer": ["体重趋势如何？", "记录覆盖是否足够？"]}})
    edited = approved.apply_human_correction(edited_correction, {"ok": True})
    assert edited.status == "EDITED" and len(edited.events) == 5
    edited_requirement = edited_correction.apply_to(AnalysisRequirementSpecV1.from_dict(requirement_payload(), user_goal="分析最近体重变化"), "分析最近体重变化")
    assert edited_requirement and edited_requirement.questions_to_answer[-1] == "记录覆盖是否足够？"
    rejected_correction = HumanCorrection.from_dict({"schema_version": "fitness-ledger-human-correction-v1", "correction_id": "correction:reject", "candidate_id": "candidate:anonymous", "decision": "REJECTED", "reason": "范围不安全", "edited_fields": {}})
    assert rejected_correction.apply_to(AnalysisRequirementSpecV1.from_dict(requirement_payload(), user_goal="分析最近体重变化"), "分析最近体重变化") is None
    expect("TRACE_INVALID_TRANSITION", lambda: edited.transition("PROPOSED"))
    expect("HUMAN_DECISION_INVALID", lambda: HumanCorrection.from_dict({"schema_version": "fitness-ledger-human-correction-v1", "correction_id": "correction:3", "candidate_id": "candidate:anonymous", "decision": "EDITED", "reason": "无字段", "edited_fields": {}}))
    expect("FORMAL_ID_FORBIDDEN", lambda: HumanCorrection.from_dict({"schema_version": "fitness-ledger-human-correction-v1", "correction_id": "correction:4", "candidate_id": "candidate:anonymous", "decision": "EDITED", "reason": "越权", "edited_fields": {"record_id": "record:1"}}))
    expect("HUMAN_DECISION_INVALID", lambda: approved.apply_human_correction(HumanCorrection.from_dict({"schema_version": "fitness-ledger-human-correction-v1", "correction_id": "correction:5", "candidate_id": "other", "decision": "REJECTED", "reason": "不匹配", "edited_fields": {}}), {"ok": False}))


def test_golden_examples() -> None:
    goldens = json.loads((Path(__file__).parent / "fixtures" / "intelligent_export_foundation_goldens.json").read_text(encoding="utf-8"))
    mapper = RequirementMapper()
    for item in goldens:
        requirement = AnalysisRequirementSpecV1.from_dict(item["requirement"], user_goal=item["user_goal"])
        mapping = mapper.map(requirement)
        assert [candidate.capability_id for candidate in mapping.mapped_capabilities] == item["expected_capabilities"], item["name"]
        assert "record_id" not in json.dumps(requirement.to_dict(), ensure_ascii=False)


def main() -> None:
    test_registry()
    test_requirement_schema_and_boundaries()
    test_mapping_permissions()
    test_gpt_package_boundary()
    test_trace_and_human_correction()
    test_golden_examples()
    assert foundation_error_info("RAW_PERMISSION_NOT_GRANTABLE")["category"] == "permission"
    contract = foundation_contract_schema()
    assert contract["schema_version"] == "fitness-ledger-intelligent-export-foundation-v1"
    assert "model_forbidden" in contract and "write" in contract["model_forbidden"]
    print("FITNESS_LEDGER_ANALYSIS_FOUNDATION_CONTRACT_OK")


if __name__ == "__main__":
    main()
