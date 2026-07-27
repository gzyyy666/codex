"""Single deterministic boundary from intent and optional hints to RequestDraft."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from .deterministic import DeterministicIntent
from .semantic_hint import MIN_READY_CONFIDENCE, REQUESTED_INFORMATION_PREFIX, SemanticHint, SemanticHintError, SemanticHintRequest, rank_candidates


class DraftAssemblyError(SemanticHintError):
    """The assembler cannot safely produce a final RequestDraft."""


@dataclass(frozen=True)
class UserConfirmation:
    """Test/UI boundary: a confirmation may approve a reparsed deterministic intent only."""

    approved: bool
    resolved_intent: DeterministicIntent | None = None


def _confirmation(value: UserConfirmation | Mapping[str, Any]) -> UserConfirmation:
    if isinstance(value, UserConfirmation):
        return value
    if not isinstance(value, Mapping) or set(value) != {"approved", "resolved_intent"}:
        raise DraftAssemblyError("confirmation shape must be approved plus resolved_intent")
    if not isinstance(value["approved"], bool):
        raise DraftAssemblyError("confirmation.approved must be boolean")
    resolved = value["resolved_intent"]
    if resolved is not None and not isinstance(resolved, DeterministicIntent):
        raise DraftAssemblyError("confirmation.resolved_intent must be DeterministicIntent")
    return UserConfirmation(value["approved"], resolved)


def _assemble_hint(intent: DeterministicIntent, request: SemanticHintRequest, hint: SemanticHint) -> dict[str, Any]:
    if hint.ambiguities and any(not rank_candidates(hint, dimension) for dimension in request.required_dimensions):
        reasons = "; ".join(item["reason"] for item in hint.ambiguities)
        return {
            "schema_version": "fitness-ledger-request-draft-v1",
            "status": "needs_confirmation",
            "purpose": intent.purpose,
            "datasets": [],
            "relations": [],
            "missing_confirmations": [f"请确认 requested information：{reasons}"],
            "warnings": [],
        }

    datasets: list[dict[str, Any]] = []
    for fixed in request.fixed_constraints:
        dataset = json.loads(json.dumps(fixed, ensure_ascii=False))
        dimension = f"{REQUESTED_INFORMATION_PREFIX}{dataset['kind']}"
        selected = rank_candidates(hint, dimension)
        if not selected:
            raise DraftAssemblyError(f"missing candidates for required dimension: {dimension}")
        if any(item.confidence < MIN_READY_CONFIDENCE for item in selected):
            return {
                "schema_version": "fitness-ledger-request-draft-v1",
                "status": "needs_confirmation",
                "purpose": intent.purpose,
                "datasets": [],
                "relations": [],
                "missing_confirmations": [f"请确认 {dimension} 的候选字段"],
                "warnings": [],
            }
        # candidate_pool is sealed by the deterministic layer. The Hint may rank or
        # evidence those values, but omission cannot silently shrink the final request.
        dataset["requested_information"] = list(request.candidate_pool[dimension])
        if not dataset["requested_information"]:
            raise DraftAssemblyError(f"empty selected candidates: {dimension}")
        datasets.append(dataset)
    return {
        "schema_version": "fitness-ledger-request-draft-v1",
        "status": "ready",
        "purpose": intent.purpose,
        "datasets": datasets,
        "relations": [dict(item) for item in request.fixed_relations],
        "missing_confirmations": [],
        "warnings": [],
    }


def assemble_request_draft(
    intent: DeterministicIntent,
    *,
    semantic_hint: SemanticHint | None = None,
    hint_request: SemanticHintRequest | None = None,
    confirmation: UserConfirmation | Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Assemble one final draft; model output can only supply validated hint candidates."""
    if confirmation is not None:
        if intent.route != "deterministic" or intent.status != "needs_confirmation":
            raise DraftAssemblyError("confirmation can resolve only a deterministic confirmation gap")
        choice = _confirmation(confirmation)
        if not choice.approved:
            return intent.to_draft()
        if choice.resolved_intent is None or choice.resolved_intent.route != "deterministic":
            raise DraftAssemblyError("approved confirmation requires a deterministic resolved_intent")
        intent = choice.resolved_intent

    if intent.route == "deterministic":
        if semantic_hint is not None or hint_request is not None:
            raise DraftAssemblyError("SemanticHint cannot modify a deterministic intent")
        return intent.to_draft()
    if semantic_hint is None or hint_request is None:
        raise DraftAssemblyError("provider route requires a validated SemanticHint")
    return _assemble_hint(intent, hint_request, semantic_hint)


def summarize_draft(draft: dict[str, Any] | None) -> dict[str, Any] | None:
    """Return an anonymous structural summary with no prompt, stdout, or user text."""
    if draft is None:
        return None
    return {
        "status": draft.get("status"),
        "purpose": draft.get("purpose"),
        "datasets": [
            {
                "draft_id": item.get("draft_id"),
                "kind": item.get("kind"),
                "scope": item.get("scope"),
                "time_intent": item.get("time_intent"),
                "requested_information": item.get("requested_information"),
                "notes": item.get("notes"),
            }
            for item in draft.get("datasets", [])
        ],
        "relations": draft.get("relations", []),
        "missing_confirmations": draft.get("missing_confirmations", []),
        "warnings": draft.get("warnings", []),
    }
