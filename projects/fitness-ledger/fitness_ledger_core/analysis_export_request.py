"""No-data validator for Analysis Export Request Protocol v1.1.

This module validates a GPT-produced data request only. It never opens the
formal tracker or movement dictionary, resolves a movement, reads Raw data, or
calls an Executor.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
import json
import re
from typing import Any

REQUEST_VERSION = "1.1"
REQUEST_SCHEMA_VERSION = "fitness-ledger-analysis-export-request-v1.1"
DATASET_TYPES = ("body", "diet", "training", "movement_progress")
TIME_MODES = ("recent_days", "explicit_range", "latest_matching_sessions", "days_before_target_session")
NOTES_SCOPES = ("daily", "diet", "training", "movement")
OUTPUT_FORMATS = ("json", "markdown")
SET_ROLES = ("top", "working", "backoff")
MATCH_MODES = ("single_latest_matching_session", "each_matching_session")

DATASET_FIELDS = {
    "body": ("date", "weight_kg", "bowel_movement", "training_label", "cardio_summary"),
    "diet": ("date", "calories_kcal", "protein_g", "carbs_g", "fat_g", "food_summary"),
    "training": ("date", "split", "standardized_summary"),
    "movement_progress": ("date", "movement_id", "movement_name", "body_part", "variant", "order", "sets"),
}
DATASET_FILTERS = {
    "body": frozenset(),
    "diet": frozenset(),
    "training": frozenset({"body_part", "split"}),
    "movement_progress": frozenset({"movement_selector"}),
}
FILTER_NAMES = ("body_part", "split", "movement_selector")
SELECTOR_KINDS = ("movement_id", "movement_name", "body_part")
NOTES_TO_DATASET = {"daily": "body", "diet": "diet", "training": "training", "movement": "movement_progress"}
NOTES_BY_DATASET = {"body": "daily", "diet": "diet", "training": "training", "movement_progress": "movement"}
_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MOVEMENT_ID = re.compile(r"^[A-Za-z0-9_.:-]+$")


@dataclass(frozen=True)
class RequestError:
    code: str
    path: str
    message: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class RequestValidationResult:
    valid: bool
    normalized_request: dict[str, Any] | None
    errors: list[RequestError]
    preview: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": REQUEST_SCHEMA_VERSION,
            "valid": self.valid,
            "normalized_request": self.normalized_request,
            "errors": [error.to_dict() for error in self.errors],
            "preview": self.preview,
        }


def _error(errors: list[RequestError], code: str, path: str, message: str) -> None:
    errors.append(RequestError(code, path, message))


def _has_duplicates(values: list[Any]) -> bool:
    return any(values[index] == values[other] for index in range(len(values)) for other in range(index))


def _unknown_keys(value: dict[str, Any], allowed: set[str], path: str, errors: list[RequestError]) -> None:
    for key in sorted(set(value) - allowed):
        _error(errors, "UNKNOWN_PROPERTY", f"{path}.{key}", f"Unknown property: {key}")


def _required(value: dict[str, Any], names: tuple[str, ...], path: str, errors: list[RequestError]) -> None:
    for name in names:
        if name not in value:
            _error(errors, "MISSING_REQUIRED_PROPERTY", f"{path}.{name}", f"Missing required property: {name}")


def _string(value: Any, path: str, errors: list[RequestError], *, minimum: int = 1, maximum: int = 500) -> str | None:
    if not isinstance(value, str):
        _error(errors, "INVALID_TYPE", path, "Expected a string")
        return None
    text = value.strip()
    if len(text) < minimum:
        _error(errors, "STRING_TOO_SHORT", path, f"String must contain at least {minimum} character(s)")
    if len(text) > maximum:
        _error(errors, "STRING_TOO_LONG", path, f"String must contain at most {maximum} characters")
    return text


def _integer(value: Any, path: str, errors: list[RequestError], minimum: int, maximum: int) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        _error(errors, "INVALID_TYPE", path, "Expected an integer")
        return None
    if not minimum <= value <= maximum:
        _error(errors, "INTEGER_OUT_OF_RANGE", path, f"Expected an integer from {minimum} to {maximum}")
    return value


def _validate_date(value: Any, path: str, errors: list[RequestError]) -> str | None:
    text = _string(value, path, errors, maximum=10)
    if text is None:
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        _error(errors, "INVALID_DATE", path, "Expected ISO date YYYY-MM-DD")
    return text


def _validate_time_range(value: Any, dataset_type: str, path: str, errors: list[RequestError]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _error(errors, "INVALID_TYPE", path, "Expected a time_range object")
        return None
    mode = value.get("mode")
    if mode not in TIME_MODES:
        _error(errors, "UNKNOWN_TIME_MODE", f"{path}.mode", f"Unsupported time mode: {mode}")
        return None
    allowed_by_type = {
        "body": {"recent_days", "explicit_range"},
        "diet": {"recent_days", "explicit_range", "days_before_target_session"},
        "training": {"recent_days", "explicit_range", "latest_matching_sessions"},
        "movement_progress": {"recent_days", "explicit_range", "latest_matching_sessions"},
    }
    if mode not in allowed_by_type[dataset_type]:
        _error(errors, "TIME_MODE_NOT_SUPPORTED_FOR_DATASET", f"{path}.mode", f"{mode} is not supported for {dataset_type}")
        return None
    normalized: dict[str, Any] = {"mode": mode}
    if mode == "recent_days":
        _unknown_keys(value, {"mode", "days"}, path, errors); _required(value, ("days",), path, errors)
        if "days" in value: normalized["days"] = _integer(value["days"], f"{path}.days", errors, 1, 3650)
    elif mode == "explicit_range":
        _unknown_keys(value, {"mode", "start", "end"}, path, errors); _required(value, ("start", "end"), path, errors)
        if "start" in value: normalized["start"] = _validate_date(value["start"], f"{path}.start", errors)
        if "end" in value: normalized["end"] = _validate_date(value["end"], f"{path}.end", errors)
        try:
            if date.fromisoformat(normalized["start"]) > date.fromisoformat(normalized["end"]):
                _error(errors, "DATE_RANGE_REVERSED", path, "start must not be after end")
        except (KeyError, TypeError, ValueError):
            pass
    elif mode == "latest_matching_sessions":
        _unknown_keys(value, {"mode", "sessions"}, path, errors); _required(value, ("sessions",), path, errors)
        if "sessions" in value: normalized["sessions"] = _integer(value["sessions"], f"{path}.sessions", errors, 1, 20)
    else:
        allowed = {"mode", "days_before", "target_dataset_id", "target_date", "match_mode", "include_target_session_day"}
        _unknown_keys(value, allowed, path, errors)
        _required(value, ("days_before", "match_mode", "include_target_session_day"), path, errors)
        if "days_before" in value: normalized["days_before"] = _integer(value["days_before"], f"{path}.days_before", errors, 1, 30)
        match_mode = value.get("match_mode")
        if match_mode not in MATCH_MODES:
            _error(errors, "UNKNOWN_MATCH_MODE", f"{path}.match_mode", f"Unsupported match mode: {match_mode}")
        else: normalized["match_mode"] = match_mode
        include_day = value.get("include_target_session_day")
        if not isinstance(include_day, bool): _error(errors, "INVALID_TYPE", f"{path}.include_target_session_day", "Expected a boolean")
        else: normalized["include_target_session_day"] = include_day
        has_dataset = "target_dataset_id" in value
        has_date = "target_date" in value
        if has_dataset == has_date:
            _error(errors, "TARGET_REFERENCE_EXCLUSIVE", path, "Provide exactly one of target_dataset_id or target_date")
        if has_dataset:
            target = _string(value.get("target_dataset_id"), f"{path}.target_dataset_id", errors, maximum=64)
            if target and not _IDENTIFIER.fullmatch(target): _error(errors, "INVALID_DATASET_ID", f"{path}.target_dataset_id", "Invalid dataset_id format")
            if target: normalized["target_dataset_id"] = target
        if has_date:
            target_date = _validate_date(value.get("target_date"), f"{path}.target_date", errors)
            if target_date: normalized["target_date"] = target_date
            if match_mode == "each_matching_session": _error(errors, "MATCH_MODE_REQUIRES_DATASET", f"{path}.match_mode", "each_matching_session requires target_dataset_id")
    return normalized


def _validate_selector(value: Any, path: str, errors: list[RequestError]) -> dict[str, str] | None:
    if not isinstance(value, dict):
        _error(errors, "INVALID_TYPE", path, "Expected movement_selector object")
        return None
    _unknown_keys(value, {"kind", "value"}, path, errors); _required(value, ("kind", "value"), path, errors)
    kind = value.get("kind")
    if kind not in SELECTOR_KINDS: _error(errors, "UNKNOWN_MOVEMENT_SELECTOR", f"{path}.kind", f"Unsupported selector kind: {kind}")
    text = _string(value.get("value"), f"{path}.value", errors, maximum=120)
    if kind == "movement_id" and text and not _MOVEMENT_ID.fullmatch(text): _error(errors, "INVALID_MOVEMENT_ID", f"{path}.value", "movement_id contains unsupported characters")
    return {"kind": kind, "value": text or ""}


def _validate_filters(value: Any, dataset_type: str, path: str, errors: list[RequestError]) -> dict[str, Any] | None:
    if not isinstance(value, dict): _error(errors, "INVALID_TYPE", path, "Expected a filters object"); return None
    allowed = DATASET_FILTERS[dataset_type]
    _unknown_keys(value, set(allowed), path, errors)
    normalized: dict[str, Any] = {}
    for key in sorted(set(value) & set(allowed)):
        if key == "movement_selector":
            selector = _validate_selector(value[key], f"{path}.{key}", errors)
            if selector: normalized[key] = selector
        else:
            text = _string(value[key], f"{path}.{key}", errors, maximum=80)
            if text: normalized[key] = text
    return normalized


def _validate_fields(value: Any, dataset_type: str, path: str, errors: list[RequestError]) -> list[str]:
    if not isinstance(value, list): _error(errors, "INVALID_TYPE", path, "Expected an array"); return []
    if not value: _error(errors, "EMPTY_FIELDS", path, "At least one field must be requested")
    if _has_duplicates(value): _error(errors, "DUPLICATE_FIELD", path, "Fields must be unique")
    fields: list[str] = []
    for index, item in enumerate(value):
        text = _string(item, f"{path}[{index}]", errors, maximum=80)
        if text:
            fields.append(text)
            if text not in DATASET_FIELDS[dataset_type]: _error(errors, "UNKNOWN_FIELD", f"{path}[{index}]", f"Field {text} is not available for {dataset_type}")
    return fields


def _validate_dataset(value: Any, index: int, errors: list[RequestError]) -> dict[str, Any] | None:
    path = f"datasets[{index}]"
    if not isinstance(value, dict): _error(errors, "INVALID_TYPE", path, "Expected a dataset object"); return None
    dataset_type = value.get("type")
    if dataset_type not in DATASET_TYPES: _error(errors, "UNKNOWN_DATASET_TYPE", f"{path}.type", f"Unsupported dataset type: {dataset_type}"); return None
    allowed = {"dataset_id", "type", "time_range", "filters", "fields", "notes_scope"} | ({"set_roles"} if dataset_type == "movement_progress" else set())
    _unknown_keys(value, allowed, path, errors); _required(value, ("dataset_id", "type", "time_range", "filters", "fields"), path, errors)
    dataset_id = _string(value.get("dataset_id"), f"{path}.dataset_id", errors, maximum=64) or ""
    if dataset_id and not _IDENTIFIER.fullmatch(dataset_id): _error(errors, "INVALID_DATASET_ID", f"{path}.dataset_id", "dataset_id must match ^[a-z][a-z0-9_]{0,63}$")
    time_range = _validate_time_range(value.get("time_range"), dataset_type, f"{path}.time_range", errors)
    filters = _validate_filters(value.get("filters"), dataset_type, f"{path}.filters", errors)
    fields = _validate_fields(value.get("fields"), dataset_type, f"{path}.fields", errors)
    normalized: dict[str, Any] = {"dataset_id": dataset_id, "type": dataset_type, "time_range": time_range or {}, "filters": filters or {}, "fields": fields}
    notes_scope = value.get("notes_scope")
    if notes_scope is not None:
        text = _string(notes_scope, f"{path}.notes_scope", errors, maximum=20)
        expected = NOTES_BY_DATASET[dataset_type]
        if text not in NOTES_SCOPES: _error(errors, "UNKNOWN_NOTES_SCOPE", f"{path}.notes_scope", f"Unsupported Notes scope: {text}")
        elif text != expected: _error(errors, "NOTES_SCOPE_DATASET_MISMATCH", f"{path}.notes_scope", f"{dataset_type} accepts Notes scope {expected}")
        else: normalized["notes_scope"] = text
    if dataset_type == "movement_progress" and "set_roles" in value:
        roles = value["set_roles"]
        if not isinstance(roles, list): _error(errors, "INVALID_TYPE", f"{path}.set_roles", "Expected an array")
        elif not roles: _error(errors, "EMPTY_SET_ROLES", f"{path}.set_roles", "At least one set role is required")
        else:
            if _has_duplicates(roles): _error(errors, "DUPLICATE_SET_ROLE", f"{path}.set_roles", "Set roles must be unique")
            normalized_roles = []
            for role_index, role in enumerate(roles):
                text = _string(role, f"{path}.set_roles[{role_index}]", errors, maximum=20)
                if text:
                    if text not in SET_ROLES: _error(errors, "UNKNOWN_SET_ROLE", f"{path}.set_roles[{role_index}]", f"Unsupported set role: {text}")
                    else: normalized_roles.append(text)
            if normalized_roles: normalized["set_roles"] = [role for role in SET_ROLES if role in normalized_roles]
    return normalized


def _preview(normalized: dict[str, Any] | None, errors: list[RequestError], raw_value: Any = False) -> dict[str, Any]:
    raw_requested = raw_value is True
    datasets = (normalized or {}).get("datasets", [])
    return {
        "status": "valid" if normalized is not None and not errors else "invalid",
        "purpose": (normalized or {}).get("purpose", ""),
        "requested_data": datasets,
        "notes": {"scopes": [item["notes_scope"] for item in datasets if "notes_scope" in item]},
        "raw": {"requested": raw_requested, "allowed": False, "status": "rejected" if raw_requested else "not_requested"},
        "execution": {"executor_called": False, "formal_data_written": False},
        "error_count": len(errors),
    }


def validate_request(value: Any) -> RequestValidationResult:
    errors: list[RequestError] = []
    if not isinstance(value, dict):
        _error(errors, "INVALID_JSON_ROOT", "$", "Request must be a JSON object")
        return RequestValidationResult(False, None, errors, _preview(None, errors))
    _unknown_keys(value, {"request_version", "purpose", "datasets", "raw", "output"}, "$", errors)
    _required(value, ("request_version", "purpose", "datasets", "raw", "output"), "$", errors)
    if value.get("request_version") != REQUEST_VERSION: _error(errors, "UNSUPPORTED_REQUEST_VERSION", "$.request_version", f"request_version must be \"{REQUEST_VERSION}\"")
    purpose = _string(value.get("purpose"), "$.purpose", errors, maximum=500)
    dataset_values = value.get("datasets")
    datasets: list[dict[str, Any]] = []
    if not isinstance(dataset_values, list): _error(errors, "INVALID_TYPE", "$.datasets", "Expected an array")
    elif not dataset_values: _error(errors, "EMPTY_DATASETS", "$.datasets", "At least one dataset must be requested")
    elif len(dataset_values) > 8: _error(errors, "TOO_MANY_DATASETS", "$.datasets", "At most 8 datasets may be requested")
    else:
        for index, item in enumerate(dataset_values):
            dataset = _validate_dataset(item, index, errors)
            if dataset is not None: datasets.append(dataset)
        ids = [item["dataset_id"] for item in datasets]
        if len(ids) != len(set(ids)): _error(errors, "DUPLICATE_DATASET_ID", "$.datasets", "dataset_id values must be unique")
        known_ids = set(ids)
        for dataset in datasets:
            time_range = dataset.get("time_range", {})
            if time_range.get("mode") != "days_before_target_session": continue
            target_id = time_range.get("target_dataset_id")
            if target_id:
                if target_id not in known_ids: _error(errors, "UNKNOWN_TARGET_DATASET", f"$.datasets[{ids.index(dataset['dataset_id'])}].time_range.target_dataset_id", f"Unknown target dataset_id: {target_id}")
                elif target_id == dataset["dataset_id"]: _error(errors, "SELF_TARGET_DATASET", f"$.datasets[{ids.index(dataset['dataset_id'])}].time_range.target_dataset_id", "A dataset cannot target itself")
                else:
                    target = next(item for item in datasets if item["dataset_id"] == target_id)
                    if target["type"] != "training": _error(errors, "TARGET_DATASET_NOT_TRAINING", f"$.datasets[{ids.index(dataset['dataset_id'])}].time_range.target_dataset_id", "Target dataset must be training")
    raw = value.get("raw")
    if not isinstance(raw, bool): _error(errors, "INVALID_TYPE", "$.raw", "raw must be boolean"); raw = False
    elif raw: _error(errors, "RAW_PERMISSION_REQUIRED", "$.raw", "Raw is not GPT-authorized in request protocol v1.1")
    output = value.get("output")
    formats: list[str] = []
    if not isinstance(output, dict): _error(errors, "INVALID_TYPE", "$.output", "Expected an output object")
    else:
        _unknown_keys(output, {"formats"}, "$.output", errors); _required(output, ("formats",), "$.output", errors)
        value_formats = output.get("formats")
        if not isinstance(value_formats, list): _error(errors, "INVALID_TYPE", "$.output.formats", "Expected an array")
        elif not value_formats: _error(errors, "EMPTY_OUTPUT_FORMATS", "$.output.formats", "At least one output format is required")
        else:
            if _has_duplicates(value_formats): _error(errors, "DUPLICATE_OUTPUT_FORMAT", "$.output.formats", "Output formats must be unique")
            for index, item in enumerate(value_formats):
                text = _string(item, f"$.output.formats[{index}]", errors, maximum=20)
                if text:
                    formats.append(text)
                    if text not in OUTPUT_FORMATS: _error(errors, "UNKNOWN_OUTPUT_FORMAT", f"$.output.formats[{index}]", f"Unsupported output format: {text}")
    normalized = {"request_version": REQUEST_VERSION, "purpose": purpose or "", "datasets": datasets, "raw": False, "output": {"formats": [item for item in OUTPUT_FORMATS if item in formats]}}
    valid = not errors
    return RequestValidationResult(valid, normalized if valid else None, errors, _preview(normalized if valid else None, errors, raw))


def validate_json(text: str) -> RequestValidationResult:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        error = RequestError("INVALID_JSON", "$", f"Invalid JSON: {exc}")
        return RequestValidationResult(False, None, [error], _preview(None, [error]))
    return validate_request(value)
