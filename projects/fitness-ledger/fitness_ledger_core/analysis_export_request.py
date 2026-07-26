"""No-data validator for Analysis Export Request v1.

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

REQUEST_VERSION = "1"
REQUEST_SCHEMA_VERSION = "fitness-ledger-analysis-export-request-v1"
DATASET_TYPES = ("body", "diet", "training", "movement_progress")
TIME_MODES = ("recent_days", "explicit_range", "latest_matching_sessions", "days_before_target_session")
NOTES_SCOPES = ("daily", "diet", "training", "movement")
OUTPUT_FORMATS = ("json", "markdown")

DATASET_FIELDS = {
    "body": ("date", "weight_kg", "bowel_movement", "training_label", "cardio_summary"),
    "diet": ("date", "calories_kcal", "protein_g", "carbs_g", "fat_g", "food_summary"),
    "training": ("date", "split", "standardized_summary"),
    "movement_progress": ("date", "movement_id", "movement_name", "body_part", "variant", "order", "sets"),
}
FILTERS_BY_DATASET = {
    "body": frozenset({"body_part"}),
    "diet": frozenset(),
    "training": frozenset({"body_part", "split"}),
    "movement_progress": frozenset({"body_part", "movement_name", "movement_id", "split"}),
}
FILTER_NAMES = ("body_part", "movement_name", "movement_id", "split")
NOTES_TO_DATASET = {"daily": "body", "diet": "diet", "training": "training", "movement": "movement_progress"}
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


class RequestProtocolError(ValueError):
    pass


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


def _validate_time_range(value: Any, path: str, errors: list[RequestError]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        _error(errors, "INVALID_TYPE", path, "Expected a time_range object")
        return None
    if "mode" not in value:
        _error(errors, "MISSING_REQUIRED_PROPERTY", f"{path}.mode", "Missing time mode")
        return None
    mode = value.get("mode")
    if mode not in TIME_MODES:
        _error(errors, "UNKNOWN_TIME_MODE", f"{path}.mode", f"Unsupported time mode: {mode}")
        return None
    requirements = {
        "recent_days": ("days",),
        "explicit_range": ("start", "end"),
        "latest_matching_sessions": ("sessions",),
        "days_before_target_session": ("days_before",),
    }
    _unknown_keys(value, {"mode", *requirements[mode]}, path, errors)
    _required(value, requirements[mode], path, errors)
    normalized: dict[str, Any] = {"mode": mode}
    if mode == "recent_days" and "days" in value:
        normalized["days"] = _integer(value["days"], f"{path}.days", errors, 1, 3650)
    elif mode == "latest_matching_sessions" and "sessions" in value:
        normalized["sessions"] = _integer(value["sessions"], f"{path}.sessions", errors, 1, 20)
    elif mode == "days_before_target_session" and "days_before" in value:
        normalized["days_before"] = _integer(value["days_before"], f"{path}.days_before", errors, 1, 30)
    elif mode == "explicit_range":
        parsed: dict[str, date] = {}
        for key in ("start", "end"):
            if key not in value:
                continue
            text = _string(value[key], f"{path}.{key}", errors, maximum=10)
            if text is None:
                continue
            try:
                parsed[key] = date.fromisoformat(text)
            except ValueError:
                _error(errors, "INVALID_DATE", f"{path}.{key}", "Expected ISO date YYYY-MM-DD")
            normalized[key] = text
        if len(parsed) == 2 and parsed["start"] > parsed["end"]:
            _error(errors, "DATE_RANGE_REVERSED", path, "start must not be after end")
    return normalized


def _validate_filters(value: Any, dataset_type: str, path: str, errors: list[RequestError]) -> dict[str, str] | None:
    if not isinstance(value, dict):
        _error(errors, "INVALID_TYPE", path, "Expected a filters object")
        return None
    _unknown_keys(value, set(FILTER_NAMES), path, errors)
    allowed = FILTERS_BY_DATASET[dataset_type]
    for name in sorted(set(value) & (set(FILTER_NAMES) - allowed)):
        _error(errors, "FILTER_NOT_SUPPORTED_FOR_DATASET", f"{path}.{name}", f"Filter {name} is not supported for {dataset_type}")
    normalized: dict[str, str] = {}
    for name, item in value.items():
        if name not in FILTER_NAMES or name not in allowed:
            continue
        text = _string(item, f"{path}.{name}", errors, maximum=120)
        if text:
            normalized[name] = text
        if name == "movement_id" and text and not _MOVEMENT_ID.fullmatch(text):
            _error(errors, "INVALID_MOVEMENT_ID", f"{path}.{name}", "movement_id contains unsupported characters")
    return normalized


def _validate_dataset(value: Any, index: int, errors: list[RequestError]) -> dict[str, Any] | None:
    path = f"datasets[{index}]"
    if not isinstance(value, dict):
        _error(errors, "INVALID_TYPE", path, "Expected a dataset object")
        return None
    _unknown_keys(value, {"type", "time_range", "filters", "fields", "include_notes"}, path, errors)
    _required(value, ("type", "time_range", "filters", "fields", "include_notes"), path, errors)
    dataset_type = value.get("type")
    if dataset_type not in DATASET_TYPES:
        _error(errors, "UNKNOWN_DATASET_TYPE", f"{path}.type", f"Unsupported dataset type: {dataset_type}")
        return None
    time_range = _validate_time_range(value.get("time_range"), f"{path}.time_range", errors)
    filters = _validate_filters(value.get("filters"), dataset_type, f"{path}.filters", errors)
    fields_value = value.get("fields")
    fields: list[str] = []
    if not isinstance(fields_value, list):
        _error(errors, "INVALID_TYPE", f"{path}.fields", "Expected an array")
    else:
        if not fields_value:
            _error(errors, "EMPTY_FIELDS", f"{path}.fields", "At least one field must be requested")
        if _has_duplicates(fields_value):
            _error(errors, "DUPLICATE_FIELD", f"{path}.fields", "Fields must be unique")
        for field_index, field in enumerate(fields_value):
            text = _string(field, f"{path}.fields[{field_index}]", errors, maximum=80)
            if text:
                fields.append(text)
                if text not in DATASET_FIELDS[dataset_type]:
                    _error(errors, "UNKNOWN_FIELD", f"{path}.fields[{field_index}]", f"Field {text} is not available for {dataset_type}")
    include_notes = value.get("include_notes")
    if not isinstance(include_notes, bool):
        _error(errors, "INVALID_TYPE", f"{path}.include_notes", "Expected a boolean")
        include_notes = False
    return {"type": dataset_type, "time_range": time_range or {}, "filters": filters or {}, "fields": fields, "include_notes": include_notes}


def _preview(normalized: dict[str, Any] | None, errors: list[RequestError], raw_value: Any = False) -> dict[str, Any]:
    raw_requested = raw_value is True
    result = {
        "status": "valid" if normalized is not None and not errors else "invalid",
        "requested_data": normalized.get("datasets", []) if normalized else [],
        "notes": {"scope": normalized.get("notes_scope", []) if normalized else [], "included": any(item.get("include_notes") for item in (normalized or {}).get("datasets", []))},
        "raw": {"requested": raw_requested, "allowed": False, "status": "rejected" if raw_requested else "not_requested"},
        "execution": {"executor_called": False, "formal_data_written": False},
    }
    if errors:
        result["error_count"] = len(errors)
    return result


def validate_request(value: Any) -> RequestValidationResult:
    errors: list[RequestError] = []
    if not isinstance(value, dict):
        _error(errors, "INVALID_JSON_ROOT", "$", "Request must be a JSON object")
        return RequestValidationResult(False, None, errors, _preview(None, errors))
    _unknown_keys(value, {"request_version", "purpose", "datasets", "notes_scope", "raw", "output"}, "$", errors)
    _required(value, ("request_version", "purpose", "datasets", "notes_scope", "raw", "output"), "$", errors)
    if value.get("request_version") != REQUEST_VERSION:
        _error(errors, "UNSUPPORTED_REQUEST_VERSION", "$.request_version", "request_version must be \"1\"")
    purpose = _string(value.get("purpose"), "$.purpose", errors, maximum=500)
    datasets_value = value.get("datasets")
    datasets: list[dict[str, Any]] = []
    if not isinstance(datasets_value, list):
        _error(errors, "INVALID_TYPE", "$.datasets", "Expected an array")
    elif not datasets_value:
        _error(errors, "EMPTY_DATASETS", "$.datasets", "At least one dataset must be requested")
    elif len(datasets_value) > 8:
        _error(errors, "TOO_MANY_DATASETS", "$.datasets", "At most 8 datasets may be requested")
    else:
        for index, item in enumerate(datasets_value):
            dataset = _validate_dataset(item, index, errors)
            if dataset is not None:
                datasets.append(dataset)
        types = [item["type"] for item in datasets]
        if len(types) != len(set(types)):
            _error(errors, "DUPLICATE_DATASET_TYPE", "$.datasets", "Each dataset type may appear at most once")
    notes_value = value.get("notes_scope")
    notes_scope: list[str] = []
    if not isinstance(notes_value, list):
        _error(errors, "INVALID_TYPE", "$.notes_scope", "Expected an array")
    else:
        if _has_duplicates(notes_value):
            _error(errors, "DUPLICATE_NOTES_SCOPE", "$.notes_scope", "Notes scopes must be unique")
        for index, item in enumerate(notes_value):
            text = _string(item, f"$.notes_scope[{index}]", errors, maximum=20)
            if text:
                notes_scope.append(text)
                if text not in NOTES_SCOPES:
                    _error(errors, "UNKNOWN_NOTES_SCOPE", f"$.notes_scope[{index}]", f"Unsupported Notes scope: {text}")
    raw = value.get("raw")
    if not isinstance(raw, bool):
        _error(errors, "INVALID_TYPE", "$.raw", "raw must be boolean")
        raw = False
    elif raw:
        _error(errors, "RAW_PERMISSION_REQUIRED", "$.raw", "Raw is not GPT-authorized in request protocol v1")
    output = value.get("output")
    formats: list[str] = []
    if not isinstance(output, dict):
        _error(errors, "INVALID_TYPE", "$.output", "Expected an output object")
    else:
        _unknown_keys(output, {"formats"}, "$.output", errors)
        _required(output, ("formats",), "$.output", errors)
        formats_value = output.get("formats")
        if not isinstance(formats_value, list):
            _error(errors, "INVALID_TYPE", "$.output.formats", "Expected an array")
        elif not formats_value:
            _error(errors, "EMPTY_OUTPUT_FORMATS", "$.output.formats", "At least one output format is required")
        else:
            if _has_duplicates(formats_value):
                _error(errors, "DUPLICATE_OUTPUT_FORMAT", "$.output.formats", "Output formats must be unique")
            for index, item in enumerate(formats_value):
                text = _string(item, f"$.output.formats[{index}]", errors, maximum=20)
                if text:
                    formats.append(text)
                    if text not in OUTPUT_FORMATS:
                        _error(errors, "UNKNOWN_OUTPUT_FORMAT", f"$.output.formats[{index}]", f"Unsupported output format: {text}")
    includes_notes = {NOTES_TO_DATASET[scope] for scope in notes_scope if scope in NOTES_TO_DATASET}
    dataset_notes = {item["type"] for item in datasets if item.get("include_notes")}
    if includes_notes and not includes_notes.intersection(dataset_notes):
        _error(errors, "NOTES_SCOPE_NOT_REQUESTED", "$.notes_scope", "Every Notes scope needs a matching dataset with include_notes=true")
    for item in datasets:
        if item.get("include_notes") and NOTES_TO_DATASET.get(next((scope for scope in notes_scope if NOTES_TO_DATASET.get(scope) == item["type"]), "")) is None:
            _error(errors, "NOTES_SCOPE_REQUIRED", "$.notes_scope", f"Dataset {item['type']} includes Notes but no matching Notes scope was requested")
    normalized = {
        "request_version": REQUEST_VERSION,
        "purpose": purpose or "",
        "datasets": datasets,
        "notes_scope": sorted(set(notes_scope)),
        "raw": False,
        "output": {"formats": [item for item in OUTPUT_FORMATS if item in formats]},
    }
    valid = not errors
    return RequestValidationResult(valid, normalized if valid else None, errors, _preview(normalized if valid else None, errors, raw))


def validate_json(text: str) -> RequestValidationResult:
    try:
        value = json.loads(text)
    except (TypeError, json.JSONDecodeError) as exc:
        error = RequestError("INVALID_JSON", "$", f"Invalid JSON: {exc}")
        return RequestValidationResult(False, None, [error], _preview(None, [error]))
    return validate_request(value)
