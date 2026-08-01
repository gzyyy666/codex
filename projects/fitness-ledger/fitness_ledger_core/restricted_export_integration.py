"""Formal Catalog binding for the restricted export parser v2.

The parser receives an anonymous projection of the existing read-only Catalog;
it never opens tracker.json or movement_dictionary.json itself.  The v1.1
Validator and the existing Preview/Confirm/Materializer chain remain the only
execution boundary.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .analysis_export_request import validate_request
from .data_catalog import DataCatalogBuilder
from .restricted_export_parser_v2 import (
    MovementEntry,
    RestrictedExportParser,
    SemanticExportPlan,
    apply_candidate_selection,
    plan_to_analysis_requests,
)
from .shared_view_models import movement_in_progress


_BODY_PART_USER_ALIASES = {
    "胸": "CHEST",
    "胸部": "CHEST",
    "胸部训练": "CHEST",
    "背": "BACK",
    "背部": "BACK",
    "背部训练": "BACK",
    "肩": "SHOULDER",
    "肩部": "SHOULDER",
    "肩部训练": "SHOULDER",
    "手臂": "ARMS",
    "手臂训练": "ARMS",
    "核心": "CORE",
    "核心训练": "CORE",
    "腹": "CORE",
    "腹部": "CORE",
    "腿": "LEGS",
    "腿部": "LEGS",
    "腿部训练": "LEGS",
}


def _formal_body_part_aliases(catalog: Sequence[MovementEntry], body_part_ids: Mapping[str, str]) -> dict[str, str]:
    """Map user-facing Chinese aliases to values present in the formal Catalog."""
    canonical_by_id: dict[str, str] = {}
    for entry in catalog:
        body_part = str(entry.body_part or "").strip()
        body_part_id = str(body_part_ids.get(body_part, "") or "").strip()
        if body_part and body_part_id and body_part_id not in canonical_by_id:
            canonical_by_id[body_part_id] = body_part
    return {
        alias: canonical_by_id[body_part_id]
        for alias, body_part_id in _BODY_PART_USER_ALIASES.items()
        if body_part_id in canonical_by_id
    }


def formal_movement_catalog(views) -> tuple[tuple[MovementEntry, ...], dict[str, str], dict[str, str]]:
    """Build the parser input from the existing read-only Catalog projection."""
    projection = DataCatalogBuilder(views).build()
    _tracker, dictionary = views.snapshot()
    definitions = {
        str(item.get("movement_id")): item
        for item in dictionary.get("movements", []) or []
        if isinstance(item, dict) and item.get("movement_id")
    }
    body_part_ids: dict[str, str] = {}
    entries: list[MovementEntry] = []
    for card in projection.movements:
        definition = definitions.get(card.movement_id, {})
        include_in_progress = movement_in_progress(definition)
        entries.append(
            MovementEntry(
                movement_id=card.movement_id,
                movement_name=card.canonical_name,
                aliases=tuple(card.aliases),
                body_part=card.body_part or None,
                include_in_progress=include_in_progress,
                record_count=card.progress_history_count if include_in_progress else 0,
                last_date=card.latest_valid_progress_date if include_in_progress else None,
            )
        )
        if card.body_part and card.body_part_id:
            body_part_ids[card.body_part] = card.body_part_id
    catalog = tuple(entries)
    return catalog, _formal_body_part_aliases(catalog, body_part_ids), body_part_ids


def make_formal_parser(views) -> tuple[RestrictedExportParser, tuple[MovementEntry, ...], dict[str, str]]:
    catalog, body_part_aliases, body_part_ids = formal_movement_catalog(views)
    parser = RestrictedExportParser(catalog, body_part_aliases=body_part_aliases)
    return parser, catalog, body_part_ids


def _formal_training_body_parts(views, catalog: Sequence[MovementEntry], body_part_ids: Mapping[str, str]) -> dict[str, str]:
    """Project semantic body-part tokens supported by the formal Split values."""
    analysis = views.analysis(days=36500, include_raw_preview=False)
    split_values = [str(row.get("Split", "")) for row in analysis.get("training", []) or []]
    tokens_by_id = {
        "CHEST": "胸",
        "BACK": "背",
        "SHOULDER": "肩",
        "ARMS": "手臂",
        "CORE": "核心",
        "LEGS": "腿",
    }
    body_part_ids = {str(body_part): str(body_id) for body_part, body_id in body_part_ids.items()}
    # The movement Catalog carries formal muscle-group labels (e.g. Back),
    # while training rows carry semantic Split labels (e.g. 背部/腿部).  Use a
    # token only when that token is observed in the formal training projection.
    result: dict[str, str] = {}
    for body_part, body_id in body_part_ids.items():
        token = tokens_by_id.get(body_id, "")
        if token and any(token in value for value in split_values):
            result[body_part] = token
    return result


def _apply_training_body_part_projection(plan: SemanticExportPlan, views, catalog: Sequence[MovementEntry], body_part_ids: Mapping[str, str]) -> None:
    body_part_values = _formal_training_body_parts(views, catalog, body_part_ids)
    for intent in plan.dataset_intents:
        if intent.domain != "training":
            continue
        body_part = str(intent.filters.get("body_part", ""))
        if body_part in body_part_values:
            intent.filters["body_part"] = body_part_values[body_part]


def _live_validate(request: Mapping[str, Any]) -> dict[str, Any]:
    return validate_request(dict(request)).to_dict()


def _candidate_row(entry: MovementEntry, *, score: Any = None, reason: str = "") -> dict[str, Any]:
    row = {
        "movement_id": entry.movement_id,
        "movement_name": entry.movement_name,
        "body_part": entry.body_part or "",
        "aliases": list(entry.aliases),
        "include_in_progress": entry.include_in_progress,
        "record_count": int(entry.record_count or 0),
        "history_count": int(entry.record_count or 0),
        "last_date": entry.last_date or "",
        "recent_date": entry.last_date or "",
    }
    if score is not None:
        row["score"] = score
    if reason:
        row["reason"] = reason
    return row


def _discovery_candidates(plan: SemanticExportPlan, catalog: Sequence[MovementEntry]) -> list[dict[str, Any]]:
    intent = next((item for item in plan.dataset_intents if item.discovery is not None), None)
    if intent is None:
        return []
    discovery = intent.discovery
    candidates = [item for item in catalog if item.include_in_progress]
    if discovery and discovery.body_part:
        candidates = [item for item in candidates if item.body_part == discovery.body_part]
    if discovery and discovery.mode in {"recorded_only", "progress_eligible_only", "representative_ranked", "session_scoped"}:
        candidates = [item for item in candidates if int(item.record_count or 0) > 0]
    candidates.sort(key=lambda item: (-(int(item.record_count or 0)), item.last_date or "", item.movement_name, item.movement_id))
    if discovery and discovery.mode == "representative_ranked" and discovery.count:
        candidates = candidates[: discovery.count]
    return [_candidate_row(item, reason="formal_catalog_discovery") for item in candidates]


def _unresolved_candidates(plan: SemanticExportPlan, catalog: Sequence[MovementEntry]) -> list[dict[str, Any]]:
    by_id = {item.movement_id: item for item in catalog}
    result: list[dict[str, Any]] = []
    seen: set[str] = set()
    for unresolved in plan.unresolved_movements:
        for candidate in unresolved.get("candidates", []) or []:
            movement_id = str(candidate.get("movement_id", ""))
            entry = by_id.get(movement_id)
            if not entry or movement_id in seen:
                continue
            seen.add(movement_id)
            result.append(_candidate_row(entry, score=candidate.get("score"), reason=str(unresolved.get("reason", ""))))
    return result


def _patch_selected_ambiguous_plan(
    parser: RestrictedExportParser,
    text: str,
    plan: SemanticExportPlan,
    selected_ids: Sequence[str],
    catalog: Sequence[MovementEntry],
) -> SemanticExportPlan:
    """Turn an explicit Guided Selection into a deterministic movement alias."""
    if not plan.unresolved_movements:
        return plan
    selected = set(str(item) for item in selected_ids)
    by_id = {item.movement_id: item for item in catalog}
    allowed_ids = {
        str(candidate.get("movement_id", ""))
        for unresolved in plan.unresolved_movements
        for candidate in unresolved.get("candidates", []) or []
    }
    if not selected.issubset(allowed_ids):
        raise ValueError("Guided Selection contains a movement outside the formal candidate set")
    selected_entries: list[MovementEntry] = []
    source_texts = [str(item.get("source_text", "")).strip() for item in plan.unresolved_movements]
    for entry in catalog:
        if entry.movement_id in selected:
            selected_entries.append(
                MovementEntry(
                    entry.movement_id,
                    entry.movement_name,
                    tuple(dict.fromkeys((*entry.aliases, *source_texts))),
                    entry.body_part,
                    entry.include_in_progress,
                    entry.record_count,
                    entry.last_date,
                )
            )
        elif entry.movement_id not in selected:
            continue
    if not selected_entries or any(item not in by_id for item in selected):
        raise ValueError("Guided Selection contains an unknown formal movement_id")
    selected_parser = RestrictedExportParser(
        selected_entries,
        body_part_aliases=parser.body_part_aliases,
    )
    return selected_parser.parse(text)


def compile_natural_language_export(
    views,
    text: str,
    selected_movement_ids: Sequence[str] = (),
) -> dict[str, Any]:
    parser, catalog, body_part_ids = make_formal_parser(views)
    plan = parser.parse(text)
    _apply_training_body_part_projection(plan, views, catalog, body_part_ids)
    selected = list(dict.fromkeys(str(item) for item in selected_movement_ids if str(item).strip()))
    if selected:
        discovery = next((item for item in plan.dataset_intents if item.discovery is not None), None)
        if discovery is not None:
            allowed_ids = {
                str(candidate.get("movement_id", ""))
                for candidate in _discovery_candidates(plan, catalog)
            }
            if not set(selected).issubset(allowed_ids):
                raise ValueError("Guided Selection contains a movement outside the formal discovery scope")
            plan = apply_candidate_selection(
                plan,
                intent_id=discovery.intent_id,
                selected_movement_ids=selected,
                catalog=catalog,
            )
        elif plan.unresolved_movements:
            plan = _patch_selected_ambiguous_plan(parser, text, plan, selected, catalog)
            _apply_training_body_part_projection(plan, views, catalog, body_part_ids)
        else:
            raise ValueError("Selected movement IDs are not applicable to this request")

    result = plan_to_analysis_requests(plan, formal_validator=_live_validate)
    response: dict[str, Any] = {
        "status": result.get("status", plan.request_kind),
        "requests": result.get("requests", []),
        "warnings": [*plan.warnings, *result.get("warnings", [])],
        "errors": [],
        "semantic_plan": plan.to_dict(),
        "batch_manifest": result.get("batch_manifest", []),
        "semantic_conservation": result.get("semantic_conservation", {}),
        "resolution": {},
    }
    if result.get("rejection_reason"):
        response["errors"] = [result["rejection_reason"]]
    if result.get("status") == "TWO_STAGE_EXPORT_REQUIRED":
        response["status"] = "candidate_confirmation_required"
        response["confirmations"] = ["该范围需要先从正式 Catalog 选择动作，再生成可执行 Request。"]
        response["candidates"] = _discovery_candidates(plan, catalog)
    elif plan.unresolved_movements:
        response["status"] = "needs_clarification"
        response["confirmations"] = ["动作别名未能唯一解析，请从正式候选中选择。"]
        response["candidates"] = _unresolved_candidates(plan, catalog)
    elif result.get("status") == "REQUEST_READY":
        response["status"] = "ready"
    elif result.get("status") == "BATCH_SPLIT_REQUIRED":
        response["status"] = "ready"
        response["confirmations"] = [f"已按单批最多 8 个 Dataset 拆分为 {len(response['requests'])} 批。"]
    elif result.get("status") == "rejected_contract":
        response["status"] = "unsupported"
    elif result.get("status") == "no_export_required":
        response["status"] = "NO_EXPORT_REQUIRED"
    elif result.get("status") == "planner_required":
        response["status"] = "planner_required"
    elif result.get("status") == "needs_clarification":
        response["status"] = "needs_clarification"
    return response


__all__ = ["compile_natural_language_export", "formal_movement_catalog", "make_formal_parser"]
