from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

REQUEST_VERSION = "1.1"
MAX_DATASETS = 8

ALLOWED_REQUEST_KEYS = {
    "request_version",
    "purpose",
    "datasets",
    "raw",
    "output",
}
REQUIRED_REQUEST_KEYS = set(ALLOWED_REQUEST_KEYS)

ALLOWED_DATASET_KEYS = {
    "dataset_id",
    "type",
    "time_range",
    "filters",
    "fields",
    "notes_scope",
}
REQUIRED_DATASET_KEYS = {
    "dataset_id",
    "type",
    "time_range",
    "filters",
    "fields",
}

ALLOWED_FIELDS: dict[str, set[str]] = {
    "body": {
        "date",
        "weight_kg",
        "bowel_movement",
        "training_label",
        "cardio_summary",
    },
    "diet": {
        "date",
        "calories_kcal",
        "protein_g",
        "carbs_g",
        "fat_g",
        "food_summary",
    },
    "training": {
        "date",
        "split",
        "standardized_summary",
    },
    "movement_progress": {
        "date",
        "movement_id",
        "movement_name",
        "body_part",
        "variant",
        "order",
        "sets",
    },
}

NOTES_SCOPE_BY_TYPE = {
    "body": "daily",
    "diet": "diet",
    "training": "training",
    "movement_progress": "movement",
}

TIME_MODE_KEYS: dict[str, tuple[set[str], set[str]]] = {
    "recent_days": ({"mode", "days"}, {"mode", "days"}),
    "latest_matching_sessions": ({"mode", "sessions"}, {"mode", "sessions"}),
    "all_available": ({"mode"}, {"mode"}),
    "explicit_range": ({"mode", "start", "end"}, {"mode", "start", "end"}),
    "days_before_target_session": (
        {
            "mode",
            "days_before",
            "include_target_session_day",
            "match_mode",
            "target_dataset_id",
        },
        {
            "mode",
            "days_before",
            "include_target_session_day",
            "target_dataset_id",
        },
    ),
}

ALLOWED_SELECTOR_KINDS = {"movement_id", "movement_name", "body_part"}


class AnalysisExportContractError(ValueError):
    """Raised when a generated request violates the known v1.1 contract."""


def _is_non_string_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def validate_analysis_export_request(
    request: Mapping[str, Any],
    *,
    max_datasets: int = MAX_DATASETS,
) -> list[str]:
    """
    Validate the conservative, confirmed AnalysisExportRequest v1.1 shape.

    This is a package-level contract guard. The live project's authoritative
    validator must still run after integration.
    """
    errors: list[str] = []

    unknown_request = sorted(set(request) - ALLOWED_REQUEST_KEYS)
    if unknown_request:
        errors.append(f"request: unknown properties {unknown_request}")

    missing_request = sorted(REQUIRED_REQUEST_KEYS - set(request))
    if missing_request:
        errors.append(f"request: missing required properties {missing_request}")

    if request.get("request_version") != REQUEST_VERSION:
        errors.append('request.request_version must equal "1.1"')
    if request.get("raw") is not False:
        errors.append("request.raw must be false")
    if not isinstance(request.get("purpose"), str) or not request.get("purpose", "").strip():
        errors.append("request.purpose must be a non-empty string")

    output = request.get("output")
    if not isinstance(output, Mapping):
        errors.append("request.output must be an object")
    else:
        if set(output) != {"formats"}:
            errors.append("request.output only supports the formats property")
        formats = output.get("formats")
        if not _is_non_string_sequence(formats) or list(formats) != ["json"]:
            errors.append('request.output.formats must equal ["json"]')

    datasets = request.get("datasets")
    if not _is_non_string_sequence(datasets):
        errors.append("request.datasets must be an array")
        return errors
    if len(datasets) == 0:
        errors.append("request.datasets must not be empty")
    if len(datasets) > max_datasets:
        errors.append(
            f"request.datasets contains {len(datasets)} items; maximum is {max_datasets}"
        )

    dataset_ids: list[str] = []
    relationship_targets: list[tuple[int, str]] = []

    for index, dataset in enumerate(datasets):
        path = f"request.datasets[{index}]"
        if not isinstance(dataset, Mapping):
            errors.append(f"{path} must be an object")
            continue

        unknown_dataset = sorted(set(dataset) - ALLOWED_DATASET_KEYS)
        if unknown_dataset:
            errors.append(f"{path}: unknown properties {unknown_dataset}")

        missing_dataset = sorted(REQUIRED_DATASET_KEYS - set(dataset))
        if missing_dataset:
            errors.append(f"{path}: missing required properties {missing_dataset}")

        dataset_id = dataset.get("dataset_id")
        if not isinstance(dataset_id, str) or not dataset_id.strip():
            errors.append(f"{path}.dataset_id must be a non-empty string")
        else:
            dataset_ids.append(dataset_id)

        dataset_type = dataset.get("type")
        if dataset_type not in ALLOWED_FIELDS:
            errors.append(f"{path}.type is unsupported: {dataset_type!r}")

        fields = dataset.get("fields")
        if not _is_non_string_sequence(fields) or not fields:
            errors.append(f"{path}.fields must be a non-empty array")
        elif dataset_type in ALLOWED_FIELDS:
            unknown_fields = sorted(set(fields) - ALLOWED_FIELDS[dataset_type])
            if unknown_fields:
                errors.append(f"{path}.fields contains unsupported fields {unknown_fields}")
            if len(set(fields)) != len(fields):
                errors.append(f"{path}.fields contains duplicates")

        notes_scope = dataset.get("notes_scope")
        expected_scope = NOTES_SCOPE_BY_TYPE.get(dataset_type)
        if notes_scope is not None and notes_scope != expected_scope:
            errors.append(
                f"{path}.notes_scope must be {expected_scope!r} for {dataset_type!r}"
            )

        filters = dataset.get("filters")
        if not isinstance(filters, Mapping):
            errors.append(f"{path}.filters must be an object")
            filters = {}

        if "movement_selector" in dataset:
            errors.append(
                f"{path}.movement_selector must be nested under {path}.filters"
            )
        if "raw" in dataset:
            errors.append(f"{path}.raw is not allowed; raw is request-level only")

        selector = filters.get("movement_selector") if isinstance(filters, Mapping) else None
        if dataset_type == "movement_progress":
            if not isinstance(selector, Mapping):
                errors.append(f"{path}.filters.movement_selector is required")
            else:
                if set(selector) != {"kind", "value"}:
                    errors.append(
                        f"{path}.filters.movement_selector must contain only kind and value"
                    )
                if selector.get("kind") not in ALLOWED_SELECTOR_KINDS:
                    errors.append(
                        f"{path}.filters.movement_selector.kind is unsupported: "
                        f"{selector.get('kind')!r}"
                    )
                if not isinstance(selector.get("value"), str) or not selector.get("value", "").strip():
                    errors.append(
                        f"{path}.filters.movement_selector.value must be a non-empty string"
                    )
        elif selector is not None:
            errors.append(
                f"{path}.filters.movement_selector is only valid for movement_progress"
            )

        time_range = dataset.get("time_range")
        if not isinstance(time_range, Mapping):
            errors.append(f"{path}.time_range must be an object")
            continue
        mode = time_range.get("mode")
        if mode not in TIME_MODE_KEYS:
            errors.append(f"{path}.time_range.mode is unsupported: {mode!r}")
            continue
        allowed_keys, required_keys = TIME_MODE_KEYS[mode]
        unknown_time_keys = sorted(set(time_range) - allowed_keys)
        if unknown_time_keys:
            errors.append(
                f"{path}.time_range has unsupported properties {unknown_time_keys} for {mode}"
            )
        missing_time_keys = sorted(required_keys - set(time_range))
        if missing_time_keys:
            errors.append(
                f"{path}.time_range is missing properties {missing_time_keys} for {mode}"
            )
        if mode in {"recent_days", "latest_matching_sessions"}:
            number_key = "days" if mode == "recent_days" else "sessions"
            value = time_range.get(number_key)
            if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
                errors.append(f"{path}.time_range.{number_key} must be a positive integer")
        if mode == "days_before_target_session":
            days_before = time_range.get("days_before")
            if not isinstance(days_before, int) or isinstance(days_before, bool) or days_before <= 0:
                errors.append(f"{path}.time_range.days_before must be a positive integer")
            if not isinstance(time_range.get("include_target_session_day"), bool):
                errors.append(
                    f"{path}.time_range.include_target_session_day must be boolean"
                )
            target = time_range.get("target_dataset_id")
            if isinstance(target, str) and target:
                relationship_targets.append((index, target))
            else:
                errors.append(
                    f"{path}.time_range.target_dataset_id must be a non-empty string"
                )

    duplicates = sorted({item for item in dataset_ids if dataset_ids.count(item) > 1})
    if duplicates:
        errors.append(f"request.datasets contains duplicate dataset_id values {duplicates}")

    dataset_id_set = set(dataset_ids)
    for index, target in relationship_targets:
        if target not in dataset_id_set:
            errors.append(
                f"request.datasets[{index}].time_range.target_dataset_id references "
                f"missing dataset {target!r}"
            )

    return errors


def assert_valid_analysis_export_request(
    request: Mapping[str, Any],
    *,
    max_datasets: int = MAX_DATASETS,
) -> None:
    errors = validate_analysis_export_request(request, max_datasets=max_datasets)
    if errors:
        raise AnalysisExportContractError("\n".join(errors))
