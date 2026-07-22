"""Read-only source snapshots, date windows, and compact candidate catalogues."""

from __future__ import annotations

import hashlib
import json
import re
import calendar
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

from .intelligent_export_models import (
    CandidateRecordCard,
    CandidateWindow,
    DataCatalog,
    DateIntent,
    IntentSpec,
    ModuleCard,
    MovementCard,
    MovementMention,
    NotesCard,
    SCHEMA_VERSION,
    stable_hash,
)
from .shared_view_models import history_in_progress, movement_in_progress
from .movement_target_scope import body_part_id_for_muscle_group


MODULE_FIELDS = {
    "body": ("Weight (kg)", "Bowel Movement", "Training", "Cardio", "Notes"),
    "diet": ("Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)", "Food Summary", "Notes"),
    "training": ("Split", "Standardized Summary", "Notes"),
    "movement_history": ("date", "movement_id", "sets", "order", "notes", "exclude_from_progress"),
    "raw_entries": ("date", "id"),
}


def _date(value) -> str:
    return str(value or "")[:10]


def _normalize(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").lower())


def _date_list(rows: Iterable[dict], key: str = "Date") -> list[str]:
    return sorted({_date(row.get(key) or row.get("date")) for row in rows if _date(row.get(key) or row.get("date"))})


def _record_id(prefix: str, row: dict, content: str = "") -> str:
    if row.get("id"):
        return f"{prefix}:{row['id']}"
    digest = hashlib.sha256(f"{prefix}|{_date(row.get('Date') or row.get('date'))}|{content}".encode("utf-8")).hexdigest()[:20]
    return f"{prefix}:derived:{digest}"


def source_snapshot(views) -> dict:
    """Return a read-only fingerprint without creating backups or checkpoints."""
    parts = []
    for path in (views.tracker_file, views.dictionary_file):
        data = path.read_bytes()
        stat = path.stat()
        parts.append({"sha256": hashlib.sha256(data).hexdigest(), "size": len(data), "mtime_ns": stat.st_mtime_ns, "path_role": path.name})
    tracker, _dictionary = views.snapshot()
    dates = [_date(row.get("Date")) for key in ("daily_records", "diet_records", "training_sessions") for row in tracker.get(key, []) if _date(row.get("Date"))]
    payload = {"schema_version": SCHEMA_VERSION, "files": parts, "latest_record_date": max(dates, default="")}
    return {"source_snapshot_id": stable_hash(payload), **payload}


def _coverage(rows: list[dict], fields: tuple[str, ...]) -> dict[str, float]:
    if not rows:
        return {field: 0.0 for field in fields}
    return {field: round(sum(bool(str(row.get(field, "")).strip()) for row in rows) / len(rows), 3) for field in fields}


def _module_card(module_id: str, rows: list[dict], fields: tuple[str, ...]) -> ModuleCard:
    dates = _date_list(rows)
    return ModuleCard(
        module_id,
        bool(rows),
        dates[0] if dates else "",
        dates[-1] if dates else "",
        len(rows),
        len(dates),
        _coverage(rows, fields),
        [],
        f"{len(rows)} records across {len(dates)} active dates.",
        ["summary", "detailed", "full"],
        min(4000, len(rows) * max(1, len(fields)) * 12),
    )


def _performance(history: dict) -> dict:
    sets = []
    for item in history.get("sets", []) or []:
        if not isinstance(item, dict):
            continue
        values = {key: item.get(key) for key in ("weight", "weight_text", "reps", "sets") if item.get(key) not in (None, "")}
        if values:
            sets.append(values)
    return {"set_count": len(sets), "structured": bool(sets)}


class MovementResolver:
    """Read-only dictionary resolver used after Intent, before Planning."""

    def __init__(self, views) -> None:
        _tracker, dictionary = views.snapshot()
        self.definitions = [item for item in dictionary.get("movements", []) or [] if isinstance(item, dict) and item.get("movement_id")]

    def resolve(self, mention: MovementMention, movement_cards: list[MovementCard]) -> list[dict]:
        query = _normalize(mention.text)
        scored = []
        for item in movement_cards:
            haystack = [item.canonical_name, *item.aliases]
            normalized = [_normalize(value) for value in haystack]
            if query and query == normalized[0]:
                score, match = 1.0, "canonical_exact"
            elif query and query in normalized:
                score, match = 0.96, "alias_exact"
            elif query and any(query in value or value in query for value in normalized if value):
                score, match = 0.68, "normalized_partial"
            else:
                continue
            scored.append({"movement_id": item.movement_id, "canonical_name": item.canonical_name, "body_part": item.body_part, "match_type": match, "score": round(score, 3), "history_count": item.history_count, "progress_history_count": item.progress_history_count})
        return sorted(scored, key=lambda value: (-value["score"], -value["progress_history_count"], value["movement_id"]))


class DateRangeResolver:
    """Deterministically turn semantic DateIntent plus the raw request into windows."""

    _ISO = re.compile(r"(?<!\d)(\d{4})[-/](\d{2})[-/](\d{2})(?!\d)")
    _ISO_LAX = re.compile(r"(?<!\d)(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")
    _CN = re.compile(r"(?:(\d{4})年)?(\d{1,2})月(\d{1,2})(?:日|号)")
    _EN = re.compile(r"\b(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{1,2})(?:,\s*(\d{4}))?\b", re.I)
    _EN_MONTH = {name.lower(): index for index, name in enumerate(calendar.month_name) if name}

    @classmethod
    def extract_raw_date_mentions(cls, request: str) -> list[str]:
        text = str(request or "")
        patterns = [cls._ISO_LAX, cls._CN, cls._EN]
        found: list[str] = []
        for pattern in patterns:
            found.extend(match.group(0) for match in pattern.finditer(text))
        month_names = "|".join(cls._EN_MONTH)
        if re.search(rf"\b(?:from|since)\s+(?:{month_names})\b|\b(?:from)\s+(?:{month_names})\s+to\s+(?:{month_names})\b", text, re.I):
            found.extend(match.group(0) for match in re.finditer(rf"\b(?:from|since)\s+(?:{month_names})(?:\s+to\s+(?:{month_names}))?\b", text, re.I))
        return list(dict.fromkeys(found))[:8]

    @staticmethod
    def infer_relative_range(request: str) -> str | None:
        text = str(request or "").lower()
        if any(token in text for token in ("全部历史", "所有记录", "完整成长记录", "all available", "all history", "all records")):
            return "all_available"
        if any(token in text for token in ("最近两个月", "这几个月", "最近几个月", "recent months", "last few months")):
            return "recent_months"
        if any(token in text for token in ("最近十二周", "最近12周", "recent 12 weeks", "last 12 weeks")):
            return "recent_12_weeks"
        if any(token in text for token in ("最近八周", "最近8周", "recent 8 weeks", "last 8 weeks")):
            return "recent_8_weeks"
        if any(token in text for token in ("最近四周", "最近4周", "recent 4 weeks", "last 4 weeks")):
            return "recent_4_weeks"
        if any(token in text for token in ("最近", "近期", "一段时间", "recent", "lately", "these months")):
            return "recent"
        return None

    def resolve(self, intent: IntentSpec, catalog: DataCatalog, request: str = "", today: date | None = None) -> list[CandidateWindow]:
        available_start, available_end = catalog.date_range.get("start", ""), catalog.date_range.get("end", "")
        if not available_start or not available_end:
            return []
        today = today or date.today()
        date_intent = intent.date_intent
        if date_intent.mode == "explicit":
            explicit = self._explicit_range(request, date_intent.raw_date_mentions, today, available_end)
            if explicit is None:
                return []
            requested_ranges = [(explicit[0], explicit[1], "explicit")]
        elif date_intent.mode == "relative":
            requested_ranges = [(start, min(today.isoformat(), available_end), "relative") for start in self._relative_starts(date_intent.relative_range or "recent", available_end)]
        elif date_intent.mode == "all_available" or date_intent.relative_range == "all_available":
            requested_ranges = [(available_start, min(today.isoformat(), available_end), "all")]
        else:
            requested_ranges = [(start, min(today.isoformat(), available_end), "safe_default_recent_28d") for start in self._relative_starts("recent_4_weeks", available_end)]
        windows = []
        for requested_start, requested_end, anchor in requested_ranges:
            try:
                requested_start = date.fromisoformat(requested_start).isoformat()
                requested_end = date.fromisoformat(requested_end).isoformat()
            except ValueError:
                continue
            resolved_start = max(requested_start, available_start)
            resolved_end = min(requested_end, available_end)
            if resolved_start > resolved_end:
                continue
            warnings = []
            if requested_start < available_start or requested_end > available_end:
                warnings.append("requested range partly falls outside available data; only the real intersection is used")
            window_id = f"window:{requested_start}..{requested_end}:{resolved_start}..{resolved_end}"
            windows.append(CandidateWindow(window_id, requested_start, requested_end, resolved_start, resolved_end, anchor, list(MODULE_FIELDS), 0, warnings))
        return list(dict((item.window_id, item) for item in windows).values())

    @staticmethod
    def _relative_starts(relative_range: str, available_end: str) -> list[str]:
        days = {"recent_4_weeks": 28, "recent_8_weeks": 56, "recent_12_weeks": 84}
        if relative_range == "recent":
            spans = (28, 56)
        elif relative_range == "recent_months":
            spans = (56, 84)
        else:
            spans = (days.get(relative_range, 28),)
        end = date.fromisoformat(available_end)
        return [(end - timedelta(days=span - 1)).isoformat() for span in spans]

    def _explicit_range(self, request: str, mentions: list[str], today: date, available_end: str) -> tuple[str, str] | None:
        text = str(request or "")
        source = text or " ".join(mentions)
        if self._ISO_LAX.search(source) and not self._ISO.search(source):
            return None
        dates = []
        for match in self._ISO.finditer(source):
            try:
                dates.append(date(int(match.group(1)), int(match.group(2)), int(match.group(3))))
            except ValueError:
                return None
        if not dates:
            for match in self._CN.finditer(source):
                parsed = self._safe_month_day(match.group(1), match.group(2), match.group(3), today, available_end)
                if parsed is None:
                    return None
                dates.append(parsed)
        if not dates:
            for match in self._EN.finditer(source):
                parsed = self._safe_month_day(match.group(3), str(self._EN_MONTH[match.group(1).lower()]), match.group(2), today, available_end)
                if parsed is None:
                    return None
                dates.append(parsed)
        if not dates:
            month_names = "|".join(self._EN_MONTH)
            month_matches = list(re.finditer(rf"\b({month_names})\b", source, re.I))
            if month_matches:
                year = today.year
                first = date(year, self._EN_MONTH[month_matches[0].group(1).lower()], 1)
                last_month = self._EN_MONTH[month_matches[-1].group(1).lower()]
                last = date(year, last_month, calendar.monthrange(year, last_month)[1])
                if re.search(rf"\bsince\s+{month_names}\b", source, re.I):
                    last = date.fromisoformat(min(today.isoformat(), available_end))
                if first > today and date(year - 1, first.month, first.day) <= today:
                    first = first.replace(year=year - 1); last = last.replace(year=year - 1)
                dates = [first, last]
        if not dates:
            return None
        start, end = min(dates), max(dates)
        return start.isoformat(), end.isoformat()

    @staticmethod
    def _safe_month_day(year_text: str | None, month_text: str, day_text: str, today: date, available_end: str) -> date | None:
        try:
            year = int(year_text) if year_text else today.year
            value = date(year, int(month_text), int(day_text))
        except (TypeError, ValueError):
            return None
        if not year_text and value > today and value.isoformat() > available_end:
            try:
                value = value.replace(year=value.year - 1)
            except ValueError:
                return None
        return value


class DataCatalogBuilder:
    """Build a compact, source-bound catalogue from read-only projections."""

    def __init__(self, views) -> None:
        self.views = views

    def build(self) -> DataCatalog:
        snapshot = source_snapshot(self.views)
        data = self.views.analysis(days=36500, include_raw_preview=False)
        tracker, dictionary = self.views.snapshot()
        all_rows = {key: list(data.get(key, [])) for key in ("body", "diet", "training", "raw_entries")}
        movement_rows = []
        definitions = {str(item.get("movement_id")): item for item in dictionary.get("movements", []) or [] if item.get("movement_id")}
        movements: list[MovementCard] = []
        notes: list[NotesCard] = []
        candidate_records: list[CandidateRecordCard] = []

        for module_id in ("body", "diet", "training"):
            for row in all_rows[module_id]:
                rid = _record_id(module_id, row)
                factual = {
                    field: (str(row.get(field))[:160] if isinstance(row.get(field), str) else row.get(field))
                    for field in MODULE_FIELDS[module_id]
                    if field not in {"Notes", "Food Summary", "Raw Record"} and row.get(field) not in (None, "", [])
                }
                note_id = self._add_note(notes, module_id, row, str(row.get("Notes", "")), rid)
                candidate_records.append(CandidateRecordCard(rid, module_id, _date(row.get("Date")), module_id, factual, [], [], [note_id] if note_id else [], 80))

        tracker_by_id = {str(item.get("movement_id", "")): item for item in tracker.get("movements", {}).values() if item.get("movement_id")}
        for movement_id in sorted(set(tracker_by_id) | set(definitions)):
            tracker_movement = tracker_by_id.get(movement_id, {"movement_id": movement_id, "history": []})
            definition = definitions.get(movement_id, {})
            histories = [dict(item) for item in tracker_movement.get("history", []) or [] if isinstance(item, dict)]
            movement_rows.extend(histories)
            progress = [item for item in histories if history_in_progress(item) and movement_in_progress(definition)]
            dates = _date_list(histories, "date")
            progress_dates = _date_list(progress, "date")
            aliases = [str(value) for value in definition.get("aliases", []) or [] if str(value).strip()]
            movements.append(MovementCard(
                movement_id,
                str(definition.get("display_name") or tracker_movement.get("name") or movement_id),
                aliases,
                str(definition.get("muscle_group", "")),
                body_part_id_for_muscle_group(str(definition.get("muscle_group", ""))) or "",
                len(histories), len(progress), len(histories) - len(progress),
                dates[0] if dates else "", dates[-1] if dates else "", dates[-1] if dates else "", progress_dates[-1] if progress_dates else "",
                _performance(progress[-1]) if progress else {},
                "sufficient" if len(progress) >= 2 else "insufficient",
                {}, min(4000, len(histories) * 32),
            ))
            for history in histories:
                rid = f"movement-history:{movement_id}:{history.get('id') or stable_hash([_date(history.get('date')), history.get('order'), history.get('sets')])[:20]}"
                note_id = self._add_note(notes, "movement", history, str(history.get("notes", "")), rid, movement_id, str(history.get("id", "")))
                flags = ["excluded_from_progress"] if history.get("exclude_from_progress") else []
                candidate_records.append(CandidateRecordCard(rid, "movement_history", _date(history.get("date")), "movement_history", {"movement_id": movement_id, "order": history.get("order"), "sets": _performance(history), "exclude_from_progress": bool(history.get("exclude_from_progress"))}, flags, [movement_id], [note_id] if note_id else [], 100))

        for row in all_rows["raw_entries"]:
            rid = _record_id("raw", row)
            candidate_records.append(CandidateRecordCard(rid, "raw_entries", _date(row.get("date")), "raw_entry", {"id": row.get("id", ""), "date": row.get("date", "")}, ["raw_available"], [], [], 180))

        module_rows = {"body": all_rows["body"], "diet": all_rows["diet"], "training": all_rows["training"], "movement_history": movement_rows, "raw_entries": all_rows["raw_entries"]}
        modules = [_module_card(module_id, rows, MODULE_FIELDS[module_id]) for module_id, rows in module_rows.items()]
        dates = sorted({_date(row.get("Date")) for key in ("body", "diet", "training") for row in all_rows[key] if _date(row.get("Date"))} | {_date(row.get("date")) for row in movement_rows if _date(row.get("date"))})
        date_range = {"start": dates[0] if dates else "", "end": dates[-1] if dates else ""}
        catalog_id = stable_hash({"snapshot": snapshot["source_snapshot_id"], "modules": [item.to_dict() for item in modules], "movements": [item.to_dict() for item in movements], "notes": [item.to_dict() for item in notes]})
        return DataCatalog(catalog_id, snapshot["source_snapshot_id"], datetime.now().replace(microsecond=0).isoformat(), date_range, date_range["end"], modules, sorted(movements, key=lambda item: (-item.progress_history_count, item.canonical_name)), notes, candidate_records)

    @staticmethod
    def _add_note(notes: list[NotesCard], note_type: str, row: dict, value: str, source_record_id: str, movement_id: str = "", history_id: str = "") -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
        scope = {"body": "daily", "diet": "diet", "training": "training"}.get(note_type, "movement")
        note_id = f"note:{scope}:{row.get('id') or source_record_id}:{movement_id}:{history_id}:{digest[:12]}"
        notes.append(NotesCard(note_id, _date(row.get("Date") or row.get("date")), scope, scope, str(row.get("id") or source_record_id), movement_id, history_id, len(text), text[:120], digest, [source_record_id], min(180, len(text))))
        return note_id


def resolve_windows(catalog: DataCatalog, intent: IntentSpec, request: str = "") -> list[CandidateWindow]:
    return DateRangeResolver().resolve(intent, catalog, request)
