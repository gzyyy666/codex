from __future__ import annotations

import copy
import math
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from numbers import Real


METRIC_ID_RE = re.compile(r"^[a-z][a-z0-9_]*$")
METRIC_STATUSES = {"active", "inactive", "archived"}
METRIC_FORMATS = {"integer", "decimal"}
PLACEMENT_MODES = {"input", "latest_value", "frequency", "trend_30d"}
RESERVED_IDS = {
    "body", "diet", "training", "movement", "movements", "date", "notes",
    "weight", "calories", "protein", "carbs", "fat", "cardio", "split",
    "daily_records", "diet_records", "training_sessions", "raw_entries",
    "custom_metric_definitions", "custom_metric_values", "custom_metric_placements",
}
KNOWN_PAGES = {"Daily Entry", "Home", "Body", "Diet", "Training", "Movement Progress", "Data Check", "Analysis"}
KNOWN_SLOTS = {"top_aux", "right_note", "card_extra", "bottom_summary"}


def fail(message: str, code: str, details: dict | None = None):
    from ledger_commands import LedgerCommandError
    raise LedgerCommandError(message, code, details)


def validate_metric_id(value: str) -> str:
    metric_id = str(value or "").strip()
    if not METRIC_ID_RE.fullmatch(metric_id):
        fail("metric_id must use lowercase letters, digits and underscores and start with a letter.", "METRIC_ID_INVALID")
    if metric_id in RESERVED_IDS:
        fail("metric_id conflicts with a reserved native field.", "METRIC_ID_RESERVED", {"metric_id": metric_id})
    return metric_id


def validate_date(value: str) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        fail("Metric dates must use YYYY-MM-DD format.", "METRIC_DATE_INVALID", {"date": text})
    if parsed.isoformat() != text:
        fail("Metric dates must use canonical YYYY-MM-DD format.", "METRIC_DATE_INVALID", {"date": text})
    return text


def validate_definition(metric_id: str, values: dict, existing: dict | None = None) -> dict:
    existing = existing or {}
    metric_id = validate_metric_id(metric_id)
    if not isinstance(values, dict):
        fail("Metric definition values must be an object.", "METRIC_DEFINITION_INVALID")
    label = str(values.get("label", existing.get("label", ""))).strip()
    unit = str(values.get("unit", existing.get("unit", ""))).strip()
    if not label or not unit:
        fail("Metric label and unit are required.", "METRIC_REQUIRED_FIELD")
    number_format = str(values.get("number_format", existing.get("number_format", "integer"))).strip().lower()
    if number_format not in METRIC_FORMATS:
        fail("Metric number_format must be integer or decimal.", "METRIC_FORMAT_INVALID")
    try:
        decimal_places = int(values.get("decimal_places", existing.get("decimal_places", 0)))
    except (TypeError, ValueError):
        fail("Metric decimal_places must be an integer.", "METRIC_DECIMAL_PLACES_INVALID")
    if decimal_places < 0 or decimal_places > 6 or (number_format == "integer" and decimal_places != 0):
        fail("Metric decimal_places is outside the supported format boundary.", "METRIC_DECIMAL_PLACES_INVALID")
    status = str(values.get("status", existing.get("status", "active"))).strip().lower()
    if status not in METRIC_STATUSES:
        fail("Metric status must be active, inactive or archived.", "METRIC_STATUS_INVALID")
    try:
        order = int(values.get("order", existing.get("order", 0)))
    except (TypeError, ValueError):
        fail("Metric order must be an integer.", "METRIC_ORDER_INVALID")
    if order < 0:
        fail("Metric order cannot be negative.", "METRIC_ORDER_INVALID")
    result = copy.deepcopy(existing)
    result.update({
        "metric_id": metric_id, "label": label, "unit": unit,
        "number_format": number_format, "decimal_places": decimal_places,
        "status": status, "order": order,
    })
    return result


def normalize_value(value, definition: dict):
    if isinstance(value, bool) or value in (None, ""):
        fail("Metric value must be a finite number; blank values are not saved.", "METRIC_VALUE_REQUIRED")
    if isinstance(value, str):
        value = value.strip()
        if not value:
            fail("Metric value must be a finite number; blank values are not saved.", "METRIC_VALUE_REQUIRED")
    if not isinstance(value, (Real, str)):
        fail("Metric value must be numeric.", "METRIC_VALUE_NON_NUMERIC")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        fail("Metric value must be numeric.", "METRIC_VALUE_NON_NUMERIC")
    if not parsed.is_finite():
        fail("Metric value must be finite.", "METRIC_VALUE_NONFINITE")
    if definition.get("number_format") == "integer":
        if parsed != parsed.to_integral_value():
            fail("Integer metrics cannot contain a fractional value.", "METRIC_INTEGER_REQUIRED")
        return int(parsed)
    places = int(definition.get("decimal_places", 0) or 0)
    quantum = Decimal(1).scaleb(-places)
    rounded = parsed.quantize(quantum)
    if rounded != parsed:
        fail("Metric value exceeds its configured decimal_places.", "METRIC_VALUE_PRECISION_INVALID")
    return int(rounded) if places == 0 else float(rounded)


def valid_stored_value(value, definition: dict):
    try:
        return normalize_value(value, definition)
    except Exception:
        return None


def normalize_definition_for_read(metric_id: str, value) -> dict:
    if not isinstance(value, dict):
        return {"metric_id": str(metric_id), "label": str(metric_id), "unit": "", "status": "invalid", "definition_valid": False}
    try:
        result = validate_definition(metric_id, value)
        result["definition_valid"] = True
        return result
    except Exception:
        result = copy.deepcopy(value)
        result.update({"metric_id": str(metric_id), "label": str(value.get("label") or metric_id), "unit": str(value.get("unit") or ""), "status": str(value.get("status") or "invalid"), "definition_valid": False})
        return result
