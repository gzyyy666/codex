from __future__ import annotations

import copy
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .custom_metrics import PLACEMENT_MODES, normalize_definition_for_read, valid_stored_value


def _number(value) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _date(value) -> str:
    return str(value or "")[:10]


def _normalize(value) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").lower())


def movement_in_progress(definition: dict) -> bool:
    """The single visibility rule for the Movement Progress product surface."""
    return bool(definition.get("active", True)) and not bool(
        definition.get("exclude_from_progress", False)
    )


class LedgerViewModels:
    """Read-only projection layer shared by Web, export, and cloud payloads."""

    def __init__(self, tracker_file: Path, dictionary_file: Path) -> None:
        self.tracker_file = Path(tracker_file)
        self.dictionary_file = Path(dictionary_file)

    def snapshot(self) -> tuple[dict, dict]:
        tracker = json.loads(self.tracker_file.read_text(encoding="utf-8"))
        dictionary = json.loads(self.dictionary_file.read_text(encoding="utf-8"))
        return copy.deepcopy(tracker), copy.deepcopy(dictionary)

    def dictionary_indexes(self, dictionary: dict) -> tuple[dict, dict]:
        by_id, by_alias = {}, {}
        for item in dictionary.get("movements", []) or []:
            movement_id = str(item.get("movement_id", ""))
            if movement_id:
                by_id[movement_id] = item
            for candidate in (item.get("display_name", ""), item.get("english_name", ""), *(item.get("aliases") or [])):
                key = _normalize(candidate)
                if key:
                    by_alias[key] = item
        return by_id, by_alias

    @staticmethod
    def history_set_lines(history: dict) -> list[str]:
        lines = []
        for item in history.get("sets", []) or []:
            weight = item.get("weight_text") or item.get("weight")
            if weight in (None, "", 0, 0.0):
                weight = "自重"
            lines.append(f"{weight} × {item.get('reps', '-')} × {item.get('sets', '-')}")
        return lines

    @staticmethod
    def history_metrics(history: dict) -> dict:
        max_weight, total_reps, volume = 0.0, 0, 0.0
        has_structured_sets = False
        for item in history.get("sets", []) or []:
            reps_value = _number(item.get("reps"))
            sets_value = _number(item.get("sets"))
            if reps_value is None or sets_value is None or reps_value <= 0 or sets_value <= 0:
                continue
            weight = _number(item.get("weight")) or 0.0
            reps = int(reps_value)
            sets = int(sets_value)
            has_structured_sets = True
            max_weight = max(max_weight, weight)
            total_reps += reps * sets
            volume += weight * reps * sets
        return {
            "max_weight": max_weight,
            "total_reps": total_reps,
            "volume": round(volume, 2),
            "has_structured_sets": has_structured_sets,
        }

    def movement_history_by_id(self, movement_id: str, limit: int = 8, before_date: str = "") -> dict:
        tracker, dictionary = self.snapshot()
        by_id, _ = self.dictionary_indexes(dictionary)
        movement_id = str(movement_id or "").strip()
        definition = by_id.get(movement_id)
        if not definition:
            return {"movement": None, "history": [], "recent_performance": []}
        movement = next(
            (item for item in tracker.get("movements", {}).values() if str(item.get("movement_id", "")) == movement_id),
            {"movement_id": movement_id, "history": []},
        )
        history = sorted(movement.get("history", []) or [], key=lambda row: _date(row.get("date")), reverse=True)
        if before_date:
            history = [row for row in history if _date(row.get("date")) < _date(before_date)]
        projected = []
        for row in history[: max(1, limit)]:
            item = copy.deepcopy(row)
            item["sets_lines"] = self.history_set_lines(item)
            item["metrics"] = self.history_metrics(item)
            projected.append(item)
        recent = [item for item in projected if item["metrics"]["has_structured_sets"]][:3]
        for index, item in enumerate(recent):
            previous = recent[index + 1]["metrics"] if index + 1 < len(recent) else None
            item["change"] = {
                key: round(item["metrics"][key] - previous[key], 2) if previous else None
                for key in ("max_weight", "total_reps", "volume")
            }
        return {
            "movement": {
                **copy.deepcopy(definition),
                "history_count": len(history),
            },
            "history": projected,
            "recent_performance": recent,
        }

    def movement_history(self, movement_name: str, limit: int = 8) -> dict:
        tracker, dictionary = self.snapshot()
        by_id, by_alias = self.dictionary_indexes(dictionary)
        definition = by_id.get(str(movement_name or "").strip()) or by_alias.get(_normalize(movement_name))
        if not definition:
            return {"movement": None, "history": [], "recent_performance": []}
        return self.movement_history_by_id(str(definition.get("movement_id", "")), limit)

    def movement_progress_index(self) -> list[dict]:
        """Project only movements eligible for Movement Progress without affecting other archives."""
        tracker, dictionary = self.snapshot()
        counts = {
            str(item.get("movement_id", "")): len(item.get("history", []) or [])
            for item in tracker.get("movements", {}).values()
            if isinstance(item, dict)
        }
        rows = []
        for definition in dictionary.get("movements", []) or []:
            if not isinstance(definition, dict) or not movement_in_progress(definition):
                continue
            item = copy.deepcopy(definition)
            item["exclude_from_progress"] = bool(item.get("exclude_from_progress", False))
            item["history_count"] = counts.get(str(item.get("movement_id", "")), 0)
            rows.append(item)
        return sorted(
            rows,
            key=lambda item: (
                not (bool(item.get("pinned", False)) or int(item.get("focus_rank", 0) or 0) > 0),
                int(item.get("focus_rank", 0) or 0) if int(item.get("focus_rank", 0) or 0) > 0 else 1_000_000,
                -int(item.get("history_count", 0) or 0),
                str(item.get("display_name", "")).casefold(),
            ),
        )

    def training_archive(self, limit: int = 50) -> list[dict]:
        """Add only read-only movement_id projections to Training sessions."""
        tracker, dictionary = self.snapshot()
        by_id, by_alias = self.dictionary_indexes(dictionary)
        history_by_day: dict[tuple[str, str], list[dict]] = {}
        for movement in tracker.get("movements", {}).values():
            fallback_id = str(movement.get("movement_id", ""))
            fallback_name = str(
                movement.get("display_name")
                or movement.get("name")
                or movement.get("movement_name")
                or ""
            )
            for history in movement.get("history", []) or []:
                declared_id = str(history.get("movement_id") or fallback_id)
                declared_name = str(
                    history.get("display_name")
                    or history.get("name")
                    or history.get("movement_name")
                    or fallback_name
                    or ""
                )
                definition = by_id.get(declared_id)
                if not definition:
                    for candidate in (declared_name, fallback_name):
                        definition = by_alias.get(_normalize(candidate)) if candidate else None
                        if definition:
                            break
                movement_id = str(definition.get("movement_id", "")) if definition else ""
                key = (_date(history.get("date")), str(history.get("training_day", "")))
                row = copy.deepcopy(history)
                row.update({
                    "movement_id": movement_id,
                    "display_name": (definition or {}).get("display_name") or declared_name or declared_id or "Unmapped movement",
                    "english_name": (definition or {}).get("english_name", ""),
                    "muscle_group": (definition or {}).get("muscle_group", ""),
                    "is_linkable": bool(movement_id),
                    "sets_lines": self.history_set_lines(row),
                    "has_structured_sets": self.history_metrics(row)["has_structured_sets"],
                })
                history_by_day.setdefault(key, []).append(row)

        rows = []
        for session in sorted(tracker.get("training_sessions", []) or [], key=lambda row: _date(row.get("Date")), reverse=True):
            projected = copy.deepcopy(session)
            date_key = _date(session.get("Date"))
            day_key = str(session.get("No.", ""))
            movement_refs = sorted(
                history_by_day.get((date_key, day_key), []),
                key=lambda row: (int(row.get("order", 9999) or 9999), row.get("movement_id", "")),
            )
            projected["movement_refs"] = [
                {
                    "movement_id": row["movement_id"],
                    "display_name": row.get("display_name", ""),
                    "english_name": row.get("english_name", ""),
                    "muscle_group": row.get("muscle_group", ""),
                    "is_linkable": bool(row.get("is_linkable")),
                    "order": row.get("order", ""),
                    "sets_lines": row.get("sets_lines", []),
                    "notes": row.get("notes", ""),
                    "has_structured_sets": bool(row.get("has_structured_sets")),
                }
                for row in movement_refs
            ]
            rows.append(projected)
        return rows[: max(1, min(limit, 200))]

    def workout_reference(self, split: str = "") -> dict:
        tracker, dictionary = self.snapshot()
        query = _normalize(split)
        sessions = sorted(tracker.get("training_sessions", []) or [], key=lambda row: _date(row.get("Date")), reverse=True)
        if query:
            sessions = [row for row in sessions if query in _normalize(row.get("Split"))]
        selected_dates = {_date(row.get("Date")) for row in sessions[:8]}
        by_id, _ = self.dictionary_indexes(dictionary)
        candidates = []
        for movement in tracker.get("movements", {}).values():
            movement_id = str(movement.get("movement_id", ""))
            definition = by_id.get(movement_id, {})
            if definition and not definition.get("active", True):
                continue
            histories = [row for row in movement.get("history", []) or [] if _date(row.get("date")) in selected_dates]
            if not histories:
                continue
            histories.sort(key=lambda row: _date(row.get("date")), reverse=True)
            candidates.append({
                "movement_id": movement_id,
                "display_name": definition.get("display_name") or movement.get("name", ""),
                "muscle_group": definition.get("muscle_group", ""),
                "frequency": len(histories),
                "recent": [{**copy.deepcopy(row), "metrics": self.history_metrics(row)} for row in histories[:3]],
            })
        candidates.sort(key=lambda row: (-row["frequency"], row["display_name"]))
        return {
            "split": split,
            "available_splits": [name for name, _count in Counter(str(row.get("Split", "")) for row in tracker.get("training_sessions", []) if row.get("Split")).most_common()],
            "last_session": copy.deepcopy(sessions[0]) if sessions else None,
            "movements": candidates[:12],
        }

    @staticmethod
    def _metric_state(tracker: dict) -> tuple[list[dict], dict, list[dict]]:
        definitions = tracker.get("custom_metric_definitions", {})
        values = tracker.get("custom_metric_values", {})
        placements = tracker.get("custom_metric_placements", {})
        if not isinstance(definitions, dict): definitions = {}
        if not isinstance(values, dict): values = {}
        if not isinstance(placements, dict): placements = {}
        defs = [normalize_definition_for_read(metric_id, item) for metric_id, item in definitions.items()]
        defs.sort(key=lambda item: (int(item.get("order", 0) or 0) if str(item.get("order", "")).lstrip("-").isdigit() else 10**9, str(item.get("label", "")).casefold(), item["metric_id"]))
        rows = []
        for placement_id, item in placements.items():
            if isinstance(item, dict):
                rows.append({"placement_id": str(item.get("placement_id") or placement_id), **copy.deepcopy(item)})
            else:
                rows.append({"placement_id": str(placement_id), "definition_valid": False})
        rows.sort(key=lambda item: (int(item.get("order", 0) or 0) if str(item.get("order", "")).lstrip("-").isdigit() else 10**9, str(item.get("placement_id", ""))))
        return defs, values, rows

    def custom_metric_definitions(self) -> list[dict]:
        tracker, _dictionary = self.snapshot()
        defs, _values, _placements = self._metric_state(tracker)
        return defs

    def custom_metric_daily_entry(self, entry_date: str) -> list[dict]:
        tracker, _dictionary = self.snapshot()
        defs, values, _placements = self._metric_state(tracker)
        target = _date(entry_date)
        result = []
        for definition in defs:
            if not definition.get("definition_valid") or definition.get("status") != "active": continue
            raw = values.get(definition["metric_id"], {}) if isinstance(values, dict) else {}
            value = valid_stored_value(raw[target], definition) if isinstance(raw, dict) and target in raw else None
            result.append({**copy.deepcopy(definition), "date": target, "value": value, "has_value": value is not None})
        return result

    def custom_metric_daily_archive(self, entry_date: str) -> list[dict]:
        tracker, _dictionary = self.snapshot()
        defs, values, _placements = self._metric_state(tracker)
        by_id = {item["metric_id"]: item for item in defs}
        target = _date(entry_date); result = []
        for metric_id, bucket in values.items() if isinstance(values, dict) else ():
            definition = by_id.get(str(metric_id), {"metric_id": str(metric_id), "label": str(metric_id), "unit": "", "definition_valid": False})
            if not isinstance(bucket, dict) or target not in bucket: continue
            value = valid_stored_value(bucket[target], definition)
            if value is None: continue
            result.append({"metric_id": str(metric_id), "label": definition.get("label", str(metric_id)), "unit": definition.get("unit", ""), "status": definition.get("status", "invalid"), "date": target, "value": value, "definition_valid": bool(definition.get("definition_valid"))})
        return sorted(result, key=lambda item: item["metric_id"])

    def custom_metric_history(self, metric_id: str, end: str = "", days: int = 30) -> dict:
        tracker, _dictionary = self.snapshot()
        defs, values, _placements = self._metric_state(tracker)
        definition = next((item for item in defs if item["metric_id"] == str(metric_id)), None)
        if not definition: return {"metric_id": str(metric_id), "definition": None, "points": [], "series": [], "latest_date": "", "latest_value": None, "record_count": 0, "valid_days": 0}
        bucket = values.get(str(metric_id), {}) if isinstance(values, dict) else {}
        valid = []
        for raw_date, raw_value in bucket.items() if isinstance(bucket, dict) else ():
            try: day = __import__('datetime').date.fromisoformat(str(raw_date))
            except ValueError: continue
            value = valid_stored_value(raw_value, definition)
            if value is not None: valid.append((day, value))
        if not valid: return {"metric_id": str(metric_id), "definition": copy.deepcopy(definition), "points": [], "series": [], "latest_date": "", "latest_value": None, "record_count": 0, "valid_days": 0}
        valid.sort(); end_day = date.fromisoformat(end) if end else valid[-1][0]
        start_day = end_day - timedelta(days=max(1, int(days)) - 1)
        points = [{"date": day.isoformat(), "value": value} for day, value in valid if start_day <= day <= end_day]
        latest = points[-1] if points else {"date": "", "value": None}
        return {"metric_id": str(metric_id), "definition": copy.deepcopy(definition), "points": points, "series": copy.deepcopy(points), "latest_date": latest["date"], "latest_value": latest["value"], "record_count": len(valid), "valid_days": len({item[0] for item in valid})}

    def custom_metric_placements(self, page: str = "", slot: str = "", entry_date: str = "", days: int = 30) -> list[dict]:
        tracker, _dictionary = self.snapshot(); defs, _values, placements = self._metric_state(tracker)
        by_id = {item["metric_id"]: item for item in defs}; result = []
        for placement in placements:
            if page and placement.get("page") != page: continue
            if slot and placement.get("slot") != slot: continue
            metric_id = str(placement.get("metric_id", "")); definition = by_id.get(metric_id)
            item = {**copy.deepcopy(placement), "metric": copy.deepcopy(definition) if definition else None}
            mode = str(placement.get("mode", ""))
            if definition and mode == "input": item["data"] = next((row for row in self.custom_metric_daily_entry(entry_date) if row["metric_id"] == metric_id), None) if entry_date else None
            elif definition and mode == "latest_value":
                history = self.custom_metric_history(metric_id, entry_date, days); item["data"] = {"date": history["latest_date"], "value": history["latest_value"]}
            elif definition and mode == "frequency":
                history = self.custom_metric_history(metric_id, entry_date, days); item["data"] = {"record_count": history["record_count"], "valid_days": history["valid_days"]}
            elif definition and mode == "trend_30d": item["data"] = self.custom_metric_history(metric_id, entry_date, 30)["series"]
            else: item["data"] = {}; item["projection_error"] = "UNKNOWN_MODE" if mode not in PLACEMENT_MODES else "METRIC_NOT_FOUND"
            result.append(item)
        return result

    def custom_metrics_export(self, start: str = "", end: str = "") -> list[dict]:
        tracker, _dictionary = self.snapshot(); defs, values, placements = self._metric_state(tracker)
        start, end = (_date(start), _date(end)); by_id = {item["metric_id"]: item for item in defs}
        grouped = {item["metric_id"]: {**copy.deepcopy(item), "placements": [], "values": []} for item in defs}
        for placement in placements:
            metric_id = str(placement.get("metric_id", "")); grouped.setdefault(metric_id, {"metric_id": metric_id, "label": metric_id, "unit": "", "status": "unknown", "definition_valid": False, "placements": [], "values": []})["placements"].append(copy.deepcopy(placement))
        for metric_id, bucket in values.items() if isinstance(values, dict) else ():
            target = grouped.setdefault(str(metric_id), {"metric_id": str(metric_id), "label": str(metric_id), "unit": "", "status": "unknown", "definition_valid": False, "placements": [], "values": []})
            for raw_date, raw_value in bucket.items() if isinstance(bucket, dict) else ():
                if start and str(raw_date) < start or end and str(raw_date) > end: continue
                definition = by_id.get(str(metric_id), target); value = valid_stored_value(raw_value, definition)
                if value is not None: target["values"].append({"date": str(raw_date), "value": value})
        for item in grouped.values(): item["placements"].sort(key=lambda row: str(row.get("placement_id", ""))); item["values"].sort(key=lambda row: row["date"])
        return sorted(grouped.values(), key=lambda item: item["metric_id"])

    def analysis(self, start: str = "", end: str = "", days: int = 14, include_raw_preview: bool = False) -> dict:
        tracker, dictionary = self.snapshot()
        dates = sorted({_date(row.get("Date")) for row in tracker.get("daily_records", []) if _date(row.get("Date"))})
        metric_values = tracker.get("custom_metric_values", {})
        if isinstance(metric_values, dict):
            for bucket in metric_values.values():
                if not isinstance(bucket, dict):
                    continue
                for day in bucket:
                    try:
                        if date.fromisoformat(str(day)).isoformat() == str(day):
                            dates.append(str(day))
                    except ValueError:
                        continue
            dates = sorted(set(dates))
        end_date = date.fromisoformat(end) if end else (date.fromisoformat(dates[-1]) if dates else date.today())
        start_date = date.fromisoformat(start) if start else end_date - timedelta(days=max(1, days) - 1)
        in_range = lambda value: start_date.isoformat() <= _date(value) <= end_date.isoformat()
        body = [copy.deepcopy(row) for row in tracker.get("daily_records", []) if in_range(row.get("Date"))]
        diet = [copy.deepcopy(row) for row in tracker.get("diet_records", []) if in_range(row.get("Date"))]
        training = [copy.deepcopy(row) for row in tracker.get("training_sessions", []) if in_range(row.get("Date"))]
        movements = []
        by_id, _ = self.dictionary_indexes(dictionary)
        for row in tracker.get("movements", {}).values():
            histories = [copy.deepcopy(item) for item in row.get("history", []) or [] if in_range(item.get("date"))]
            if not histories:
                continue
            definition = by_id.get(str(row.get("movement_id", "")), {})
            movements.append({
                "movement_id": row.get("movement_id", ""),
                "display_name": definition.get("display_name") or row.get("name", ""),
                "muscle_group": definition.get("muscle_group", ""),
                "history": [{**item, "metrics": self.history_metrics(item)} for item in histories],
            })
        raw_refs = []
        for item in tracker.get("raw_entries", []) or []:
            if not in_range(item.get("date")):
                continue
            raw_refs.append({
                "id": item.get("id", ""), "date": item.get("date", ""),
                "preview": str(item.get("text", ""))[:180] if include_raw_preview else "",
            })
        weights = [_number(row.get("Weight (kg)")) for row in body]
        weights = [item for item in weights if item is not None]
        return {
            "range": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "summary": {
                "days": len(set(_date(row.get("Date")) for row in body)),
                "training_sessions": len(training),
                "movement_records": sum(len(item["history"]) for item in movements),
                "weight_start": weights[0] if weights else None,
                "weight_end": weights[-1] if weights else None,
            },
            "body": body, "diet": diet, "training": training,
            "movements": movements, "raw_entries": raw_refs,
            # Metric definitions/placements/history are a complete extension
            # contract; unlike the native period tables they are not truncated
            # by the daily analysis window.
            "custom_metrics": self.custom_metrics_export(),
        }
