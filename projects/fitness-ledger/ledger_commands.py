from __future__ import annotations

import copy
import hashlib
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

from fitness_ledger_core.notes import normalize_note_text
from fitness_ledger_core.pair_transaction import (
    PairTransactionError,
)
from fitness_ledger_core.pair_transaction import (
    begin as begin_pair_transaction,
)
from fitness_ledger_core.pair_transaction import (
    commit as commit_pair_transaction,
)
from fitness_ledger_core.pair_transaction import (
    journal_path as pair_transaction_journal_path,
)
from fitness_ledger_core.pair_transaction import (
    recover as recover_pair_transaction,
)
from fitness_ledger_core.record_relations import (
    canonical_date,
    migrate_state,
    movement_items,
    movement_items_by_date,
    movement_items_by_session,
    now_iso,
    rebuild_movement_projection,
    record_day_id,
    validate_relations,
)
from fitness_ledger_core.shared_view_models import LedgerViewModels, movement_in_progress
from fitness_ledger_core.training_organization import (
    THEME_COLOR_KEYS,
    normalize_label,
    normalize_training_organization,
    organization_catalog,
    theme_color_key,
)

ParserCallback = Callable[[str, dict, dict], dict]


class LedgerCommandError(RuntimeError):
    def __init__(self, message: str, code: str = "COMMAND_FAILED", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


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
    try:
        payload = json.dumps(value, ensure_ascii=False, indent=2)
        with temp.open("w", encoding="utf-8", newline="") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        json.loads(temp.read_text(encoding="utf-8"))
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


_NON_SEMANTIC_FIELDS = {
    "id", "created_at", "updated_at", "superseded_at", "superseded_by", "save_mode", "source",
    "record_day_id", "training_session_id", "movement_instance_id", "raw_entry_id", "raw_revision_id", "revision",
}

_PRODUCT_PLACEMENTS = {
    "main": {"label": "主内容", "slot": "top", "visible_by_default": True},
    "detail": {"label": "详情区", "slot": "secondary", "visible_by_default": True},
    "history": {"label": "仅历史", "slot": "history", "visible_by_default": True},
    "record": {"label": "仅记录，不展示", "slot": "auxiliary", "visible_by_default": False},
}

_PRODUCT_SURFACES = {
    "category_page": {
        "label": "跟随所属类别页面",
        "description": "例如 Body 的腰围，进入 Body 记录里的同级指标。",
    },
    "page_widget": {
        "label": "页面角落小模块",
        "description": "不创建新页面，可放在首页、Body、Diet、Training 或 Movement 的角落。",
    },
    "history_only": {
        "label": "只在记录、历史和导出中保留",
        "description": "不自动放进任何页面，但仍可输入、查询、导出。",
    },
    "record_only": {
        "label": "只记录，不自动展示",
        "description": "保留正式记录和历史，页面不显示。",
    },
    "detail_page": {
        "label": "训练详情上方的其他扩展",
        "description": "不占 Body、Diet、Training 列表位置，在打开每日详情时显示在训练记录上方。",
    },
}


def _product_placement(category_id: str, choice: str, order: int = 0, surface: str = "category_page", display_page: str = "home") -> dict:
    key = str(choice or "main").strip().lower()
    if key == "summary":
        key = "main"
    placement = _PRODUCT_PLACEMENTS.get(key, _PRODUCT_PLACEMENTS["main"])
    surface_key = str(surface or "category_page").strip().lower()
    if surface_key in {"home_widget", "page_widget"}:
        section = display_page if display_page in {"home", "body", "diet", "training", "movement"} else "home"
        slot = "auxiliary"
        visible = True
    elif surface_key in {"history_only", "record_only"}:
        section = "extension"
        slot = "history" if surface_key == "history_only" else "auxiliary"
        visible = surface_key == "history_only"
    elif surface_key == "detail_page":
        section = "extension"
        slot = "secondary"
        visible = True
    else:
        section = category_id if category_id in {"body", "diet", "training", "movement"} else "extension"
        slot = placement["slot"]
        visible = bool(placement["visible_by_default"])
    return {
        "section": section,
        "slot": slot,
        "order": int(order or 0),
        "visible_by_default": visible,
        "renderer": "metric_history" if key in {"detail", "history"} or surface_key == "history_only" else "single_metric",
    }


def _product_surface(category_id: str, presentation: dict) -> str:
    section = str((presentation or {}).get("section", "extension"))
    slot = str((presentation or {}).get("slot", "top"))
    if slot == "summary":
        slot = "top"
    if section == "home":
        return "page_widget"
    if slot == "history":
        return "history_only"
    if not bool((presentation or {}).get("visible_by_default", True)):
        return "record_only"
    if section in {"body", "diet", "training", "movement"} and slot == "auxiliary":
        return "page_widget"
    if section in {"body", "diet", "training", "movement"} and section == str(category_id):
        return "category_page"
    if section == "extension" and str(category_id) == "extension" and slot in {"top", "secondary"}:
        return "detail_page"
    return "history_only"


def _normalise_business_value(value, field_name: str = ""):
    """Compare ledger content, not JSON layout or write-time bookkeeping."""
    if isinstance(value, str):
        if field_name.lower() in {"text", "raw", "raw_input"}:
            return value.strip()
        if field_name.lower() in {"notes", "daily_notes", "diet_notes", "training_notes", "movement_notes"}:
            return normalize_note_text(value)
        lines = [line.rstrip() for line in value.splitlines()]
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        compact = []
        for line in lines:
            if not line.strip() and compact and not compact[-1].strip():
                continue
            compact.append(line)
        return "\n".join(compact).strip() if len(compact) == 1 else "\n".join(compact)
    if isinstance(value, list):
        # Revision rows are an audit projection of the active raw entry.  A
        # semantically identical overwrite must not be treated as a business
        # change merely because it would append another audit row.
        if field_name == "raw_entry_revisions":
            return []
        return [_normalise_business_value(item, field_name) for item in value if not (isinstance(item, dict) and item.get("superseded"))]
    if isinstance(value, dict):
        return {
            key: _normalise_business_value(item, str(key))
            for key, item in sorted(value.items())
            if key not in _NON_SEMANTIC_FIELDS and key != "superseded"
        }
    return value


def _same_business_content(before, after) -> bool:
    return _normalise_business_value(before) == _normalise_business_value(after)


def _normalize_name(value: str) -> str:
    value = str(value or "").lower().strip()
    value = re.sub(r"[\s_\-/（）()]+", "", value)
    return re.sub(r"[^\w\u4e00-\u9fff]", "", value)


def _stable_json_hash(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


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


_CANONICAL_GROUP_PREFIXES = {
    "Shoulder": "SHOULDER",
    "Chest": "CHEST",
    "Back": "BACK",
    "Legs": "LEG",
    "Arms": "ARM",
    "Core": "CORE",
    "Cardio": "CARDIO",
}


def _existing_muscle_groups(dictionary: dict) -> list[str]:
    """Return the established body-part taxonomy, excluding temporary definitions."""
    groups = {
        str(item.get("muscle_group", "")).strip()
        for item in dictionary.get("movements", []) or []
        if isinstance(item, dict)
        and not re.fullmatch(r"CUSTOM_\d+", str(item.get("movement_id", "")).strip())
        and str(item.get("muscle_group", "")).strip()
        and str(item.get("muscle_group", "")).strip() != "Unclassified"
    }
    order = {name: index for index, name in enumerate(_CANONICAL_GROUP_PREFIXES)}
    return sorted(groups, key=lambda name: (order.get(name, len(order)), name.casefold()))


def _next_canonical_id(dictionary: dict, muscle_group: str) -> str:
    prefix = _CANONICAL_GROUP_PREFIXES.get(str(muscle_group or "").strip())
    if not prefix:
        raise LedgerCommandError("请选择已有的训练部位。", "INVALID_MUSCLE_GROUP")
    used = []
    pattern = re.compile(rf"{re.escape(prefix)}_(\d+)")
    for definition in dictionary.get("movements", []) or []:
        match = pattern.fullmatch(str(definition.get("movement_id", "")).strip())
        if match:
            used.append(int(match.group(1)))
    return f"{prefix}_{max(used, default=0) + 1:03d}"


def _new_definition(
    candidate: str,
    display_name: str,
    dictionary: dict,
    muscle_group: str = "Unclassified",
) -> dict:
    name = str(display_name or candidate).strip()
    established_groups = _existing_muscle_groups(dictionary)
    movement_id = (
        _next_canonical_id(dictionary, muscle_group)
        if muscle_group in established_groups
        else _next_custom_id(dictionary)
    )
    definition = {
        "movement_id": movement_id,
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
        module_registry_file: Path | None = None,
    ) -> None:
        self.data_file = Path(data_file)
        self.dictionary_file = Path(dictionary_file)
        self.backup_dir = Path(backup_dir)
        self.parser = parser
        self.module_registry_file = Path(module_registry_file) if module_registry_file else None
        self.lock_file = self.data_file.parent / ".fitness-ledger-write.lock"
        self.pair_transaction_file = pair_transaction_journal_path(self.data_file)
        self._last_migration_report: dict = {}
        self._recover_pending_pair_transaction()

    def _recover_pending_pair_transaction(self) -> dict:
        try:
            return recover_pair_transaction(
                self.pair_transaction_file, self.data_file, self.dictionary_file
            )
        except PairTransactionError as exc:
            raise LedgerCommandError(
                "Paired data recovery is incomplete; no data operation was started.",
                "PAIR_RECOVERY_REQUIRED",
                {"journal": str(self.pair_transaction_file), "cause": str(exc)},
            ) from exc

    def load_state(self) -> tuple[dict, dict]:
        self._recover_pending_pair_transaction()
        database = _read_json(
            self.data_file,
            {"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []},
        )
        dictionary = _read_json(self.dictionary_file, {"version": "1.0", "movements": []})
        database, dictionary, report = migrate_state(database, dictionary)
        self._last_migration_report = report
        return database, dictionary

    def migration_preview(self) -> dict:
        database = _read_json(self.data_file, {})
        dictionary = _read_json(self.dictionary_file, {})
        migrated, migrated_dictionary, report = migrate_state(database, dictionary)
        return {
            "status": "preview_ready", "source_schema": database.get("record_schema_version", "legacy"),
            "target_schema": migrated.get("record_schema_version", ""), "report": report,
            "before_issues": validate_relations(database, dictionary),
            "after_issues": validate_relations(migrated, migrated_dictionary),
            "write_attempted": False,
        }

    def migrate_legacy_state(self, *, confirmed: bool = False) -> dict:
        preview = self.migration_preview()
        if not confirmed:
            raise LedgerCommandError("Migration preview must be explicitly confirmed before writing.", "MIGRATION_CONFIRMATION_REQUIRED", preview)
        if preview["report"].get("changed") is not True:
            return {**preview, "status": "NO_CHANGES", "changed": False}
        with self.write_lock():
            database = _read_json(self.data_file, {})
            dictionary = _read_json(self.dictionary_file, {})
            migrated, migrated_dictionary, report = migrate_state(database, dictionary)
            self._validate_relations_or_raise(migrated, migrated_dictionary)
            tracker_backup, dictionary_backup = self._checkpoint()
            self._write_pair(migrated, migrated_dictionary, tracker_backup, dictionary_backup)
            return {"status": "MIGRATED", "changed": True, "report": report, "checkpoint": str(tracker_backup), "sync_state": "LOCAL_NEWER"}

    @staticmethod
    def _touch_record_day(database: dict, entry_date: str) -> None:
        day = record_day_id(entry_date)
        if not day:
            return
        days = database.setdefault("record_days", [])
        row = next((item for item in days if str(item.get("record_day_id")) == day), None)
        if row is None:
            row = {"record_day_id": day, "date": canonical_date(entry_date), "revision": 1}
            days.append(row)
        else:
            row["revision"] = int(row.get("revision", 1) or 1) + 1
        row["updated_at"] = now_iso()

    @staticmethod
    def _validate_relations_or_raise(database: dict, dictionary: dict) -> None:
        issues = validate_relations(database, dictionary)
        if issues:
            raise LedgerCommandError(
                "The record relationship graph is inconsistent; save was cancelled.",
                "RELATION_INTEGRITY_FAILED",
                {"issues": issues[:30], "issue_count": len(issues)},
            )

    def data_module_engine(self, registry_file: Path | None = None):
        """Return the registry-driven extension engine at the shared save boundary."""
        from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore, DataModuleEngine

        path = Path(registry_file) if registry_file else self.module_registry_file
        if path is None:
            raise LedgerCommandError(
                "Data Module registry is not configured.",
                "MODULE_REGISTRY_REQUIRED",
            )
        try:
            store = DataModuleDefinitionStore(path, backup_dir=self.backup_dir / "data_module_definitions")
            categories, registry, issues = store.load(strict=False)
            return DataModuleEngine(
                registry,
                self.data_file,
                self.dictionary_file,
                self.backup_dir,
                command_service=self,
                category_registry=categories,
                definition_issues=issues,
            )
        except Exception as exc:
            if isinstance(exc, LedgerCommandError):
                raise
            code = getattr(exc, "code", "MODULE_REGISTRY_INVALID")
            details = getattr(exc, "details", {})
            raise LedgerCommandError(str(exc), code, details) from exc

    def data_module_definition_store(self, registry_file: Path | None = None):
        from fitness_ledger_core.data_module_engine import DataModuleDefinitionStore

        path = Path(registry_file) if registry_file else self.module_registry_file
        if path is None:
            raise LedgerCommandError("Data Module definition store is not configured.", "MODULE_REGISTRY_REQUIRED")
        return DataModuleDefinitionStore(path, backup_dir=self.backup_dir / "data_module_definitions")

    def data_module_catalog(self) -> dict:
        try:
            return self.data_module_definition_store().catalog()
        except Exception as exc:
            code = getattr(exc, "code", "DEFINITION_STORE_ERROR")
            details = getattr(exc, "details", {})
            raise LedgerCommandError(str(exc), code, details) from exc

    def data_module_product_catalog(self) -> dict:
        """Return the ordinary-user view of the registry for the formal Web mirror."""
        catalog = self.data_module_catalog()
        categories = catalog.get("categories", [])
        labels = {str(item.get("category_id")): str(item.get("label") or item.get("category_id")) for item in categories}
        placement_labels = {key: value["label"] for key, value in _PRODUCT_PLACEMENTS.items()}
        modules = []
        for item in catalog.get("modules", []):
            presentation = item.get("presentation", {}) or {}
            display_surface = _product_surface(item.get("category_id", ""), presentation)
            placement = "widget" if display_surface == "page_widget" else next(
                (key for key, value in _PRODUCT_PLACEMENTS.items() if value["slot"] == ("top" if presentation.get("slot") == "summary" else presentation.get("slot")) and bool(value["visible_by_default"]) == bool(presentation.get("visible_by_default", True))),
                "main",
            )
            display_page = str(presentation.get("section", "")) if display_surface == "page_widget" else ""
            modules.append({
                "module_id": item.get("module_id", ""),
                "label": item.get("label", ""),
                "aliases": list(item.get("aliases", []) or []),
                "category_id": item.get("category_id", ""),
                "category_label": labels.get(str(item.get("category_id")), item.get("category_id", "")),
                "actual_unit": item.get("actual_unit", ""),
                "display_unit": item.get("display_unit", ""),
                "data_type": item.get("data_type", "number" if not item.get("actual_unit", "") else "quantity"),
                "status": item.get("status", "active"),
                "definition_version": item.get("definition_version", 1),
                "placement": placement,
                "placement_label": placement_labels.get(placement, placement),
                "display_surface": display_surface,
                "display_surface_label": _PRODUCT_SURFACES.get(display_surface, {}).get("label", ""),
                "display_page": display_page,
                "record_level": "daily_scalar",
                "record_level_label": "每日一个数值",
                "capabilities": {
                    "recordable": bool((item.get("capabilities") or {}).get("recordable", False)),
                    "exportable": bool((item.get("capabilities") or {}).get("exportable", False)),
                    "analysis_visible": bool((item.get("capabilities") or {}).get("analysis_visible", False)),
                    "statistics_visible": bool((item.get("capabilities") or {}).get("statistics_visible", False)),
                    "cloud_syncable": bool((item.get("capabilities") or {}).get("cloud_syncable", False)),
                    "mini_program_visible": bool((item.get("capabilities") or {}).get("mini_program_visible", False)),
                },
            })
        return {
            "schema": "fitness-ledger-data-module-product-catalog-v1",
            "categories": [
                {
                    "category_id": item.get("category_id", ""),
                    "label": item.get("label", item.get("category_id", "")),
                    "status": item.get("status", "active"),
                    "system": bool(item.get("system", False)),
                }
                for item in categories
            ],
            "modules": modules,
            "placement_choices": [{"value": key, "label": value["label"]} for key, value in _PRODUCT_PLACEMENTS.items()],
            "record_levels": [{"value": "daily_scalar", "label": "每日一个数值", "description": "每天最多保存一个数值，例如腰围、静息心率、肌酸摄入量。", "supported": True}],
            "display_page_choices": [
                {"value": "home", "label": "首页"},
                {"value": "body", "label": "Body 身体"},
                {"value": "diet", "label": "Diet 饮食"},
                {"value": "training", "label": "Training 训练"},
                {"value": "movement", "label": "Movement 动作"},
            ],
            "display_surfaces": [{"value": key, **value} for key, value in _PRODUCT_SURFACES.items()],
            "issues": catalog.get("issues", []),
            "source_fingerprint": catalog.get("source_fingerprint", ""),
        }

    def data_module_import_preview(self, payload: dict | str) -> dict:
        """Recognize a data-module package without importing or writing it."""
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except json.JSONDecodeError as exc:
                raise LedgerCommandError("导入内容不是有效的 JSON。", "MODULE_IMPORT_JSON_INVALID") from exc
        if not isinstance(payload, dict):
            raise LedgerCommandError("导入内容必须是对象。", "MODULE_IMPORT_PAYLOAD_INVALID")
        source_schema = str(payload.get("schema", "")).strip()
        supported_schemas = {
            "fitness-ledger-data-module-export-v1",
            "fitness-ledger-data-module-cloud-v1",
            "fitness-ledger-mini-module-contract-v1",
        }
        if source_schema not in supported_schemas:
            raise LedgerCommandError("这不是可识别的 Data Module 导出包。", "MODULE_IMPORT_SCHEMA_UNSUPPORTED", {"schema": source_schema})
        current = self.data_module_product_catalog()
        known = {str(item.get("module_id")): item for item in current.get("modules", [])}
        incoming_modules = [item for item in payload.get("modules", []) if isinstance(item, dict)]
        incoming_records = [item for item in payload.get("records", []) if isinstance(item, dict)]
        recognized = []
        unknown = []
        for item in incoming_modules:
            module_id = str(item.get("module_id", ""))
            target = known.get(module_id)
            (recognized if target else unknown).append({
                "module_id": module_id,
                "label": item.get("label", ""),
                "category_id": item.get("category_id", ""),
                "current_status": target.get("status") if target else "unknown",
                "record_level": "每日一个数值",
                "display_surface": target.get("display_surface") if target else "需要先建立定义",
            })
        known_ids = {item["module_id"] for item in recognized}
        orphan_records = [
            {"module_id": str(item.get("module_id", "")), "date": item.get("date", "")}
            for item in incoming_records
            if str(item.get("module_id", "")) not in known_ids
        ]
        return {
            "schema": "fitness-ledger-data-module-import-preview-v1",
            "source_schema": source_schema,
            "status": "preview_ready",
            "write_attempted": False,
            "recognized_modules": recognized,
            "unknown_modules": unknown,
            "orphan_records": orphan_records,
            "record_count": len(incoming_records),
            "next_step": "先确认类别和展示去向，再进行人工审核；本候选不自动导入。",
        }

    def data_module_discover(self, raw_text: str, record_date: str | None = None) -> dict:
        """Recognize an existing module or offer a generic explicit-field candidate."""
        raw = str(raw_text or "").strip()
        if not raw:
            raise LedgerCommandError("请先写下要记录的内容。", "MODULE_RAW_EMPTY")
        try:
            preview = self.data_module_preview(raw, record_date)
            return {"kind": "known", "preview": preview}
        except LedgerCommandError as exc:
            if exc.code != "MODULE_NOT_RECOGNIZED":
                # Existing aliases with a bad value/date should keep the useful
                # validation message instead of being mistaken for a new field.
                if exc.code not in {"MODULE_NOT_RECOGNIZED", "MODULE_DATE_REQUIRED"}:
                    raise

        without_dates = re.sub(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", " ", raw)
        without_dates = re.sub(r"(?:今天|today)", " ", without_dates, flags=re.IGNORECASE)

        # A new free-content field must be explicit (``名称: 内容``).  This
        # prevents ordinary prose from accidentally becoming a new module,
        # while allowing text such as mental state, symptoms, or a long note.
        text_match = re.match(r"^\s*([^:\n：=]{1,80}?)\s*[:：=]\s*(.+?)\s*$", without_dates, flags=re.DOTALL)
        if text_match:
            label = text_match.group(1).strip(" \t,，。")
            label = re.sub(r"^(?:记录|测量|我的|当前|早上|上午|晚上|晚间)+", "", label).strip(" \t,，。")
            value = text_match.group(2).strip()
            # Keep new-field discovery consistent with the registered-module
            # parser when another native field follows the candidate value.
            from fitness_ledger_core.data_module_engine import NATIVE_FIELD_RE
            boundary = NATIVE_FIELD_RE.search(value)
            if boundary:
                value = value[:boundary.start()].strip()
            if label and value:
                label_lower = label.casefold()
                category_hints = [
                    ("body", r"腰围|体重|体脂|心率|脉搏|体温|睡眠|血压|排便|围度|精神|情绪|大脑|状态|waist|weight|body|heart|pulse|sleep|temperature|mood|emotion|mental"),
                    ("diet", r"肌酸|蛋白|碳水|脂肪|热量|饮食|饮水|水|钠|糖|creatine|protein|carb|fat|calorie|diet|water|sodium"),
                    ("training", r"训练|有氧|跑步|步数|训练时长|training|cardio|run|steps|workout"),
                    ("movement", r"动作|卧推|深蹲|硬拉|引体|movement|bench|squat|deadlift|pullup"),
                ]
                suggested_category_id = "extension"
                suggestion_reason = "这是显式的文字记录项，默认放入“其他扩展”；你仍然可以手动改选类别和展示位置。"
                for category_id, pattern in category_hints:
                    if re.search(pattern, label_lower, flags=re.IGNORECASE):
                        suggested_category_id = category_id
                        suggestion_reason = f"根据名称中的常见词，建议归入“{category_id}”；你仍然可以手动改选。"
                        break
                return {
                    "kind": "new_candidate",
                    "candidate": {
                        "label": label,
                        "aliases": [label],
                        "value": value,
                        "data_type": "text",
                        "content_format": "free_text",
                        "unit": "",
                        "date": record_date or date.today().isoformat(),
                        "raw": raw,
                        "suggested_category_id": suggested_category_id,
                        "suggested_display_surface": "category_page" if suggested_category_id != "extension" else "page_widget",
                        "suggestion_reason": suggestion_reason,
                        "record_level": "daily_scalar",
                    },
                }
        number = re.search(r"(?<![\d.])[-+]?(?:\d+(?:\.\d+)?|\.\d+)(?![\d.])", without_dates)
        if not number:
            return {"kind": "not_data_module", "message": "请使用“记录项: 内容”或“记录项 数值”的格式。"}
        label = without_dates[: number.start()].strip(" \t,，。:：=是为的")
        label = re.sub(r"^(?:记录|测量|我的|当前|早上|上午|晚上|晚间)+", "", label).strip(" \t,，。:：=是为的")
        label = re.sub(r"\s+", " ", label)
        if not label:
            return {"kind": "not_data_module", "message": "请把记录项名称写在数值前面，例如“晨间脉搏 58”。"}
        tail = without_dates[number.end():].strip()
        unit_match = re.match(r"(次/分|厘米|公斤|小时|分钟|bpm|cm|kg|mm|%|h|min|g|mg|mcg|ml|l|克|毫克|毫升|斤)", tail, flags=re.IGNORECASE)
        unit = unit_match.group(1) if unit_match else ""
        value_text = number.group(0)
        value = float(value_text)
        if value.is_integer():
            value = int(value)
        label_lower = label.casefold()
        category_hints = [
            ("body", r"腰围|体重|体脂|心率|脉搏|体温|睡眠|血压|排便|围度|waist|weight|body|heart|pulse|sleep|temperature"),
            ("diet", r"肌酸|蛋白|碳水|脂肪|热量|饮食|饮水|水|钠|糖|creatine|protein|carb|fat|calorie|diet|water|sodium"),
            ("training", r"训练|有氧|跑步|步数|训练时长|training|cardio|run|steps|workout"),
            ("movement", r"动作|卧推|深蹲|硬拉|引体|movement|bench|squat|deadlift|pullup"),
        ]
        suggested_category_id = "extension"
        suggestion_reason = "没有匹配到现有类别，默认放入“其他扩展”；不会创建新的一级页面。"
        for category_id, pattern in category_hints:
            if re.search(pattern, label_lower, flags=re.IGNORECASE):
                suggested_category_id = category_id
                suggestion_reason = f"根据名称中的常见词，建议归入“{category_id}”；你仍然可以手动改选。"
                break
        return {
            "kind": "new_candidate",
            "candidate": {
                "label": label,
                "aliases": [label],
                "value": value,
                "unit": unit,
                "date": record_date or date.today().isoformat(),
                "raw": raw,
                "suggested_category_id": suggested_category_id,
                "suggested_display_surface": "category_page" if suggested_category_id != "extension" else "page_widget",
                "suggestion_reason": suggestion_reason,
                "record_level": "daily_scalar",
            },
        }

    def data_module_product_definition_preview(self, request: dict) -> dict:
        """Map the small user form to the engine's stable definition contract."""
        kind = str(request.get("kind", "module")).strip().lower()
        action = str(request.get("action", "create")).strip().lower()
        if kind == "category":
            if action == "delete":
                category_id = str(request.get("category_id", "")).strip()
                if not category_id:
                    raise LedgerCommandError("缺少要删除的类别。", "CATEGORY_ID_REQUIRED")
                return self.data_module_definition_preview({"kind": "category", "action": "delete", "category_id": category_id})
            if action in {"retire", "re_enable", "reenable"}:
                category_id = str(request.get("category_id", "")).strip()
                if not category_id:
                    raise LedgerCommandError("缺少要操作的类别。", "CATEGORY_ID_REQUIRED")
                return self.data_module_definition_preview({"kind": "category", "action": action, "category_id": category_id, "changes": {}})
            values = dict(request.get("values", request))
            values["label"] = str(values.get("label", "")).strip()
            if not values["label"]:
                raise LedgerCommandError("请填写类别名称。", "CATEGORY_LABEL_REQUIRED")
            return self.data_module_definition_preview({"kind": "category", "action": action, "values": values, "category_id": request.get("category_id"), "changes": request.get("changes", {})})
        if action == "delete":
            module_id = str(request.get("module_id", "")).strip()
            if not module_id:
                raise LedgerCommandError("缺少要删除的记录项。", "MODULE_ID_REQUIRED")
            return self.data_module_definition_preview({"kind": "module", "action": "delete", "module_id": module_id})
        if action in {"retire", "re_enable", "reenable"}:
            module_id = str(request.get("module_id", "")).strip()
            if not module_id:
                raise LedgerCommandError("缺少要操作的记录项。", "MODULE_ID_REQUIRED")
            return self.data_module_definition_preview({"kind": "module", "action": action, "module_id": module_id, "changes": {}})
        values = dict(request.get("values", request))
        label = str(values.get("label", "")).strip()
        category_id = str(values.get("category_id", "")).strip()
        if not label:
            raise LedgerCommandError("请填写记录项名称。", "MODULE_LABEL_REQUIRED")
        if not category_id:
            raise LedgerCommandError("请选择一个类别。", "MODULE_CATEGORY_REQUIRED")
        aliases = values.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [item.strip() for item in re.split(r"[,，\n]", aliases) if item.strip()]
        values["label"] = label
        values["aliases"] = aliases
        values["actual_unit"] = str(values.get("actual_unit", values.get("unit", ""))).strip()
        values["display_unit"] = str(values.get("display_unit", values["actual_unit"])).strip()
        values["data_type"] = str(values.get("data_type") or ("quantity" if values["actual_unit"] else "number")).strip().lower()
        values["capabilities"] = values.get("capabilities") if isinstance(values.get("capabilities"), dict) else {}
        placement = str(values.get("placement", values.get("placement_choice", "main"))).strip().lower()
        if placement == "summary":
            placement = "main"
        display_surface = str(values.get("display_surface", "category_page")).strip().lower()
        if display_surface == "home_widget":
            display_surface = "page_widget"
        display_page = str(values.get("display_page", "home")).strip().lower()
        values["display_surface"] = display_surface
        values["display_page"] = display_page
        values["presentation"] = _product_placement(category_id, placement, int(values.get("order", 0) or 0), display_surface, display_page)
        if action == "create":
            return self.data_module_definition_preview({"kind": "module", "action": "create", "values": values})
        module_id = str(request.get("module_id", values.get("module_id", ""))).strip()
        changes = dict(request.get("changes", values))
        changes.pop("module_id", None)
        changes["aliases"] = aliases
        changes["actual_unit"] = values["actual_unit"]
        changes["display_unit"] = values["display_unit"]
        changes["label"] = label
        changes["category_id"] = category_id
        changes.update(values["presentation"])
        return self.data_module_definition_preview({"kind": "module", "action": action, "module_id": module_id, "changes": changes})

    def data_module_definition_preview(self, request: dict) -> dict:
        try:
            store = self.data_module_definition_store()
            kind = str(request.get("kind", "")).strip().lower()
            action = str(request.get("action", "create")).strip().lower()
            if kind == "category" and action == "create":
                return store.preview_create_category(request.get("values", request))
            if kind == "category" and action == "delete":
                return store.preview_delete_category(str(request.get("category_id", "")).strip())
            if kind == "category" and action in {"update", "rename", "retire", "re_enable", "reenable"}:
                category_id = str(request.get("category_id", "")).strip()
                changes = dict(request.get("changes", {}))
                if action == "retire":
                    changes.update({"status": "retired"})
                elif action in {"re_enable", "reenable"}:
                    changes.update({"status": "active"})
                return store.preview_update_category(category_id, changes)
            if kind == "module" and action == "create":
                return store.preview_create_module(request.get("values", request))
            if kind == "module" and action == "delete":
                return store.preview_delete_module(str(request.get("module_id", "")).strip())
            if kind == "module" and action in {"update", "rename", "retire", "re_enable", "reenable"}:
                module_id = str(request.get("module_id", "")).strip()
                changes = dict(request.get("changes", {}))
                if action == "retire":
                    changes.update({"status": "retired", "capabilities": {"recordable": False}})
                elif action in {"re_enable", "reenable"}:
                    changes.update({"status": "active", "capabilities": {"recordable": True}})
                return store.preview_update_module(module_id, changes)
            raise LedgerCommandError("Unsupported definition preview action.", "DEFINITION_ACTION_UNSUPPORTED")
        except LedgerCommandError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "DEFINITION_PREVIEW_INVALID")
            details = getattr(exc, "details", {})
            raise LedgerCommandError(str(exc), code, details) from exc

    def data_module_definition_save(self, preview: dict, *, confirmed: bool = False) -> dict:
        try:
            with self.write_lock():
                result = self.data_module_definition_store().commit_preview(preview, confirmed=confirmed)
                if (preview or {}).get("operation") == "delete_module":
                    module_id = str(preview.get("module_id", ""))
                    database, _dictionary = self.load_state()
                    records = database.get("data_module_records", []) or []
                    kept = [item for item in records if not isinstance(item, dict) or str(item.get("module_id", "")) != module_id]
                    removed = len(records) - len(kept)
                    if removed:
                        database["data_module_records"] = kept
                        _write_json_atomic(self.data_file, database)
                    result["deleted_record_count"] = removed
                return result
        except LedgerCommandError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "DEFINITION_SAVE_FAILED")
            details = getattr(exc, "details", {})
            raise LedgerCommandError(str(exc), code, details) from exc

    def _data_module_call(self, method: str, *args, **kwargs):
        try:
            return getattr(self.data_module_engine(), method)(*args, **kwargs)
        except LedgerCommandError:
            raise
        except Exception as exc:
            code = getattr(exc, "code", "DATA_MODULE_ERROR")
            details = getattr(exc, "details", {})
            raise LedgerCommandError(str(exc), code, details) from exc

    def data_module_preview(self, raw_text: str, record_date: str | None = None) -> dict:
        return self._data_module_call("preview", raw_text, record_date)

    def data_module_save(self, preview: dict, *, confirmed: bool = False, raw_entry_id: str | None = None) -> dict:
        return self._data_module_call("save_preview", preview, confirmed=confirmed, raw_entry_id=raw_entry_id)

    def data_module_query(self, module_id: str, start: str = "", end: str = "", *, latest: bool = False, category_id: str = "") -> list[dict]:
        return self._data_module_call("query", module_id, start, end, latest=latest, category_id=category_id)

    def data_module_history(self, module_id: str, start: str = "", end: str = "") -> dict:
        return self._data_module_call("history", module_id, start, end)

    def data_module_llm_template(self) -> dict:
        return self._data_module_call("llm_entry_template")

    def data_module_statistics(self, module_id: str, start: str = "", end: str = "") -> dict:
        return self._data_module_call("statistics", module_id, start, end)

    def data_module_export(self) -> dict:
        return self._data_module_call("normal_export")

    def data_module_analysis_catalog(self) -> dict:
        return self._data_module_call("analysis_catalog")

    def data_module_analysis_preview(self, module_ids: list[str]) -> dict:
        return self._data_module_call("analysis_preview", module_ids)

    def data_module_check(self) -> list[dict]:
        return self._data_module_call("data_check")

    def data_module_cloud_payload(self) -> dict:
        return self._data_module_call("build_cloud_payload")

    def data_module_cloud_verify(self, payload: dict) -> dict:
        from fitness_ledger_core.data_module_engine import DataModuleEngine

        return DataModuleEngine.verify_cloud_payload(payload)

    def data_module_cloud_roundtrip(self, payload: dict) -> dict:
        from fitness_ledger_core.data_module_engine import DataModuleEngine

        try:
            return DataModuleEngine.cloud_roundtrip(payload)
        except Exception as exc:
            code = getattr(exc, "code", "MODULE_CLOUD_VERIFY_FAILED")
            details = getattr(exc, "details", {})
            raise LedgerCommandError(str(exc), code, details) from exc

    def data_module_mini_contract(self) -> dict:
        return self._data_module_call("build_mini_program_contract")

    def data_module_release_readiness(self) -> dict:
        return self._data_module_call("release_readiness")

    def data_module_presentation_contract(self) -> dict:
        return self._data_module_call("presentation_contract")

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
            begin_pair_transaction(
                self.pair_transaction_file,
                self.data_file,
                self.dictionary_file,
                pre_tracker,
                pre_dictionary,
            )
            try:
                _write_json_atomic(self.dictionary_file, restored_dictionary)
                _write_json_atomic(self.data_file, restored_database)
                commit_pair_transaction(self.pair_transaction_file)
            except Exception as exc:
                rollback_errors = []
                for backup, destination in ((pre_tracker, self.data_file), (pre_dictionary, self.dictionary_file)):
                    try:
                        shutil.copy2(backup, destination)
                    except Exception as rollback_exc:
                        rollback_errors.append(str(rollback_exc))
                if not rollback_errors:
                    self.pair_transaction_file.unlink(missing_ok=True)
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
            str(definition.get("movement_id", "")): len(movement_items(database, str(definition.get("movement_id", ""))))
            for definition in dictionary.get("movements", []) or []
            if isinstance(definition, dict)
        }
        result = []
        for definition in dictionary.get("movements", []) or []:
            item = copy.deepcopy(definition)
            item["history_count"] = counts.get(str(item.get("movement_id", "")), 0)
            item["exclude_from_progress"] = bool(item.get("exclude_from_progress", False))
            result.append(item)
        return sorted(
            result,
            key=lambda item: (
                not (bool(item.get("pinned", False)) or int(item.get("focus_rank", 0) or 0) > 0),
                int(item.get("focus_rank", 0) or 0) if int(item.get("focus_rank", 0) or 0) > 0 else 1_000_000,
                -int(item.get("history_count", 0) or 0),
                str(item.get("display_name", "")).casefold(),
            ),
        )

    def movement_progress_definitions(self) -> list[dict]:
        """Return the single formal Movement Progress projection."""
        return [item for item in self.movement_definitions() if movement_in_progress(item)]

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
    def _definition_summary(definition: dict | None, movement_id: str) -> dict:
        definition = definition or {}
        return {
            "movement_id": movement_id,
            "display_name": str(definition.get("display_name", "")),
            "english_name": str(definition.get("english_name", "")),
            "muscle_group": str(definition.get("muscle_group", "")),
            "aliases": copy.deepcopy(definition.get("aliases", []) or []),
            "active": bool(definition.get("active", True)) if definition else None,
        }

    @staticmethod
    def _checkpoint_identity(tracker_backup: Path) -> str:
        return tracker_backup.name.removeprefix("undo_tracker_").removesuffix(".json")

    @staticmethod
    def _discard_checkpoint(tracker_backup: Path, dictionary_backup: Path) -> None:
        tracker_backup.unlink(missing_ok=True)
        dictionary_backup.unlink(missing_ok=True)

    def _strict_state_snapshot(self) -> tuple[dict, dict, dict]:
        files = (("tracker", self.data_file), ("dictionary", self.dictionary_file))
        decoded: dict[str, dict] = {}
        fingerprint: dict[str, dict | str] = {}
        for label, path in files:
            try:
                before = path.stat()
                payload = path.read_bytes()
                after = path.stat()
                if (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns):
                    raise LedgerCommandError(
                        "Formal data changed while it was being read; retry the preview.",
                        "STATE_CHANGED_DURING_READ",
                    )
                value = json.loads(payload.decode("utf-8"))
                if not isinstance(value, dict):
                    raise ValueError("top-level JSON value is not an object")
            except LedgerCommandError:
                raise
            except Exception as exc:
                raise LedgerCommandError(
                    f"Current {label} data is unavailable or invalid; no migration was attempted.",
                    "FORMAL_DATA_INVALID",
                    {"file": label, "path": str(path.resolve())},
                ) from exc
            decoded[label] = value
            fingerprint[label] = {
                "path": str(path.resolve()),
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size": len(payload),
                "mtime_ns": after.st_mtime_ns,
            }
        fingerprint["identity"] = _stable_json_hash(fingerprint)
        # Read-only previews use the same in-memory canonicalization as normal
        # commands, while the byte fingerprint still detects stale files.
        tracker, dictionary, report = migrate_state(decoded["tracker"], decoded["dictionary"])
        self._last_migration_report = report
        return tracker, dictionary, fingerprint

    @staticmethod
    def _history_business_fingerprint(history: dict) -> str:
        # These fields are rebuilt compatibility/provenance fields.  They do
        # not change the recorded date, order, sets, notes, raw text, or
        # extension values that define the history event itself.
        derived = _NON_SEMANTIC_FIELDS | {"display_name"}
        value = {key: item for key, item in history.items() if key not in derived and key != "movement_id"}
        return _stable_json_hash(value)

    @staticmethod
    def _source_reference_paths(database: dict, dictionary: dict, source_id: str) -> dict:
        migratable: list[dict] = []
        unknown: list[dict] = []
        raw_occurrences: list[dict] = []
        movements = database.get("movements", {})
        if not isinstance(movements, dict):
            return {
                "migratable": [],
                "unknown": [{"path": "tracker.movements", "value": type(movements).__name__}],
                "raw_occurrences": [],
            }

        if source_id in movements:
            migratable.append({"kind": "tracker_movement_index", "path": f"tracker.movements.{source_id}"})
        for key, movement in movements.items():
            if not isinstance(movement, dict):
                continue
            if str(movement.get("movement_id", "")) == source_id:
                migratable.append({
                    "kind": "tracker_movement_identity",
                    "path": f"tracker.movements.{key}.movement_id",
                })

        for session_index, session in enumerate(database.get("training_sessions", []) or []):
            for item_index, item in enumerate(session.get("movement_items", []) or []):
                if isinstance(item, dict) and str(item.get("movement_id", "")) == source_id:
                    migratable.append({
                        "kind": "training_session_movement_item",
                        "path": f"tracker.training_sessions[{session_index}].movement_items[{item_index}].movement_id",
                        "history_id": str(item.get("id") or item.get("movement_instance_id") or ""),
                        "date": str(item.get("date", ""))[:10],
                        "training_day": item.get("training_day"),
                    })

        for index, definition in enumerate(dictionary.get("movements", []) or []):
            if isinstance(definition, dict) and str(definition.get("movement_id", "")) == source_id:
                migratable.append({
                    "kind": "dictionary_definition",
                    "path": f"dictionary.movements[{index}].movement_id",
                })

        def walk(value, path: tuple, root: str) -> None:
            if isinstance(value, dict):
                for key, item in value.items():
                    walk(item, (*path, key), root)
            elif isinstance(value, list):
                for index, item in enumerate(value):
                    walk(item, (*path, index), root)
            elif isinstance(value, str) and value == source_id:
                rendered = root + "".join(f"[{item}]" if isinstance(item, int) else f".{item}" for item in path)
                if not path or path[-1] != "movement_id":
                    raw_occurrences.append({"path": rendered, "value": source_id})
                    return
                known_tracker_path = root == "tracker" and (
                    (path[0:1] == ("movements",) and (
                        (len(path) == 3 and path[-1] == "movement_id")
                        or (len(path) == 5 and path[2] == "history" and isinstance(path[3], int) and path[4] == "movement_id")
                    ))
                    or (len(path) == 5 and path[0] == "training_sessions" and path[2] == "movement_items" and isinstance(path[1], int) and isinstance(path[3], int) and path[4] == "movement_id")
                )
                known = known_tracker_path or (
                    root == "dictionary"
                    and len(path) == 3
                    and path[0] == "movements"
                    and path[-1] == "movement_id"
                )
                if not known:
                    unknown.append({"path": rendered, "value": source_id})

        # The old tracker movement history is a derived compatibility
        # projection.  Never inspect it as a business-reference source.
        for key, value in database.items():
            if key != "movements":
                walk(value, (key,), "tracker")
        walk(dictionary, (), "dictionary")
        return {"migratable": migratable, "unknown": unknown, "raw_occurrences": raw_occurrences}

    def _build_movement_merge_plan(
        self,
        database: dict,
        dictionary: dict,
        source_id: str,
        target_id: str,
        data_fingerprint: dict,
        require_custom_source: bool = False,
    ) -> dict:
        source_id = str(source_id or "").strip()
        target_id = str(target_id or "").strip()
        blockers: list[dict] = []
        warnings: list[dict] = []

        def block(code: str, message: str, **details) -> None:
            item = {"code": code, "message": message}
            item.update(details)
            blockers.append(item)

        def warn(code: str, message: str, **details) -> None:
            item = {"code": code, "message": message}
            item.update(details)
            warnings.append(item)

        definitions = dictionary.get("movements", [])
        if not isinstance(definitions, list):
            definitions = []
            block("INVALID_DICTIONARY_SHAPE", "movement_dictionary.movements must be a list.")
        elif any(not isinstance(item, dict) for item in definitions):
            block("INVALID_DICTIONARY_DEFINITION", "Every movement dictionary definition must be an object.")
        source_defs = [item for item in definitions if isinstance(item, dict) and str(item.get("movement_id", "")) == source_id]
        target_defs = [item for item in definitions if isinstance(item, dict) and str(item.get("movement_id", "")) == target_id]
        source = source_defs[0] if len(source_defs) == 1 else None
        target = target_defs[0] if len(target_defs) == 1 else None

        if not source_id:
            block("SOURCE_ID_REQUIRED", "source_id cannot be blank.")
        if not target_id:
            block("TARGET_ID_REQUIRED", "target_id cannot be blank.")
        if source_id and source_id == target_id:
            block("SOURCE_EQUALS_TARGET", "source_id and target_id must be different.")
        if len(source_defs) != 1:
            block("SOURCE_NOT_UNIQUE", "Source must exist exactly once in the movement dictionary.", count=len(source_defs))
        if len(target_defs) != 1:
            block("TARGET_NOT_UNIQUE", "Target must exist exactly once in the movement dictionary.", count=len(target_defs))
        invalid_alias_definitions = [
            str(item.get("movement_id", "")) for item in definitions
            if isinstance(item, dict) and not isinstance(item.get("aliases", []), list)
        ]
        if invalid_alias_definitions:
            block(
                "INVALID_DICTIONARY_ALIAS_SHAPE",
                "Every dictionary aliases field must be a list before ownership can be validated.",
                movement_ids=invalid_alias_definitions,
            )
        migration_conflicts = [
            item for item in (self._last_migration_report.get("movement_conflicts") or [])
            if item.get("type") == "duplicate_history_id"
        ]
        if migration_conflicts:
            block(
                "HISTORY_ID_CONFLICT",
                "A legacy history ID is already used by another movement; no merge is safe until it is reviewed.",
                conflicts=migration_conflicts,
            )
        if require_custom_source and source and not re.fullmatch(r"CUSTOM_\d+", source_id):
            block("SOURCE_NOT_CUSTOM", "Source is not a structurally valid CUSTOM dictionary identity.")
        if target and re.fullmatch(r"CUSTOM_\d+", target_id):
            block("TARGET_IS_CUSTOM", "Target must be an existing non-CUSTOM canonical movement.")
        if target and (
            not str(target.get("display_name", "")).strip()
            or target.get("active", True) is False
            or bool(target.get("deleted") or target.get("invalid") or target.get("temporary"))
        ):
            block("TARGET_UNAVAILABLE", "Target is inactive, invalid, temporary, deleted, or missing its display name.")

        movements = database.get("movements", {})
        if not isinstance(movements, dict):
            movements = {}
            block("INVALID_TRACKER_SHAPE", "tracker.movements must be an object.")
        elif any(not isinstance(row, dict) for row in movements.values()):
            block("INVALID_TRACKER_MOVEMENT", "Every tracker movement row must be an object.")
        raw_entries_value = database.get("raw_entries", [])
        if not isinstance(raw_entries_value, list) or any(not isinstance(row, dict) for row in raw_entries_value):
            block("INVALID_RAW_ENTRIES_SHAPE", "tracker.raw_entries must be a list of objects.")
        if source_id in movements and str((movements[source_id] or {}).get("movement_id", "")) != source_id:
            block("SOURCE_INDEX_MISMATCH", "The source tracker index points to a different movement identity.")
        if target_id in movements and str((movements[target_id] or {}).get("movement_id", "")) != target_id:
            block("TARGET_INDEX_MISMATCH", "The target tracker index points to a different movement identity.")
        source_rows = [(key, row) for key, row in movements.items() if isinstance(row, dict) and str(row.get("movement_id", "")) == source_id]
        target_rows = [(key, row) for key, row in movements.items() if isinstance(row, dict) and str(row.get("movement_id", "")) == target_id]
        if len(target_rows) > 1:
            block("TARGET_TRACKER_NOT_UNIQUE", "Target has multiple tracker movement rows.", count=len(target_rows))
        for key, row in source_rows:
            unknown_fields = sorted(
                set(row) - {"movement_id", "name", "aliases", "history", "created_at", "projection"}
            )
            if unknown_fields:
                block(
                    "SOURCE_ROW_UNKNOWN_FIELDS",
                    "The source tracker row contains fields that cannot be safely migrated.",
                    path=f"tracker.movements.{key}",
                    fields=unknown_fields,
                )
            if not isinstance(row.get("aliases", []), list):
                block(
                    "SOURCE_ALIAS_INVALID_SHAPE",
                    "The source tracker aliases field must be a list.",
                    path=f"tracker.movements.{key}.aliases",
                )
        for key, row in target_rows:
            if not isinstance(row.get("aliases", []), list):
                block(
                    "TARGET_ALIAS_INVALID_SHAPE",
                    "The target tracker aliases field must be a list.",
                    path=f"tracker.movements.{key}.aliases",
                )

        references = self._source_reference_paths(database, dictionary, source_id) if source_id else {
            "migratable": [], "unknown": [], "raw_occurrences": [],
        }
        for item in references["unknown"]:
            block("UNKNOWN_SOURCE_REFERENCE", "An unsupported source_id reference path was found.", **item)

        source_history_records = [copy.deepcopy(item) for item in movement_items(database, source_id)]
        target_history_records = [copy.deepcopy(item) for item in movement_items(database, target_id)]
        all_histories = [
            (str(session.get("id", "")), index, item)
            for session in database.get("training_sessions", []) or []
            for index, item in enumerate(session.get("movement_items", []) or [])
            if isinstance(item, dict)
        ]

        id_locations: dict[str, list[str]] = {}
        for key, index, history in all_histories:
            history_id = str(history.get("id", "")).strip()
            if history_id:
                id_locations.setdefault(history_id, []).append(f"tracker.training_sessions[{key}].movement_items[{index}]")
        history_id_conflicts = []
        for history in source_history_records:
            history_id = str(history.get("id", "")).strip()
            if not history_id:
                history_id_conflicts.append({"history_id": "", "reason": "missing_id"})
            elif len(id_locations.get(history_id, [])) > 1:
                history_id_conflicts.append({
                    "history_id": history_id,
                    "reason": "duplicate_id",
                    "paths": id_locations[history_id],
                })
        if history_id_conflicts:
            block(
                "HISTORY_ID_CONFLICT",
                "Source history IDs are missing or already occupied by another record.",
                conflicts=history_id_conflicts,
            )

        exact_duplicates = []
        combined_histories = [
            *(('target', row) for row in target_history_records),
            *(('source', row) for row in source_history_records),
        ]
        combined_signatures = [
            (origin, row, self._history_business_fingerprint(row))
            for origin, row in combined_histories
        ]
        for left_index, (left_origin, left_row, signature) in enumerate(combined_signatures):
            for right_origin, right_row, right_signature in combined_signatures[left_index + 1:]:
                if "source" not in {left_origin, right_origin} or signature != right_signature:
                    continue
                exact_duplicates.append({
                    "left_history_id": str(left_row.get("id", "")),
                    "right_history_id": str(right_row.get("id", "")),
                    "origins": [left_origin, right_origin],
                    "date": str(left_row.get("date", ""))[:10],
                })
        source_dates = {str(row.get("date", ""))[:10] for row in source_history_records if str(row.get("date", ""))[:10]}
        combined_date_counts: dict[str, int] = {}
        for _origin, row in combined_histories:
            day = str(row.get("date", ""))[:10]
            if day:
                combined_date_counts[day] = combined_date_counts.get(day, 0) + 1
        same_dates = sorted(day for day in source_dates if combined_date_counts.get(day, 0) > 1)
        source_days = {(str(row.get("date", ""))[:10], str(row.get("training_day", ""))) for row in source_history_records}
        combined_day_counts: dict[tuple[str, str], int] = {}
        for _origin, row in combined_histories:
            key = (str(row.get("date", ""))[:10], str(row.get("training_day", "")))
            combined_day_counts[key] = combined_day_counts.get(key, 0) + 1
        same_training_days = [
            {"date": day, "training_day": training_day}
            for day, training_day in sorted(source_days)
            if combined_day_counts.get((day, training_day), 0) > 1
        ]
        if exact_duplicates:
            warn("POTENTIAL_EXACT_DUPLICATES", "Potential duplicate histories will be preserved, not deduplicated.", count=len(exact_duplicates))
        if same_dates:
            warn("SAME_DATE_HISTORY", "Source and target both have history on one or more dates; all rows will be preserved.", dates=same_dates)
        if same_training_days:
            warn("SAME_TRAINING_DAY_HISTORY", "Source and target both appear in the same training-day identity.", days=same_training_days)

        source_names = []
        if source:
            source_aliases = source.get("aliases", []) if isinstance(source.get("aliases", []), list) else []
            source_names.extend([source.get("display_name", ""), source.get("english_name", ""), *source_aliases])
        for _key, row in source_rows:
            row_aliases = row.get("aliases", []) if isinstance(row.get("aliases", []), list) else []
            source_names.extend([row.get("name", ""), *row_aliases])
        target_names = []
        if target:
            target_aliases = target.get("aliases", []) if isinstance(target.get("aliases", []), list) else []
            target_names.extend([target.get("display_name", ""), target.get("english_name", ""), *target_aliases])
        target_keys = {_normalize_name(value) for value in target_names if _normalize_name(value)}
        candidate_keys: set[str] = set()
        aliases_to_add: list[str] = []
        aliases_existing: list[str] = []
        normalized_duplicates: list[str] = []
        alias_conflicts: list[dict] = []
        ownership: dict[str, list[dict]] = {}
        for definition in definitions:
            if not isinstance(definition, dict):
                continue
            definition_aliases = definition.get("aliases", []) if isinstance(definition.get("aliases", []), list) else []
            for candidate in (definition.get("display_name", ""), definition.get("english_name", ""), *definition_aliases):
                normalized = _normalize_name(candidate)
                if normalized:
                    ownership.setdefault(normalized, []).append(definition)
        for value in source_names:
            alias = str(value or "").strip()
            normalized = _normalize_name(alias)
            if not alias or not normalized:
                continue
            if normalized in target_keys:
                if alias not in aliases_existing:
                    aliases_existing.append(alias)
                continue
            if normalized in candidate_keys:
                normalized_duplicates.append(alias)
                continue
            candidate_keys.add(normalized)
            conflicts = [
                item for item in ownership.get(normalized, [])
                if str(item.get("movement_id", "")) not in {source_id, target_id}
            ]
            if conflicts:
                alias_conflicts.append({
                    "alias": alias,
                    "normalized": normalized,
                    "owners": [
                        {"movement_id": item.get("movement_id", ""), "display_name": item.get("display_name", "")}
                        for item in conflicts
                    ],
                })
            else:
                aliases_to_add.append(alias)
        if alias_conflicts:
            block("ALIAS_OWNERSHIP_CONFLICT", "One or more source names belong to another formal movement.", conflicts=alias_conflicts)

        raw_entries = database.get("raw_entries", []) or []
        raw_texts = [str(item.get("text", "")) for item in raw_entries if isinstance(item, dict)]
        source_name_keys = {_normalize_name(value) for value in source_names if _normalize_name(value)}
        skipped_matches = []
        for index, raw_entry in enumerate(raw_entries):
            if not isinstance(raw_entry, dict):
                continue
            matches = [
                str(name) for name in (raw_entry.get("skipped_movements") or [])
                if _normalize_name(name) in source_name_keys
            ]
            if matches:
                skipped_matches.append({
                    "raw_entry_id": str(raw_entry.get("id", "")),
                    "index": index,
                    "date": str(raw_entry.get("date", ""))[:10],
                    "names": matches,
                })
        if skipped_matches:
            warn(
                "SKIPPED_SOURCE_NAMES_PRESERVED",
                "Skipped movement names are name-based audit metadata; they will remain unchanged and become target-recognizable through aliases.",
                count=len(skipped_matches),
            )

        target_summary = self._definition_summary(target, target_id)
        target_summary["canonical_metadata_sha256"] = _stable_json_hash({
            key: value for key, value in (target or {}).items() if key != "aliases"
        })
        expected_target_history = [copy.deepcopy(row) for row in target_history_records]
        target_display_name = target.get("display_name", "") if target else ""
        expected_target_history.extend(
            [{**copy.deepcopy(row), "movement_id": target_id, "display_name": target_display_name} for row in source_history_records]
        )
        plan = {
            "operation": (
                "CUSTOM_TO_CANONICAL_MOVEMENT_MERGE"
                if require_custom_source else
                "MOVEMENT_TO_CANONICAL_MOVEMENT_MERGE"
            ),
            "source": self._definition_summary(source, source_id),
            "target": target_summary,
            "references": {
                "migratable": references["migratable"],
                "migratable_count": len(references["migratable"]),
                "unknown": references["unknown"],
                "unknown_count": len(references["unknown"]),
                "non_structured_occurrences": references["raw_occurrences"],
            },
            "history": {
                "source_history_count": len(source_history_records),
                "target_history_count": len(target_history_records),
                "target_history_after": len(source_history_records) + len(target_history_records),
                "source_history_ids": [str(row.get("id", "")) for row in source_history_records],
                "dates": sorted(source_dates),
                "training_days": sorted({str(row.get("training_day", "")) for row in source_history_records}),
                "target_history_after_sha256": _stable_json_hash(expected_target_history),
            },
            "duplicates": {
                "exact_content": exact_duplicates,
                "same_dates": same_dates,
                "same_training_days": same_training_days,
                "history_id_conflicts": history_id_conflicts,
                "policy": "preserve_all_no_automatic_deduplication",
            },
            "aliases": {
                "to_add": aliases_to_add,
                "already_recognized": aliases_existing,
                "normalized_duplicates": normalized_duplicates,
                "ownership_conflicts": alias_conflicts,
                "source_name_candidates": [str(value).strip() for value in source_names if str(value).strip()],
            },
            "raw": {
                "entry_count": len(raw_entries),
                "entries_sha256": _stable_json_hash(raw_entries),
                "text_sha256": _stable_json_hash(raw_texts),
                "text_unchanged": True,
                "skipped_source_matches": skipped_matches,
                "migration_plan": "Preserve raw text and skipped name audit metadata; add source names as target aliases; do not reparse raw input.",
                "preserved_non_structured_occurrences": references["raw_occurrences"],
            },
            "warnings": warnings,
            "blockers": blockers,
            "can_execute": not blockers,
            "data_fingerprint": copy.deepcopy(data_fingerprint),
        }
        plan["plan_identity"] = _stable_json_hash(plan)
        return plan

    def preview_merge_custom_movement(self, source_id: str, target_id: str) -> dict:
        """Build a UI-ready, strictly read-only CUSTOM-to-canonical migration plan."""
        database, dictionary, fingerprint = self._strict_state_snapshot()
        return self._build_movement_merge_plan(
            database,
            dictionary,
            source_id,
            target_id,
            fingerprint,
            require_custom_source=True,
        )

    def preview_merge_movement(self, source_id: str, target_id: str) -> dict:
        """Build a UI-ready plan for merging any existing source into a canonical target."""
        database, dictionary, fingerprint = self._strict_state_snapshot()
        return self._build_movement_merge_plan(database, dictionary, source_id, target_id, fingerprint)

    @staticmethod
    def _append_normalized_aliases(existing, additions) -> list[str]:
        result = [str(value).strip() for value in (existing or []) if str(value).strip()]
        seen = {_normalize_name(value) for value in result if _normalize_name(value)}
        for value in additions or []:
            alias = str(value or "").strip()
            normalized = _normalize_name(alias)
            if alias and normalized and normalized not in seen:
                result.append(alias)
                seen.add(normalized)
        return result

    def _apply_custom_movement_merge(self, database: dict, dictionary: dict, plan: dict) -> None:
        source_id = plan["source"]["movement_id"]
        target_id = plan["target"]["movement_id"]
        target_definition = next(
            item for item in dictionary["movements"] if str(item.get("movement_id", "")) == target_id
        )
        target_definition["aliases"] = self._append_normalized_aliases(
            target_definition.get("aliases", []), plan["aliases"]["to_add"]
        )

        movements = database["movements"]
        target_matches = [row for row in movements.values() if str(row.get("movement_id", "")) == target_id]
        if target_matches:
            target_row = target_matches[0]
        else:
            target_row = {
                "movement_id": target_id,
                "name": target_definition.get("display_name", ""),
                "aliases": [],
                "history": [],
                "created_at": datetime.now().replace(microsecond=0).isoformat(),
            }
            movements[target_id] = target_row

        source_keys = []
        tracker_aliases = list(plan["aliases"]["source_name_candidates"])
        for key, row in list(movements.items()):
            if not isinstance(row, dict):
                continue
            if str(row.get("movement_id", "")) == source_id:
                source_keys.append(key)
                tracker_aliases.extend([row.get("name", ""), *(row.get("aliases") or [])])
        for key in source_keys:
            movements.pop(key, None)
        target_row["aliases"] = self._append_normalized_aliases(target_row.get("aliases", []), tracker_aliases)
        for session in database.get("training_sessions", []) or []:
            for item in session.get("movement_items", []) or []:
                if isinstance(item, dict) and str(item.get("movement_id", "")) == source_id:
                    item["movement_id"] = target_id
                    item["display_name"] = target_definition.get("display_name", item.get("display_name", ""))
        rebuild_movement_projection(database)
        dictionary["movements"] = [
            item for item in dictionary["movements"] if str(item.get("movement_id", "")) != source_id
        ]

    def _validate_custom_movement_merge_state(self, database: dict, dictionary: dict, plan: dict) -> dict:
        source_id = plan["source"]["movement_id"]
        target_id = plan["target"]["movement_id"]
        errors = []
        source_definitions = [item for item in dictionary.get("movements", []) if str(item.get("movement_id", "")) == source_id]
        target_definitions = [item for item in dictionary.get("movements", []) if str(item.get("movement_id", "")) == target_id]
        references = self._source_reference_paths(database, dictionary, source_id)
        remaining = [*references["migratable"], *references["unknown"]]
        target_rows = [
            row for row in database.get("movements", {}).values()
            if isinstance(row, dict) and str(row.get("movement_id", "")) == target_id
        ]
        target_history = movement_items(database, target_id)
        target_history_count = len(target_history)
        raw_entries = database.get("raw_entries", []) or []
        raw_texts = [str(item.get("text", "")) for item in raw_entries if isinstance(item, dict)]
        if source_definitions:
            errors.append("source_dictionary_definition_remains")
        if len(target_definitions) != 1:
            errors.append("target_dictionary_definition_not_unique")
        if remaining:
            errors.append("source_structured_references_remain")
        if len(target_rows) != 1:
            errors.append("target_tracker_row_not_unique")
        if target_history_count != plan["history"]["target_history_after"]:
            errors.append("target_history_count_mismatch")
        if _stable_json_hash(target_history) != plan["history"]["target_history_after_sha256"]:
            errors.append("target_history_integrity_mismatch")
        if _stable_json_hash(raw_entries) != plan["raw"]["entries_sha256"]:
            errors.append("raw_entries_changed")
        if _stable_json_hash(raw_texts) != plan["raw"]["text_sha256"]:
            errors.append("raw_text_changed")
        if len(target_definitions) == 1 and _stable_json_hash({
            key: value for key, value in target_definitions[0].items() if key != "aliases"
        }) != plan["target"]["canonical_metadata_sha256"]:
            errors.append("target_canonical_metadata_changed")
        by_id, by_alias = _dictionary_indexes(dictionary)
        for alias in plan["aliases"]["to_add"]:
            owner = by_alias.get(_normalize_name(alias))
            if not owner or str(owner.get("movement_id", "")) != target_id:
                errors.append(f"alias_not_owned_by_target:{alias}")
        validation = {
            "ok": not errors,
            "errors": errors,
            "source_definition_absent": not source_definitions,
            "target_definition_present": len(target_definitions) == 1,
            "remaining_source_references": remaining,
            "target_history_count": target_history_count,
            "history_business_data_preserved": "target_history_integrity_mismatch" not in errors,
            "target_canonical_metadata_preserved": "target_canonical_metadata_changed" not in errors,
            "raw_entries_unchanged": _stable_json_hash(raw_entries) == plan["raw"]["entries_sha256"],
            "raw_text_unchanged": _stable_json_hash(raw_texts) == plan["raw"]["text_sha256"],
            "aliases_resolve_to_target": not any(item.startswith("alias_not_owned_by_target:") for item in errors),
        }
        return validation

    def _post_write_custom_movement_validation(self, plan: dict) -> tuple[dict, dict]:
        database, dictionary, fingerprint = self._strict_state_snapshot()
        validation = self._validate_custom_movement_merge_state(database, dictionary, plan)
        validation["data_fingerprint"] = fingerprint
        return validation, fingerprint

    def _merge_movement(
        self,
        source_id: str,
        target_id: str,
        plan_identity: str,
        require_custom_source: bool,
        post_write_validation,
    ) -> dict:
        """Execute one confirmed, fresh movement merge as a paired transaction."""
        if not str(plan_identity or "").strip():
            raise LedgerCommandError(
                "A confirmed preview plan identity is required.",
                "PREVIEW_REQUIRED",
            )
        with self.write_lock():
            database, dictionary, fingerprint = self._strict_state_snapshot()
            plan = self._build_movement_merge_plan(
                database,
                dictionary,
                source_id,
                target_id,
                fingerprint,
                require_custom_source=require_custom_source,
            )
            if plan["plan_identity"] != str(plan_identity):
                raise LedgerCommandError(
                    "The preview is stale; run dry-run again before migrating.",
                    "PREVIEW_STALE",
                    {
                        "expected_plan_identity": str(plan_identity),
                        "current_plan_identity": plan["plan_identity"],
                        "data_fingerprint": fingerprint,
                    },
                )
            if not plan["can_execute"]:
                raise LedgerCommandError(
                    "The migration plan contains blocking issues; no data was changed.",
                    "MIGRATION_BLOCKED",
                    {"blockers": plan["blockers"], "plan_identity": plan["plan_identity"]},
                )

            tracker_backup, dictionary_backup = self._checkpoint()
            checkpoint = self._checkpoint_identity(tracker_backup)
            checkpoint_hashes = {
                "tracker": hashlib.sha256(tracker_backup.read_bytes()).hexdigest(),
                "dictionary": hashlib.sha256(dictionary_backup.read_bytes()).hexdigest(),
            }
            if any(
                checkpoint_hashes[label] != fingerprint[label]["sha256"]
                for label in ("tracker", "dictionary")
            ):
                self._discard_checkpoint(tracker_backup, dictionary_backup)
                raise LedgerCommandError(
                    "Formal data changed before the checkpoint completed; run dry-run again.",
                    "PREVIEW_STALE",
                    {"data_fingerprint": fingerprint},
                )
            stage = "checkpoint_created"
            rolled_back = False
            begin_pair_transaction(
                self.pair_transaction_file,
                self.data_file,
                self.dictionary_file,
                tracker_backup,
                dictionary_backup,
            )
            try:
                working_database = copy.deepcopy(database)
                working_dictionary = copy.deepcopy(dictionary)
                self._apply_custom_movement_merge(working_database, working_dictionary, plan)
                stage = "in_memory_validation"
                validation = self._validate_custom_movement_merge_state(
                    working_database, working_dictionary, plan
                )
                if not validation["ok"]:
                    raise LedgerCommandError(
                        "In-memory migration validation failed.",
                        "MIGRATION_VALIDATION_FAILED",
                        validation,
                    )
                stage = "dictionary_write"
                _write_json_atomic(self.dictionary_file, working_dictionary)
                stage = "tracker_write"
                _write_json_atomic(self.data_file, working_database)
                stage = "post_write_validation"
                validation, after_fingerprint = post_write_validation(plan)
                if not validation["ok"]:
                    raise LedgerCommandError(
                        "Post-write migration validation failed.",
                        "MIGRATION_VALIDATION_FAILED",
                        validation,
                    )
                commit_pair_transaction(self.pair_transaction_file)
            except Exception as exc:
                rollback_errors = []
                for backup, destination, label in (
                    (tracker_backup, self.data_file, "tracker"),
                    (dictionary_backup, self.dictionary_file, "dictionary"),
                ):
                    try:
                        shutil.copy2(backup, destination)
                    except Exception as rollback_exc:
                        rollback_errors.append(f"{label}: {rollback_exc}")
                rolled_back = not rollback_errors
                if rolled_back:
                    self._discard_checkpoint(tracker_backup, dictionary_backup)
                    self.pair_transaction_file.unlink(missing_ok=True)
                details = {
                    "failed_stage": stage,
                    "rolled_back": rolled_back,
                    "checkpoint": checkpoint,
                    "rollback_errors": rollback_errors,
                    "cause_code": getattr(exc, "code", exc.__class__.__name__),
                    "cause": str(exc),
                }
                if isinstance(exc, LedgerCommandError):
                    details["cause_details"] = exc.details
                raise LedgerCommandError(
                    "Movement migration failed; both formal files were restored."
                    if rolled_back else
                    "Movement migration failed and paired rollback needs manual review.",
                    "MIGRATION_FAILED",
                    details,
                ) from exc

            return {
                "ok": True,
                "status": "UPDATED",
                "changed": True,
                "source_id": plan["source"]["movement_id"],
                "target_id": plan["target"]["movement_id"],
                "plan_identity": plan["plan_identity"],
                "migrated_reference_count": plan["references"]["migratable_count"],
                "migrated_history_count": plan["history"]["source_history_count"],
                "source_history_before": plan["history"]["source_history_count"],
                "target_history_before": plan["history"]["target_history_count"],
                "target_history_after": plan["history"]["target_history_after"],
                "aliases_added": plan["aliases"]["to_add"],
                "warnings": plan["warnings"],
                "checkpoint": checkpoint,
                "undo": {"available": True, "checkpoint": checkpoint},
                "validation": validation,
                "remaining_source_references": validation["remaining_source_references"],
                "raw_entries_unchanged": validation["raw_entries_unchanged"],
                "data_fingerprint": after_fingerprint,
            }

    def merge_custom_movement(self, source_id: str, target_id: str, plan_identity: str) -> dict:
        """Compatibility wrapper for the original CUSTOM-to-canonical command."""
        return self._merge_movement(
            source_id,
            target_id,
            plan_identity,
            require_custom_source=True,
            post_write_validation=self._post_write_custom_movement_validation,
        )

    def merge_movement(self, source_id: str, target_id: str, plan_identity: str) -> dict:
        """Merge any existing source movement into an existing canonical target."""
        return self._merge_movement(
            source_id,
            target_id,
            plan_identity,
            require_custom_source=False,
            post_write_validation=self._post_write_custom_movement_validation,
        )

    def movement_groups(self) -> list[str]:
        """Return the body-part values already established by formal movements."""
        _database, dictionary = self.load_state()
        return _existing_muscle_groups(dictionary)

    def training_organization(self) -> dict:
        """Return editable Session Theme metadata without changing training facts."""
        database, dictionary = self.load_state()
        return organization_catalog(database, dictionary)

    def _apply_session_theme_update(self, database: dict, values: dict) -> tuple[dict, bool]:
        """Apply one Theme edit to an in-memory database without writing it."""
        if not isinstance(values, dict):
            raise LedgerCommandError("Session Theme values must be an object.", "THEME_VALUES_INVALID")
        display_name = str(values.get("display_name", "")).strip()
        if not display_name:
            raise LedgerCommandError("Session Theme name cannot be blank.", "THEME_NAME_REQUIRED")
        themes = database["training_organization"]["session_themes"]
        theme_id = str(values.get("theme_id", "")).strip()
        theme = next((item for item in themes if str(item.get("theme_id")) == theme_id), None)
        duplicate = next((item for item in themes if item is not theme and normalize_label(item.get("display_name")) == normalize_label(display_name)), None)
        if duplicate is not None:
            raise LedgerCommandError("A Session Theme with this name already exists.", "THEME_NAME_CONFLICT", {"theme_id": duplicate.get("theme_id")})
        was_pinned = bool(theme.get("pinned", False)) if theme else False
        previous_rank = int(theme.get("focus_rank", 0) or 0) if theme else 0
        changed = False
        if theme is None:
            base = f"theme:{normalize_label(display_name) or 'custom'}"
            theme_id = base
            used = {str(item.get("theme_id")) for item in themes}
            suffix = 2
            while theme_id in used:
                theme_id = f"{base}:{suffix}"
                suffix += 1
            theme = {
                "theme_id": theme_id,
                "display_name": display_name,
                "active": bool(values.get("active", True)),
                "sort_order": int(values.get("sort_order", max((int(item.get("sort_order", 0) or 0) for item in themes), default=0) + 10)),
                "pinned": bool(values.get("pinned", False)),
                "focus_rank": 0,
                "artwork_key": "",
                "color_key": next(
                    (candidate for candidate in THEME_COLOR_KEYS if candidate not in {str(item.get("color_key", "")).strip() for item in themes}),
                    theme_color_key(theme_id),
                ),
                "system": False,
            }
            themes.append(theme)
            changed = True
        else:
            old_name = str(theme.get("display_name") or "").strip()
            if old_name != display_name:
                aliases = [str(item).strip() for item in theme.get("aliases", []) or [] if str(item).strip()]
                if old_name and normalize_label(old_name) not in {normalize_label(item) for item in aliases}:
                    aliases.append(old_name)
                theme["aliases"] = aliases
                theme["display_name"] = display_name
                changed = True
                for session in database.get("training_sessions", []) or []:
                    memberships = session.get("session_theme_ids")
                    if isinstance(memberships, list):
                        belongs = theme_id in {str(item) for item in memberships}
                    else:
                        belongs = str(session.get("session_theme_id", "")) == theme_id
                    if belongs and str(session.get("session_theme_name") or "").strip() in {"", old_name}:
                        session["session_theme_name"] = display_name
            for key in ("active", "pinned"):
                if key in values:
                    next_value = bool(values[key])
                    if bool(theme.get(key, False if key == "pinned" else True)) != next_value:
                        theme[key] = next_value
                        changed = True
            if values.get("sort_order") is not None:
                next_order = int(values["sort_order"])
                if int(theme.get("sort_order", 0) or 0) != next_order:
                    theme["sort_order"] = next_order
                    changed = True
        theme.setdefault("color_key", theme_color_key(theme_id))
        theme["artwork_key"] = ""
        if theme.get("pinned") and not was_pinned:
            for other in themes:
                if other is not theme and other.get("pinned"):
                    other["focus_rank"] = max(1, int(other.get("focus_rank", 0) or 0)) + 1
            theme["focus_rank"] = 1
            changed = True
        elif not theme.get("pinned"):
            theme["focus_rank"] = 0
            if was_pinned and previous_rank:
                for other in themes:
                    if other is not theme and other.get("pinned") and int(other.get("focus_rank", 0) or 0) > previous_rank:
                        other["focus_rank"] -= 1
                changed = True
        elif int(theme.get("focus_rank", 0) or 0) <= 0:
            theme["focus_rank"] = 1
            changed = True
        return copy.deepcopy(theme), changed

    def update_session_theme(self, values: dict) -> dict:
        """Create, rename, pin, or otherwise update a Session Theme."""
        with self.write_lock():
            database, dictionary = self.load_state()
            theme, changed = self._apply_session_theme_update(database, values)
            if not changed:
                return {"status": "NO_CHANGES", "theme": theme, "organization": organization_catalog(database, dictionary)}
            tracker_backup, dictionary_backup = self._checkpoint()
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"status": "UPDATED", "theme": theme, "organization": organization_catalog(database, dictionary)}

    def update_session_themes(self, values: list[dict]) -> dict:
        """Atomically apply a complete Theme manager form in one write."""
        if not isinstance(values, list):
            raise LedgerCommandError("Session Theme updates must be a list.", "THEME_BATCH_INVALID")
        with self.write_lock():
            database, dictionary = self.load_state()
            changed = False
            updated = []
            for item in values:
                theme, item_changed = self._apply_session_theme_update(database, item)
                updated.append(theme)
                changed = changed or item_changed
            if not changed:
                return {"status": "NO_CHANGES", "themes": updated, "organization": organization_catalog(database, dictionary)}
            tracker_backup, dictionary_backup = self._checkpoint()
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"status": "UPDATED", "themes": updated, "organization": organization_catalog(database, dictionary)}

    def set_session_theme_active(self, theme_id: str, active: bool) -> dict:
        theme_id = str(theme_id or "").strip()
        with self.write_lock():
            database, dictionary = self.load_state()
            theme = next((item for item in database["training_organization"]["session_themes"] if str(item.get("theme_id")) == theme_id), None)
            if theme is None:
                raise LedgerCommandError("Session Theme was not found.", "THEME_NOT_FOUND")
            active = bool(active)
            if bool(theme.get("active", True)) == active:
                return {"status": "NO_CHANGES", "theme": copy.deepcopy(theme), "organization": organization_catalog(database, dictionary)}
            theme["active"] = active
            tracker_backup, dictionary_backup = self._checkpoint()
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"status": "UPDATED", "theme": copy.deepcopy(theme), "organization": organization_catalog(database, dictionary)}

    def promote_custom_movement(self, source_id: str, values: dict) -> dict:
        """Turn one CUSTOM definition into a new independent canonical movement."""
        source_id = str(source_id or "").strip()
        if not re.fullmatch(r"CUSTOM_\d+", source_id):
            raise LedgerCommandError("只有 CUSTOM 动作可以独立转正。", "SOURCE_NOT_CUSTOM")
        with self.write_lock():
            database, dictionary, fingerprint = self._strict_state_snapshot()
            definitions = [
                item for item in dictionary.get("movements", []) or []
                if isinstance(item, dict) and str(item.get("movement_id", "")) == source_id
            ]
            if len(definitions) != 1:
                raise LedgerCommandError("CUSTOM 动作不存在或身份不唯一。", "SOURCE_NOT_UNIQUE")
            source = definitions[0]
            muscle_group = str(values.get("muscle_group", source.get("muscle_group", ""))).strip()
            if muscle_group not in _existing_muscle_groups(dictionary):
                raise LedgerCommandError("训练部位必须从现有部位中选择。", "INVALID_MUSCLE_GROUP")
            display_name = str(values.get("display_name", source.get("display_name", ""))).strip()
            if not display_name:
                raise LedgerCommandError("中文标准名不能为空。")
            aliases = self._clean_aliases(
                values.get("aliases", source.get("aliases", [])),
                display_name,
                str(source.get("display_name", "")).strip(),
            )
            self._validate_definition_conflicts(dictionary, source_id, aliases)
            references = self._source_reference_paths(database, dictionary, source_id)
            if references["unknown"]:
                raise LedgerCommandError(
                    "发现无法安全迁移的 CUSTOM 引用；未修改数据。",
                    "PROMOTION_BLOCKED",
                    {"references": references["unknown"]},
                )
            target_id = _next_canonical_id(dictionary, muscle_group)
            occupied_tracker_ids = {
                str(row.get("movement_id", ""))
                for row in database.get("movements", {}).values()
                if isinstance(row, dict)
            } | {str(key) for key in database.get("movements", {})}
            prefix, number = target_id.rsplit("_", 1)
            while target_id in occupied_tracker_ids:
                target_id = f"{prefix}_{int(number) + 1:03d}"
                number = target_id.rsplit("_", 1)[1]
            before_raw = _stable_json_hash(database.get("raw_entries", []) or [])
            before_history = [copy.deepcopy(item) for item in movement_items(database, source_id)]
            tracker_backup, dictionary_backup = self._checkpoint()
            checkpoint = self._checkpoint_identity(tracker_backup)
            checkpoint_hashes = {
                "tracker": hashlib.sha256(tracker_backup.read_bytes()).hexdigest(),
                "dictionary": hashlib.sha256(dictionary_backup.read_bytes()).hexdigest(),
            }
            if any(checkpoint_hashes[label] != fingerprint[label]["sha256"] for label in ("tracker", "dictionary")):
                self._discard_checkpoint(tracker_backup, dictionary_backup)
                raise LedgerCommandError("数据在转正前发生变化，请重试。", "PROMOTION_STALE")
            try:
                working_database = copy.deepcopy(database)
                working_dictionary = copy.deepcopy(dictionary)
                definition = next(
                    item for item in working_dictionary["movements"]
                    if str(item.get("movement_id", "")) == source_id
                )
                definition.update({
                    "movement_id": target_id,
                    "display_name": display_name,
                    "english_name": str(values.get("english_name", definition.get("english_name", ""))).strip(),
                    "aliases": aliases,
                    "muscle_group": muscle_group,
                    "category": str(values.get("category", definition.get("category", "Strength"))).strip() or "Strength",
                    "equipment": str(values.get("equipment", definition.get("equipment", ""))).strip(),
                    "notes": str(values.get("notes", definition.get("notes", ""))).strip(),
                    "pinned": bool(values.get("pinned", definition.get("pinned", False))) or max(0, int(values.get("focus_rank", definition.get("focus_rank", 0)) or 0)) > 0,
                    "focus_rank": max(0, int(values.get("focus_rank", definition.get("focus_rank", 0)) or 0)),
                })
                movements = working_database.get("movements", {})
                source_rows = [
                    (key, row) for key, row in movements.items()
                    if isinstance(row, dict) and str(row.get("movement_id", "")) == source_id
                ]
                if len(source_rows) > 1:
                    raise LedgerCommandError("CUSTOM 成长记录身份不唯一；未修改数据。", "PROMOTION_BLOCKED")
                for row in movements.values():
                    if not isinstance(row, dict):
                        continue
                    if str(row.get("movement_id", "")) == source_id:
                        row["movement_id"] = target_id
                        row["name"] = display_name
                if source_rows:
                    source_key = source_rows[0][0]
                    movements[target_id] = movements.pop(source_key)

                for session in working_database.get("training_sessions", []) or []:
                    for item in session.get("movement_items", []) or []:
                        if isinstance(item, dict) and str(item.get("movement_id", "")) == source_id:
                            item["movement_id"] = target_id
                            item["display_name"] = display_name
                rebuild_movement_projection(working_database)
                remaining = self._source_reference_paths(working_database, working_dictionary, source_id)
                promoted_history = [copy.deepcopy(item) for item in movement_items(working_database, target_id)]
                if remaining["migratable"] or remaining["unknown"]:
                    raise LedgerCommandError("CUSTOM 引用迁移不完整。", "PROMOTION_VALIDATION_FAILED")
                if [self._history_business_fingerprint(item) for item in promoted_history] != [
                    self._history_business_fingerprint(item) for item in before_history
                ]:
                    raise LedgerCommandError("动作历史在转正时发生了非身份变化。", "PROMOTION_VALIDATION_FAILED")
                if _stable_json_hash(working_database.get("raw_entries", []) or []) != before_raw:
                    raise LedgerCommandError("原始录入在转正时发生变化。", "PROMOTION_VALIDATION_FAILED")
                begin_pair_transaction(
                    self.pair_transaction_file,
                    self.data_file,
                    self.dictionary_file,
                    tracker_backup,
                    dictionary_backup,
                )
                _write_json_atomic(self.dictionary_file, working_dictionary)
                _write_json_atomic(self.data_file, working_database)
                after_database, after_dictionary, after_fingerprint = self._strict_state_snapshot()
                after_remaining = self._source_reference_paths(after_database, after_dictionary, source_id)
                if after_remaining["migratable"] or after_remaining["unknown"]:
                    raise LedgerCommandError("写入后的 CUSTOM 引用验证失败。", "PROMOTION_VALIDATION_FAILED")
                if _stable_json_hash(after_database.get("raw_entries", []) or []) != before_raw:
                    raise LedgerCommandError("写入后的原始录入验证失败。", "PROMOTION_VALIDATION_FAILED")
                after_history = [copy.deepcopy(item) for item in movement_items(after_database, target_id)]
                if [self._history_business_fingerprint(item) for item in after_history] != [
                    self._history_business_fingerprint(item) for item in before_history
                ]:
                    raise LedgerCommandError("写入后的成长记录验证失败。", "PROMOTION_VALIDATION_FAILED")
                commit_pair_transaction(self.pair_transaction_file)
            except Exception as exc:
                rollback_errors = []
                for backup, destination, label in (
                    (tracker_backup, self.data_file, "tracker"),
                    (dictionary_backup, self.dictionary_file, "dictionary"),
                ):
                    try:
                        shutil.copy2(backup, destination)
                    except Exception as rollback_exc:
                        rollback_errors.append(f"{label}: {rollback_exc}")
                if not rollback_errors:
                    self._discard_checkpoint(tracker_backup, dictionary_backup)
                    self.pair_transaction_file.unlink(missing_ok=True)
                raise LedgerCommandError(
                    "动作转正失败，数据已恢复。" if not rollback_errors else "动作转正失败，回滚需要人工检查。",
                    "PROMOTION_FAILED",
                    {"rollback_errors": rollback_errors, "cause": str(exc), "data_fingerprint": fingerprint},
                ) from exc
            return {
                "ok": True,
                "source_id": source_id,
                "target_id": target_id,
                "display_name": display_name,
                "muscle_group": muscle_group,
                "migrated_history_count": len(before_history),
                "migrated_reference_count": len(references["migratable"]),
                "raw_entries_unchanged": True,
                "checkpoint": checkpoint,
                "undo": {"available": True, "checkpoint": checkpoint},
                "data_fingerprint": after_fingerprint,
            }

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
        existing = {self._history_fingerprint(row) for row in movement_items(database, movement_id)}
        custom_ids = set()
        for key, source in list(database.get("movements", {}).items()):
            source_id = str(source.get("movement_id", ""))
            if source is target or (source_id and not source_id.startswith("CUSTOM_")):
                continue
            names = [source.get("name", ""), *(source.get("aliases") or [])]
            if not any(_normalize_name(name) in alias_keys for name in names if str(name).strip()):
                continue
            for session in database.get("training_sessions", []) or []:
                for item in session.get("movement_items", []) or []:
                    if not isinstance(item, dict) or str(item.get("movement_id", "")) != source_id:
                        continue
                    fingerprint = self._history_fingerprint(item)
                    if fingerprint in existing:
                        continue
                    item["movement_id"] = movement_id
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
                    "id": str(uuid.uuid4()), "movement_id": movement_id, "display_name": definition.get("display_name", candidate_key), "date": entry_date,
                    "training_day": int(session.get("No.") or 0), "order": movement_data.get("order"),
                    "sets": movement_data.get("sets") or [],
                    "raw": movement_data.get("raw", ""), "notes": movement_data.get("notes", ""),
                    "source": "alias reconciliation",
                    "record_day_id": record_day_id(entry_date), "training_session_id": session.get("id", ""),
                }
                history["movement_instance_id"] = history["id"]
                fingerprint = self._history_fingerprint(history)
                if fingerprint not in existing:
                    session.setdefault("movement_items", []).append(history)
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
        rebuild_movement_projection(database)
        return result

    def _write_pair(self, database: dict, dictionary: dict, tracker_backup: Path, dictionary_backup: Path) -> None:
        begin_pair_transaction(
            self.pair_transaction_file,
            self.data_file,
            self.dictionary_file,
            tracker_backup,
            dictionary_backup,
        )
        try:
            self._validate_relations_or_raise(database, dictionary)
            _write_json_atomic(self.dictionary_file, dictionary)
            _write_json_atomic(self.data_file, database)
            commit_pair_transaction(self.pair_transaction_file)
        except Exception as exc:
            rollback_errors = []
            for backup, destination in ((dictionary_backup, self.dictionary_file), (tracker_backup, self.data_file)):
                try:
                    shutil.copy2(backup, destination)
                except Exception as rollback_exc:
                    rollback_errors.append(str(rollback_exc))
            if not rollback_errors:
                self._discard_checkpoint(tracker_backup, dictionary_backup)
                self.pair_transaction_file.unlink(missing_ok=True)
            raise LedgerCommandError(
                "Paired write failed; both formal files were restored."
                if not rollback_errors
                else "Paired write failed and rollback needs manual review.",
                "SAVE_FAILED",
                {"rolled_back": not rollback_errors, "rollback_errors": rollback_errors, "cause": str(exc)},
            ) from exc

    def create_movement_definition(self, values: dict) -> dict:
        with self.write_lock():
            database, dictionary = self.load_state()
            display_name = str(values.get("display_name", "")).strip()
            if not display_name:
                raise LedgerCommandError("Display name cannot be blank.")
            aliases = self._clean_aliases(values.get("aliases", []), display_name)
            self._validate_definition_conflicts(dictionary, "", aliases)
            tracker_backup, dictionary_backup = self._checkpoint()
            definition = _new_definition(
                display_name,
                display_name,
                dictionary,
                str(values.get("muscle_group", "Unclassified")).strip() or "Unclassified",
            )
            definition.update({
                "english_name": str(values.get("english_name", "")).strip(),
                "aliases": aliases,
                "muscle_group": str(values.get("muscle_group", "Unclassified")).strip() or "Unclassified",
                "category": str(values.get("category", "Strength")).strip() or "Strength",
                "equipment": str(values.get("equipment", "")).strip(),
                "notes": str(values.get("notes", "")).strip(),
                "active": bool(values.get("active", True)),
                "pinned": bool(values.get("pinned", False)) or max(0, int(values.get("focus_rank", 0) or 0)) > 0,
                "focus_rank": max(0, int(values.get("focus_rank", 0) or 0)),
                "revision": 1,
                "updated_at": now_iso(),
            })
            reconciliation = self._reconcile_definition(database, dictionary, definition)
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"definition": copy.deepcopy(definition), "reconciliation": reconciliation}

    def update_movement_definition(self, movement_id: str, values: dict, *, expected_revision: int | None = None) -> dict:
        with self.write_lock():
            database, dictionary = self.load_state()
            definition = self._definition_by_id(dictionary, movement_id)
            current_revision = int(definition.get("revision", 1) or 1)
            if expected_revision is not None and int(expected_revision) != current_revision:
                raise LedgerCommandError(
                    "This movement definition changed after the page was opened. Reload it before saving.",
                    "REVISION_CONFLICT",
                    {"expected_revision": expected_revision, "current_revision": current_revision, "definition": copy.deepcopy(definition)},
                )
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
                "pinned": bool(values.get("pinned", definition.get("pinned", False))) or max(0, int(values.get("focus_rank", definition.get("focus_rank", 0)) or 0)) > 0,
                "focus_rank": max(0, int(values.get("focus_rank", definition.get("focus_rank", 0)) or 0)),
                "revision": current_revision + 1,
                "updated_at": now_iso(),
            })
            for movement in database.get("movements", {}).values():
                if str(movement.get("movement_id", "")) == str(movement_id):
                    movement["name"] = display_name
                    movement["aliases"] = list(dict.fromkeys([*movement.get("aliases", []), *aliases]))
            reconciliation = self._reconcile_definition(database, dictionary, definition)
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"definition": copy.deepcopy(definition), "reconciliation": reconciliation, "sync_state": "LOCAL_NEWER"}

    def set_movement_active(self, movement_id: str, active: bool) -> dict:
        with self.write_lock():
            database, dictionary = self.load_state()
            definition = self._definition_by_id(dictionary, movement_id)
            tracker_backup, dictionary_backup = self._checkpoint()
            definition["active"] = bool(active)
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"movement_id": movement_id, "active": bool(active)}

    def set_movement_exclude_from_progress(self, movement_id: str, excluded: bool) -> dict:
        """Hide or restore one movement only in the Movement Progress projection."""
        movement_id = str(movement_id or "").strip()
        if not movement_id:
            raise LedgerCommandError("Movement ID cannot be blank.", "MOVEMENT_ID_REQUIRED")
        excluded = bool(excluded)
        with self.write_lock():
            database, dictionary, _fingerprint = self._strict_state_snapshot()
            definition = self._definition_by_id(dictionary, movement_id)
            current = bool(definition.get("exclude_from_progress", False))
            if current == excluded:
                return {
                    "status": "NO_CHANGES",
                    "changed": False,
                    "movement_id": movement_id,
                    "exclude_from_progress": excluded,
                }

            tracker_backup, dictionary_backup = self._checkpoint()
            checkpoint = self._checkpoint_identity(tracker_backup)
            try:
                definition["exclude_from_progress"] = excluded
                self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
                _stored_database, stored_dictionary, after_fingerprint = self._strict_state_snapshot()
                stored = self._definition_by_id(stored_dictionary, movement_id)
                if bool(stored.get("exclude_from_progress", False)) != excluded:
                    raise LedgerCommandError(
                        "Movement Progress visibility validation failed.",
                        "PROGRESS_VISIBILITY_VALIDATION_FAILED",
                    )
            except Exception as exc:
                rollback_errors = []
                if tracker_backup.exists() or dictionary_backup.exists():
                    for backup, destination, label in (
                        (tracker_backup, self.data_file, "tracker"),
                        (dictionary_backup, self.dictionary_file, "dictionary"),
                    ):
                        try:
                            shutil.copy2(backup, destination)
                        except Exception as rollback_exc:
                            rollback_errors.append(f"{label}: {rollback_exc}")
                # _write_pair performs and finalizes its own rollback.  In
                # that case both checkpoint files are already gone.
                rolled_back = not rollback_errors and not (
                    tracker_backup.exists() ^ dictionary_backup.exists()
                )
                if rolled_back:
                    self._discard_checkpoint(tracker_backup, dictionary_backup)
                raise LedgerCommandError(
                    "Movement Progress visibility update failed; both files were restored."
                    if rolled_back else
                    "Movement Progress visibility update failed and rollback needs manual review.",
                    "PROGRESS_VISIBILITY_UPDATE_FAILED",
                    {
                        "movement_id": movement_id,
                        "rolled_back": rolled_back,
                        "rollback_errors": rollback_errors,
                        "cause_code": getattr(exc, "code", exc.__class__.__name__),
                        "cause": str(exc),
                    },
                ) from exc
            return {
                "status": "UPDATED",
                "changed": True,
                "movement_id": movement_id,
                "exclude_from_progress": excluded,
                "checkpoint": checkpoint,
                "undo": {"available": True, "checkpoint": checkpoint},
                "data_fingerprint": after_fingerprint,
            }

    def delete_movement_definition(self, movement_id: str, confirmation: str) -> dict:
        with self.write_lock():
            database, dictionary = self.load_state()
            definition = self._definition_by_id(dictionary, movement_id)
            display_name = str(definition.get("display_name", ""))
            if confirmation.strip() != display_name:
                raise LedgerCommandError("Delete confirmation does not match the movement name.")
            history_count = len(movement_items(database, str(movement_id)))
            tracker_backup, dictionary_backup = self._checkpoint()
            dictionary["movements"] = [
                item for item in dictionary.get("movements", []) if str(item.get("movement_id", "")) != str(movement_id)
            ]
            database["movements"] = {
                key: movement for key, movement in database.get("movements", {}).items()
                if str(movement.get("movement_id", "")) != str(movement_id)
            }
            for session in database.get("training_sessions", []):
                session["movement_items"] = [item for item in session.get("movement_items", []) if str(item.get("movement_id", "")) != str(movement_id)]
            rebuild_movement_projection(database)
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

    def update_record(
        self,
        record_type: str,
        record_id: str,
        values: dict,
        *,
        expected_revision: int | None = None,
        move_scope: str = "record",
    ) -> dict:
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
            current_revision = int(record.get("revision", 1) or 1)
            if expected_revision is not None and int(expected_revision) != current_revision:
                raise LedgerCommandError(
                    "This record changed after the page was opened. Reload it before saving.",
                    "REVISION_CONFLICT",
                    {"expected_revision": expected_revision, "current_revision": current_revision, "record": copy.deepcopy(record)},
                )
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
                    updates[field] = normalize_note_text(value) if field == "Notes" else str(value or "").strip()
            if "Date" in updates:
                try:
                    date.fromisoformat(updates["Date"])
                except ValueError as exc:
                    raise LedgerCommandError("Date must use YYYY-MM-DD format.") from exc
            if "Raw Record" in updates and updates["Raw Record"] != str(record.get("Raw Record", "")):
                raise LedgerCommandError(
                    "Training raw text must be previewed and confirmed before it is saved.",
                    "RAW_EDIT_REQUIRES_PREVIEW",
                )
            before = copy.deepcopy(record)
            old_date = canonical_date(record.get("Date"))
            record.update(updates)
            if _same_business_content(before, record):
                return {"status": "NO_CHANGES", "changed": False, "record_type": record_type, "record": copy.deepcopy(before)}
            record["revision"] = current_revision + 1
            record["updated_at"] = now_iso()
            new_date = canonical_date(record.get("Date"))
            if new_date != old_date:
                if move_scope not in {"record", "day"}:
                    raise LedgerCommandError("move_scope must be 'record' or 'day'.")
                if move_scope == "day":
                    record["record_day_id"] = record_day_id(new_date)
                    self._move_day_entities(database, old_date, new_date, anchor_type=record_type, anchor_id=record_id)
                else:
                    record["record_day_id"] = record_day_id(new_date)
                    if record_type == "training":
                        for item in movement_items_by_session(database, record_id):
                            item["date"] = new_date
                            item["record_day_id"] = record_day_id(new_date)
                            item["updated_at"] = now_iso()
                        rebuild_movement_projection(database)
                self._touch_record_day(database, old_date)
                self._touch_record_day(database, new_date)
            else:
                self._touch_record_day(database, old_date)
            tracker_backup, dictionary_backup = self._checkpoint()
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"status": "UPDATED", "changed": True, "record_type": record_type, "record": copy.deepcopy(record), "sync_state": "LOCAL_NEWER"}

    @staticmethod
    def _move_day_entities(database: dict, source_date: str, target_date: str, *, anchor_type: str, anchor_id: str) -> None:
        """Move the complete date aggregate, preserving entity IDs and links."""
        for collection, date_field in (("daily_records", "Date"), ("diet_records", "Date"), ("training_sessions", "Date"), ("data_module_records", "date"), ("raw_entries", "date")):
            for row in database.get(collection, []) or []:
                if canonical_date(row.get(date_field)) != source_date:
                    continue
                row[date_field] = target_date
                row["record_day_id"] = record_day_id(target_date)
                row["revision"] = int(row.get("revision", 1) or 1) + 1
                row["updated_at"] = now_iso()
        for revision in database.get("raw_entry_revisions", []) or []:
            if canonical_date(revision.get("date")) == source_date:
                revision["date"] = target_date
                revision["record_day_id"] = record_day_id(target_date)
                revision["revision"] = int(revision.get("revision", 1) or 1) + 1
                revision["updated_at"] = now_iso()
        for item in movement_items_by_date(database, source_date):
            item["date"] = target_date
            item["record_day_id"] = record_day_id(target_date)
            item["revision"] = int(item.get("revision", 1) or 1) + 1
            item["updated_at"] = now_iso()
        rebuild_movement_projection(database)

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

    def update_movement_history(
        self,
        movement_id: str,
        history_id: str,
        values: dict,
        *,
        expected_revision: int | None = None,
    ) -> dict:
        if not isinstance(values, dict):
            raise LedgerCommandError("Movement history values must be an object.")
        with self.write_lock():
            database, dictionary = self.load_state()
            item = next((row for row in movement_items(database, str(movement_id)) if str(row.get("id") or row.get("movement_instance_id")) == str(history_id)), None)
            if not item:
                raise LedgerCommandError("Movement was not found.")
            history = item
            current_revision = int(item.get("revision", 1) or 1)
            if expected_revision is not None and int(expected_revision) != current_revision:
                raise LedgerCommandError(
                    "This movement instance changed after the page was opened. Reload it before saving.",
                    "REVISION_CONFLICT",
                    {"expected_revision": expected_revision, "current_revision": current_revision, "history": copy.deepcopy(history)},
                )
            try:
                order_text = str(values.get("order", history.get("order", ""))).strip()
                order = int(order_text) if order_text else None
            except (TypeError, ValueError) as exc:
                raise LedgerCommandError("Order must be numeric or blank.") from exc
            updates = {
                "order": order,
                "sets": (
                    self._parse_sets_text(str(values.get("sets_text", "")))
                    if "sets_text" in values else copy.deepcopy(history.get("sets") or [])
                ),
                "raw": str(values.get("raw", history.get("raw", ""))).strip(),
                "notes": normalize_note_text(values.get("notes", history.get("notes", ""))),
                "updated_at": now_iso(),
            }
            if "exclude_from_progress" in values:
                excluded = values.get("exclude_from_progress")
                if not isinstance(excluded, bool):
                    raise LedgerCommandError(
                        "exclude_from_progress must be boolean.",
                        "INVALID_PROGRESS_EXCLUSION",
                    )
                updates["exclude_from_progress"] = excluded
            before = copy.deepcopy(history)
            history.update(updates)
            if _same_business_content(before, history):
                unchanged = copy.deepcopy(before)
                unchanged.setdefault("exclude_from_progress", False)
                return {"status": "NO_CHANGES", "changed": False, "movement_id": movement_id, "history": unchanged}
            history["revision"] = current_revision + 1
            session_id = str(history.get("training_session_id", ""))
            session = next(
                (row for row in database.get("training_sessions", []) if str(row.get("id", "")) == session_id),
                None,
            )
            if session:
                session["revision"] = int(session.get("revision", 1) or 1) + 1
                session["updated_at"] = now_iso()
                refs = movement_items_by_session(database, session_id)
                refs.sort(key=lambda item: (int(item.get("order", 9999) or 9999), str(item.get("movement_id", ""))))
                session["Standardized Summary"] = "；".join(
                    f"第{item.get('order')}个动作：{next((definition.get('display_name', item.get('movement_id', '')) for definition in dictionary.get('movements', []) if str(definition.get('movement_id')) == str(item.get('movement_id'))), item.get('movement_id', ''))}"
                    for item in refs
                )
                rebuild_movement_projection(database)
            history.setdefault("record_day_id", record_day_id(history.get("date")))
            self._touch_record_day(database, history.get("date", ""))
            tracker_backup, dictionary_backup = self._checkpoint()
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"status": "UPDATED", "changed": True, "movement_id": movement_id, "history": copy.deepcopy(history), "session": copy.deepcopy(session) if session else None, "sync_state": "LOCAL_NEWER"}

    def update_data_module_record(self, record_id: str, values: dict, *, expected_revision: int | None = None) -> dict:
        """Edit one module value through the same paired tracker transaction."""
        if not isinstance(values, dict):
            raise LedgerCommandError("Data Module values must be an object.")
        with self.write_lock():
            database, dictionary = self.load_state()
            record = next((item for item in database.get("data_module_records", []) if str(item.get("record_id")) == str(record_id)), None)
            if record is None:
                raise LedgerCommandError("Data Module record was not found.")
            current_revision = int(record.get("revision", 1) or 1)
            if expected_revision is not None and int(expected_revision) != current_revision:
                raise LedgerCommandError("This Data Module record changed after the page was opened. Reload it before saving.", "REVISION_CONFLICT", {"expected_revision": expected_revision, "current_revision": current_revision, "record": copy.deepcopy(record)})
            engine = self.data_module_engine()
            definition = engine.registry.require(str(record.get("module_id", "")))
            if "value" not in values:
                raise LedgerCommandError("A module value is required.")
            value = definition.normalize_value(values.get("value")) if hasattr(definition, "normalize_value") else None
            if value is None:
                from fitness_ledger_core.data_module_engine import normalize_value
                value = normalize_value(values.get("value"), definition)
            before = copy.deepcopy(record)
            record["value"] = copy.deepcopy(value)
            if "date" in values and str(values.get("date", "")).strip() != str(record.get("date", "")):
                target = str(values.get("date", "")).strip()
                try:
                    date.fromisoformat(target)
                except ValueError as exc:
                    raise LedgerCommandError("Date must use YYYY-MM-DD format.") from exc
                record["date"] = target
                record["record_day_id"] = record_day_id(target)
            if _same_business_content(before, record):
                return {"status": "NO_CHANGES", "changed": False, "record": before}
            record["revision"] = current_revision + 1
            record["updated_at"] = now_iso()
            self._touch_record_day(database, record.get("date", ""))
            tracker_backup, dictionary_backup = self._checkpoint()
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"status": "UPDATED", "changed": True, "record": copy.deepcopy(record), "sync_state": "LOCAL_NEWER"}

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

    @staticmethod
    def _session_histories(database: dict, session_id: str) -> list[tuple[dict, dict]]:
        definitions = {str(item.get("movement_id")): item for item in database.get("movements", {}).values() if isinstance(item, dict)}
        return [(definitions.get(str(item.get("movement_id")), {"movement_id": item.get("movement_id", "")}), item) for item in movement_items_by_session(database, session_id)]

    def preview_training_raw_edit(self, session_id: str, raw_text: str, expected_revision: int | None = None) -> dict:
        raw = str(raw_text or "").strip()
        if not raw:
            raise LedgerCommandError("Training raw text cannot be blank.")
        database, dictionary = self.load_state()
        session = next((row for row in database.get("training_sessions", []) if str(row.get("id")) == str(session_id)), None)
        if session is None:
            raise LedgerCommandError("Training session was not found.")
        current_revision = int(session.get("revision", 1) or 1)
        if expected_revision is not None and int(expected_revision) != current_revision:
            raise LedgerCommandError("This training session changed after the page was opened. Reload it before previewing.", "REVISION_CONFLICT", {"expected_revision": expected_revision, "current_revision": current_revision})
        parsed = self.parser(raw, database, dictionary)
        parsed["date"] = canonical_date(session.get("Date"))
        self._prepare_generated_training_fields(parsed)
        by_id, by_alias = _dictionary_indexes(dictionary)
        new_items = []
        unmapped = []
        for item in parsed.get("training", {}).get("movements", []) or []:
            candidate = str(item.get("name", "")).strip()
            definition = by_id.get(str(item.get("movement_id", ""))) or by_alias.get(_normalize_name(candidate))
            if not definition:
                unmapped.append(candidate)
                continue
            new_items.append({
                "movement_id": definition["movement_id"], "display_name": definition.get("display_name", candidate),
                "order": item.get("order"), "sets": copy.deepcopy(item.get("sets", []) or []),
                "raw": item.get("raw", ""),
                "notes": normalize_note_text(item.get("notes", "")), "exclude_from_progress": bool(item.get("exclude_from_progress", False)),
            })
        old_items = []
        for _movement, history in self._session_histories(database, session_id):
            old_items.append({
                "history_id": history.get("id", ""), "movement_id": history.get("movement_id", ""),
                "order": history.get("order"), "sets": copy.deepcopy(history.get("sets", []) or []),
                "notes": normalize_note_text(history.get("notes", "")),
            })
        old_by_key = {(str(item.get("movement_id")), str(item.get("order"))): item for item in old_items}
        new_by_key = {(str(item.get("movement_id")), str(item.get("order"))): item for item in new_items}
        updated = [new_by_key[key] for key in sorted(set(old_by_key) & set(new_by_key)) if not _same_business_content(old_by_key[key], new_by_key[key])]
        added = [new_by_key[key] for key in sorted(set(new_by_key) - set(old_by_key))]
        removed = [old_by_key[key] for key in sorted(set(old_by_key) - set(new_by_key))]
        preview_id = _stable_json_hash({"session_id": session_id, "revision": current_revision, "raw": raw})[:24]
        return {
            "status": "raw_edit_preview", "preview_id": preview_id, "training_session_id": session_id,
            "expected_revision": current_revision, "raw_text": raw, "parsed": parsed,
            "diff": {"added": added, "removed": removed, "updated": updated, "unmapped": unmapped},
            "requires_confirmation": True,
        }

    def apply_training_raw_edit(self, preview: dict, *, confirmed: bool = False) -> dict:
        if not confirmed:
            raise LedgerCommandError("The training raw diff must be explicitly confirmed.", "RAW_EDIT_CONFIRMATION_REQUIRED")
        if not isinstance(preview, dict) or preview.get("status") != "raw_edit_preview":
            raise LedgerCommandError("A valid training raw edit preview is required.", "RAW_EDIT_PREVIEW_REQUIRED")
        session_id = str(preview.get("training_session_id", ""))
        raw_text = str(preview.get("raw_text", "")).strip()
        with self.write_lock():
            database, dictionary = self.load_state()
            session = next((row for row in database.get("training_sessions", []) if str(row.get("id")) == session_id), None)
            if session is None:
                raise LedgerCommandError("Training session was not found.")
            current_revision = int(session.get("revision", 1) or 1)
            if current_revision != int(preview.get("expected_revision", 0) or 0):
                raise LedgerCommandError("This training session changed after preview. Run the raw diff again.", "REVISION_CONFLICT", {"current_revision": current_revision})
            parsed = preview.get("parsed") or {}
            by_id, by_alias = _dictionary_indexes(dictionary)
            desired = []
            for item in parsed.get("training", {}).get("movements", []) or []:
                candidate = str(item.get("name", "")).strip()
                definition = by_id.get(str(item.get("movement_id", ""))) or by_alias.get(_normalize_name(candidate))
                if definition:
                    desired.append((definition, item))
            existing = {(str(history.get("movement_id")), str(history.get("order"))): history for _movement, history in self._session_histories(database, session_id)}
            desired_keys = set()
            for definition, item in desired:
                key = (str(definition["movement_id"]), str(item.get("order")))
                desired_keys.add(key)
                if key in existing:
                    history = existing[key]
                    history.update({"sets": copy.deepcopy(item.get("sets", []) or []), "raw": item.get("raw", ""), "notes": normalize_note_text(item.get("notes", "")), "exclude_from_progress": bool(item.get("exclude_from_progress", False)), "revision": int(history.get("revision", 1) or 1) + 1, "updated_at": now_iso()})
                else:
                    item_id = str(uuid.uuid4())
                    session.setdefault("movement_items", []).append({"id": item_id, "movement_instance_id": item_id, "movement_id": definition["movement_id"], "display_name": definition.get("display_name", item.get("name", "")), "date": canonical_date(session.get("Date")), "training_day": session.get("No.", ""), "order": item.get("order"), "sets": copy.deepcopy(item.get("sets", []) or []), "raw": item.get("raw", ""), "notes": normalize_note_text(item.get("notes", "")), "exclude_from_progress": bool(item.get("exclude_from_progress", False)), "source": "raw edit", "record_day_id": record_day_id(session.get("Date")), "training_session_id": session_id, "raw_entry_id": session.get("raw_entry_id", ""), "raw_revision_id": session.get("raw_revision_id", ""), "revision": 1, "updated_at": now_iso()})
            for key, history in existing.items():
                if key not in desired_keys:
                    session["movement_items"] = [item for item in session.get("movement_items", []) if item is not history]
            raw_entry = next((item for item in database.get("raw_entries", []) if str(item.get("id")) == str(session.get("raw_entry_id", ""))), None)
            if raw_entry is None:
                raw_entry = {"id": _stable_json_hash({"session_id": session_id, "raw": raw_text})[:24], "date": canonical_date(session.get("Date")), "source": "raw edit", "record_day_id": record_day_id(session.get("Date")), "revision": 0}
                database.setdefault("raw_entries", []).append(raw_entry)
                session["raw_entry_id"] = raw_entry["id"]
            next_raw_revision = int(raw_entry.get("revision", 0) or 0) + 1
            raw_entry.update({"date": canonical_date(session.get("Date")), "text": raw_text, "raw_revision_id": f"rawrev:{raw_entry['id']}:{next_raw_revision}", "revision": next_raw_revision, "updated_at": now_iso(), "record_day_id": record_day_id(session.get("Date"))})
            database.setdefault("raw_entry_revisions", []).append({"raw_revision_id": raw_entry["raw_revision_id"], "raw_entry_id": raw_entry["id"], "record_day_id": raw_entry["record_day_id"], "date": raw_entry["date"], "revision": next_raw_revision, "text": raw_text, "created_at": raw_entry.get("created_at", raw_entry["updated_at"]), "updated_at": raw_entry["updated_at"], "source": "raw edit"})
            for _movement, history in self._session_histories(database, session_id):
                history["raw_entry_id"] = raw_entry["id"]
                history["raw_revision_id"] = raw_entry["raw_revision_id"]
            rebuild_movement_projection(database)
            session.update({"Raw Record": raw_text, "raw_entry_id": raw_entry["id"], "raw_revision_id": raw_entry["raw_revision_id"], "Standardized Summary": "；".join(f"第{item.get('order')}个动作：{definition.get('display_name', '')}" for definition, item in desired), "revision": current_revision + 1, "updated_at": now_iso()})
            if parsed.get("training", {}).get("split"):
                session["Split"] = str(parsed["training"]["split"]).strip()
            session["Notes"] = normalize_note_text(parsed.get("training", {}).get("notes", session.get("Notes", "")))
            self._touch_record_day(database, session.get("Date", ""))
            tracker_backup, dictionary_backup = self._checkpoint()
            self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            return {"status": "UPDATED", "changed": True, "training_session_id": session_id, "session": copy.deepcopy(session), "diff": preview.get("diff", {}), "sync_state": "LOCAL_NEWER"}

    def _prepare_generated_training_fields(self, parsed: dict) -> None:
        training = parsed.setdefault("training", {})
        body = parsed.setdefault("body", {})
        source_movements = training.setdefault("movements", [])
        movements = []
        cardio_lines = []
        cardio_names = {"cardio", "有氧", "treadmill", "跑步机", "walk", "步行"}
        for movement in source_movements:
            name = str(movement.get("name", "")).strip().casefold()
            is_cardio = name in cardio_names or (bool(movement.get("cardio")) and not (movement.get("sets") or []))
            if is_cardio:
                raw = str(movement.get("raw", "")).strip()
                if raw:
                    cardio_lines.append(raw)
                continue
            movements.append(movement)
        training["movements"] = movements
        if cardio_lines and not str(body.get("cardio_summary", "") or "").strip():
            body["cardio_summary"] = "; ".join(cardio_lines)
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
        training["notes"] = normalize_note_text(training.get("notes", ""))

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
            movement.setdefault("exclude_from_progress", False)
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
            "progress_excluded_count": sum(
                1 for item in included if bool(item.get("exclude_from_progress", False))
            ),
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
            if not movement.get("sets"):
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

        for movement in parsed.get("training", {}).get("movements", []):
            if "exclude_from_progress" not in movement:
                movement["exclude_from_progress"] = False
            elif not isinstance(movement.get("exclude_from_progress"), bool):
                raise LedgerCommandError(
                    "exclude_from_progress must be boolean.",
                    "INVALID_PROGRESS_EXCLUSION",
                )

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
        try:
            shutil.copy2(self.data_file, tracker_backup)
            shutil.copy2(self.dictionary_file, dictionary_backup)
        except Exception as exc:
            tracker_backup.unlink(missing_ok=True)
            dictionary_backup.unlink(missing_ok=True)
            raise LedgerCommandError(
                "Paired checkpoint creation failed; no data was changed.",
                "CHECKPOINT_FAILED",
            ) from exc
        return tracker_backup, dictionary_backup

    @staticmethod
    def _remove_for_overwrite(database: dict, entry_date: str, replacement_id: str) -> int | None:
        target = str(entry_date)[:10]
        removed_sessions = [row for row in database.get("training_sessions", []) if str(row.get("Date", ""))[:10] == target]
        removed_days = {int(row.get("No.")) for row in removed_sessions if str(row.get("No.", "")).isdigit()}
        database["daily_records"] = [row for row in database.get("daily_records", []) if str(row.get("Date", ""))[:10] != target]
        database["diet_records"] = [row for row in database.get("diet_records", []) if str(row.get("Date", ""))[:10] != target]
        database["training_sessions"] = [row for row in database.get("training_sessions", []) if str(row.get("Date", ""))[:10] != target]
        for session in database.get("training_sessions", []):
            session["movement_items"] = [row for row in session.get("movement_items", []) if str(row.get("date", ""))[:10] != target]
        for movement in database.get("movements", {}).values():
            if isinstance(movement, dict):
                movement["history"] = [
                    row for row in movement.get("history", []) or []
                    if str(row.get("date", ""))[:10] != target
                    and str(row.get("record_day_id", "")) != record_day_id(target)
                ]
        rebuild_movement_projection(database)
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
            module_preview = parsed.get("_data_module_preview")
            if module_preview:
                # The preview must match the state the user reviewed.  Check
                # before Body/Diet/Training are applied; those edits are part
                # of the same transaction and would otherwise make a valid
                # mixed Daily Entry look stale.
                module_engine = self.data_module_engine()
                if module_engine._fingerprint(database) != str(module_preview.get("source_fingerprint", "")):
                    raise LedgerCommandError("Data Module preview is stale; re-run preview.", "MODULE_PREVIEW_STALE")
            duplicates = self.records_on_date(database, parsed["date"])
            if any(duplicates.values()) and save_mode not in {"overwrite", "append_training"}:
                raise DuplicateDateError({key: len(rows) for key, rows in duplicates.items()})
            save_mode = save_mode or "normal"
            before_database, before_dictionary = copy.deepcopy(database), copy.deepcopy(dictionary)
            tracker_backup = None
            dictionary_backup = None
            try:
                result = self._apply_save(database, dictionary, parsed, save_mode)
                if _same_business_content(before_database, database) and _same_business_content(before_dictionary, dictionary):
                    return {
                        "ok": True, "status": "NO_CHANGES", "changed": False, "date": parsed["date"],
                        "save_mode": save_mode, "saved_movements": 0, "working_sets": 0,
                        "progress_excluded_count": 0,
                        "record_id": None, "personal_records": [],
                        "split_label": "", "movement_count": 0,
                        "body_updated": False, "diet_updated": False, "training_updated": False, "notes_updated": False,
                        "movements_added": 0, "movements_removed": 0,
                    }
                tracker_backup, dictionary_backup = self._checkpoint()
                self._write_pair(database, dictionary, tracker_backup, dictionary_backup)
            except Exception as exc:
                rollback_errors = []
                if tracker_backup and dictionary_backup:
                    for backup, destination, label in (
                        (tracker_backup, self.data_file, "tracker"),
                        (dictionary_backup, self.dictionary_file, "dictionary"),
                    ):
                        try:
                            shutil.copy2(backup, destination)
                        except Exception as rollback_exc:
                            rollback_errors.append(f"{label}: {rollback_exc}")
                    if not rollback_errors:
                        self._discard_checkpoint(tracker_backup, dictionary_backup)
                raise LedgerCommandError(
                    "Daily save failed; both formal files were restored." if not rollback_errors else "Daily save failed and rollback needs manual review.",
                    "SAVE_FAILED",
                    {"rolled_back": not rollback_errors, "rollback_errors": rollback_errors, "cause_code": getattr(exc, "code", exc.__class__.__name__), "cause": str(exc)},
                ) from exc
            result.update({
                "status": "UPDATED" if any(duplicates.values()) else "CREATED", "changed": True,
                "working_sets": sum(int(block.get("sets") or 0) for movement in parsed.get("training", {}).get("movements", []) for block in movement.get("sets", [])),
                "body_updated": bool(parsed.get("body")), "diet_updated": bool(parsed.get("diet")),
                "training_updated": bool(parsed.get("training", {}).get("split") or parsed.get("training", {}).get("movements")),
                "notes_updated": bool(
                    parsed.get("body", {}).get("notes")
                    or parsed.get("diet", {}).get("notes")
                    or parsed.get("training", {}).get("notes")
                    or any(str(item.get("notes", "")).strip() for item in parsed.get("training", {}).get("movements", []))
                ),
                "movements_added": result.get("saved_movements", 0), "movements_removed": 0,
                "sync_state": "LOCAL_NEWER",
            })
            return result

    def _apply_save(self, database: dict, dictionary: dict, parsed: dict, save_mode: str) -> dict:
        # Keep this lower-level boundary safe for direct callers and tests as
        # well as the public save() path: all writes start from one canonical
        # in-memory graph, while migrate_state itself remains file-free.
        normalized_database, normalized_dictionary, _migration_report = migrate_state(database, dictionary)
        database.clear()
        database.update(normalized_database)
        dictionary.clear()
        dictionary.update(normalized_dictionary)
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
            "record_day_id": record_day_id(entry_date),
            "raw_revision_id": f"rawrev:{parsed['id']}:1",
            "revision": 1,
            "updated_at": now_iso(),
        }
        database.setdefault("raw_entries", []).append(raw_record)
        database.setdefault("raw_entry_revisions", []).append({
            "raw_revision_id": raw_record["raw_revision_id"], "raw_entry_id": raw_record["id"],
            "record_day_id": record_day_id(entry_date), "date": entry_date, "revision": 1,
            "text": parsed["raw"], "created_at": raw_record["created_at"],
            "updated_at": raw_record["updated_at"], "source": "text entry",
        })
        save_primary = save_mode != "append_training"
        body = parsed.get("body", {})
        body["notes"] = normalize_note_text(body.get("notes", ""))
        if save_primary and any(body.get(field) not in (None, "") for field in ("weight", "bowel_movement", "training_summary", "cardio_summary", "notes")):
            database.setdefault("daily_records", []).append(
                {
                    "id": str(uuid.uuid4()), "Date": entry_date, "Weight (kg)": body.get("weight"),
                    "Body Fat %": body.get("body_fat"), "Waist (cm)": body.get("waist"),
                    "Sleep (h)": body.get("sleep"), "Steps": body.get("steps"), "Context": body.get("context", ""),
                    "Bowel Movement": body.get("bowel_movement", ""), "Training": body.get("training_summary", ""),
                    "Cardio": body.get("cardio_summary", ""), "Notes": body.get("notes", ""), "source": "text entry",
                    "record_day_id": record_day_id(entry_date), "revision": 1, "updated_at": now_iso(),
                }
            )
        diet = parsed.get("diet", {})
        diet["notes"] = normalize_note_text(diet.get("notes", ""))
        if save_primary and (diet.get("food_summary") or any(diet.get(field) is not None for field in ("calories", "protein", "carbs", "fat"))):
            database.setdefault("diet_records", []).append(
                {
                    "id": str(uuid.uuid4()), "Date": entry_date, "Food Summary": diet.get("food_summary", ""),
                    "Calories (kcal)": diet.get("calories"), "Protein (g)": diet.get("protein"),
                    "Carbs (g)": diet.get("carbs"), "Fat (g)": diet.get("fat"),
                    "Notes": diet.get("notes", ""), "source": "text entry",
                    "record_day_id": record_day_id(entry_date), "revision": 1, "updated_at": now_iso(),
                }
            )
        training = parsed.get("training", {})
        training["notes"] = normalize_note_text(training.get("notes", ""))
        saved_movements = 0
        progress_excluded_count = 0
        skipped = []
        personal_records = []
        training_record_id = None
        if training.get("split") or training.get("movements"):
            training_record_id = str(uuid.uuid4())
            existing_days = [int(row.get("No.") or 0) for row in database.get("training_sessions", [])]
            day_number = replacement_day or (max(existing_days, default=0) + 1)
            summary_parts = []
            note_parts = []
            training_items = []
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
                self._tracker_movement(database, definition, candidate)
                previous_history = list(movement_items(database, definition["movement_id"]))
                history_record = {
                    "id": str(uuid.uuid4()), "movement_id": definition["movement_id"], "display_name": definition.get("display_name") or candidate, "date": entry_date,
                    "training_day": day_number, "order": movement_data.get("order"), "sets": movement_data.get("sets", []),
                    "raw": movement_data.get("raw", ""),
                    "notes": normalize_note_text(movement_data.get("notes", "")),
                    "exclude_from_progress": bool(movement_data.get("exclude_from_progress", False)),
                    "source": "text entry",
                    "record_day_id": record_day_id(entry_date), "training_session_id": training_record_id,
                    "raw_entry_id": raw_record["id"], "raw_revision_id": raw_record["raw_revision_id"],
                    "revision": 1, "updated_at": now_iso(),
                }
                history_record["movement_instance_id"] = history_record["id"]
                variant = str(movement_data.get("variant") or "").strip()
                if variant:
                    history_record["variant"] = variant
                training_items.append(history_record)
                personal_record = LedgerViewModels.personal_record_summary(definition, history_record, previous_history)
                if personal_record:
                    personal_records.append(personal_record)
                display_name = definition.get("display_name") or movement_data.get("display_name") or candidate
                summary_parts.append(f"第{movement_data.get('order')}个动作：{display_name}")
                note = str(movement_data.get("notes", "")).strip().rstrip("，。?!！？")
                if note:
                    note_parts.append(f"{display_name}：{note}")
                saved_movements += 1
                progress_excluded_count += int(bool(movement_data.get("exclude_from_progress", False)))
            training_notes = normalize_note_text(training.get("notes", ""))
            if save_mode == "append_training":
                training_notes = f"同日追加训练。{training_notes}" if training_notes else "同日追加训练。"
            database.setdefault("training_sessions", []).append(
                {
                    "id": training_record_id, "No.": day_number, "Date": entry_date,
                    "Split": training.get("split", ""), "Raw Record": training.get("raw", ""),
                    "Standardized Summary": training.get("standardized_summary") or "；".join(summary_parts),
                    "Notes": training_notes,
                    "movement_items": training_items,
                    "save_mode": save_mode, "source": "text entry",
                    "record_day_id": record_day_id(entry_date), "raw_entry_id": raw_record["id"],
                    "raw_revision_id": raw_record["raw_revision_id"], "revision": 1, "updated_at": now_iso(),
                }
            )
            if skipped:
                raw_record["skipped_movements"] = skipped
            normalize_training_organization(database, dictionary)
            rebuild_movement_projection(database)
        data_module_result = {"changed": False, "status": "NO_CHANGES"}
        module_preview = parsed.get("_data_module_preview")
        if module_preview:
            data_module_result = self.data_module_engine().apply_preview_to_database(database, module_preview, raw_entry_id=raw_record["id"])
        self._touch_record_day(database, entry_date)
        return {
            "ok": True,
            "date": entry_date,
            "save_mode": save_mode,
            "saved_movements": saved_movements,
            "progress_excluded_count": progress_excluded_count,
            "skipped_movements": skipped,
            "record_id": training_record_id,
            "personal_records": personal_records,
            "split_label": str(training.get("split") or ""),
            "movement_count": saved_movements,
            "data_module_result": data_module_result,
        }
