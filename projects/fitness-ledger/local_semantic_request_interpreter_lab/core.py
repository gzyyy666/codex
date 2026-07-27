"""Stable semantic boundary and deterministic safety checks."""

from __future__ import annotations

import json
import re
from datetime import date
from typing import Any, Callable

from .draft_assembler import assemble_request_draft, summarize_draft
from .deterministic import parse_deterministic_intent
from .inference import InferenceProvider, ModelUnavailable, ProviderConfigurationError, ProviderOutputError, ProviderRuntimeError
from .semantic_hint import SemanticHintError, validate_semantic_hint

SCHEMA_VERSION = "fitness-ledger-request-draft-v1"
RESULT_VERSION = "fitness-ledger-request-interpreter-result-v1"
DATASET_KINDS = {"body", "diet", "training", "movement_progress"}
TIME_TYPES = {"recent_days", "explicit_date_range", "latest_matching_sessions", "before_each_target_event", "unspecified"}
NOTE_SCOPES = {"daily", "diet", "training", "movement"}
GLOBAL_KEYS = {"schema_version", "status", "purpose", "datasets", "relations", "missing_confirmations", "warnings"}
DATASET_KEYS = {"draft_id", "kind", "scope", "time_intent", "requested_information", "notes"}
SCOPE_KEYS = {"body_part", "movement", "split"}
TIME_KEYS = {"type", "days", "start", "end", "count", "target_draft_id", "days_before", "include_target_day"}
NOTE_KEYS = {"requested", "scopes"}
RELATION_KEYS = {"type", "source_draft_id", "dependent_draft_id"}
BODY_PART_TERMS = {"chest": "胸", "back": "背", "shoulders": "肩", "legs": "腿", "arms": "臂", "core": "核心"}
SPLIT_TERMS = {"push": "推", "pull": "拉", "legs": "腿", "upper": "上肢", "lower": "下肢", "full_body": "全身"}
MOVEMENT_TERMS = {
    "bench_press": ("卧推",),
    "incline_dumbbell_press": ("上斜哑铃推",),
    "barbell_row": ("杠铃划船",),
    "lat_pulldown": ("高位下拉",),
    "squat": ("深蹲",),
    "deadlift": ("硬拉",),
    "overhead_press": ("肩推", "推举"),
    "lateral_raise": ("侧平举",),
    "cable_fly": ("绳索夹胸", "夹胸"),
}
NUMBER_TERMS = {0: ("零",), 1: ("一",), 2: ("二", "两"), 3: ("三",), 4: ("四",), 5: ("五",), 6: ("六",), 7: ("七",), 8: ("八",), 9: ("九",), 10: ("十",)}

FIELD_RULES = {
    "body": {"date", "weight", "bowel_movement", "training_label", "cardio_summary"},
    "diet": {"date", "energy", "protein", "carbohydrate", "fat", "food_summary"},
    "training": {"date", "session", "split", "movements", "sets", "training_notes"},
    "movement_progress": {"date", "movement", "body_part", "variant", "order", "sets", "load", "repetitions", "movement_notes"},
}


class DraftError(ValueError):
    """A fail-closed validation error."""


class ModelUnavailable(RuntimeError):
    """The local model/runtime cannot be used."""


def _reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DraftError(f"duplicate field: {key}")
        result[key] = value
    return result


def parse_json_strict(raw: str) -> dict[str, Any]:
    try:
        value = json.loads(raw, object_pairs_hook=_reject_duplicates, parse_constant=lambda x: (_ for _ in ()).throw(DraftError(f"invalid constant: {x}")))
    except (json.JSONDecodeError, DraftError) as exc:
        raise DraftError(f"invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise DraftError("root must be an object")
    return value


def _dict(value: Any, label: str, keys: set[str]) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise DraftError(f"{label} must be an object")
    unknown = set(value) - keys
    if unknown:
        raise DraftError(f"{label} has unknown fields: {sorted(unknown)}")
    return value


def _str(value: Any, label: str, *, nonempty: bool = True) -> str:
    if not isinstance(value, str) or (nonempty and not value.strip()):
        raise DraftError(f"{label} must be a non-empty string")
    return value


def _int(value: Any, label: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise DraftError(f"{label} must be an integer in [{low}, {high}]")
    return value


def _list(value: Any, label: str, *, min_items: int = 0, max_items: int = 100) -> list[Any]:
    if not isinstance(value, list) or not min_items <= len(value) <= max_items:
        raise DraftError(f"{label} must be a list with {min_items}..{max_items} items")
    if len({json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value}) != len(value):
        raise DraftError(f"{label} must not contain duplicates")
    return value


def _validate_time(value: Any) -> dict[str, Any]:
    time = _dict(value, "time_intent", TIME_KEYS)
    kind = _str(time.get("type"), "time_intent.type")
    if kind not in TIME_TYPES:
        raise DraftError(f"unsupported time intent: {kind}")
    expected = {
        "recent_days": {"type", "days"},
        "explicit_date_range": {"type", "start", "end"},
        "latest_matching_sessions": {"type", "count"},
        "before_each_target_event": {"type", "target_draft_id", "days_before", "include_target_day"},
        "unspecified": {"type"},
    }[kind]
    if set(time) != expected:
        raise DraftError(f"time_intent fields do not match {kind}")
    if kind == "recent_days":
        _int(time["days"], "time_intent.days", 1, 3650)
    elif kind == "explicit_date_range":
        start = _str(time["start"], "time_intent.start")
        end = _str(time["end"], "time_intent.end")
        try:
            if date.fromisoformat(start) > date.fromisoformat(end):
                raise DraftError("explicit date range start is after end")
        except ValueError as exc:
            raise DraftError("explicit date range must use ISO dates") from exc
    elif kind == "latest_matching_sessions":
        _int(time["count"], "time_intent.count", 1, 20)
    elif kind == "before_each_target_event":
        _str(time["target_draft_id"], "time_intent.target_draft_id")
        _int(time["days_before"], "time_intent.days_before", 1, 30)
        if not isinstance(time["include_target_day"], bool):
            raise DraftError("time_intent.include_target_day must be boolean")
    return time


def _validate_dataset(value: Any, catalog: dict[str, Any]) -> dict[str, Any]:
    dataset = _dict(value, "dataset", DATASET_KEYS)
    for key in DATASET_KEYS:
        if key not in dataset:
            raise DraftError(f"dataset missing {key}")
    draft_id = _str(dataset["draft_id"], "dataset.draft_id")
    if not re.fullmatch(r"[a-z][a-z0-9_]{1,48}", draft_id):
        raise DraftError("dataset.draft_id has invalid format")
    kind = _str(dataset["kind"], "dataset.kind")
    if kind not in DATASET_KINDS:
        raise DraftError(f"unsupported dataset kind: {kind}")
    scope = _dict(dataset["scope"], "dataset.scope", SCOPE_KEYS)
    for key, value in scope.items():
        _str(value, f"dataset.scope.{key}")
    time = _validate_time(dataset["time_intent"])
    info = _list(dataset["requested_information"], "requested_information", min_items=1, max_items=12)
    for item in info:
        _str(item, "requested_information item")
    allowed = set(catalog.get("datasets", {}).get(kind, FIELD_RULES[kind]))
    unknown_info = set(info) - allowed
    if unknown_info:
        raise DraftError(f"requested information not available for {kind}: {sorted(unknown_info)}")
    notes = _dict(dataset["notes"], "dataset.notes", NOTE_KEYS)
    if set(notes) != NOTE_KEYS:
        raise DraftError("dataset.notes must contain requested and scopes")
    if not isinstance(notes["requested"], bool):
        raise DraftError("dataset.notes.requested must be boolean")
    scopes = _list(notes["scopes"], "dataset.notes.scopes", max_items=4)
    for scope_name in scopes:
        if scope_name not in NOTE_SCOPES:
            raise DraftError(f"unsupported Notes scope: {scope_name}")
    if notes["requested"] != bool(scopes):
        raise DraftError("Notes requested must match non-empty scopes")
    if kind != "training" and "split" in scope and kind not in {"movement_progress"}:
        raise DraftError("split scope is only valid for training or movement_progress")
    if kind not in {"training", "movement_progress"} and ("body_part" in scope or "movement" in scope):
        raise DraftError("movement scope is only valid for training or movement_progress")
    if kind == "body" and time["type"] == "latest_matching_sessions":
        raise DraftError("latest_matching_sessions is only valid for session datasets")
    if time["type"] == "before_each_target_event" and kind != "diet":
        raise DraftError("before_each_target_event is currently only valid for diet")
    return dataset


def validate_request_draft(draft: dict[str, Any], capability_catalog: dict[str, Any]) -> dict[str, Any]:
    root = _dict(draft, "request draft", GLOBAL_KEYS)
    if set(root) != GLOBAL_KEYS:
        raise DraftError(f"request draft fields do not match v1: {sorted(set(root) ^ GLOBAL_KEYS)}")
    if root["schema_version"] != SCHEMA_VERSION:
        raise DraftError("unsupported schema_version")
    status = _str(root["status"], "status")
    if status not in {"ready", "needs_confirmation", "unsupported"}:
        raise DraftError("invalid status")
    _str(root["purpose"], "purpose")
    datasets = _list(root["datasets"], "datasets", max_items=4)
    if status == "ready" and not datasets:
        raise DraftError("ready draft must contain datasets")
    relations = _list(root["relations"], "relations", max_items=4)
    missing = _list(root["missing_confirmations"], "missing_confirmations", max_items=8)
    warnings = _list(root["warnings"], "warnings", max_items=8)
    for item in [*missing, *warnings]:
        _str(item, "message")
    normalized = json.loads(json.dumps(root, ensure_ascii=False))
    seen: set[str] = set()
    for dataset in datasets:
        checked = _validate_dataset(dataset, capability_catalog)
        if checked["draft_id"] in seen:
            raise DraftError(f"duplicate draft_id: {checked['draft_id']}")
        seen.add(checked["draft_id"])
    for relation in relations:
        checked = _dict(relation, "relation", RELATION_KEYS)
        if set(checked) != RELATION_KEYS or checked["type"] != "preceding_event_window":
            raise DraftError("invalid relation")
        if checked["source_draft_id"] not in seen or checked["dependent_draft_id"] not in seen:
            raise DraftError("relation references unknown dataset")
        if checked["source_draft_id"] == checked["dependent_draft_id"]:
            raise DraftError("relation cannot reference itself")
    for dataset in datasets:
        time = dataset["time_intent"]
        if time["type"] == "before_each_target_event":
            target = time["target_draft_id"]
            if target not in seen or target == dataset["draft_id"]:
                raise DraftError("before_each_target_event references invalid target")
            matching = [r for r in relations if r["source_draft_id"] == target and r["dependent_draft_id"] == dataset["draft_id"]]
            if len(matching) != 1:
                raise DraftError("dependent time intent requires exactly one matching relation")
    if status == "ready" and missing:
        raise DraftError("ready draft cannot contain missing confirmations")
    if status == "needs_confirmation" and not missing:
        raise DraftError("needs_confirmation requires missing confirmations")
    if status == "unsupported" and datasets:
        raise DraftError("unsupported draft cannot request datasets")
    return normalized


def validate_request_grounding(draft: dict[str, Any], user_text: str) -> dict[str, Any]:
    """Reject semantically expanded scope that is absent from the user text."""
    if not isinstance(user_text, str):
        raise DraftError("user_text must be a string for grounding")
    for dataset in draft.get("datasets", []):
        scope = dataset.get("scope", {})
        if "body_part" in scope:
            term = BODY_PART_TERMS.get(scope["body_part"])
            if term is None or term not in user_text:
                raise DraftError(f"ungrounded body_part: {scope['body_part']}")
        if "split" in scope:
            term = SPLIT_TERMS.get(scope["split"])
            if term is None or term not in user_text:
                raise DraftError(f"ungrounded split: {scope['split']}")
        if "movement" in scope:
            terms = MOVEMENT_TERMS.get(scope["movement"], ())
            if not any(term in user_text for term in terms):
                raise DraftError(f"ungrounded movement: {scope['movement']}")
        notes = dataset.get("notes", {})
        if notes.get("requested") and not any(term in user_text.lower() for term in ("笔记", "备注", "notes")):
            raise DraftError("ungrounded Notes request")
        time_intent = dataset.get("time_intent", {})
        time_type = time_intent.get("type")
        if time_type == "latest_matching_sessions":
            count = time_intent.get("count")
            if not (str(count) in user_text or any(term in user_text for term in NUMBER_TERMS.get(count, ()) )):
                raise DraftError(f"ungrounded session count: {count}")
        elif time_type == "recent_days":
            days = time_intent.get("days")
            month_phrase = days == 30 and any(term in user_text for term in ("最近一个月", "最近一月"))
            if not (str(days) in user_text or any(term in user_text for term in NUMBER_TERMS.get(days, ()) ) or month_phrase):
                raise DraftError(f"ungrounded day count: {days}")
        elif time_type == "before_each_target_event":
            days_before = time_intent.get("days_before")
            if not (str(days_before) in user_text or any(term in user_text for term in NUMBER_TERMS.get(days_before, ()) )):
                raise DraftError(f"ungrounded preceding-day count: {days_before}")
    return draft


def compile_request_draft(draft: dict[str, Any], capability_catalog: dict[str, Any]) -> dict[str, Any]:
    """Compile only a validated semantic draft into a read-only handoff shape."""
    checked = validate_request_draft(draft, capability_catalog)
    if checked["status"] != "ready":
        raise DraftError("only ready drafts can be compiled")
    return {
        "compiled_version": "fitness-ledger-compiled-request-v1",
        "status": "ready",
        "purpose": checked["purpose"],
        "datasets": checked["datasets"],
        "relations": checked["relations"],
        "execution": {"allowed": False, "mode": "preview_only", "executor_called": False, "write_allowed": False, "raw": False},
    }


def _error_code(value: str) -> str:
    return value.split(":", 1)[0]


def _audit_summary(intent: Any = None, *, provider_called: bool = False, semantic_hint: Any = None, draft: dict[str, Any] | None = None, errors: list[str] | None = None) -> dict[str, Any]:
    return {
        "route_kind": "unknown" if intent is None else intent.route,
        "provider_called": provider_called,
        "deterministic_intent": None if intent is None else intent.to_summary(),
        "semantic_hint": None if semantic_hint is None else semantic_hint.to_summary(),
        "final_draft": summarize_draft(draft),
        "validation_errors": [_error_code(item) for item in (errors or [])],
    }


def interpret_request(
    user_text: str,
    capability_catalog: dict[str, Any],
    runner: InferenceProvider | Callable[[str], str] | None = None,
) -> dict[str, Any]:
    """Interpret one request through an injectable model runner and fail closed."""
    if not isinstance(user_text, str) or not user_text.strip():
        return {
            "result_version": RESULT_VERSION,
            "status": "needs_confirmation",
            "draft": None,
            "errors": ["EMPTY_REQUEST"],
            "warnings": [],
            "audit": _audit_summary(errors=["EMPTY_REQUEST"]),
        }
    intent = None
    semantic_hint = None
    provider_called = False
    draft = None
    try:
        intent = parse_deterministic_intent(user_text, capability_catalog)
        if intent.route == "deterministic":
            draft = assemble_request_draft(intent)
        else:
            if runner is None or not isinstance(runner, InferenceProvider) or intent.hint_request is None:
                errors = ["MODEL_UNAVAILABLE"]
                return {"result_version": RESULT_VERSION, "status": "model_unavailable", "draft": None, "errors": errors, "warnings": [], "audit": _audit_summary(intent, errors=errors)}
            provider_called = True
            raw = runner.infer_semantic_hint(intent.hint_request)
            semantic_hint = validate_semantic_hint(parse_json_strict(raw), intent.hint_request)
            draft = assemble_request_draft(intent, semantic_hint=semantic_hint, hint_request=intent.hint_request)
        checked = validate_request_draft(draft, capability_catalog)
        validate_request_grounding(checked, user_text)
        return {
            "result_version": RESULT_VERSION,
            "status": checked["status"],
            "draft": checked,
            "errors": [],
            "warnings": checked["warnings"],
            "audit": _audit_summary(intent, provider_called=provider_called, semantic_hint=semantic_hint, draft=checked),
        }
    except ProviderOutputError as exc:
        errors = [str(exc)]
        return {"result_version": RESULT_VERSION, "status": "invalid_model_output", "draft": None, "errors": errors, "warnings": [], "audit": _audit_summary(intent, provider_called=provider_called, semantic_hint=semantic_hint, errors=errors)}
    except (ProviderRuntimeError, ProviderConfigurationError) as exc:
        errors = [str(exc)]
        return {"result_version": RESULT_VERSION, "status": "model_unavailable", "draft": None, "errors": errors, "warnings": [], "audit": _audit_summary(intent, provider_called=provider_called, semantic_hint=semantic_hint, errors=errors)}
    except DraftError as exc:
        errors = [str(exc)]
        return {"result_version": RESULT_VERSION, "status": "invalid_model_output", "draft": None, "errors": errors, "warnings": [], "audit": _audit_summary(intent, provider_called=provider_called, semantic_hint=semantic_hint, errors=errors)}
    except SemanticHintError as exc:
        errors = [str(exc)]
        return {"result_version": RESULT_VERSION, "status": "invalid_model_output", "draft": None, "errors": errors, "warnings": [], "audit": _audit_summary(intent, provider_called=provider_called, semantic_hint=semantic_hint, errors=errors)}
