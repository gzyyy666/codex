from __future__ import annotations

import copy
import json
import os
import re
import shutil
import time
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from typing import Callable


ParserCallback = Callable[[str, dict, dict], dict]


class LedgerCommandError(RuntimeError):
    pass


class DuplicateDateError(LedgerCommandError):
    def __init__(self, duplicates: dict[str, int]):
        super().__init__("A record already exists for this date.")
        self.duplicates = duplicates


def _read_json(path: Path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(fallback)


def _write_json_atomic(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    payload = json.dumps(value, ensure_ascii=False, indent=2)
    temp.write_text(payload, encoding="utf-8")
    json.loads(temp.read_text(encoding="utf-8"))
    os.replace(temp, path)


def _normalize_name(value: str) -> str:
    value = str(value or "").lower().strip()
    value = re.sub(r"[\s_\-/（）()]+", "", value)
    return re.sub(r"[^\w\u4e00-\u9fff]", "", value)


def _format_number(value) -> str:
    if value in (None, ""):
        return "缺失"
    try:
        number = float(value)
        return str(int(number)) if number.is_integer() else f"{number:g}"
    except (TypeError, ValueError):
        return str(value)


def _dictionary_indexes(dictionary: dict) -> tuple[dict[str, dict], dict[str, dict]]:
    by_id: dict[str, dict] = {}
    by_alias: dict[str, dict] = {}
    for definition in dictionary.get("movements", []) or []:
        movement_id = str(definition.get("movement_id", "")).strip()
        if not movement_id:
            continue
        by_id[movement_id] = definition
        for candidate in (
            definition.get("display_name", ""),
            definition.get("english_name", ""),
            *(definition.get("aliases") or []),
        ):
            normalized = _normalize_name(candidate)
            if normalized:
                by_alias[normalized] = definition
    return by_id, by_alias


def _next_custom_id(dictionary: dict) -> str:
    used = set()
    for definition in dictionary.get("movements", []) or []:
        match = re.fullmatch(r"CUSTOM_(\d+)", str(definition.get("movement_id", "")))
        if match:
            used.add(int(match.group(1)))
    number = 1
    while number in used:
        number += 1
    return f"CUSTOM_{number:03d}"


def _new_definition(candidate: str, display_name: str, dictionary: dict) -> dict:
    name = str(display_name or candidate).strip()
    definition = {
        "movement_id": _next_custom_id(dictionary),
        "display_name": name,
        "english_name": name if not re.search(r"[\u4e00-\u9fff]", name) else "",
        "aliases": [candidate] if candidate else [],
        "muscle_group": "Unclassified",
        "category": "Strength",
        "equipment": "",
        "active": True,
        "notes": "Registered from a confirmed training entry.",
    }
    dictionary.setdefault("movements", []).append(definition)
    return definition


class LedgerCommandService:
    """Shared, UI-free parse/review/save boundary for desktop and Web."""

    def __init__(
        self,
        data_file: Path,
        dictionary_file: Path,
        backup_dir: Path,
        parser: ParserCallback,
    ) -> None:
        self.data_file = Path(data_file)
        self.dictionary_file = Path(dictionary_file)
        self.backup_dir = Path(backup_dir)
        self.parser = parser
        self.lock_file = self.data_file.parent / ".fitness-ledger-write.lock"

    def load_state(self) -> tuple[dict, dict]:
        database = _read_json(
            self.data_file,
            {"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []},
        )
        dictionary = _read_json(self.dictionary_file, {"version": "1.0", "movements": []})
        return database, dictionary

    @contextmanager
    def write_lock(self, timeout: float = 8.0):
        deadline = time.monotonic() + timeout
        self.lock_file.parent.mkdir(parents=True, exist_ok=True)
        while True:
            try:
                descriptor = os.open(self.lock_file, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(descriptor, f"{os.getpid()} {time.time()}".encode("ascii"))
                os.close(descriptor)
                break
            except FileExistsError:
                try:
                    age = time.time() - self.lock_file.stat().st_mtime
                    if age > 120:
                        self.lock_file.unlink(missing_ok=True)
                        continue
                except OSError:
                    pass
                if time.monotonic() >= deadline:
                    raise LedgerCommandError("Another Fitness Ledger save is in progress.")
                time.sleep(0.1)
        try:
            yield
        finally:
            self.lock_file.unlink(missing_ok=True)

    def parse(self, raw_text: str) -> dict:
        raw = str(raw_text or "").strip()
        if not raw:
            raise LedgerCommandError("Daily entry is empty.")
        database, dictionary = self.load_state()
        parsed = self.parser(raw, database, dictionary)
        self._prepare_generated_training_fields(parsed)
        return self.review_payload(parsed, database, dictionary)

    def _prepare_generated_training_fields(self, parsed: dict) -> None:
        training = parsed.setdefault("training", {})
        movements = training.setdefault("movements", [])
        summary = "；".join(
            f"第{movement.get('order')}个动作：{movement.get('display_name') or movement.get('name', '')}"
            for movement in movements
        )
        notes = []
        for movement in movements:
            note = str(movement.get("notes", "")).strip().rstrip("，。?!！？")
            if note:
                notes.append(f"{movement.get('display_name') or movement.get('name', '')}：{note}")
        training["standardized_summary"] = summary
        training["notes"] = f"{'；'.join(notes)}。" if notes else ""

    @staticmethod
    def records_on_date(database: dict, entry_date: str) -> dict[str, list[dict]]:
        target = str(entry_date)[:10]
        return {
            "body": [row for row in database.get("daily_records", []) if str(row.get("Date", ""))[:10] == target],
            "diet": [row for row in database.get("diet_records", []) if str(row.get("Date", ""))[:10] == target],
            "training": [row for row in database.get("training_sessions", []) if str(row.get("Date", ""))[:10] == target],
        }

    def review_payload(self, parsed: dict, database: dict | None = None, dictionary: dict | None = None) -> dict:
        if database is None or dictionary is None:
            database, dictionary = self.load_state()
        by_id, by_alias = _dictionary_indexes(dictionary)
        movements = parsed.get("training", {}).get("movements", [])
        for movement in movements:
            definition = by_id.get(str(movement.get("movement_id", ""))) or by_alias.get(
                _normalize_name(movement.get("name", ""))
            )
            if definition:
                movement["movement_id"] = definition["movement_id"]
                movement["display_name"] = definition.get("display_name") or movement.get("name", "")
                movement["_review_action"] = "use"
                movement["_matched_active"] = bool(definition.get("active", True))
            else:
                movement.setdefault("_review_action", "add")
                movement["_matched_active"] = None
        duplicates = self.records_on_date(database, parsed.get("date", ""))
        return {
            "review_id": parsed.get("id"),
            "review": parsed,
            "summary": self.summary(parsed),
            "warnings": self.warnings(parsed, database),
            "duplicates": {key: len(rows) for key, rows in duplicates.items()},
            "mapping_options": [
                {
                    "movement_id": item.get("movement_id", ""),
                    "display_name": item.get("display_name", ""),
                    "english_name": item.get("english_name", ""),
                }
                for item in dictionary.get("movements", []) or []
                if item.get("active", True)
            ],
        }

    def summary(self, parsed: dict) -> dict:
        body = parsed.get("body", {})
        diet = parsed.get("diet", {})
        training = parsed.get("training", {})
        included = [m for m in training.get("movements", []) if m.get("_review_action") not in {"skip", "cancel"}]
        return {
            "date": parsed.get("date", ""),
            "weight": body.get("weight"),
            "bowel_movement": body.get("bowel_movement", ""),
            "calories": diet.get("calories"),
            "protein": diet.get("protein"),
            "carbs": diet.get("carbs"),
            "fat": diet.get("fat"),
            "training": training.get("split") or body.get("training_summary", ""),
            "movement_count": len(included),
            "new_movement_count": sum(1 for item in included if not item.get("movement_id") and item.get("_review_action") != "map"),
            "cardio": body.get("cardio_summary", ""),
            "notes_present": bool(body.get("notes") or training.get("notes")),
        }

    def warnings(self, parsed: dict, database: dict | None = None) -> list[dict]:
        database = database or self.load_state()[0]
        body = parsed.get("body", {})
        diet = parsed.get("diet", {})
        training = parsed.get("training", {})
        warnings = []

        def add(severity: str, code: str, message: str) -> None:
            warnings.append({"severity": severity, "code": code, "message": message})

        if body.get("weight") is None:
            add("high", "missing_weight", "缺少体重。")
        if not body.get("bowel_movement"):
            add("medium", "missing_bowel", "缺少排便记录。")
        for field, label in (("calories", "热量"), ("protein", "蛋白质"), ("carbs", "碳水"), ("fat", "脂肪")):
            if diet.get(field) is None:
                add("high", f"missing_{field}", f"缺少{label}。")
        for movement in training.get("movements", []):
            if not movement.get("sets") and not movement.get("cardio"):
                add("medium", "missing_sets", f"动作“{movement.get('name', '')}”没有识别到组数。")
            if not movement.get("movement_id"):
                add("medium", "new_movement", f"新动作“{movement.get('name', '')}”需要确认处理方式。")
        duplicates = self.records_on_date(database, parsed.get("date", ""))
        if any(duplicates.values()):
            add(
                "high",
                "duplicate_date",
                f"同日期已有记录：Body {len(duplicates['body'])} / Diet {len(duplicates['diet'])} / Training {len(duplicates['training'])}。",
            )
        return warnings

    def validate_review(self, parsed: dict) -> None:
        try:
            date.fromisoformat(str(parsed.get("date", "")))
        except ValueError as exc:
            raise LedgerCommandError("Date must use YYYY-MM-DD format.") from exc
        for section, fields in (("body", ("weight",)), ("diet", ("calories", "protein", "carbs", "fat"))):
            for field in fields:
                value = parsed.get(section, {}).get(field)
                if value in (None, ""):
                    parsed.setdefault(section, {})[field] = None
                    continue
                try:
                    parsed[section][field] = float(value)
                except (TypeError, ValueError) as exc:
                    raise LedgerCommandError(f"{field} must be numeric or blank.") from exc
        for movement in parsed.get("training", {}).get("movements", []):
            action = movement.get("_review_action", "use")
            if action not in {"use", "add", "map", "skip"}:
                raise LedgerCommandError("Invalid movement review action.")
            if action == "map" and not movement.get("_mapped_movement_id"):
                raise LedgerCommandError(f"Movement {movement.get('name', '')} needs a mapping target.")

    def _checkpoint(self) -> tuple[Path, Path]:
        try:
            json.loads(self.data_file.read_text(encoding="utf-8"))
            json.loads(self.dictionary_file.read_text(encoding="utf-8"))
        except Exception as exc:
            raise LedgerCommandError("Current data files are not valid JSON; save was cancelled.") from exc
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        tracker_backup = self.backup_dir / f"undo_tracker_{stamp}.json"
        dictionary_backup = self.backup_dir / f"undo_dictionary_{stamp}.json"
        shutil.copy2(self.data_file, tracker_backup)
        shutil.copy2(self.dictionary_file, dictionary_backup)
        return tracker_backup, dictionary_backup

    @staticmethod
    def _remove_for_overwrite(database: dict, entry_date: str, replacement_id: str) -> int | None:
        target = str(entry_date)[:10]
        removed_sessions = [row for row in database.get("training_sessions", []) if str(row.get("Date", ""))[:10] == target]
        removed_days = {int(row.get("No.")) for row in removed_sessions if str(row.get("No.", "")).isdigit()}
        database["daily_records"] = [row for row in database.get("daily_records", []) if str(row.get("Date", ""))[:10] != target]
        database["diet_records"] = [row for row in database.get("diet_records", []) if str(row.get("Date", ""))[:10] != target]
        database["training_sessions"] = [row for row in database.get("training_sessions", []) if str(row.get("Date", ""))[:10] != target]
        for movement in database.get("movements", {}).values():
            movement["history"] = [row for row in movement.get("history", []) if str(row.get("date", ""))[:10] != target]
        for raw_record in database.get("raw_entries", []):
            if str(raw_record.get("date", ""))[:10] == target and not raw_record.get("superseded"):
                raw_record.update({"superseded": True, "superseded_at": datetime.now().replace(microsecond=0).isoformat(), "superseded_by": replacement_id})
        return min(removed_days) if removed_days else None

    @staticmethod
    def _tracker_movement(database: dict, definition: dict, candidate: str) -> dict:
        movement_id = definition["movement_id"]
        for movement in database.setdefault("movements", {}).values():
            if movement.get("movement_id") == movement_id:
                if candidate and candidate not in movement.setdefault("aliases", []):
                    movement["aliases"].append(candidate)
                return movement
        movement = {
            "movement_id": movement_id,
            "name": definition.get("display_name") or candidate,
            "aliases": [candidate] if candidate else [],
            "history": [],
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
        }
        database["movements"][movement_id] = movement
        return movement

    def save(self, parsed: dict, save_mode: str | None = None) -> dict:
        parsed = copy.deepcopy(parsed)
        self.validate_review(parsed)
        with self.write_lock():
            database, dictionary = self.load_state()
            duplicates = self.records_on_date(database, parsed["date"])
            if any(duplicates.values()) and save_mode not in {"overwrite", "append_training"}:
                raise DuplicateDateError({key: len(rows) for key, rows in duplicates.items()})
            save_mode = save_mode or "normal"
            tracker_backup, dictionary_backup = self._checkpoint()
            try:
                result = self._apply_save(database, dictionary, parsed, save_mode)
                _write_json_atomic(self.dictionary_file, dictionary)
                try:
                    _write_json_atomic(self.data_file, database)
                except Exception:
                    shutil.copy2(dictionary_backup, self.dictionary_file)
                    raise
            except Exception:
                if not self.data_file.exists():
                    shutil.copy2(tracker_backup, self.data_file)
                raise
            return result

    def _apply_save(self, database: dict, dictionary: dict, parsed: dict, save_mode: str) -> dict:
        by_id, by_alias = _dictionary_indexes(dictionary)
        entry_date = parsed["date"]
        replacement_day = None
        if save_mode == "overwrite":
            replacement_day = self._remove_for_overwrite(database, entry_date, parsed["id"])
        raw_record = {
            "id": parsed["id"],
            "date": entry_date,
            "text": parsed["raw"],
            "created_at": datetime.now().replace(microsecond=0).isoformat(),
            "save_mode": save_mode,
        }
        database.setdefault("raw_entries", []).append(raw_record)
        save_primary = save_mode != "append_training"
        body = parsed.get("body", {})
        if save_primary and any(body.get(field) not in (None, "") for field in ("weight", "bowel_movement", "training_summary", "cardio_summary", "notes")):
            database.setdefault("daily_records", []).append(
                {
                    "id": str(uuid.uuid4()), "Date": entry_date, "Weight (kg)": body.get("weight"),
                    "Body Fat %": body.get("body_fat"), "Waist (cm)": body.get("waist"),
                    "Sleep (h)": body.get("sleep"), "Steps": body.get("steps"), "Context": body.get("context", ""),
                    "Bowel Movement": body.get("bowel_movement", ""), "Training": body.get("training_summary", ""),
                    "Cardio": body.get("cardio_summary", ""), "Notes": body.get("notes", ""), "source": "text entry",
                }
            )
        diet = parsed.get("diet", {})
        if save_primary and (diet.get("food_summary") or any(diet.get(field) is not None for field in ("calories", "protein", "carbs", "fat"))):
            database.setdefault("diet_records", []).append(
                {
                    "id": str(uuid.uuid4()), "Date": entry_date, "Food Summary": diet.get("food_summary", ""),
                    "Calories (kcal)": diet.get("calories"), "Protein (g)": diet.get("protein"),
                    "Carbs (g)": diet.get("carbs"), "Fat (g)": diet.get("fat"),
                    "Notes": diet.get("notes", ""), "source": "text entry",
                }
            )
        training = parsed.get("training", {})
        saved_movements = 0
        skipped = []
        if training.get("split") or training.get("movements"):
            existing_days = [int(row.get("No.") or 0) for row in database.get("training_sessions", [])]
            day_number = replacement_day or (max(existing_days, default=0) + 1)
            summary_parts = []
            note_parts = []
            for movement_data in training.get("movements", []):
                action = movement_data.get("_review_action", "use")
                candidate = str(movement_data.get("name", "")).strip()
                if action == "skip":
                    skipped.append(candidate)
                    continue
                definition = None
                if action == "map":
                    definition = by_id.get(str(movement_data.get("_mapped_movement_id", "")))
                    if not definition or not definition.get("active", True):
                        raise LedgerCommandError(f"Mapping target for {candidate} is unavailable or inactive.")
                    if candidate and candidate not in definition.setdefault("aliases", []):
                        definition["aliases"].append(candidate)
                elif action == "add" and _normalize_name(candidate) not in by_alias:
                    definition = _new_definition(candidate, movement_data.get("display_name", ""), dictionary)
                else:
                    definition = by_id.get(str(movement_data.get("movement_id", ""))) or by_alias.get(_normalize_name(candidate))
                if not definition:
                    skipped.append(candidate)
                    continue
                by_id, by_alias = _dictionary_indexes(dictionary)
                movement = self._tracker_movement(database, definition, candidate)
                movement.setdefault("history", []).append(
                    {
                        "id": str(uuid.uuid4()), "movement_id": definition["movement_id"], "date": entry_date,
                        "training_day": day_number, "order": movement_data.get("order"), "sets": movement_data.get("sets", []),
                        "cardio": movement_data.get("cardio") or {}, "raw": movement_data.get("raw", ""),
                        "notes": movement_data.get("notes", ""), "source": "text entry",
                    }
                )
                display_name = definition.get("display_name") or movement_data.get("display_name") or candidate
                summary_parts.append(f"第{movement_data.get('order')}个动作：{display_name}")
                note = str(movement_data.get("notes", "")).strip().rstrip("，。?!！？")
                if note:
                    note_parts.append(f"{display_name}：{note}")
                saved_movements += 1
            training_notes = str(training.get("notes", ""))
            if save_mode == "append_training":
                training_notes = f"同日追加训练。{training_notes}" if training_notes else "同日追加训练。"
            database.setdefault("training_sessions", []).append(
                {
                    "id": str(uuid.uuid4()), "No.": day_number, "Date": entry_date,
                    "Split": training.get("split", ""), "Raw Record": training.get("raw", ""),
                    "Standardized Summary": training.get("standardized_summary") or "；".join(summary_parts),
                    "Notes": training_notes or (f"{'；'.join(note_parts)}。" if note_parts else ""),
                    "save_mode": save_mode, "source": "text entry",
                }
            )
            if skipped:
                raw_record["skipped_movements"] = skipped
        return {
            "ok": True,
            "date": entry_date,
            "save_mode": save_mode,
            "saved_movements": saved_movements,
            "skipped_movements": skipped,
        }

