"""Planning stage: ask the model to select only real candidate IDs."""

from __future__ import annotations

import json

from .candidate_cards import CandidatePackage
from .intelligent_export_models import ExportPlanDraft, plan_json_schema
from .intent_interpreter import parse_json_object, PROMPT_VERSION
from .local_model_adapter import PLANNING_MODEL_CONFIG, LocalModelAdapter


PLANNING_SYSTEM_PROMPT = """You are the Fitness Ledger export planner. Return exactly one JSON object. Select only IDs and fields supplied in the candidate package. Never invent dates, modules, fields, movement IDs, Notes IDs, record IDs, or window IDs. Do not execute an export or modify data. Excluded movement history may only be selected as context_only; all progress metrics must use valid progress history. Prefer the smallest useful selection within the budget, include concrete inclusion and exclusion reasons, and set needs_fallback=true when evidence is insufficient."""


class ExportPlanner:
    def __init__(self, adapter: LocalModelAdapter) -> None:
        self.adapter = adapter
        self.last_result = None

    def plan(self, request: str, intent, package: CandidatePackage) -> tuple[ExportPlanDraft, object]:
        payload = {
            "original_request": str(request or "")[:2000],
            "intent": intent.to_dict(),
            "candidate_package": package.to_prompt_dict(),
            "allowed_ids": package.allowed_ids,
            "allowed_fields": package.allowed_fields,
            "budget": package.budget,
            "plan_schema": plan_json_schema(),
        }
        result = self.adapter.generate_json(system_prompt=PLANNING_SYSTEM_PROMPT, user_payload=payload, response_schema=plan_json_schema(), config=PLANNING_MODEL_CONFIG)
        self.last_result = result
        draft = ExportPlanDraft.from_dict(parse_json_object(result.raw_text))
        return draft, result
