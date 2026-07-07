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


def _new_definition(
    candidate: str,
    display_name: str,
    dictionary: dict,
    muscle_group: str = "Unclassified",
) -> dict:
    name = str(display_name or candidate).strip()
    definition = {
        "movement_id": _next_custom_id(dictionary),
        "display_name": name,
        "english_name": name if not re.search(r"[\u4e00-\u9fff]", name) else "",
        "aliases": [candidate] if candidate else [],
        "muscle_group": str(muscle_group or "Unclassified").strip() or "Unclassified",
        "category": "Strength",
        "equipment": "",
        "active": True,
        "pinned": False,
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

    def undo_status(self) -> dict:
        """Describe the newest valid paired checkpoint without changing data."""
        for tracker_checkpoint in sorted(
            self.backup_dir.glob("undo_tracker_*.json"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        ):
            suffix = tracker_checkpoint.name[len("undo_tracker_") :]
            dictionary_checkpoint = self.backup_dir / f"undo_dictionary_{suffix}"
            if not dictionary_checkpoint.exists():
                continue
            try:
                tracker = _read_json(tracker_checkpoint, None)
                dictionary = _read_json(dictionary_checkpoint, None)
            except Exception:
                continue
            if isinstance(tracker, dict) and isinstance(dictionary, dict):
                stamp = suffix.removesuffix(".json")
                return {
                    "available": True,
                    "checkpoint": stamp,
                    "created_at": datetime.fromtimestamp(tracker_checkpoint.stat().st_mtime).replace(microsecond=0).isoformat(),
                }
        return {"available": False, "checkpoint": "", "created_at": ""}

    def undo_last_write(self) -> dict:
        """Restore the latest paired checkpoint using the same semantics as desktop Undo."""
        with self.write_lock():
            status = self.undo_status()
            if not status["available"]:
                raise LedgerCommandError("没有可撤销的保存记录。")
            suffix = f"{status['checkpoint']}.json"
            tracker_checkpoint = self.backup_dir / f"undo_tracker_{suffix}"
            dictionary_checkpoint = self.backup_dir / f"undo_dictionary_{suffix}"
            restored_database = _read_json(tracker_checkpoint, None)
            restored_dictionary = _read_json(dictionary_checkpoint, None)
            if not isinstance(restored_database, dict) or not isinstance(restored_dictionary, dict):
                raise LedgerCommandError("最近的撤销检查点无效，数据未更改。")

            self.backup_dir.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            pre_tracker = self.backup_dir / f"pre_undo_tracker_{stamp}.json"
            pre_dictionary = self.backup_dir / f"pre_undo_dictionary_{stamp}.json"
            shutil.copy2(self.data_file, pre_tracker)
            shutil.copy2(self.dictionary_file, pre_dictionary)
            try:
                _write_json_atomic(self.dictionary_file, restored_dictionary)
                try:
                    _write_json_atomic(self.data_file, restored_database)
                except Exception:
                    shutil.copy2(pre_dictionary, self.dictionary_file)
                    raise
            except Exception as exc:
                if not self.data_file.exists():
                    shutil.copy2(pre_tracker, self.data_file)
                raise LedgerCommandError("撤销失败，原数据已保留。") from exc

            tracker_checkpoint.rename(
                tracker_checkpoint.with_name(tracker_checkpoint.name.replace("undo_tracker_", "undone_tracker_", 1))
            )
            dictionary_checkpoint.rename(
                dictionary_checkpoint.with_name(
                    dictionary_checkpoint.name.replace("undo_dictionary_", "undone_dictionary_", 1)
                )
            )
            return {
                "undone": True,
                "checkpoint": status["checkpoint"],
                "pre_undo_backups": [pre_tracker.name, pre_dictionary.name],
            }

    def movement_definitions(self) -> list[dict]:
        """Return dictionary terms with tracker history counts, without exposing mutable state."""
        database, dictionary = self.load_state()
        counts = {
            str(movement.get("movement_id", "")): len(movement.get("history", []) or [])
            for movement in database.get("movements", {}).values()
        }
        result = []
        for definition in dictionary.get("movements", []) or []:
            item = copy.deepcopy(definition)
            item["history_count"] = counts.get(str(item.get("movement_id", "")), 0)
            result.append(item)
        return sorted(
            result,
            key=lambda item: (
                not bool(item.get("pinned", False)),
                int(item.get("focus_rank", 0) or 0),
                -int(item.get("history_count", 0) or 0),
                str(item.get("display_name", "")).casefold(),
            ),
        )

    @staticmethod
    def _definition_by_id(dictionary: dict, movement_id: str) -> dict:
        definition = next(
            (
                item
                for item in dictionary.get("movements", []) or []
                if str(item.get("movement_id", "")) == str(movement_id)
            ),
            None,
        )
        if not definition:
            raise LedgerCommandError("Movement dictionary entry was not found.")
        return definition

    @staticmethod
    def _clean_aliases(values, display_name: str, old_display: str = "") -> list[str]:
        if isinstance(values, str):
            values = re.split(r"[\n,，;；]+", values)
        aliases = [str(value).strip() for value in (values or []) if str(value).strip()]
        if old_display and old_display != display_name:
            aliases.append(old_display)
        return list(dict.fromkeys([display_name, *aliases]))

    @staticmethod
    def _validate_definition_conflicts(dictionary: dict, movement_id: str, aliases: list[str]) -> None:
        _by_id, by_alias = _dictionary_indexes(dictionary)
        for alias in aliases:
            conflict = by_alias.get(_normalize_name(alias))
            if conflict and str(conflict.get("movement_id", "")) != movement_id:
                raise LedgerCommandError(
                    f"Alias '{alias}' already belongs to {conflict.get('display_name') or conflict.get('movement_id')}."
                )

    @staticmethod
    def _history_fingerprint(history: dict) -> tuple[str, int, str]:
        try:
            order = int(history.get("order") or 0)
        except (TypeError, ValueError):
            order = 0
        return (
            str(history.get("date", ""))[:10],
            order,
            _normalize_name(str(history.get("raw", ""))),
        )

    def _reconcile_definition(self, database: dict, dictionary: dict, definition: dict) -> dict[str, int]:
        """Merge matching custom rows and previously skipped raw movements after alias edits."""
        movement_id = str(definition.get("movement_id", ""))
        alias_keys = {
            _normalize_name(value)
            for value in [
                definition.get("display_name", ""),
                definition.get("english_name", ""),
                *(definition.get("aliases") or []),
            ]
            if str(value).strip()
        }
        result = {"merged_rows": 0, "merged_history": 0, "restored_skipped": 0}
        if not movement_id or not alias_keys:
            return result
        target = self._tracker_movement(database, definition, "")
        existing = {self._history_fingerprint(row) for row in target.get("history", [])}
        custom_ids = set()
        for key, source in list(database.get("movements", {}).items()):
            source_id = str(source.get("movement_id", ""))
            if source is target or (source_id and not source_id.startswith("CUSTOM_")):
                continue
            names = [source.get("name", ""), *(source.get("aliases") or [])]
            if not any(_normalize_name(name) in alias_keys for name in names if str(name).strip()):
                continue
            for history in source.get("history", []) or []:
                fingerprint = self._history_fingerprint(history)
                if fingerprint in existing:
                    continue
                history["movement_id"] = movement_id
                target.setdefault("history", []).append(history)
                existing.add(fingerprint)
                result["merged_history"] += 1
            target["aliases"] = list(dict.fromkeys([*target.get("aliases", []), *names, *(definition.get("aliases") or [])]))
            database["movements"].pop(key, None)
            if source_id.startswith("CUSTOM_"):
                custom_ids.add(source_id)
            result["merged_rows"] += 1
        if custom_ids:
            dictionary["movements"] = [
                item for item in dictionary.get("movements", []) if item.get("movement_id") not in custom_ids
            ]

        sessions_by_date: dict[str, list[dict]] = {}
        for session in database.get("training_sessions", []):
            sessions_by_date.setdefault(str(session.get("Date", ""))[:10], []).append(session)
        for sessions in sessions_by_date.values():
            sessions.sort(key=lambda row: int(row.get("No.") or 0))
        for raw_record in database.get("raw_entries", []):
            if raw_record.get("superseded"):
                continue
            skipped = list(raw_record.get("skipped_movements") or [])
            matching = {_normalize_name(name) for name in skipped if _normalize_name(name) in alias_keys}
            if not matching or not str(raw_record.get("text", "")).strip():
                continue
            parsed = self.parser(str(raw_record.get("text", "")), database, dictionary)
            entry_date = str(parsed.get("date") or raw_record.get("date", ""))[:10]
            sessions = sessions_by_date.get(entry_date, [])
            session = (sessions[-1] if raw_record.get("save_mode") == "append_training" else sessions[0]) if sessions else {}
            restored = set()
            for movement_data in parsed.get("training", {}).get("movements", []):
                candidate_key = _normalize_name(movement_data.get("name", ""))
                if candidate_key not in matching:
                    continue
                history = {
                    "id": str(uuid.uuid4()), "movement_id": movement_id, "date": entry_date,
                    "training_day": int(session.get("No.") or 0), "order": movement_data.get("order"),
                    "sets": movement_data.get("sets") or [], "cardio": movement_data.get("cardio") or {},
                    "raw": movement_data.get("raw", ""), "notes": movement_data.get("notes", ""),
                    "source": "alias reconciliation",
                }
                fingerprint = self._history_fingerprint(history)
                if fingerprint not in existing:
                    target.setdefault("history", []).append(history)
                    existing.add(fingerprint)
                    result["restored_skipped"] += 1
                restored.add(candidate_key)
            remaining = [name for name in skipped if _normalize_name(name) not in restored]
            if remaining:
                raw_record["skipped_movements"] = remaining
            else:
                raw_record.pop("skipped_movements", None)
        target["name"] = definition.get("display_name") or target.get("name", "")
        target["aliases"] = list(dict.fromkeys([*target.get("aliases", []), *(definition.get("aliases") or [])]))
        target["history"] = sorted(
            target.get("history", []), key=lambda row: (str(row.get("date", "")), self._history_fingerprint(row)[1])
        )
        return result

    def _write_pair(self, database: dict, dictionary: dict, tracker_backup: Path, dictionary_backup: Path) -> None:
        _write_json_atomic(self.dictionary_file, dictionary)
        try:
            _write_json_atomic(self.data_file, database)
        except Exception:
            shutil.copy2(dictionary_backup, self.dictionary_file)
            shutil.copy2(tracker_backup, self.data_file)
            raise

    def create_movement_definition(self, values: dict) -> dict:
        with self.write_lock():
            database, dictionary = self.load_state()
            display_name = str(values.get("display_name", "")).strip()
            if not display_name:
                raise LedgerCommandError("Display name cannot be blank.")
            aliases = self._clean_aliases(values.get("aliases", []), display_name)
            self._validate_definition_conflicts(dictionary, "", aliases)
            tracker_backup, dictionary_backup = self._checkpoint()
            definition = _new_definition(display_name, display_name, dictionary)
            definition.update({
                "english_name": str(values.get("english_name", "")).strip(),
                "aliases": aliases,
                "muscle_group": str(values.get("muscle_group", "Unclassified")).strip() or "Unclassified",
                "category": str(values.get("category", "Strength")).strip() or "Strength",
                "equipment": str(values.get("equipment", "")).strip(),
                "notes": str(values.get("notes", "")).strip(),
                "active": bool(values.get("active", True)),
                "pinned": bool(values.get("pinned", False)),
                "focus_rank": max(0, int(values.get("focus_rank", 0) or 0)),
            })
            reconciliation = self._reconcile_definition(database, dictionary, definition)
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"definition": copy.deepcopy(definition), "reconciliation": reconciliation}

    def update_movement_definition(self, movement_id: str, values: dict) -> dict:
        with self.write_lock():
            database, dictionary = self.load_state()
            definition = self._definition_by_id(dictionary, movement_id)
            display_name = str(values.get("display_name", definition.get("display_name", ""))).strip()
            if not display_name:
                raise LedgerCommandError("Display name cannot be blank.")
            aliases = self._clean_aliases(values.get("aliases", definition.get("aliases", [])), display_name, str(definition.get("display_name", "")).strip())
            self._validate_definition_conflicts(dictionary, str(movement_id), aliases)
            tracker_backup, dictionary_backup = self._checkpoint()
            definition.update({
                "display_name": display_name,
                "english_name": str(values.get("english_name", definition.get("english_name", ""))).strip(),
                "aliases": aliases,
                "muscle_group": str(values.get("muscle_group", definition.get("muscle_group", ""))).strip(),
                "category": str(values.get("category", definition.get("category", ""))).strip(),
                "equipment": str(values.get("equipment", definition.get("equipment", ""))).strip(),
                "notes": str(values.get("notes", definition.get("notes", ""))).strip(),
                "pinned": bool(values.get("pinned", definition.get("pinned", False))),
                "focus_rank": max(0, int(values.get("focus_rank", definition.get("focus_rank", 0)) or 0)),
            })
            for movement in database.get("movements", {}).values():
                if str(movement.get("movement_id", "")) == str(movement_id):
                    movement["name"] = display_name
                    movement["aliases"] = list(dict.fromkeys([*movement.get("aliases", []), *aliases]))
            reconciliation = self._reconcile_definition(database, dictionary, definition)
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"definition": copy.deepcopy(definition), "reconciliation": reconciliation}

    def set_movement_active(self, movement_id: str, active: bool) -> dict:
        with self.write_lock():
            database, dictionary = self.load_state()
            definition = self._definition_by_id(dictionary, movement_id)
            tracker_backup, dictionary_backup = self._checkpoint()
            definition["active"] = bool(active)
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"movement_id": movement_id, "active": bool(active)}

    def delete_movement_definition(self, movement_id: str, confirmation: str) -> dict:
        with self.write_lock():
            database, dictionary = self.load_state()
            definition = self._definition_by_id(dictionary, movement_id)
            display_name = str(definition.get("display_name", ""))
            if confirmation.strip() != display_name:
                raise LedgerCommandError("Delete confirmation does not match the movement name.")
            history_count = sum(
                len(movement.get("history", []) or [])
                for movement in database.get("movements", {}).values()
                if str(movement.get("movement_id", "")) == str(movement_id)
            )
            tracker_backup, dictionary_backup = self._checkpoint()
            dictionary["movements"] = [
                item for item in dictionary.get("movements", []) if str(item.get("movement_id", "")) != str(movement_id)
            ]
            database["movements"] = {
                key: movement for key, movement in database.get("movements", {}).items()
                if str(movement.get("movement_id", "")) != str(movement_id)
            }
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"movement_id": movement_id, "display_name": display_name, "deleted_history": history_count}

    @staticmethod
    def _record_config(record_type: str) -> tuple[str, tuple[str, ...], set[str]]:
        configs = {
            "body": (
                "daily_records",
                ("Date", "Weight (kg)", "Bowel Movement", "Training", "Cardio", "Notes"),
                {"Weight (kg)"},
            ),
            "diet": (
                "diet_records",
                ("Date", "Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)", "Food Summary", "Notes"),
                {"Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)"},
            ),
            "training": (
                "training_sessions",
                ("Date", "Split", "Raw Record", "Standardized Summary", "Notes"),
                set(),
            ),
        }
        if record_type not in configs:
            raise LedgerCommandError("Unsupported record type.")
        return configs[record_type]

    def update_record(self, record_type: str, record_id: str, values: dict) -> dict:
        collection, allowed_fields, numeric_fields = self._record_config(record_type)
        if not isinstance(values, dict):
            raise LedgerCommandError("Record values must be an object.")
        with self.write_lock():
            database, dictionary = self.load_state()
            record = next(
                (row for row in database.get(collection, []) if str(row.get("id", "")) == str(record_id)),
                None,
            )
            if not record:
                raise LedgerCommandError("Record was not found.")
            updates = {}
            for field in allowed_fields:
                if field not in values:
                    continue
                value = values[field]
                if field in numeric_fields:
                    if value in (None, ""):
                        updates[field] = None
                    else:
                        try:
                            updates[field] = float(value)
                        except (TypeError, ValueError) as exc:
                            raise LedgerCommandError(f"{field} must be numeric or blank.") from exc
                else:
                    updates[field] = str(value or "").strip()
            if "Date" in updates:
                try:
                    date.fromisoformat(updates["Date"])
                except ValueError as exc:
                    raise LedgerCommandError("Date must use YYYY-MM-DD format.") from exc
            tracker_backup, dictionary_backup = self._checkpoint()
            record.update(updates)
            record["updated_at"] = datetime.now().replace(microsecond=0).isoformat()
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"record_type": record_type, "record": copy.deepcopy(record)}

    @staticmethod
    def _parse_sets_text(text: str) -> list[dict]:
        sets = []
        normalized = str(text or "").replace("×", "x").replace("*", "x").replace("X", "x")
        pattern = re.compile(r"(?P<load>自重|body\s*weight|bw|\d+(?:\.\d+)?(?:\s*kg)?)\s*x\s*(?P<reps>\d+)\s*x\s*(?P<sets>\d+)", re.I)
        for match in pattern.finditer(normalized):
            load = match.group("load").strip()
            item = {"reps": int(match.group("reps")), "sets": int(match.group("sets"))}
            number = re.search(r"\d+(?:\.\d+)?", load)
            if number:
                item["weight"] = float(number.group())
            else:
                item["weight"] = 0.0
                item["weight_text"] = "自重"
            sets.append(item)
        if normalized.strip() and not sets:
            raise LedgerCommandError("Sets must use 'weight x reps x sets', one set block per line.")
        return sets

    def update_movement_history(self, movement_id: str, history_id: str, values: dict) -> dict:
        if not isinstance(values, dict):
            raise LedgerCommandError("Movement history values must be an object.")
        with self.write_lock():
            database, dictionary = self.load_state()
            movement = next(
                (row for row in database.get("movements", {}).values() if str(row.get("movement_id", "")) == str(movement_id)),
                None,
            )
            if not movement:
                raise LedgerCommandError("Movement was not found.")
            history = next(
                (row for row in movement.get("history", []) if str(row.get("id", "")) == str(history_id)),
                None,
            )
            if not history:
                raise LedgerCommandError("Movement history record was not found.")
            try:
                order_text = str(values.get("order", "")).strip()
                order = int(order_text) if order_text else None
                cardio = {}
                for field in ("duration_minutes", "incline", "speed", "heart_rate"):
                    text = str(values.get(field, "")).strip()
                    cardio[field] = float(text) if text else None
                cardio = {key: value for key, value in cardio.items() if value is not None}
            except (TypeError, ValueError) as exc:
                raise LedgerCommandError("Order and cardio values must be numeric or blank.") from exc
            updates = {
                "order": order,
                "sets": self._parse_sets_text(str(values.get("sets_text", ""))),
                "cardio": cardio,
                "raw": str(values.get("raw", "")).strip(),
                "notes": str(values.get("notes", "")).strip(),
                "updated_at": datetime.now().replace(microsecond=0).isoformat(),
            }
            tracker_backup, dictionary_backup = self._checkpoint()
            history.update(updates)
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"movement_id": movement_id, "history": copy.deepcopy(history)}

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
            if action == "add" and not str(movement.get("_muscle_group", "")).strip():
                raise LedgerCommandError(f"请为新动作“{movement.get('name', '')}”选择训练部位。")

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
                    definition = _new_definition(
                        candidate,
                        movement_data.get("display_name", ""),
                        dictionary,
                        movement_data.get("_muscle_group", "Unclassified"),
                    )
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
