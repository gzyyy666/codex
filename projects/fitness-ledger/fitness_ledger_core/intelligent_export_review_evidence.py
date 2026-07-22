"""Deterministic, privacy-safe evidence projection for Intelligent Export review.

This module deliberately sits beside the export contracts.  It consumes the
already validated runtime result and never re-plans, re-resolves, or reads the
formal files directly.  The projection is an audit artifact, not an
ExportPlan or an ExportResult replacement.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from typing import Any, Iterable


REVIEW_SCHEMA_VERSION = "fitness-ledger-review-evidence-v1.0"
MAX_SNIPPET = 80
BLOCKING_CODES = {
    "REVIEW_INTENT_MISSING", "REVIEW_INTENT_INVALID", "REVIEW_DATE_EVIDENCE_INVALID",
    "REVIEW_INTENT_SEMANTIC_INVALID", "REVIEW_INTENT_REPAIR_EVIDENCE_MISSING",
    "REVIEW_CANDIDATE_IDS_MISSING", "REVIEW_SELECTED_ID_NOT_IN_CANDIDATES",
    "REVIEW_SELECTION_IDS_MISSING", "REVIEW_EXECUTION_IDS_MISSING",
    "REVIEW_PROGRESS_FIELD_MISMATCH", "REVIEW_COUNT_ID_MISMATCH",
    "REVIEW_SNAPSHOT_MISMATCH", "REVIEW_CATALOG_MISMATCH",
    "REVIEW_STABILITY_IDS_MISSING", "REVIEW_REPAIR_DIFF_MISSING",
    "REVIEW_PRIVACY_VIOLATION",
}


@dataclass(frozen=True)
class RequestReviewEvidence:
    """Named DTO boundary for one request's deterministic review projection."""

    request_id: str
    data: dict

    def to_dict(self) -> dict:
        return dict(self.data)


@dataclass(frozen=True)
class ReviewEvidenceBundle:
    """Named DTO boundary for the complete privacy-safe review artifact."""

    review_schema_version: str
    source_snapshot_id: str
    catalog_id: str
    request_evidence: list[dict]
    stability_evidence: list[dict]
    integrity_audit: dict
    privacy_audit: dict
    review_status: str
    stability_comparison: dict

    def to_dict(self) -> dict:
        return asdict(self)


def _short(value: Any) -> str:
    value = re.sub(r"\s+", " ", str(value or "")).strip()
    return value[:MAX_SNIPPET]


def _hash(value: Any) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _ids(values: Iterable[Any]) -> list[str]:
    return [str(value) for value in values if str(value)]


def _unique(values: Iterable[str]) -> bool:
    values = list(values)
    return len(values) == len(set(values))


def _selected_modules(selection: dict) -> list[str]:
    return _ids(item.get("module_id") for item in selection.get("selected_modules", []) or [])


def _selected_fields(selection: dict) -> dict[str, list[str]]:
    return {str(item.get("module_id")): _ids(item.get("field_ids", [])) for item in selection.get("selected_fields", []) or []}


def _selected_movements(selection: dict) -> list[str]:
    return _ids(item.get("movement_id") for item in selection.get("selected_movements", []) or [])


def _candidate_projection(package: dict) -> dict:
    matches = {str(item.get("movement_id")): item for item in package.get("movement_matches", []) or []}
    windows = []
    for item in package.get("windows", []) or []:
        windows.append({
            "window_id": item.get("window_id", ""),
            "label": item.get("anchor", ""),
            "requested_start": item.get("requested_start", ""),
            "requested_end": item.get("requested_end", ""),
            "resolved_start": item.get("resolved_start", ""),
            "resolved_end": item.get("resolved_end", ""),
            "coverage": {"record_count": item.get("record_count", 0), "modules": item.get("modules", [])},
            "warning_codes": item.get("missing_data_warnings", []) or [],
        })
    modules = []
    for item in package.get("modules", []) or []:
        modules.append({
            "module_id": item.get("module_id", ""),
            "available_field_ids": sorted((item.get("field_coverage") or {}).keys()),
            "coverage": item.get("field_coverage", {}),
            "candidate_flags": ([] if item.get("available") else ["unavailable"]),
            "record_count": item.get("record_count", 0),
        })
    movements = []
    for item in package.get("movements", []) or []:
        movement_id = str(item.get("movement_id", ""))
        match = matches.get(movement_id, {})
        excluded = int(item.get("excluded_history_count", 0) or 0)
        flags = [item.get("trend_sample_sufficiency", "") or ""]
        if excluded:
            flags.append("has_excluded_history")
        movements.append({
            "movement_id": movement_id,
            "display_name": item.get("canonical_name", movement_id),
            "body_part": item.get("body_part", ""),
            "history_count": item.get("history_count", 0),
            "valid_progress_count": item.get("progress_history_count", 0),
            "excluded_history_count": excluded,
            "context_only_count": excluded,
            "candidate_reason": match.get("match_type", "catalog_candidate"),
            "candidate_score": match.get("score"),
            "candidate_flags": [value for value in flags if value],
            "date_start": item.get("date_start", ""),
            "date_end": item.get("date_end", ""),
            "latest_valid_progress_date": item.get("latest_valid_progress_date", ""),
        })
    notes = []
    for item in package.get("notes", []) or []:
        notes.append({
            "note_candidate_id": item.get("note_candidate_id", ""),
            "scope": item.get("scope", ""),
            "date": item.get("date", ""),
            "associated_movement_id": item.get("movement_id", ""),
            "snippet_hash": item.get("dedup_hash", "") or _hash(item.get("short_fragment", "")),
            "snippet": _short(item.get("short_fragment", "")),
            "choice_reason": "candidate catalog; planner reason is stored in selection",
        })
    records = []
    for item in package.get("candidate_records", []) or []:
        records.append({
            "record_candidate_id": item.get("candidate_record_id", ""),
            "record_type": item.get("record_kind", ""),
            "module_id": item.get("module_id", ""),
            "date": item.get("date", ""),
            "associated_movement_ids": item.get("related_movement_ids", []) or [],
            "candidate_flags": item.get("flags", []) or [],
        })
    resolver_matches = []
    for item in package.get("movement_matches", []) or []:
        resolver_matches.append({key: item.get(key) for key in ("movement_id", "canonical_name", "body_part", "match_type", "score", "history_count", "progress_history_count")})
    return {"windows": windows, "modules": modules, "movements": movements, "notes": notes, "records": records,
            "resolver_matches": resolver_matches, "budget": package.get("budget", {}), "allowed_ids": package.get("allowed_ids", {})}


def _execution_projection(result: dict) -> dict:
    output = result.get("output", {}) or {}
    evidence = output.get("execution_evidence", {}) or {}
    payload = output.get("payload", {}) or {}
    if not evidence:
        return {"actual_record_ids": [], "actual_note_ids": [], "output_sections": sorted(k for k in payload if k in {"body", "diet", "training", "movements", "notes", "raw_entries"}),
                "actual_output_size": len(str(output.get("json", ""))), "progress_history_count": 0, "progress_history_ids": [],
                "context_only_count": 0, "context_only_ids": [], "module_record_counts": {}, "movement_record_counts": {},
                "missing_data_codes": [], "insufficient_sample_codes": [], "execution_warning_codes": [], "evidence_present": False}
    projected = {
        "actual_record_ids": _ids(evidence.get("actual_record_ids", [])),
        "actual_note_ids": _ids(evidence.get("actual_note_ids", [])),
        "output_sections": list(evidence.get("output_sections", [])),
        "actual_output_size": int(evidence.get("actual_output_size", len(str(output.get("json", "")))) or 0),
        "progress_history_count": int(evidence.get("progress_history_count", 0) or 0),
        "progress_history_ids": _ids(evidence.get("progress_history_ids", [])),
        "context_only_count": int(evidence.get("context_only_count", 0) or 0),
        "context_only_ids": _ids(evidence.get("context_only_ids", [])),
        "module_record_counts": evidence.get("module_record_counts", {}) or {},
        "movement_record_counts": evidence.get("movement_record_counts", {}) or {},
        "missing_data_codes": evidence.get("missing_data_codes", []) or [],
        "insufficient_sample_codes": evidence.get("insufficient_sample_codes", []) or [],
        "execution_warning_codes": evidence.get("execution_warning_codes", []) or [],
        "evidence_present": True,
    }
    return projected


def _repair_projection(result: dict) -> dict:
    repair = (result.get("diagnostics", {}) or {}).get("repair", {}) or {}
    trace = result.get("trace", {}) or {}
    intent_repair = repair.get("intent_repair", {}) or {}
    return {
        "repair_used": bool(repair.get("repair_used", trace.get("repaired", False))),
        "intent_repair_used": bool(repair.get("intent_repair_used", False)),
        "phase": repair.get("phase", ""),
        "original_validation_codes": _ids(repair.get("original_validation_codes", [])),
        "repaired_validation_codes": _ids(repair.get("repaired_validation_codes", [])),
        "changed_field_names": _ids(repair.get("changed_field_names", [])),
        "added_selected_ids": _ids(repair.get("added_selected_ids", [])),
        "removed_selected_ids": _ids(repair.get("removed_selected_ids", [])),
        "decision_changed": bool(repair.get("decision_changed", False)),
        "confidence_before": repair.get("confidence_before"),
        "confidence_after": repair.get("confidence_after"),
        "intent_schema_status": repair.get("intent_schema_status", "valid"),
        "intent_semantic_status": repair.get("intent_semantic_status", "valid"),
        "intent_semantic_error_codes": _ids(repair.get("intent_semantic_error_codes", [])),
        "intent_initial_semantic_error_codes": _ids(repair.get("intent_initial_semantic_error_codes", [])),
        "intent_semantic_diagnostics": repair.get("intent_semantic_diagnostics", {}) or {},
        "repair_reason": intent_repair.get("repair_reason", ""),
        "changed_field_paths": _ids(intent_repair.get("changed_field_paths", [])),
        "fields_added": _ids(intent_repair.get("fields_added", [])),
        "fields_removed": _ids(intent_repair.get("fields_removed", [])),
        "semantic_codes_before": _ids(intent_repair.get("semantic_codes_before", [])),
        "semantic_codes_after": _ids(intent_repair.get("semantic_codes_after", [])),
        "field_snapshots": intent_repair.get("field_snapshots", {}) or {},
    }


def project_request(result: dict, request_id: str, original_request: str) -> dict:
    intent = result.get("intent", {}) or {}
    package = result.get("candidate_package", {}) or {}
    selection = result.get("selection", {}) or {}
    plan = result.get("plan", {}) or {}
    candidate = _candidate_projection(package)
    selected_modules = _selected_modules(selection)
    selected_fields = _selected_fields(selection)
    selected_movements = _selected_movements(selection)
    selected_notes = _ids(selection.get("selected_note_candidate_ids", []))
    selected_records = _ids(selection.get("selected_candidate_record_ids", []))
    movement_reasons = {str(item.get("movement_id")): str(item.get("reason", "")) for item in selection.get("selected_movements", []) or [] if item.get("movement_id")}
    inclusion = dict(plan.get("inclusion_reasons", {}) or {})
    inclusion.update({key: value for key, value in movement_reasons.items() if value})
    execution = _execution_projection(result)
    repair = _repair_projection(result)
    intent_semantic = (result.get("diagnostics", {}) or {}).get("intent_semantic", {}) or {}
    if intent_semantic:
        repair["intent_schema_status"] = intent_semantic.get("schema_status", repair.get("intent_schema_status", "valid"))
        repair["intent_semantic_status"] = intent_semantic.get("final_status", repair.get("intent_semantic_status", "valid"))
        repair["intent_semantic_error_codes"] = _ids(intent_semantic.get("error_codes", repair.get("intent_semantic_error_codes", [])))
        repair["intent_semantic_diagnostics"] = intent_semantic.get("diagnostics", repair.get("intent_semantic_diagnostics", {})) or {}
    return {
        "request_id": request_id,
        "original_request": original_request,
        "status": result.get("status", ""),
        "intent": {
            "interpreted_goal": intent.get("interpreted_goal", ""),
            "analysis_dimensions": intent.get("analysis_dimensions", []) or [],
            "date_intent": intent.get("date_intent", {}) or {},
            "movement_mentions": intent.get("movement_mentions", []) or [],
            "requested_modules": intent.get("catalog_requirements", []) or [],
            "requested_detail": intent.get("preferred_detail", ""),
            "raw_entry_relevance": intent.get("raw_entry_relevance", "none"),
            "intent_confidence": intent.get("confidence", 0),
            "intent_warning_codes": intent.get("warnings", []) or [],
            "schema_version": intent.get("schema_version", ""),
        },
        "date_resolution": {
            "candidate_windows": candidate["windows"],
            "selected_window_id": selection.get("selected_window_id", ""),
            "resolved_start": (plan.get("date_range") or {}).get("resolved_start", ""),
            "resolved_end": (plan.get("date_range") or {}).get("resolved_end", ""),
            "warning_codes": selection.get("missing_data_warning_codes", []) or [],
        },
        "candidates": candidate,
        "selection": {
            "planning_decision": selection.get("planning_decision", ""),
            "fallback_reason_codes": selection.get("fallback_reason_codes", []) or [],
            "selected_window_id": selection.get("selected_window_id", ""),
            "selected_module_ids": selected_modules,
            "selected_field_ids_by_module": selected_fields,
            "selected_movement_ids": selected_movements,
            "selected_note_candidate_ids": selected_notes,
            "selected_candidate_record_ids": selected_records,
            "training_detail_level": selection.get("training_detail_level", ""),
            "movement_detail_level": selection.get("movement_detail_level", ""),
            "include_raw_entries": selection.get("include_raw_entries", False),
            "include_excluded_history": selection.get("include_excluded_history", False),
            "excluded_history_usage": selection.get("excluded_history_usage", ""),
            "use_progress_history_for_metrics": selection.get("use_progress_history_for_metrics", False),
            "missing_data_warning_codes": selection.get("missing_data_warning_codes", []) or [],
            "inclusion_reasons": inclusion,
            "exclusion_decisions": selection.get("exclusion_decisions", []) or [],
            "planner_confidence": selection.get("planner_confidence", 0),
        },
        "plan": {
            "plan_id": str(plan.get("plan_id", ""))[:24],
            "selected_window_id": (plan.get("date_range") or {}).get("window_id", ""),
            "resolved_start": (plan.get("date_range") or {}).get("resolved_start", ""),
            "resolved_end": (plan.get("date_range") or {}).get("resolved_end", ""),
            "selected_module_ids": plan.get("selected_modules", []) or [],
            "selected_movement_ids": plan.get("selected_movements", []) or [],
            "selected_note_ids": plan.get("notes_selection", []) or [],
            "selected_record_ids": plan.get("candidate_record_ids", []) or [],
            "warning_codes": plan.get("missing_data_warnings", []) or [],
            "estimated_record_count": plan.get("estimated_record_count", 0),
            "estimated_output_size": plan.get("estimated_output_size", 0),
            "source_snapshot_id": plan.get("source_snapshot_id", ""),
            "catalog_id": package.get("catalog_id", ""),
        },
        "execution": execution,
        "model_call": (result.get("diagnostics", {}) or {}).get("stages", {}) or {},
        "repair": repair,
        "warnings": sorted(set((intent.get("warnings", []) or []) + (selection.get("missing_data_warning_codes", []) or []) + (plan.get("missing_data_warnings", []) or []))),
        "source_snapshot_id": package.get("source_snapshot_id", ""),
        "catalog_id": package.get("catalog_id", ""),
    }


def _intent_errors(item: dict) -> list[str]:
    intent = item.get("intent", {}) or {}
    required = {"interpreted_goal", "analysis_dimensions", "date_intent", "movement_mentions", "intent_confidence"}
    errors = [] if required.issubset(intent) else ["REVIEW_INTENT_MISSING"]
    date_intent = intent.get("date_intent", {}) or {}
    if not isinstance(date_intent, dict) or set(date_intent) - {"mode", "relative_range", "comparison_needed", "raw_date_mentions"}:
        errors.append("REVIEW_INTENT_INVALID")
    if not str(intent.get("interpreted_goal", "")).strip() or "???" in str(intent.get("interpreted_goal", "")) or "repr(" in str(intent.get("interpreted_goal", "")):
        errors.append("REVIEW_INTENT_INVALID")
    if any(key in date_intent for key in ("start", "end", "resolved_start", "resolved_end")):
        errors.append("REVIEW_DATE_EVIDENCE_INVALID")
    repair = item.get("repair", {}) or {}
    semantic_status = repair.get("intent_semantic_status", "valid")
    if semantic_status == "invalid":
        errors.append("REVIEW_INTENT_SEMANTIC_INVALID")
    return sorted(set(errors))


def audit_request(item: dict) -> list[str]:
    errors = _intent_errors(item)
    candidates = item.get("candidates", {}) or {}
    allowed = candidates.get("allowed_ids", {}) or {}
    if not allowed or not allowed.get("window_ids") and not allowed.get("movement_ids"):
        errors.append("REVIEW_CANDIDATE_IDS_MISSING")
    for key in ("window_ids", "movement_ids", "note_candidate_ids", "candidate_record_ids"):
        values = _ids(allowed.get(key, []))
        if not _unique(values):
            errors.append("REVIEW_CANDIDATE_IDS_MISSING")
    selection = item.get("selection", {}) or {}
    selected_map = {
        "window_ids": [selection.get("selected_window_id", "")],
        "movement_ids": selection.get("selected_movement_ids", []),
        "note_candidate_ids": selection.get("selected_note_candidate_ids", []),
        "candidate_record_ids": selection.get("selected_candidate_record_ids", []),
    }
    for key, values in selected_map.items():
        if values and any(value not in set(_ids(allowed.get(key, []))) for value in _ids(values)):
            errors.append("REVIEW_SELECTED_ID_NOT_IN_CANDIDATES")
        if values and not _unique(_ids(values)):
            errors.append("REVIEW_SELECTION_IDS_MISSING")
    if not selection.get("selected_module_ids"):
        errors.append("REVIEW_SELECTION_IDS_MISSING")
    plan = item.get("plan", {}) or {}
    if plan.get("selected_window_id") != selection.get("selected_window_id") or set(plan.get("selected_module_ids", [])) != set(selection.get("selected_module_ids", [])) or set(plan.get("selected_movement_ids", [])) != set(selection.get("selected_movement_ids", [])) or set(plan.get("selected_note_ids", [])) != set(selection.get("selected_note_candidate_ids", [])) or set(plan.get("selected_record_ids", [])) != set(selection.get("selected_candidate_record_ids", [])):
        errors.append("REVIEW_SNAPSHOT_MISMATCH")
    if plan.get("source_snapshot_id") != item.get("source_snapshot_id"):
        errors.append("REVIEW_SNAPSHOT_MISMATCH")
    if plan.get("catalog_id") != item.get("catalog_id"):
        errors.append("REVIEW_CATALOG_MISMATCH")
    execution = item.get("execution", {}) or {}
    if not execution.get("evidence_present") or "actual_record_ids" not in execution or "actual_note_ids" not in execution:
        errors.append("REVIEW_EXECUTION_IDS_MISSING")
    if execution.get("progress_history_count", 0) != len(execution.get("progress_history_ids", [])) or execution.get("context_only_count", 0) != len(execution.get("context_only_ids", [])):
        errors.append("REVIEW_COUNT_ID_MISMATCH")
    if not execution.get("evidence_present") or "progress" in execution:
        errors.append("REVIEW_PROGRESS_FIELD_MISMATCH")
    repair = item.get("repair", {}) or {}
    if repair.get("repair_used") and not (repair.get("changed_field_names") or repair.get("original_validation_codes") or repair.get("repaired_validation_codes")):
        errors.append("REVIEW_REPAIR_DIFF_MISSING")
    if repair.get("repair_used") and repair.get("phase") == "intent" and not repair.get("changed_field_paths") and not repair.get("fields_added") and not repair.get("fields_removed"):
        errors.append("REVIEW_INTENT_REPAIR_EVIDENCE_MISSING")
    return sorted(set(errors))


def privacy_audit(value: Any) -> dict:
    violations: list[str] = []
    forbidden_keys = {"raw_text", "full_prompt", "prompt", "tracker", "movement_dictionary", "formal_path", "formal_paths"}
    def walk(node: Any, path: str = "") -> None:
        if isinstance(node, dict):
            for key, child in node.items():
                key_name = str(key).lower()
                if key_name in forbidden_keys:
                    violations.append(path + "." + str(key))
                if key_name in {"snippet", "short_fragment"} and len(str(child)) > MAX_SNIPPET:
                    violations.append(path + "." + str(key) + ":over_80")
                walk(child, path + "." + str(key))
        elif isinstance(node, list):
            for index, child in enumerate(node):
                walk(child, f"{path}[{index}]")
    walk(value)
    return {"passed": not violations, "violations": sorted(set(violations)), "snippet_max_chars": MAX_SNIPPET}


def _stability_projection(items: list[dict]) -> dict:
    notes = [set(item.get("selection", {}).get("selected_note_candidate_ids", [])) for item in items]
    records = [set(item.get("selection", {}).get("selected_candidate_record_ids", [])) for item in items]
    movements = [set(item.get("selection", {}).get("selected_movement_ids", [])) for item in items]
    note_maps = [{note.get("note_candidate_id"): note for note in item.get("candidates", {}).get("notes", []) or []} for item in items]
    common = lambda values: sorted(set.intersection(*values)) if values else []
    only = lambda values, index: sorted(values[index] - set.union(*(values[j] for j in range(len(values)) if j != index))) if len(values) > 1 else sorted(values[index])
    return {
        "common_note_ids": common(notes), "run_1_only_note_ids": only(notes, 0), "run_2_only_note_ids": only(notes, 1), "run_3_only_note_ids": only(notes, 2),
        "common_record_ids": common(records), "run_1_only_record_ids": only(records, 0), "run_2_only_record_ids": only(records, 1), "run_3_only_record_ids": only(records, 2),
        "common_movement_ids": common(movements), "movement_differences": [sorted(values) for values in movements],
        "note_differences": [{"run": index + 1, "notes": [note_maps[index].get(note_id, {"note_candidate_id": note_id}) for note_id in sorted(values)]} for index, values in enumerate(notes)],
        "detail_level_differences": [{"training": item.get("selection", {}).get("training_detail_level", ""), "movement": item.get("selection", {}).get("movement_detail_level", "")} for item in items],
        "runs": [{"run_id": item.get("request_id", ""), "source_snapshot_id": item.get("source_snapshot_id", ""), "catalog_id": item.get("catalog_id", ""),
                  "selected_window_id": item.get("selection", {}).get("selected_window_id", ""), "selected_module_ids": item.get("selection", {}).get("selected_module_ids", []),
                  "selected_field_ids_by_module": item.get("selection", {}).get("selected_field_ids_by_module", {}), "selected_movement_ids": item.get("selection", {}).get("selected_movement_ids", []),
                  "selected_note_candidate_ids": item.get("selection", {}).get("selected_note_candidate_ids", []), "selected_candidate_record_ids": item.get("selection", {}).get("selected_candidate_record_ids", []),
                  "training_detail_level": item.get("selection", {}).get("training_detail_level", ""), "movement_detail_level": item.get("selection", {}).get("movement_detail_level", ""),
                  "warning_codes": item.get("warnings", []), "planner_confidence": item.get("selection", {}).get("planner_confidence", 0),
                  "repair_used": item.get("repair", {}).get("repair_used", False), "output_sections": item.get("execution", {}).get("output_sections", []),
                  "actual_output_size": item.get("execution", {}).get("actual_output_size", 0), "final_status": item.get("status", "")} for item in items]
    }


def assemble_bundle(requests: list[dict], stability_items: list[dict] | None = None) -> dict:
    stability_items = list(stability_items or [])
    request_errors = {item["request_id"]: audit_request(item) for item in requests}
    stability_errors = {item["request_id"]: audit_request(item) for item in stability_items}
    integrity_errors = {"requests": request_errors, "stability": stability_errors}
    blocking = sorted({code for errors in list(request_errors.values()) + list(stability_errors.values()) for code in errors if code in BLOCKING_CODES})
    bundle = {
        "review_schema_version": REVIEW_SCHEMA_VERSION,
        "generated_at": "deterministic_projection",
        "source_snapshot_id": next((item.get("source_snapshot_id", "") for item in requests if item.get("source_snapshot_id")), ""),
        "catalog_id": next((item.get("catalog_id", "") for item in requests if item.get("catalog_id")), ""),
        "request_evidence": requests,
        "stability_evidence": stability_items,
        "integrity_audit": {"passed": not blocking, "request_errors": request_errors, "stability_errors": stability_errors, "blocking_integrity_codes": blocking},
    }
    bundle["privacy_audit"] = privacy_audit(bundle)
    if not bundle["privacy_audit"]["passed"]:
        bundle["integrity_audit"]["blocking_integrity_codes"] = sorted(set(bundle["integrity_audit"]["blocking_integrity_codes"] + ["REVIEW_PRIVACY_VIOLATION"]))
        bundle["integrity_audit"]["passed"] = False
    bundle["review_status"] = "ready" if bundle["integrity_audit"]["passed"] else "blocked"
    bundle["stability_comparison"] = _stability_projection(stability_items) if stability_items else {"error": "REVIEW_STABILITY_IDS_MISSING"}
    return ReviewEvidenceBundle(
        bundle["review_schema_version"], bundle["source_snapshot_id"], bundle["catalog_id"],
        bundle["request_evidence"], bundle["stability_evidence"], bundle["integrity_audit"],
        bundle["privacy_audit"], bundle["review_status"], bundle["stability_comparison"],
    ).to_dict()


def build_bundle(results: list[tuple[str, str, dict]], stability_results: list[dict] | None = None) -> dict:
    requests = [project_request(result, request_id, request) for request_id, request, result in results]
    stability_items = [project_request(result, f"low-carb-training-run-{index}", "分析最近低碳是否导致胸部训练表现下降") for index, result in enumerate(stability_results or [], 1)]
    return assemble_bundle(requests, stability_items)


def write_review_index(bundle: dict, output_dir) -> None:
    from pathlib import Path
    out = Path(output_dir) / "human-review"
    out.mkdir(parents=True, exist_ok=True)
    lines = ["# Intelligent Export Core — Review Evidence Index", "", "## 1. Package 状态", "", f"- review_status: **{bundle.get('review_status')}**", f"- source_snapshot_id: `{bundle.get('source_snapshot_id', '')}`", f"- catalog_id: `{bundle.get('catalog_id', '')}`", f"- integrity errors: `{bundle.get('integrity_audit', {}).get('blocking_integrity_codes', [])}`", f"- privacy passed: `{bundle.get('privacy_audit', {}).get('passed')}`", ""]
    lines += ["## 2. Intent Semantic Summary", "", "| request | initial semantic | Repair | final semantic | semantic codes |", "|---|---|---|---|---|"]
    for item in bundle.get("request_evidence", []):
        repair = item.get("repair", {}) or {}
        initial = "invalid" if repair.get("intent_initial_semantic_error_codes") else "valid"
        lines.append(f"| {item['request_id']} | {initial} | {repair.get('repair_used', False)} | {repair.get('intent_semantic_status', 'valid')} | {','.join(repair.get('intent_semantic_error_codes', [])) or '—'} |")
    lines += ["", "## 3. 四请求总览", "", "| request | Intent | window | modules | movements | Notes | records | progress | context | confidence | Repair | 人工判断 |", "|---|---|---|---|---:|---:|---:|---:|---:|---:|---|---|"]
    for item in bundle.get("request_evidence", []):
        sel, exe = item["selection"], item["execution"]
        lines.append(f"| {item['request_id']} | {_short(item['intent'].get('interpreted_goal'))} | {item['date_resolution'].get('resolved_start')}..{item['date_resolution'].get('resolved_end')} | {','.join(sel.get('selected_module_ids', []))} | {','.join(sel.get('selected_movement_ids', [])) or '—'} | {len(sel.get('selected_note_candidate_ids', []))} | {len(sel.get('selected_candidate_record_ids', []))} | {exe.get('progress_history_count', 0)} | {exe.get('context_only_count', 0)} | {sel.get('planner_confidence')} | {item.get('repair', {}).get('repair_used')} | {'是' if not audit_request(item) else '否'} |")
    lines += ["", "## 3. 低碳请求证据链", ""]
    low = next((item for item in bundle.get("request_evidence", []) if item["request_id"] == "02-low-carb-training"), None)
    if low:
        mentions = low["intent"].get("movement_mentions", [])
        ids = [item.get("movement_id") for item in low["candidates"].get("movements", [])]
        lines += [f"- Original Request → Intent：{_short(low['intent'].get('interpreted_goal'))}；movement mentions={json.dumps(mentions, ensure_ascii=False)}", f"- Resolver Matches：`{low['candidates'].get('resolver_matches', [])}`", f"- Candidate movement IDs：`{ids}`；CHEST_006={'存在' if 'CHEST_006' in ids else '未在候选中'}", f"- Selection movement IDs：`{low['selection'].get('selected_movement_ids', [])}`", f"- Plan movement IDs：`{low['plan'].get('selected_movement_ids', [])}`", f"- Execution progress IDs：`{low['execution'].get('progress_history_ids', [])}`", f"- Integrity：`{audit_request(low)}`", ""]
    lines += ["## 4. 卧推证据链", ""]
    bench = next((item for item in bundle.get("request_evidence", []) if item["request_id"] == "03-bench-progress"), None)
    if bench:
        chest = next((item for item in bench["candidates"].get("movements", []) if item.get("movement_id") == "CHEST_006"), {})
        lines += [f"- CHEST_006：{chest.get('display_name')}；history={chest.get('history_count')}；valid progress={chest.get('valid_progress_count')}；excluded={chest.get('excluded_history_count')}", f"- Selection：`{bench['selection'].get('selected_movement_ids', [])}`；Repair：`{bench['repair']}`", f"- progress_history IDs：`{bench['execution'].get('progress_history_ids', [])}`", f"- Note IDs：`{bench['selection'].get('selected_note_candidate_ids', [])}`", f"- Record IDs：`{bench['selection'].get('selected_candidate_record_ids', [])}`", ""]
    lines += ["## 5. 肩部上下文证据", ""]
    shoulder = next((item for item in bundle.get("request_evidence", []) if item["request_id"] == "04-shoulder-progress"), None)
    if shoulder:
        for movement in shoulder["candidates"].get("movements", []):
            if movement.get("movement_id") in shoulder["selection"].get("selected_movement_ids", []):
                lines.append(f"- `{movement['movement_id']}` {movement['display_name']}：selection reason={shoulder['selection'].get('inclusion_reasons', {}).get(movement['movement_id'], movement['candidate_reason'])}")
        lines.append(f"- resolved intersection：{shoulder['date_resolution'].get('resolved_start')}..{shoulder['date_resolution'].get('resolved_end')}；warnings={shoulder['warnings']}")
    lines += ["", "## 6. 减脂请求动作证据", ""]
    fat = next((item for item in bundle.get("request_evidence", []) if item["request_id"] == "01-fat-loss"), None)
    if fat:
        for movement in fat["candidates"].get("movements", []):
            if movement.get("movement_id") in fat["selection"].get("selected_movement_ids", []):
                lines.append(f"- `{movement['movement_id']}` {movement['display_name']}：{fat['selection'].get('inclusion_reasons', {}).get(movement['movement_id'], movement['candidate_reason'])}")
    lines += ["", "## 7. 稳定性差异", ""]
    comparison = bundle.get("stability_comparison", {})
    for key in ("common_note_ids", "run_1_only_note_ids", "run_2_only_note_ids", "run_3_only_note_ids", "common_record_ids", "run_1_only_record_ids", "run_2_only_record_ids", "run_3_only_record_ids", "detail_level_differences"):
        lines.append(f"- {key}: `{comparison.get(key)}`")
    for group in comparison.get("note_differences", []):
        if group.get("notes"):
            lines.append(f"- Run {group.get('run')} Note details: " + "; ".join(f"{note.get('note_candidate_id')} [{note.get('scope')}] {note.get('date')} movement={note.get('associated_movement_id') or '-'} snippet={_short(note.get('snippet'))}" for note in group["notes"]))
    lines += ["", "## 8. 用户判断问题", ""]
    for item in bundle.get("request_evidence", []):
        lines += [f"### {item['request_id']}", "- 时间范围是否合理？", "- 模块是否选多或选少？", "- 动作是否选对？", "- Notes 是否有噪声或遗漏？", "- Records 是否合适？", "- 导出是否足以回答问题？", ""]
    (out / "review-index.md").write_text("\n".join(lines), encoding="utf-8")
    (out / "review-index.json").write_text(json.dumps(bundle, ensure_ascii=False, indent=2), encoding="utf-8")
