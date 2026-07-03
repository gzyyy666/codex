from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
TRACKER_FILE = DATA_DIR / "tracker.json"
MOVEMENT_DICTIONARY_FILE = DATA_DIR / "movement_dictionary.json"


def read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback


def normalize_name(value: str) -> str:
    value = value.lower().strip()
    value = re.sub(r"[\s_\-/（）()]+", "", value)
    value = re.sub(r"[^\w\u4e00-\u9fff]", "", value)
    return value


def parse_iso_date(value: str) -> date | None:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def format_weight(item: dict) -> str:
    if str(item.get("weight_text", "")).strip():
        return str(item["weight_text"]).strip()
    weight = item.get("weight")
    if weight in (None, ""):
        return "-"
    return f"{float(weight):g}kg"


def format_set_line(item: dict) -> str:
    return f"{format_weight(item)} × {item.get('reps', '-')} × {item.get('sets', '-')}"


def extract_set_lines_from_raw(raw: str) -> list[str]:
    text = str(raw or "").strip()
    if not text:
        return []

    normalized = (
        text.replace("＊", "*")
        .replace("✕", "x")
        .replace("×", "x")
        .replace("X", "x")
        .replace("自體", "自重")
    )
    lines = [line.strip() for line in normalized.splitlines() if line.strip()]
    results: list[str] = []

    weighted_pattern = re.compile(
        r"(?P<weight>自重|body\s*weight|\d+(?:\.\d+)?\s*kg?)\s*x\s*(?P<reps>\d+)\s*x\s*(?P<sets>\d+)",
        re.IGNORECASE,
    )
    reps_pattern = re.compile(
        r"(?P<reps>\d+)\s*(?:reps?)?\s*x\s*(?P<sets>\d+)",
        re.IGNORECASE,
    )

    def append_unique(value: str) -> None:
        if value and value not in results:
            results.append(value)

    for line in lines:
        if line.lower().startswith("notes:"):
            continue
        line_hits = 0
        for match in weighted_pattern.finditer(line):
            weight_text = re.sub(r"\s+", "", match.group("weight"))
            if weight_text.lower() == "bodyweight":
                weight_text = "自重"
            append_unique(f"{weight_text} × {match.group('reps')} × {match.group('sets')}")
            line_hits += 1

        if line_hits:
            continue

        for match in reps_pattern.finditer(line):
            append_unique(f"自重 × {match.group('reps')} × {match.group('sets')}")

    return results


@dataclass
class MovementMatch:
    movement_id: str
    display_name: str
    english_name: str
    aliases: list[str]
    muscle_group: str
    category: str
    active: bool


class LedgerDataAccess:
    def __init__(self, tracker_file: Path = TRACKER_FILE, dictionary_file: Path = MOVEMENT_DICTIONARY_FILE):
        self.tracker_file = tracker_file
        self.dictionary_file = dictionary_file
        self._cache: dict | None = None
        self._mtimes: tuple[float | None, float | None] = (None, None)

    def _current_mtimes(self) -> tuple[float | None, float | None]:
        return (
            self.tracker_file.stat().st_mtime if self.tracker_file.exists() else None,
            self.dictionary_file.stat().st_mtime if self.dictionary_file.exists() else None,
        )

    def _ensure_loaded(self) -> dict:
        mtimes = self._current_mtimes()
        if self._cache is not None and mtimes == self._mtimes:
            return self._cache

        tracker = read_json(
            self.tracker_file,
            {"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []},
        )
        dictionary = read_json(self.dictionary_file, {"movements": []})

        movements_by_id = {}
        alias_index: dict[str, list[MovementMatch]] = {}
        for entry in dictionary.get("movements", []) or []:
            match = MovementMatch(
                movement_id=str(entry.get("movement_id", "")),
                display_name=str(entry.get("display_name", "")).strip(),
                english_name=str(entry.get("english_name", "")).strip(),
                aliases=[str(alias).strip() for alias in (entry.get("aliases") or []) if str(alias).strip()],
                muscle_group=str(entry.get("muscle_group", "")).strip(),
                category=str(entry.get("category", "")).strip(),
                active=bool(entry.get("active", True)),
            )
            if not match.movement_id:
                continue
            movements_by_id[match.movement_id] = match
            for candidate in [match.display_name, match.english_name, *match.aliases]:
                normalized = normalize_name(candidate)
                if normalized:
                    alias_index.setdefault(normalized, []).append(match)

        self._cache = {
            "tracker": tracker,
            "dictionary": dictionary,
            "movements_by_id": movements_by_id,
            "alias_index": alias_index,
        }
        self._mtimes = mtimes
        return self._cache

    def _tracker(self) -> dict:
        return self._ensure_loaded()["tracker"]

    def _movements_by_id(self) -> dict[str, MovementMatch]:
        return self._ensure_loaded()["movements_by_id"]

    def _alias_index(self) -> dict[str, list[MovementMatch]]:
        return self._ensure_loaded()["alias_index"]

    def all_dates(self) -> list[str]:
        tracker = self._tracker()
        dates = set()
        for section in ("daily_records", "diet_records", "training_sessions", "raw_entries"):
            for record in tracker.get(section, []):
                value = record.get("Date") if section != "raw_entries" else record.get("date")
                if value:
                    dates.add(str(value)[:10])
        return sorted(dates, reverse=True)

    def latest_date(self) -> str:
        return next(iter(self.all_dates()), "")

    def records_on_date(self, entry_date: str) -> dict[str, list[dict]]:
        tracker = self._tracker()
        entry_date = str(entry_date)[:10]
        return {
            "body": [item for item in tracker.get("daily_records", []) if str(item.get("Date", ""))[:10] == entry_date],
            "diet": [item for item in tracker.get("diet_records", []) if str(item.get("Date", ""))[:10] == entry_date],
            "training": [
                item for item in tracker.get("training_sessions", []) if str(item.get("Date", ""))[:10] == entry_date
            ],
            "raw": [item for item in tracker.get("raw_entries", []) if str(item.get("date", ""))[:10] == entry_date],
        }

    def display_name_for_movement_id(self, movement_id: str, fallback: str = "") -> str:
        match = self._movements_by_id().get(str(movement_id).strip())
        return match.display_name if match and match.display_name else fallback

    def _movement_rows_for_training_day(self, day_number: int | str) -> list[dict]:
        tracker = self._tracker()
        rows = []
        for movement in tracker.get("movements", {}).values():
            for history in movement.get("history", []) or []:
                if str(history.get("training_day", "")) == str(day_number):
                    rows.append(
                        {
                            "movement_id": history.get("movement_id") or movement.get("movement_id", ""),
                            "display_name": self.display_name_for_movement_id(
                                history.get("movement_id") or movement.get("movement_id", ""),
                                fallback=str(movement.get("name", "")),
                            ),
                            "order": history.get("order", ""),
                            "sets": history.get("sets", []) or [],
                            "notes": str(history.get("notes", "") or "").strip(),
                            "raw": str(history.get("raw", "") or "").strip(),
                            "date": str(history.get("date", ""))[:10],
                        }
                    )
        return sorted(rows, key=lambda item: (int(item["order"] or 9999), item["display_name"]))

    def get_training_by_date(self, entry_date: str) -> dict:
        grouped = self.records_on_date(entry_date)
        sessions = []
        for session in sorted(grouped["training"], key=lambda item: int(item.get("No.", 0) or 0), reverse=True):
            day_number = session.get("No.", "")
            sessions.append(
                {
                    "date": str(session.get("Date", ""))[:10],
                    "day_number": day_number,
                    "split": str(session.get("Split", "") or "").strip(),
                    "notes": str(session.get("Notes", "") or "").strip(),
                    "raw_record": str(session.get("Raw Record", "") or "").strip(),
                    "standardized_summary": str(session.get("Standardized Summary", "") or "").strip(),
                    "movements": self._movement_rows_for_training_day(day_number),
                }
            )
        return {"date": str(entry_date)[:10], "sessions": sessions}

    def get_today_summary(self) -> dict:
        entry_date = self.latest_date()
        if not entry_date:
            return {"date": "", "body": {}, "diet": {}, "training": {}, "cardio": "", "notes": ""}
        grouped = self.records_on_date(entry_date)
        body = grouped["body"][-1] if grouped["body"] else {}
        diet = grouped["diet"][-1] if grouped["diet"] else {}
        training_data = self.get_training_by_date(entry_date)
        latest_training = training_data["sessions"][0] if training_data["sessions"] else {}
        return {
            "date": entry_date,
            "body": body,
            "diet": diet,
            "training": latest_training,
            "training_sessions": training_data["sessions"],
            "cardio": str(body.get("Cardio", "") or "").strip(),
            "notes": str(body.get("Notes", "") or "").strip(),
        }

    def get_record_detail(self, entry_date: str) -> dict:
        grouped = self.records_on_date(entry_date)
        body = grouped["body"][-1] if grouped["body"] else {}
        diet = grouped["diet"][-1] if grouped["diet"] else {}
        training = self.get_training_by_date(entry_date)
        return {
            "date": str(entry_date)[:10],
            "body": body,
            "diet": diet,
            "training": training["sessions"],
            "raw_entries": grouped["raw"],
        }

    def find_movement_candidates(self, query: str, limit: int = 12) -> list[MovementMatch]:
        query_text = str(query or "").strip()
        if not query_text:
            return []
        normalized_query = normalize_name(query_text)
        results: list[MovementMatch] = []
        seen = set()
        for match in self._movements_by_id().values():
            haystack = [match.display_name, match.english_name, *match.aliases]
            if any(
                normalized_query and normalized_query in normalize_name(candidate)
                or query_text.lower() in candidate.lower()
                for candidate in haystack
                if candidate
            ):
                if match.movement_id not in seen:
                    seen.add(match.movement_id)
                    results.append(match)
        results.sort(key=lambda item: (not item.active, item.display_name or item.english_name))
        return results[:limit]

    def get_movement_history(self, movement_name: str, limit: int = 5) -> dict:
        candidates = self.find_movement_candidates(movement_name, limit=1)
        if not candidates:
            return {"query": movement_name, "movement": None, "history": []}
        movement = candidates[0]
        tracker_movement = next(
            (
                item
                for item in self._tracker().get("movements", {}).values()
                if str(item.get("movement_id", "")) == movement.movement_id
            ),
            None,
        )
        history = []
        for record in (tracker_movement or {}).get("history", []) or []:
            structured_sets = record.get("sets", []) or []
            sets_lines = [format_set_line(item) for item in structured_sets]
            if not sets_lines:
                sets_lines = extract_set_lines_from_raw(record.get("raw", ""))
            history.append(
                {
                    "id": str(record.get("id", "")),
                    "date": str(record.get("date", ""))[:10],
                    "order": record.get("order", ""),
                    "training_day": record.get("training_day", ""),
                    "sets": structured_sets,
                    "sets_lines": sets_lines,
                    "cardio": record.get("cardio", {}) or {},
                    "notes": str(record.get("notes", "") or "").strip(),
                    "raw": str(record.get("raw", "") or "").strip(),
                }
            )
        history.sort(key=lambda item: item["date"], reverse=True)
        return {
            "query": movement_name,
            "movement": {
                "movement_id": movement.movement_id,
                "display_name": movement.display_name,
                "english_name": movement.english_name,
                "aliases": movement.aliases,
                "muscle_group": movement.muscle_group,
                "category": movement.category,
                "active": movement.active,
            },
            "history": history[:limit],
        }

    def search_records(self, query: str, scope: str = "30d") -> dict:
        query_text = str(query or "").strip()
        normalized_query = normalize_name(query_text)
        movement_candidates = self.find_movement_candidates(query_text, limit=8) if query_text else []
        movement_ids = {item.movement_id for item in movement_candidates}

        dates = self.all_dates()
        if scope == "30d":
            cutoff = date.today() - timedelta(days=30)
            dates = [item for item in dates if (parse_iso_date(item) or cutoff) >= cutoff]

        record_results = []
        for entry_date in dates:
            detail = self.get_record_detail(entry_date)
            body = detail["body"]
            diet = detail["diet"]
            training = detail["training"]
            search_blobs = [
                entry_date,
                str(body.get("Training", "") or ""),
                str(body.get("Cardio", "") or ""),
                str(body.get("Notes", "") or ""),
                str(diet.get("Food Summary", "") or ""),
                str(diet.get("Notes", "") or ""),
                " ".join(str(session.get("Split", "") or "") for session in training),
                " ".join(str(session.get("Standardized Summary", "") or "") for session in training),
            ]
            movement_rows = [row for session in training for row in session.get("movements", [])]
            movement_match = False
            if movement_ids:
                movement_match = any(str(row.get("movement_id", "")) in movement_ids for row in movement_rows)
            elif normalized_query:
                movement_match = any(
                    normalized_query in normalize_name(
                        " ".join([str(row.get("display_name", "")), str(row.get("raw", "")), str(row.get("notes", ""))])
                    )
                    for row in movement_rows
                )
            keyword_match = not query_text or any(
                query_text.lower() in blob.lower() or (normalized_query and normalized_query in normalize_name(blob))
                for blob in search_blobs
                if blob
            )
            if keyword_match or movement_match:
                record_results.append(
                    {
                        "date": entry_date,
                        "weight": body.get("Weight (kg)", ""),
                        "training": str(body.get("Training", "") or ""),
                        "calories": diet.get("Calories (kcal)", ""),
                        "food_summary": str(diet.get("Food Summary", "") or ""),
                        "movement_count": len(movement_rows),
                        "matched_sections": [
                            label
                            for label, condition in (
                                ("Body", query_text.lower() in str(body.get("Notes", "")).lower()),
                                ("Diet", query_text.lower() in str(diet.get("Food Summary", "")).lower()),
                                ("Training", any(query_text.lower() in str(session.get("Split", "")).lower() for session in training)),
                                ("Movement", movement_match),
                            )
                            if query_text and condition
                        ]
                        or ["General"],
                    }
                )

        return {
            "query": query_text,
            "scope": scope,
            "records": record_results,
            "movements": [
                {
                    "movement_id": item.movement_id,
                    "display_name": item.display_name,
                    "english_name": item.english_name,
                    "aliases": item.aliases[:6],
                    "muscle_group": item.muscle_group,
                }
                for item in movement_candidates
            ],
        }
