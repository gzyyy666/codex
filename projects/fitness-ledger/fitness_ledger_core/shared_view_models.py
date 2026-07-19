from __future__ import annotations

import copy
import json
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

from .notes import normalize_note_text


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


def history_in_progress(history: dict) -> bool:
    """Return whether one recorded movement instance contributes to progress."""
    return not bool(history.get("exclude_from_progress", False))


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
            return {
                "movement": None,
                "history": [],
                "progress_history": [],
                "recent_performance": [],
                "all_recent_performance": [],
            }
        movement = next(
            (item for item in tracker.get("movements", {}).values() if str(item.get("movement_id", "")) == movement_id),
            {"movement_id": movement_id, "history": []},
        )
        history = sorted(movement.get("history", []) or [], key=lambda row: _date(row.get("date")), reverse=True)
        if before_date:
            history = [row for row in history if _date(row.get("date")) < _date(before_date)]
        movement_is_progress = movement_in_progress(definition)
        progress_history = [row for row in history if movement_is_progress and history_in_progress(row)]
        projected = []
        for row in history[: max(1, limit)]:
            item = copy.deepcopy(row)
            item["exclude_from_progress"] = bool(item.get("exclude_from_progress", False))
            item["movement_notes"] = normalize_note_text(item.get("notes", ""))
            item["sets_lines"] = self.history_set_lines(item)
            item["metrics"] = self.history_metrics(item)
            projected.append(item)
        projected_progress = [item for item in projected if movement_is_progress and history_in_progress(item)]
        recent = [item for item in projected_progress if item["metrics"]["has_structured_sets"]][:3]
        all_recent = [item for item in projected if item["metrics"]["has_structured_sets"]][:3]
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
                "progress_history_count": len(progress_history),
            },
            "history": projected,
            "progress_history": projected_progress,
            "recent_performance": recent,
            "all_recent_performance": all_recent,
        }

    def movement_history(self, movement_name: str, limit: int = 8) -> dict:
        tracker, dictionary = self.snapshot()
        by_id, by_alias = self.dictionary_indexes(dictionary)
        definition = by_id.get(str(movement_name or "").strip()) or by_alias.get(_normalize(movement_name))
        if not definition:
            return {
                "movement": None,
                "history": [],
                "progress_history": [],
                "recent_performance": [],
                "all_recent_performance": [],
            }
        return self.movement_history_by_id(str(definition.get("movement_id", "")), limit)

    def movement_progress_index(self) -> list[dict]:
        """Project only movements eligible for Movement Progress without affecting other archives."""
        tracker, dictionary = self.snapshot()
        counts = {
            str(item.get("movement_id", "")): sum(
                1 for history in (item.get("history", []) or []) if history_in_progress(history)
            )
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
            item["progress_history_count"] = item["history_count"]
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
            projected["training_notes"] = normalize_note_text(session.get("Notes", ""))
            date_key = _date(session.get("Date"))
            day_key = str(session.get("No.", ""))
            movement_refs = sorted(
                history_by_day.get((date_key, day_key), []),
                key=lambda row: (int(row.get("order", 9999) or 9999), row.get("movement_id", "")),
            )
            projected["movement_refs"] = [
                {
                    "history_id": row.get("id", ""),
                    "movement_id": row["movement_id"],
                    "display_name": row.get("display_name", ""),
                    "english_name": row.get("english_name", ""),
                    "muscle_group": row.get("muscle_group", ""),
                    "is_linkable": bool(row.get("is_linkable")),
                    "order": row.get("order", ""),
                    "sets_lines": row.get("sets_lines", []),
                    "notes": row.get("notes", ""),
                    "movement_notes": normalize_note_text(row.get("notes", "")),
                    "exclude_from_progress": bool(row.get("exclude_from_progress", False)),
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

    def analysis(self, start: str = "", end: str = "", days: int = 14, include_raw_preview: bool = False) -> dict:
        tracker, dictionary = self.snapshot()
        dates = sorted({_date(row.get("Date")) for row in tracker.get("daily_records", []) if _date(row.get("Date"))})
        end_date = date.fromisoformat(end) if end else (date.fromisoformat(dates[-1]) if dates else date.today())
        start_date = date.fromisoformat(start) if start else end_date - timedelta(days=max(1, days) - 1)
        in_range = lambda value: start_date.isoformat() <= _date(value) <= end_date.isoformat()
        body = [{**copy.deepcopy(row), "daily_notes": normalize_note_text(row.get("Notes", ""))} for row in tracker.get("daily_records", []) if in_range(row.get("Date"))]
        diet = [{**copy.deepcopy(row), "diet_notes": normalize_note_text(row.get("Notes", ""))} for row in tracker.get("diet_records", []) if in_range(row.get("Date"))]
        training = [{**copy.deepcopy(row), "training_notes": normalize_note_text(row.get("Notes", ""))} for row in tracker.get("training_sessions", []) if in_range(row.get("Date"))]
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
                "history": [
                    {
                        **item,
                        "exclude_from_progress": bool(item.get("exclude_from_progress", False)),
                        "movement_notes": normalize_note_text(item.get("notes", "")),
                        "metrics": self.history_metrics(item),
                    }
                    for item in histories
                ],
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
        }
