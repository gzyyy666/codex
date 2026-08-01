from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable, Mapping

try:
    from .analysis_export_contract import assert_valid_analysis_export_request
    from .restricted_export_parser import SemanticExportPlan
except ImportError:  # direct script/test execution
    from analysis_export_contract import assert_valid_analysis_export_request
    from restricted_export_parser import SemanticExportPlan


FormalValidator = Callable[[Mapping[str, Any]], Any]


def _dataset_id(domain: str, index: int) -> str:
    return f"{domain}_{index:02d}"


def _run_optional_validator(
    validator: FormalValidator | None,
    request: Mapping[str, Any],
) -> None:
    if validator is None:
        return
    result = validator(request)
    if result is False:
        raise ValueError("The injected formal validator rejected the generated request")
    if isinstance(result, Mapping):
        status = result.get("status")
        valid = result.get("valid")
        errors = result.get("errors")
        if valid is False or status in {"invalid", "rejected", "error"} or errors:
            raise ValueError(f"The injected formal validator rejected the request: {result}")


def plan_to_analysis_requests(
    plan: SemanticExportPlan,
    *,
    max_datasets: int = 8,
    formal_validator: FormalValidator | None = None,
) -> dict[str, Any]:
    """
    Convert a deterministic SemanticExportPlan into one or more strict
    AnalysisExportRequest v1.1 dictionaries.

    The returned request objects contain only live-contract properties. Internal
    batch/plan metadata is returned separately in ``batch_manifest``.
    """
    if plan.request_kind != "direct_data_export":
        return {
            "status": plan.request_kind,
            "warnings": list(plan.warnings),
            "rejection_reason": plan.rejection_reason,
            "requests": [],
        }

    discovery_intents = [
        intent for intent in plan.dataset_intents if intent.discovery is not None
    ]
    if discovery_intents:
        return {
            "status": "TWO_STAGE_EXPORT_REQUIRED",
            "warnings": list(plan.warnings),
            "discovery_intents": [asdict(intent) for intent in discovery_intents],
            "requests": [],
        }

    if not plan.dataset_intents:
        return {
            "status": "needs_clarification",
            "warnings": [*plan.warnings, "NO_DATASET_INTENTS"],
            "requests": [],
        }

    # Precompute all IDs so relationship targets resolve regardless of intent order.
    intent_to_dataset_id = {
        intent.intent_id: _dataset_id(intent.domain, index)
        for index, intent in enumerate(plan.dataset_intents, start=1)
    }

    internal_datasets: list[dict[str, Any]] = []
    for intent in plan.dataset_intents:
        dataset_id = intent_to_dataset_id[intent.intent_id]

        time_range = asdict(intent.time_scope)
        time_range.pop("source", None)
        time_range.pop("rule_id", None)
        time_range = {key: value for key, value in time_range.items() if value is not None}

        target_intent_id = time_range.pop("target_intent_id", None)
        if target_intent_id:
            if target_intent_id not in intent_to_dataset_id:
                raise ValueError(f"Unknown target intent: {target_intent_id}")
            time_range["target_dataset_id"] = intent_to_dataset_id[target_intent_id]

        filters = dict(intent.filters)
        if intent.movement_selector:
            existing_selector = filters.get("movement_selector")
            if existing_selector and existing_selector != intent.movement_selector:
                raise ValueError(
                    f"Intent {intent.intent_id} has conflicting movement selectors"
                )
            # A formal movement ID/name is sufficient. Drop redundant body_part
            # metadata so an unverified part label cannot invalidate the request.
            if intent.movement_selector.get("kind") in {"movement_id", "movement_name"}:
                filters.pop("body_part", None)
            filters["movement_selector"] = dict(intent.movement_selector)

        dataset: dict[str, Any] = {
            "dataset_id": dataset_id,
            "type": intent.domain,
            "time_range": time_range,
            "filters": filters,
            "fields": list(intent.fields),
        }
        if intent.notes_scope:
            dataset["notes_scope"] = intent.notes_scope

        internal_datasets.append(
            {
                "dataset": dataset,
                "relationship_id": intent.relationship_id,
                "intent_id": intent.intent_id,
            }
        )

    # Preserve intent order while keeping relationship groups indivisible.
    grouped: list[list[dict[str, Any]]] = []
    emitted_relationships: set[str] = set()
    for item in internal_datasets:
        relationship_id = item["relationship_id"]
        if not relationship_id:
            grouped.append([item])
            continue
        if relationship_id in emitted_relationships:
            continue
        group = [
            candidate
            for candidate in internal_datasets
            if candidate["relationship_id"] == relationship_id
        ]
        emitted_relationships.add(relationship_id)
        grouped.append(group)

    batches: list[list[dict[str, Any]]] = []
    current: list[dict[str, Any]] = []
    for group in grouped:
        if len(group) > max_datasets:
            relationship_id = group[0].get("relationship_id")
            raise ValueError(
                f"Relationship group {relationship_id!r} exceeds dataset limit {max_datasets}"
            )
        if current and len(current) + len(group) > max_datasets:
            batches.append(current)
            current = []
        current.extend(group)
    if current:
        batches.append(current)

    purpose = f"按用户明确需求导出：{plan.original_user_input.strip()}"
    requests: list[dict[str, Any]] = []
    batch_manifest: list[dict[str, Any]] = []

    for batch_index, batch in enumerate(batches, start=1):
        request = {
            "request_version": "1.1",
            "purpose": purpose,
            "datasets": [item["dataset"] for item in batch],
            "raw": False,
            "output": {"formats": ["json"]},
        }
        assert_valid_analysis_export_request(request, max_datasets=max_datasets)
        _run_optional_validator(formal_validator, request)
        requests.append(request)
        batch_manifest.append(
            {
                "batch_index": batch_index,
                "batch_count": len(batches),
                "source_plan_id": plan.plan_id,
                "intent_ids": [item["intent_id"] for item in batch],
                "dataset_ids": [item["dataset"]["dataset_id"] for item in batch],
            }
        )

    before = len(internal_datasets)
    after = sum(len(request["datasets"]) for request in requests)
    return {
        "status": "BATCH_SPLIT_REQUIRED" if len(requests) > 1 else "REQUEST_READY",
        "requests": requests,
        "batch_manifest": batch_manifest,
        "semantic_conservation": {
            "valid": before == after,
            "dataset_count_before": before,
            "dataset_count_after": after,
        },
    }
