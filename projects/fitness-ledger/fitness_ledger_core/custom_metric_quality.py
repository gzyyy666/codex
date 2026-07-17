from __future__ import annotations

import math
from datetime import date

from .custom_metrics import KNOWN_PAGES, KNOWN_SLOTS, METRIC_FORMATS, METRIC_ID_RE, METRIC_STATUSES, RESERVED_IDS, valid_stored_value


def collect_custom_metric_issues(database: dict) -> list[dict]:
    issues = []
    definitions = database.get("custom_metric_definitions", {})
    values = database.get("custom_metric_values", {})
    placements = database.get("custom_metric_placements", {})
    if not isinstance(definitions, dict): return [_issue("high", "custom_metric", "definitions", "custom_metric_definitions must be an object map", "Repair the extension storage shape.")]
    if not isinstance(values, dict): values = {}
    if not isinstance(placements, dict): placements = {}
    def add(severity, target_type, target_id, message, action): issues.append(_issue(severity, target_type, target_id, message, action))
    for metric_id, definition in definitions.items():
        metric_id = str(metric_id)
        if not METRIC_ID_RE.fullmatch(metric_id): add("high", "custom_metric", metric_id, "invalid metric_id", "Rename through the Custom Metric command service.")
        if metric_id in RESERVED_IDS: add("high", "custom_metric", metric_id, "metric_id conflicts with a reserved native field", "Choose a non-reserved metric_id.")
        if not isinstance(definition, dict): add("high", "custom_metric", metric_id, "missing or invalid definition object", "Repair through the command service."); continue
        for field in ("label", "unit", "number_format", "decimal_places", "status", "order"):
            if field not in definition: add("high", "custom_metric", metric_id, f"missing required field: {field}", "Repair the definition through the command service.")
        if definition.get("number_format") not in METRIC_FORMATS: add("high", "custom_metric", metric_id, "invalid number_format", "Use integer or decimal.")
        places = definition.get("decimal_places")
        if not isinstance(places, int) or isinstance(places, bool) or places < 0 or places > 6 or (definition.get("number_format") == "integer" and places != 0): add("high", "custom_metric", metric_id, "invalid decimal_places", "Use a non-negative integer compatible with the format.")
        if definition.get("status") not in METRIC_STATUSES: add("high", "custom_metric", metric_id, "invalid status", "Use active, inactive or archived.")
        if not isinstance(definition.get("order"), int) or isinstance(definition.get("order"), bool) or definition.get("order", 0) < 0: add("medium", "custom_metric", metric_id, "abnormal order", "Use a non-negative integer order.")
    for metric_id, bucket in values.items():
        definition = definitions.get(metric_id)
        if not isinstance(definition, dict): add("high", "custom_metric_value", str(metric_id), "orphan history has no metric definition", "Restore the definition or remove the orphan through a reviewed migration."); continue
        if not isinstance(bucket, dict): add("high", "custom_metric_value", str(metric_id), "metric values must be an object map", "Repair the values through a reviewed migration."); continue
        for raw_date, raw_value in bucket.items():
            try:
                if date.fromisoformat(str(raw_date)).isoformat() != str(raw_date): raise ValueError
            except ValueError: add("high", "custom_metric_value", f"{metric_id}:{raw_date}", "invalid date", "Use canonical YYYY-MM-DD.")
            if isinstance(raw_value, bool) or raw_value is None or valid_stored_value(raw_value, definition) is None:
                add("high", "custom_metric_value", f"{metric_id}:{raw_date}", "non-numeric, non-finite, or format-invalid value", "Store a finite value matching the metric format.")
    for placement_id, placement in placements.items():
        if not isinstance(placement, dict): add("high", "custom_metric_placement", str(placement_id), "invalid placement object", "Repair through the command service."); continue
        if str(placement.get("placement_id", placement_id)) != str(placement_id): add("high", "custom_metric_placement", str(placement_id), "placement_id conflict", "Use one stable placement_id.")
        metric_id = str(placement.get("metric_id", ""))
        if metric_id not in definitions: add("high", "custom_metric_placement", str(placement_id), "placement references a missing metric", "Restore the metric or remove the placement.")
        if placement.get("page") not in KNOWN_PAGES: add("medium", "custom_metric_placement", str(placement_id), "unknown page", "Use a supported page or update the placement contract.")
        if placement.get("slot") not in KNOWN_SLOTS: add("medium", "custom_metric_placement", str(placement_id), "unknown slot", "Use a supported slot or update the placement contract.")
        if placement.get("mode") not in {"input", "latest_value", "frequency", "trend_30d"}: add("medium", "custom_metric_placement", str(placement_id), "unknown placement mode", "Use input, latest_value, frequency or trend_30d.")
        if not isinstance(placement.get("order"), int) or isinstance(placement.get("order"), bool) or placement.get("order", 0) < 0: add("medium", "custom_metric_placement", str(placement_id), "abnormal order", "Use a non-negative integer order.")
        if placement.get("enabled") is not True and placement.get("enabled") is not False: add("medium", "custom_metric_placement", str(placement_id), "enabled must be boolean", "Use true or false.")
        if placement.get("mode") == "input" and isinstance(definitions.get(metric_id), dict) and definitions[metric_id].get("status") == "archived" and placement.get("enabled", True): add("medium", "custom_metric_placement", str(placement_id), "archived metric is still projected as input", "Disable or repoint the input placement.")
    return sorted(issues, key=lambda row: (row["severity"], row["target_type"], row.get("target_id", ""), row["issue"]))


def _issue(severity, target_type, target_id, issue, action, entry_date=""):
    return {"severity": severity, "date": entry_date, "area": "Custom Metrics", "issue": issue, "action": action, "target_type": target_type, "target_id": str(target_id), "movement_id": ""}
