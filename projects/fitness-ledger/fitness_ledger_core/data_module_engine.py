"""Bounded, registry-driven Data Module extension layer.

This module deliberately does not replace Body, Diet, Training, or Movement.
It provides the candidate implementation for ordinary extension modules and
keeps all formal writes behind LedgerCommandService's existing transaction
boundary.  The public record shape is a list of records so future event,
session, meal, and structured modules do not require a second storage model.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable


MODULE_ID_RE = re.compile(r"^[a-z][a-z0-9_]{1,63}$")
DATE_RE = re.compile(r"(?<!\d)(\d{4})[-/](\d{1,2})[-/](\d{1,2})(?!\d)")
NUMBER_RE = re.compile(r"(?<![\d.])[-+]?\d+(?:\.\d+)?(?![\d.])")

SUPPORTED_DATA_TYPES = {"number", "quantity", "text", "boolean", "enum", "rating", "duration", "structured"}
SUPPORTED_STATUSES = {"active", "inactive", "retired"}
SUPPORTED_RECORDING_KINDS = {"scalar", "event", "session", "meal", "structured"}
SUPPORTED_CARDINALITIES = {"one_per_day", "many_per_day", "many_per_session"}
SUPPORTED_RENDERERS = {"single_metric", "metric_history"}
KNOWN_CATEGORIES = {"body", "diet", "training", "movement", "extension"}
KNOWN_PRESENTATION_SECTIONS = {"body", "diet", "training", "movement", "extension", "analysis", "home"}
KNOWN_PRESENTATION_SLOTS = {"top", "summary", "history", "secondary", "auxiliary"}
SUPPORTED_PRESENTATION_FALLBACKS = {"empty_state", "hide"}
SUPPORTED_UNSUPPORTED_BEHAVIORS = {"hide", "reject"}

DEFAULT_CAPABILITIES = {
    "recordable": True,
    "queryable": True,
    "history_enabled": True,
    "exportable": True,
    "analysis_visible": False,
    "cloud_syncable": False,
    "mini_program_visible": False,
}

DEFAULT_CATEGORIES = [
    {"category_id": "body", "label": "Body", "order": 10, "status": "active", "system": True, "presentation": {"template": "core"}},
    {"category_id": "diet", "label": "Diet", "order": 20, "status": "active", "system": True, "presentation": {"template": "core"}},
    {"category_id": "training", "label": "Training", "order": 30, "status": "active", "system": True, "presentation": {"template": "core"}},
    {"category_id": "movement", "label": "Movement", "order": 40, "status": "active", "system": True, "presentation": {"template": "core"}},
    {"category_id": "extension", "label": "Extensions", "order": 50, "status": "active", "system": True, "presentation": {"template": "extension"}},
]


class DataModuleError(ValueError):
    """Deterministic error used by the candidate engine and adapter layer."""

    def __init__(self, message: str, code: str = "DATA_MODULE_ERROR", details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.details = details or {}


def _error(message: str, code: str, details: dict | None = None) -> DataModuleError:
    return DataModuleError(message, code, details)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value).encode("utf-8")).hexdigest()


def _read_json(path: Path, fallback: Any) -> Any:
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return copy.deepcopy(fallback)


def _write_json_atomic(path: Path, value: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        json.loads(temp.read_text(encoding="utf-8"))
        temp.replace(path)
    finally:
        temp.unlink(missing_ok=True)


def normalize_alias(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").casefold())


def validate_iso_date(value: Any) -> str:
    text = str(value or "").strip()
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise _error("Data Module dates must use YYYY-MM-DD.", "MODULE_DATE_INVALID", {"date": text}) from exc
    if parsed.isoformat() != text:
        raise _error("Data Module dates must use canonical YYYY-MM-DD.", "MODULE_DATE_INVALID", {"date": text})
    return text


def _bool(value: Any, default: bool = False) -> bool:
    return default if value is None else value is True


def _finite_number(value: Any, field_name: str = "value") -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise _error(f"{field_name} must be numeric.", "MODULE_VALUE_TYPE_INVALID", {"field": field_name}) from exc
    if not math.isfinite(number):
        raise _error(f"{field_name} must be finite.", "MODULE_VALUE_NONFINITE", {"field": field_name})
    return number


def _normalize_numeric(value: Any, definition: "ModuleDefinition") -> int | float:
    if isinstance(value, bool) or value in (None, ""):
        raise _error("Numeric module values cannot be blank or boolean.", "MODULE_VALUE_REQUIRED")
    try:
        parsed = Decimal(str(value).strip())
    except (InvalidOperation, AttributeError) as exc:
        raise _error("Numeric module values must be numeric.", "MODULE_VALUE_TYPE_INVALID") from exc
    if not parsed.is_finite():
        raise _error("Numeric module values must be finite.", "MODULE_VALUE_NONFINITE")
    contract = definition.validation_contract
    if definition.data_type == "number" and contract.get("integer") is True and parsed != parsed.to_integral_value():
        raise _error("This module accepts integer values only.", "MODULE_INTEGER_REQUIRED")
    decimals = contract.get("decimal_places")
    if decimals is not None:
        try:
            places = int(decimals)
        except (TypeError, ValueError) as exc:
            raise _error("decimal_places must be an integer.", "MODULE_VALIDATION_INVALID") from exc
        quantum = Decimal(1).scaleb(-places)
        if parsed.quantize(quantum) != parsed:
            raise _error("Value exceeds the module decimal precision.", "MODULE_VALUE_PRECISION_INVALID")
    number = float(parsed)
    minimum = contract.get("minimum")
    maximum = contract.get("maximum")
    if minimum is not None and number < _finite_number(minimum, "minimum"):
        raise _error("Value is below the module minimum.", "MODULE_VALUE_OUT_OF_RANGE")
    if maximum is not None and number > _finite_number(maximum, "maximum"):
        raise _error("Value is above the module maximum.", "MODULE_VALUE_OUT_OF_RANGE")
    return int(parsed) if parsed == parsed.to_integral_value() else number


def normalize_value(value: Any, definition: "ModuleDefinition") -> Any:
    if definition.data_type in {"number", "quantity", "rating", "duration"}:
        return _normalize_numeric(value, definition)
    if definition.data_type == "boolean":
        if not isinstance(value, bool):
            raise _error("Boolean module values must be boolean.", "MODULE_VALUE_TYPE_INVALID")
        return value
    if definition.data_type == "enum":
        value = str(value or "").strip()
        if not value or value not in definition.validation_contract.get("options", []):
            raise _error("Enum value is not in the module option list.", "MODULE_ENUM_VALUE_INVALID")
        return value
    if definition.data_type == "structured":
        if not isinstance(value, dict):
            raise _error("Structured module values must be objects.", "MODULE_VALUE_TYPE_INVALID")
        return copy.deepcopy(value)
    text = str(value or "").strip()
    if not text:
        raise _error("Text module values cannot be blank.", "MODULE_VALUE_REQUIRED")
    maximum = int(definition.validation_contract.get("max_length", 2000) or 2000)
    if len(text) > maximum:
        raise _error("Text module value is too long.", "MODULE_VALUE_TOO_LONG")
    return text


@dataclass
class ModuleDefinition:
    module_id: str
    label: str
    aliases: list[str]
    category_id: str
    data_type: str
    actual_unit: str
    display_unit: str
    definition_version: int
    status: str
    capabilities: dict[str, bool]
    validation_contract: dict[str, Any]
    recording_behavior: dict[str, str]
    presentation: dict[str, Any]
    renderer: str | None = None
    definition_history: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any], *, allowed_categories: set[str] | None = None) -> "ModuleDefinition":
        if not isinstance(raw, dict):
            raise _error("Module definition must be an object.", "MODULE_DEFINITION_INVALID")
        module_id = str(raw.get("module_id", "")).strip()
        if not MODULE_ID_RE.fullmatch(module_id):
            raise _error("module_id must be stable lowercase snake_case.", "MODULE_ID_INVALID", {"module_id": module_id})
        label = str(raw.get("label", "")).strip()
        if not label:
            raise _error("Module label is required.", "MODULE_LABEL_REQUIRED", {"module_id": module_id})
        category_id = str(raw.get("category_id", "")).strip()
        category_ids = KNOWN_CATEGORIES if allowed_categories is None else set(allowed_categories)
        if category_id not in category_ids:
            raise _error("Module category is not registered.", "MODULE_CATEGORY_UNKNOWN", {"module_id": module_id, "category_id": category_id})
        data_type = str(raw.get("data_type", "")).strip().lower()
        if data_type not in SUPPORTED_DATA_TYPES:
            raise _error("Module data_type is unsupported.", "MODULE_DATA_TYPE_UNSUPPORTED", {"module_id": module_id, "data_type": data_type})
        aliases = raw.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        if not isinstance(aliases, list):
            raise _error("Module aliases must be a list.", "MODULE_ALIASES_INVALID", {"module_id": module_id})
        aliases = list(dict.fromkeys(str(item).strip() for item in aliases if str(item).strip()))
        actual_unit = str(raw.get("actual_unit", "")).strip()
        display_unit = str(raw.get("display_unit", actual_unit)).strip()
        if data_type in {"quantity", "duration"} and not actual_unit:
            raise _error("Quantity and duration modules require actual_unit.", "MODULE_UNIT_REQUIRED", {"module_id": module_id})
        if actual_unit and not re.fullmatch(r"[A-Za-z0-9%µμ°/._\-\s一-鿿]+", actual_unit):
            raise _error("actual_unit contains unsupported characters.", "MODULE_UNIT_INVALID", {"module_id": module_id})
        try:
            version = int(raw.get("definition_version", 1))
        except (TypeError, ValueError) as exc:
            raise _error("definition_version must be an integer.", "MODULE_VERSION_INVALID", {"module_id": module_id}) from exc
        if version < 1:
            raise _error("definition_version must be positive.", "MODULE_VERSION_INVALID", {"module_id": module_id})
        status = str(raw.get("status", "active")).strip().lower()
        if status not in SUPPORTED_STATUSES:
            raise _error("Module status is unsupported.", "MODULE_STATUS_INVALID", {"module_id": module_id, "status": status})
        capabilities = copy.deepcopy(DEFAULT_CAPABILITIES)
        supplied_capabilities = raw.get("capabilities", {})
        if not isinstance(supplied_capabilities, dict):
            raise _error("Module capabilities must be an object.", "MODULE_CAPABILITIES_INVALID", {"module_id": module_id})
        for key, value in supplied_capabilities.items():
            if key not in capabilities or not isinstance(value, bool):
                raise _error("Module capability is unknown or not boolean.", "MODULE_CAPABILITY_INVALID", {"module_id": module_id, "capability": key})
            capabilities[key] = value
        validation = copy.deepcopy(raw.get("validation_contract", {}))
        if not isinstance(validation, dict):
            raise _error("validation_contract must be an object.", "MODULE_VALIDATION_INVALID", {"module_id": module_id})
        if data_type in {"number", "quantity", "rating", "duration"}:
            for key in ("minimum", "maximum"):
                if key in validation:
                    _finite_number(validation[key], key)
            if validation.get("minimum") is not None and validation.get("maximum") is not None and float(validation["minimum"]) > float(validation["maximum"]):
                raise _error("minimum must not exceed maximum.", "MODULE_VALIDATION_RANGE_INVALID", {"module_id": module_id})
            if "decimal_places" in validation:
                try:
                    places = int(validation["decimal_places"])
                except (TypeError, ValueError) as exc:
                    raise _error("decimal_places must be an integer.", "MODULE_VALIDATION_INVALID", {"module_id": module_id}) from exc
                if places < 0 or places > 8:
                    raise _error("decimal_places is outside the supported range.", "MODULE_VALIDATION_INVALID", {"module_id": module_id})
        behaviour = copy.deepcopy(raw.get("recording_behavior", {"kind": "scalar", "cardinality": "one_per_day"}))
        if isinstance(behaviour, str):
            behaviour = {"kind": behaviour, "cardinality": "one_per_day"}
        if not isinstance(behaviour, dict):
            raise _error("recording_behavior must be an object.", "MODULE_RECORDING_BEHAVIOR_INVALID", {"module_id": module_id})
        kind = str(behaviour.get("kind", "scalar")).strip().lower()
        cardinality = str(behaviour.get("cardinality", "one_per_day")).strip().lower()
        if kind not in SUPPORTED_RECORDING_KINDS or cardinality not in SUPPORTED_CARDINALITIES:
            raise _error("recording_behavior is outside the bounded extension contract.", "MODULE_RECORDING_BEHAVIOR_INVALID", {"module_id": module_id})
        behaviour = {"kind": kind, "cardinality": cardinality}
        presentation = copy.deepcopy(raw.get("presentation", {}))
        if not isinstance(presentation, dict):
            raise _error("presentation must be an object.", "MODULE_PRESENTATION_INVALID", {"module_id": module_id})
        allowed_presentation = {"section", "slot", "order", "visible_by_default", "renderer", "fallback", "unsupported_behavior"}
        if set(presentation) - allowed_presentation:
            raise _error("Module presentation may only use semantic placement fields.", "MODULE_PRESENTATION_INVALID", {"module_id": module_id, "unknown_fields": sorted(set(presentation) - allowed_presentation)})
        section = str(presentation.get("section", "extension")).strip()
        slot = str(presentation.get("slot", "summary")).strip()
        try:
            order = int(presentation.get("order", 0))
        except (TypeError, ValueError) as exc:
            raise _error("presentation.order must be an integer.", "MODULE_PRESENTATION_INVALID", {"module_id": module_id}) from exc
        if section not in KNOWN_PRESENTATION_SECTIONS or slot not in KNOWN_PRESENTATION_SLOTS or order < 0:
            raise _error("Module presentation section/slot/order is unsupported.", "MODULE_PRESENTATION_INVALID", {"module_id": module_id})
        renderer = presentation.get("renderer", raw.get("renderer"))
        renderer = str(renderer).strip() if renderer not in (None, "") else None
        if renderer and renderer not in SUPPORTED_RENDERERS:
            raise _error("Module renderer is unsupported.", "MODULE_RENDERER_UNSUPPORTED", {"module_id": module_id, "renderer": renderer})
        if capabilities["mini_program_visible"] and renderer not in SUPPORTED_RENDERERS:
            raise _error("Mini Program visibility requires a supported renderer.", "MODULE_MINI_RENDERER_REQUIRED", {"module_id": module_id})
        if capabilities["cloud_syncable"] and not capabilities["exportable"]:
            raise _error("Cloud-syncable modules must be exportable.", "MODULE_CLOUD_CONTRACT_INVALID", {"module_id": module_id})
        if capabilities["analysis_visible"] and not capabilities["exportable"]:
            raise _error("Analysis-visible modules must be exportable.", "MODULE_ANALYSIS_CONTRACT_INVALID", {"module_id": module_id})
        if not capabilities["recordable"] and status == "active":
            raise _error("An active module must be recordable or explicitly inactive/retired.", "MODULE_CAPABILITY_INVALID", {"module_id": module_id})
        fallback = str(presentation.get("fallback", "empty_state")).strip().lower()
        unsupported_behavior = str(presentation.get("unsupported_behavior", "hide")).strip().lower()
        if fallback not in SUPPORTED_PRESENTATION_FALLBACKS or unsupported_behavior not in SUPPORTED_UNSUPPORTED_BEHAVIORS:
            raise _error("Module presentation fallback/unsupported behavior is invalid.", "MODULE_PRESENTATION_FALLBACK_INVALID", {"module_id": module_id})
        presentation = {
            "section": section,
            "slot": slot,
            "order": order,
            "visible_by_default": _bool(presentation.get("visible_by_default"), True),
            "renderer": renderer,
            "fallback": fallback,
            "unsupported_behavior": unsupported_behavior,
        }
        history = raw.get("definition_history", [])
        if not isinstance(history, list) or not all(isinstance(item, dict) for item in history):
            raise _error("definition_history must be a list of snapshots.", "MODULE_VERSION_HISTORY_INVALID", {"module_id": module_id})
        return cls(
            module_id=module_id,
            label=label,
            aliases=aliases,
            category_id=category_id,
            data_type=data_type,
            actual_unit=actual_unit,
            display_unit=display_unit,
            definition_version=version,
            status=status,
            capabilities=capabilities,
            validation_contract=validation,
            recording_behavior=behaviour,
            presentation=presentation,
            renderer=renderer,
            definition_history=copy.deepcopy(history),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "label": self.label,
            "aliases": list(self.aliases),
            "category_id": self.category_id,
            "data_type": self.data_type,
            "actual_unit": self.actual_unit,
            "display_unit": self.display_unit,
            "definition_version": self.definition_version,
            "status": self.status,
            "capabilities": copy.deepcopy(self.capabilities),
            "validation_contract": copy.deepcopy(self.validation_contract),
            "recording_behavior": copy.deepcopy(self.recording_behavior),
            "presentation": copy.deepcopy(self.presentation),
            "definition_history": copy.deepcopy(self.definition_history),
        }

    def snapshot(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("definition_history", None)
        return value

    def alias_keys(self) -> set[str]:
        return {normalize_alias(value) for value in [self.label, *self.aliases] if normalize_alias(value)}

    def display_value(self, value: Any) -> Any:
        if self.data_type not in {"number", "quantity", "rating", "duration"}:
            return copy.deepcopy(value)
        conversion = self.validation_contract.get("display_conversion", {})
        try:
            scale = float(conversion.get("scale", 1))
            offset = float(conversion.get("offset", 0))
        except (TypeError, ValueError) as exc:
            raise _error("display_conversion is invalid.", "MODULE_DISPLAY_CONVERSION_INVALID", {"module_id": self.module_id}) from exc
        return round(_finite_number(value) * scale + offset, 8)


class ModuleRegistry:
    """Validated source of truth for ordinary extension modules."""

    def __init__(self, definitions: Iterable[ModuleDefinition] = (), *, raw_issues: list[dict[str, Any]] | None = None, category_ids: set[str] | None = None):
        self._definitions: dict[str, ModuleDefinition] = {}
        self.raw_issues = list(raw_issues or [])
        self.category_ids = set(KNOWN_CATEGORIES if category_ids is None else category_ids)
        for definition in definitions:
            self.register(definition)

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, strict: bool = True, category_ids: set[str] | None = None) -> "ModuleRegistry":
        if not isinstance(payload, dict):
            raise _error("Module registry root must be an object.", "MODULE_REGISTRY_INVALID")
        raw_modules = payload.get("modules", [])
        if not isinstance(raw_modules, list):
            raise _error("Module registry modules must be a list.", "MODULE_REGISTRY_INVALID")
        registry = cls(category_ids=category_ids)
        for index, raw in enumerate(raw_modules):
            try:
                registry.register(ModuleDefinition.from_dict(raw, allowed_categories=registry.category_ids))
            except DataModuleError as exc:
                issue = {"severity": "high", "area": "Data Modules", "issue": exc.code, "action": str(exc), "target_type": "definition", "target_id": str(raw.get("module_id", index) if isinstance(raw, dict) else index), "details": copy.deepcopy(exc.details)}
                registry.raw_issues.append(issue)
                if strict:
                    raise
        return registry

    @classmethod
    def from_file(cls, path: Path, *, strict: bool = True, category_ids: set[str] | None = None) -> "ModuleRegistry":
        path = Path(path)
        if not path.exists():
            if strict:
                raise _error("Module registry file does not exist.", "MODULE_REGISTRY_NOT_FOUND", {"path": str(path)})
            return cls()
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")), strict=strict, category_ids=category_ids)

    def register(self, definition: ModuleDefinition) -> ModuleDefinition:
        if definition.category_id not in self.category_ids:
            raise _error("Module category is not registered.", "MODULE_CATEGORY_UNKNOWN", {"module_id": definition.module_id, "category_id": definition.category_id})
        if definition.module_id in self._definitions:
            raise _error("Module ID already exists.", "MODULE_ID_DUPLICATE", {"module_id": definition.module_id})
        new_aliases = definition.alias_keys()
        for existing in self._definitions.values():
            conflict = sorted(new_aliases & existing.alias_keys())
            if conflict:
                raise _error("Module alias belongs to another module.", "MODULE_ALIAS_CONFLICT", {"module_id": definition.module_id, "conflict_with": existing.module_id, "aliases": conflict})
        self._definitions[definition.module_id] = copy.deepcopy(definition)
        return copy.deepcopy(definition)

    def require(self, module_id: str) -> ModuleDefinition:
        try:
            return copy.deepcopy(self._definitions[str(module_id)])
        except KeyError as exc:
            raise _error("Module definition was not found.", "MODULE_NOT_FOUND", {"module_id": str(module_id)}) from exc

    def get(self, module_id: str) -> ModuleDefinition | None:
        return copy.deepcopy(self._definitions.get(str(module_id)))

    def all(self, *, include_retired: bool = True) -> list[ModuleDefinition]:
        items = list(self._definitions.values())
        if not include_retired:
            items = [item for item in items if item.status != "retired"]
        return sorted((copy.deepcopy(item) for item in items), key=lambda item: (item.presentation["order"], item.label.casefold(), item.module_id))

    def active_recordable(self) -> list[ModuleDefinition]:
        return [item for item in self.all(include_retired=False) if item.status == "active" and item.capabilities["recordable"]]

    def lookup_alias(self, value: str, *, include_retired: bool = False) -> ModuleDefinition | None:
        key = normalize_alias(value)
        matches = [item for item in self.all(include_retired=include_retired) if key and key in item.alias_keys()]
        if len(matches) > 1:
            raise _error("Module alias is ambiguous.", "MODULE_ALIAS_AMBIGUOUS", {"alias": value, "module_ids": [item.module_id for item in matches]})
        return matches[0] if matches else None

    def capability_catalog(self) -> dict[str, Any]:
        return {
            "schema": "fitness-ledger-data-module-capabilities-v1",
            "modules": [
                {
                    "module_id": item.module_id,
                    "label": item.label,
                    "category_id": item.category_id,
                    "data_type": item.data_type,
                    "status": item.status,
                    "capabilities": copy.deepcopy(item.capabilities),
                    "renderer": item.renderer,
                }
                for item in self.all()
            ],
        }

    def to_dict(self) -> dict[str, Any]:
        return {"schema_version": "fitness-ledger-data-module-registry-v1", "modules": [item.to_dict() for item in self.all()]}

    def clone(self) -> "ModuleRegistry":
        return ModuleRegistry(self.all(), raw_issues=copy.deepcopy(self.raw_issues), category_ids=set(self.category_ids))

    def preview_update(self, module_id: str, changes: dict[str, Any], *, allow_actual_unit_change: bool = False) -> tuple[ModuleDefinition, ModuleDefinition]:
        current = self.require(module_id)
        if "module_id" in changes and str(changes["module_id"]) != current.module_id:
            raise _error("module_id is immutable.", "MODULE_ID_IMMUTABLE", {"module_id": module_id})
        if "actual_unit" in changes and str(changes["actual_unit"]).strip() != current.actual_unit and not allow_actual_unit_change:
            raise _error("Actual unit changes require an explicit migration.", "MODULE_ACTUAL_UNIT_MIGRATION_REQUIRED", {"module_id": module_id})
        updated = current.to_dict()
        updated.update(copy.deepcopy(changes))
        updated["definition_version"] = current.definition_version + (1 if any(key != "module_id" and changes[key] != current.to_dict().get(key) for key in changes) else 0)
        if updated["definition_version"] > current.definition_version:
            updated["definition_history"] = [*current.definition_history, current.snapshot()]
        candidate = ModuleDefinition.from_dict(updated, allowed_categories=self.category_ids)
        other = [item for item in self.all() if item.module_id != module_id]
        check = ModuleRegistry(other, category_ids=set(self.category_ids))
        check.register(candidate)
        return current, candidate

    def update(self, module_id: str, changes: dict[str, Any], *, allow_actual_unit_change: bool = False) -> ModuleDefinition:
        _current, candidate = self.preview_update(module_id, changes, allow_actual_unit_change=allow_actual_unit_change)
        self._definitions[module_id] = candidate
        return copy.deepcopy(candidate)

    def replace_fixture_definition(self, definition: ModuleDefinition) -> ModuleDefinition:
        """Replace one definition after a fixture migration plan has been validated."""
        if definition.module_id not in self._definitions:
            raise _error("Module definition was not found.", "MODULE_NOT_FOUND", {"module_id": definition.module_id})
        others = [item for item in self.all() if item.module_id != definition.module_id]
        check = ModuleRegistry(others, category_ids=set(self.category_ids))
        check.register(definition)
        self._definitions[definition.module_id] = copy.deepcopy(definition)
        return copy.deepcopy(definition)

    def data_check_issues(self) -> list[dict[str, Any]]:
        issues = list(self.raw_issues)
        for item in self.all():
            if item.status == "retired" and item.capabilities["recordable"]:
                issues.append(self._issue("medium", "definition", item.module_id, "retired module remains recordable", "Set recordable=false or explicitly re-enable the module."))
            if item.capabilities["mini_program_visible"] and item.renderer not in SUPPORTED_RENDERERS:
                issues.append(self._issue("high", "capability", item.module_id, "mini_program_visible requires a supported renderer", "Choose single_metric or metric_history."))
        return sorted(issues, key=lambda row: (row["severity"], row["target_type"], row["target_id"], row["issue"]))

    @staticmethod
    def _issue(severity: str, target_type: str, target_id: str, issue: str, action: str) -> dict[str, Any]:
        return {"severity": severity, "date": "", "area": "Data Modules", "issue": issue, "action": action, "target_type": target_type, "target_id": str(target_id), "module_id": str(target_id)}


@dataclass
class CategoryDefinition:
    category_id: str
    label: str
    order: int
    status: str = "active"
    system: bool = False
    presentation: dict[str, Any] = field(default_factory=dict)
    definition_version: int = 1
    definition_history: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "CategoryDefinition":
        if not isinstance(raw, dict):
            raise _error("Category definition must be an object.", "CATEGORY_DEFINITION_INVALID")
        category_id = str(raw.get("category_id", "")).strip()
        if not MODULE_ID_RE.fullmatch(category_id):
            raise _error("category_id must be stable lowercase snake_case.", "CATEGORY_ID_INVALID", {"category_id": category_id})
        label = str(raw.get("label", "")).strip()
        if not label:
            raise _error("Category label is required.", "CATEGORY_LABEL_REQUIRED", {"category_id": category_id})
        try:
            order = int(raw.get("order", 0))
            version = int(raw.get("definition_version", 1))
        except (TypeError, ValueError) as exc:
            raise _error("Category order and definition_version must be integers.", "CATEGORY_METADATA_INVALID", {"category_id": category_id}) from exc
        status = str(raw.get("status", "active")).strip().lower()
        if status not in {"active", "retired"}:
            raise _error("Category status is unsupported.", "CATEGORY_STATUS_INVALID", {"category_id": category_id})
        if order < 0 or version < 1:
            raise _error("Category order/version is invalid.", "CATEGORY_METADATA_INVALID", {"category_id": category_id})
        presentation = copy.deepcopy(raw.get("presentation", {}))
        if not isinstance(presentation, dict):
            raise _error("Category presentation must be an object.", "CATEGORY_PRESENTATION_INVALID", {"category_id": category_id})
        allowed_presentation = {"template", "section", "slot", "order", "visible_by_default", "renderer", "fallback", "unsupported_behavior", "semantic"}
        if set(presentation) - allowed_presentation:
            raise _error("Category presentation may only use semantic placement fields.", "CATEGORY_PRESENTATION_INVALID", {"category_id": category_id, "unknown_fields": sorted(set(presentation) - allowed_presentation)})
        history = raw.get("definition_history", [])
        if not isinstance(history, list) or not all(isinstance(item, dict) for item in history):
            raise _error("Category definition_history must be a list.", "CATEGORY_VERSION_HISTORY_INVALID", {"category_id": category_id})
        return cls(category_id, label, order, status, bool(raw.get("system", False)), presentation, version, copy.deepcopy(history))

    def to_dict(self) -> dict[str, Any]:
        return {
            "category_id": self.category_id,
            "label": self.label,
            "order": self.order,
            "status": self.status,
            "system": self.system,
            "presentation": copy.deepcopy(self.presentation),
            "definition_version": self.definition_version,
            "definition_history": copy.deepcopy(self.definition_history),
        }

    def snapshot(self) -> dict[str, Any]:
        value = self.to_dict()
        value.pop("definition_history", None)
        return value


class CategoryRegistry:
    def __init__(self, definitions: Iterable[CategoryDefinition] = (), *, raw_issues: list[dict[str, Any]] | None = None):
        self._definitions: dict[str, CategoryDefinition] = {}
        self.raw_issues = list(raw_issues or [])
        for definition in definitions:
            self.register(definition)

    @classmethod
    def from_dict(cls, payload: dict[str, Any], *, strict: bool = True) -> "CategoryRegistry":
        raw_categories = payload.get("categories", []) if isinstance(payload, dict) else []
        if not isinstance(raw_categories, list):
            raise _error("Category registry categories must be a list.", "CATEGORY_REGISTRY_INVALID")
        registry = cls()
        for index, raw in enumerate(raw_categories):
            try:
                registry.register(CategoryDefinition.from_dict(raw))
            except DataModuleError as exc:
                issue = {"severity": "high", "area": "Data Modules", "issue": exc.code, "action": str(exc), "target_type": "category", "target_id": str(raw.get("category_id", index) if isinstance(raw, dict) else index), "details": copy.deepcopy(exc.details)}
                registry.raw_issues.append(issue)
                if strict:
                    raise
        return registry

    @classmethod
    def defaults(cls) -> "CategoryRegistry":
        return cls(CategoryDefinition.from_dict(item) for item in DEFAULT_CATEGORIES)

    def register(self, definition: CategoryDefinition) -> CategoryDefinition:
        if definition.category_id in self._definitions:
            raise _error("Category ID already exists.", "CATEGORY_ID_DUPLICATE", {"category_id": definition.category_id})
        self._definitions[definition.category_id] = copy.deepcopy(definition)
        return copy.deepcopy(definition)

    def require(self, category_id: str) -> CategoryDefinition:
        try:
            return copy.deepcopy(self._definitions[str(category_id)])
        except KeyError as exc:
            raise _error("Category definition was not found.", "CATEGORY_NOT_FOUND", {"category_id": str(category_id)}) from exc

    def get(self, category_id: str) -> CategoryDefinition | None:
        return copy.deepcopy(self._definitions.get(str(category_id)))

    def all(self) -> list[CategoryDefinition]:
        return sorted((copy.deepcopy(item) for item in self._definitions.values()), key=lambda item: (item.order, item.label.casefold(), item.category_id))

    def clone(self) -> "CategoryRegistry":
        return CategoryRegistry(self.all(), raw_issues=copy.deepcopy(self.raw_issues))

    def preview_update(self, category_id: str, changes: dict[str, Any]) -> tuple[CategoryDefinition, CategoryDefinition]:
        current = self.require(category_id)
        if "category_id" in changes and str(changes["category_id"]) != current.category_id:
            raise _error("category_id is immutable.", "CATEGORY_ID_IMMUTABLE", {"category_id": category_id})
        updated = current.to_dict()
        updated.update(copy.deepcopy(changes))
        changed = any(key != "category_id" and changes[key] != current.to_dict().get(key) for key in changes)
        updated["definition_version"] = current.definition_version + (1 if changed else 0)
        if changed:
            updated["definition_history"] = [*current.definition_history, current.snapshot()]
        candidate = CategoryDefinition.from_dict(updated)
        return current, candidate

    def update(self, category_id: str, changes: dict[str, Any]) -> CategoryDefinition:
        _current, candidate = self.preview_update(category_id, changes)
        self._definitions[category_id] = candidate
        return copy.deepcopy(candidate)

    def to_dict(self) -> dict[str, Any]:
        return {"categories": [item.to_dict() for item in self.all()]}


def _generated_module_id(label: str, aliases: Iterable[str], category_id: str, existing: Iterable[str]) -> str:
    identity = {"label": str(label).strip(), "aliases": list(aliases), "category_id": category_id}
    base = f"module_{stable_hash(identity)[:12]}"
    candidate = base
    index = 2
    known = set(existing)
    while candidate in known:
        candidate = f"{base}_{index}"
        index += 1
    return candidate


class DataModuleDefinitionStore:
    """Authoritative Candidate-only persistence for categories and definitions."""

    SCHEMA = "fitness-ledger-data-module-definition-store-v1"

    def __init__(self, path: Path, *, backup_dir: Path | None = None, seed_payload: dict[str, Any] | None = None):
        self.path = Path(path)
        self.backup_dir = Path(backup_dir) if backup_dir else self.path.parent / "definition_backups"
        self.seed_payload = copy.deepcopy(seed_payload)

    @classmethod
    def seed_from_registry_file(cls, path: Path) -> dict[str, Any]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        modules = raw.get("modules", []) if isinstance(raw, dict) else []
        return {"schema": cls.SCHEMA, "categories": copy.deepcopy(DEFAULT_CATEGORIES), "modules": copy.deepcopy(modules)}

    @classmethod
    def initialize(cls, path: Path, seed_registry_file: Path, *, backup_dir: Path | None = None) -> "DataModuleDefinitionStore":
        store = cls(path, backup_dir=backup_dir, seed_payload=cls.seed_from_registry_file(seed_registry_file))
        store._write_atomic(store.seed_payload)
        return store

    def _read_payload(self, *, strict: bool = True) -> dict[str, Any]:
        if not self.path.exists():
            if self.seed_payload is None:
                raise _error("Definition store file does not exist.", "DEFINITION_STORE_NOT_FOUND", {"path": str(self.path)})
            return copy.deepcopy(self.seed_payload)
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as exc:
            if strict:
                raise _error("Definition store JSON is corrupted.", "DEFINITION_STORE_CORRUPT", {"path": str(self.path)}) from exc
            return {"schema": self.SCHEMA, "categories": [], "modules": [], "_raw_issues": [{"severity": "high", "area": "Data Modules", "issue": "DEFINITION_STORE_CORRUPT", "action": "Restore a valid Candidate definition store.", "target_type": "store", "target_id": str(self.path)}]}
        if not isinstance(payload, dict):
            raise _error("Definition store root must be an object.", "DEFINITION_STORE_INVALID")
        if payload.get("schema") not in {None, self.SCHEMA, "fitness-ledger-data-module-registry-v1"}:
            raise _error("Definition store schema is unsupported.", "DEFINITION_STORE_SCHEMA_INVALID")
        payload.setdefault("categories", copy.deepcopy(DEFAULT_CATEGORIES))
        payload.setdefault("modules", [])
        return payload

    def load(self, *, strict: bool = False) -> tuple[CategoryRegistry, ModuleRegistry, list[dict[str, Any]]]:
        payload = self._read_payload(strict=strict)
        categories = CategoryRegistry.from_dict(payload, strict=strict)
        category_ids = {item.category_id for item in categories.all()}
        modules = ModuleRegistry.from_dict(payload, strict=strict, category_ids=category_ids)
        issues = [*payload.get("_raw_issues", []), *categories.raw_issues, *modules.raw_issues]
        return categories, modules, issues

    def snapshot(self, *, strict: bool = True) -> dict[str, Any]:
        categories, modules, issues = self.load(strict=strict)
        if strict and issues:
            raise _error("Definition store contains invalid definitions.", "DEFINITION_STORE_INVALID", {"issues": issues})
        return {"schema": self.SCHEMA, "categories": [item.to_dict() for item in categories.all()], "modules": [item.to_dict() for item in modules.all()]}

    def fingerprint(self) -> str:
        return stable_hash(self._read_payload(strict=False))

    def _candidate_payload(self, categories: CategoryRegistry, modules: ModuleRegistry) -> dict[str, Any]:
        return {"schema": self.SCHEMA, "categories": [item.to_dict() for item in categories.all()], "modules": [item.to_dict() for item in modules.all()]}

    def preview_create_category(self, values: dict[str, Any]) -> dict[str, Any]:
        categories, modules, _issues = self.load(strict=True)
        category_id = str(values.get("category_id", "")).strip()
        label = str(values.get("label", "")).strip()
        if not category_id:
            identity = {"label": label, "existing": [item.category_id for item in categories.all()]}
            category_id = f"category_{stable_hash(identity)[:12]}"
        raw = {"category_id": category_id, "label": label, "order": values.get("order", (categories.all()[-1].order + 10) if categories.all() else 10), "status": "active", "system": False, "presentation": values.get("presentation", {"template": "extension"})}
        candidate = CategoryDefinition.from_dict(raw)
        check = categories.clone()
        check.register(candidate)
        return {"schema": "fitness-ledger-category-definition-preview-v1", "kind": "category", "status": "preview_ready", "write_attempted": False, "source_fingerprint": self.fingerprint(), "after": self._candidate_payload(check, modules)}

    def preview_create_module(self, values: dict[str, Any]) -> dict[str, Any]:
        categories, modules, _issues = self.load(strict=True)
        category_id = str(values.get("category_id", "")).strip()
        category = categories.require(category_id)
        if category.status != "active":
            raise _error("Retired categories cannot receive new modules.", "CATEGORY_NOT_RECORDABLE", {"category_id": category_id})
        label = str(values.get("label", "")).strip()
        aliases = values.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        aliases = list(dict.fromkeys([label, *(str(item).strip() for item in aliases if str(item).strip())]))
        module_id = str(values.get("module_id", "")).strip() or _generated_module_id(label, aliases, category_id, [item.module_id for item in modules.all()])
        data_type = str(values.get("data_type", "quantity")).strip().lower()
        renderer = str(values.get("renderer", "single_metric")).strip()
        recording_kind = str(values.get("recording_kind", "scalar")).strip().lower()
        cardinality = str(values.get("cardinality", "one_per_day")).strip().lower()
        if recording_kind != "scalar" or cardinality != "one_per_day":
            raise _error("Only scalar one-per-day recording is implemented in this Candidate.", "MODULE_RECORDING_BEHAVIOR_NOT_IMPLEMENTED", {"kind": recording_kind, "cardinality": cardinality})
        capabilities = copy.deepcopy(DEFAULT_CAPABILITIES)
        supplied = values.get("capabilities", {})
        if not isinstance(supplied, dict):
            raise _error("capabilities must be an object.", "MODULE_CAPABILITIES_INVALID")
        capabilities.update(supplied)
        supplied_presentation = values.get("presentation", {})
        if not isinstance(supplied_presentation, dict):
            raise _error("presentation must be an object.", "MODULE_PRESENTATION_INVALID")
        presentation = {
            "section": str(values.get("section", "extension")),
            "slot": str(values.get("slot", "summary")),
            "order": int(values.get("order", 0) or 0),
            "visible_by_default": bool(values.get("visible_by_default", True)),
            "renderer": renderer,
        }
        presentation.update(copy.deepcopy(supplied_presentation))
        raw = {
            "module_id": module_id,
            "label": label,
            "aliases": aliases,
            "category_id": category_id,
            "data_type": data_type,
            "actual_unit": str(values.get("actual_unit", "")).strip(),
            "display_unit": str(values.get("display_unit", values.get("actual_unit", ""))).strip(),
            "definition_version": 1,
            "status": "active",
            "capabilities": capabilities,
            "validation_contract": {key: values[key] for key in ("minimum", "maximum", "decimal_places") if key in values and values[key] not in ("", None)},
            "recording_behavior": {"kind": recording_kind, "cardinality": cardinality},
            "presentation": presentation,
        }
        candidate = ModuleDefinition.from_dict(raw, allowed_categories={item.category_id for item in categories.all()})
        check = modules.clone()
        check.register(candidate)
        return {"schema": "fitness-ledger-module-definition-preview-v1", "kind": "module", "status": "preview_ready", "write_attempted": False, "source_fingerprint": self.fingerprint(), "after": self._candidate_payload(categories, check)}

    def preview_update_module(self, module_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        categories, modules, _issues = self.load(strict=True)
        current = modules.require(module_id)
        changes = copy.deepcopy(changes)
        presentation_keys = {"renderer", "section", "slot", "order", "visible_by_default", "fallback", "unsupported_behavior"}
        if presentation_keys & set(changes):
            presentation = copy.deepcopy(current.presentation)
            for key in presentation_keys:
                if key in changes:
                    presentation[key] = changes.pop(key)
            changes["presentation"] = presentation
        validation_keys = {"minimum", "maximum", "decimal_places"}
        if validation_keys & set(changes):
            validation = copy.deepcopy(current.validation_contract)
            for key in validation_keys:
                if key in changes:
                    value = changes.pop(key)
                    if value in (None, ""):
                        validation.pop(key, None)
                    else:
                        validation[key] = value
            changes["validation_contract"] = validation
        if isinstance(changes.get("capabilities"), dict):
            merged_capabilities = copy.deepcopy(current.capabilities)
            merged_capabilities.update(changes["capabilities"])
            changes["capabilities"] = merged_capabilities
        if "category_id" in changes:
            category = categories.require(str(changes["category_id"]))
            if category.status != "active":
                raise _error("A module cannot move into a retired category.", "CATEGORY_NOT_RECORDABLE", {"category_id": category.category_id})
        _current, candidate = modules.preview_update(module_id, changes)
        check = modules.clone()
        check._definitions[module_id] = candidate
        return {"schema": "fitness-ledger-module-definition-preview-v1", "kind": "module", "status": "preview_ready", "write_attempted": False, "source_fingerprint": self.fingerprint(), "after": self._candidate_payload(categories, check)}

    def preview_update_category(self, category_id: str, changes: dict[str, Any]) -> dict[str, Any]:
        categories, modules, _issues = self.load(strict=True)
        _current, candidate = categories.preview_update(category_id, changes)
        check = categories.clone()
        check._definitions[category_id] = candidate
        return {"schema": "fitness-ledger-category-definition-preview-v1", "kind": "category", "status": "preview_ready", "write_attempted": False, "source_fingerprint": self.fingerprint(), "after": self._candidate_payload(check, modules)}

    def commit_preview(self, preview: dict[str, Any], *, confirmed: bool = False) -> dict[str, Any]:
        if not confirmed:
            raise _error("A confirmed definition preview is required before saving.", "DEFINITION_CONFIRMATION_REQUIRED")
        if not isinstance(preview, dict) or preview.get("status") != "preview_ready":
            raise _error("Only a valid definition preview can be saved.", "DEFINITION_PREVIEW_REQUIRED")
        if self.fingerprint() != str(preview.get("source_fingerprint", "")):
            raise _error("Definition preview is stale; re-run preview.", "DEFINITION_PREVIEW_STALE")
        after = preview.get("after")
        if not isinstance(after, dict):
            raise _error("Definition preview has no candidate payload.", "DEFINITION_PREVIEW_INVALID")
        CategoryRegistry.from_dict(after, strict=True)
        category_ids = {str(item.get("category_id")) for item in after.get("categories", [])}
        ModuleRegistry.from_dict(after, strict=True, category_ids=category_ids)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        checkpoint = self.backup_dir / f"definition_checkpoint_{uuid.uuid4().hex}.json"
        if self.path.exists():
            shutil.copy2(self.path, checkpoint)
        try:
            self._write_atomic(after)
        except Exception:
            if checkpoint.exists():
                shutil.copy2(checkpoint, self.path)
            raise
        return {"status": "UPDATED", "changed": True, "write_attempted": True, "checkpoint": str(checkpoint) if checkpoint.exists() else "", "definition_fingerprint": self.fingerprint()}

    def _write_atomic(self, payload: dict[str, Any]) -> None:
        _write_json_atomic(self.path, payload)

    def catalog(self) -> dict[str, Any]:
        categories, modules, issues = self.load(strict=False)
        return {"schema": "fitness-ledger-data-module-catalog-v1", "categories": [item.to_dict() for item in categories.all()], "modules": [item.to_dict() for item in modules.all()], "issues": issues, "source_fingerprint": self.fingerprint()}


@dataclass
class ParseCandidate:
    module_id: str
    date: str
    value: Any
    raw_text: str
    matched_alias: str
    unit_hint: str = ""
    warnings: list[str] = field(default_factory=list)
    status: str = "candidate"

    def to_dict(self) -> dict[str, Any]:
        return {
            "module_id": self.module_id,
            "date": self.date,
            "value": copy.deepcopy(self.value),
            "raw_text": self.raw_text,
            "matched_alias": self.matched_alias,
            "unit_hint": self.unit_hint,
            "warnings": list(self.warnings),
            "status": self.status,
        }


class RegistryDrivenParser:
    """Recognizes candidates from registry aliases; no module-specific branches."""

    def __init__(self, registry: ModuleRegistry):
        self.registry = registry

    def parse(self, raw_text: str, record_date: str | None = None) -> list[ParseCandidate]:
        raw = str(raw_text or "").strip()
        if not raw:
            raise _error("Data Module input is empty.", "MODULE_RAW_EMPTY")
        resolved_date = record_date or self._date_from_text(raw)
        if not resolved_date:
            raise _error("Data Module input requires a record date.", "MODULE_DATE_REQUIRED")
        resolved_date = validate_iso_date(resolved_date)
        occurrences: list[tuple[int, int, ModuleDefinition, str]] = []
        for definition in self.registry.active_recordable():
            for alias in [definition.label, *definition.aliases]:
                if not alias:
                    continue
                for match in re.finditer(re.escape(alias), raw, flags=re.IGNORECASE):
                    occurrences.append((match.start(), match.end(), definition, alias))
        occurrences.sort(key=lambda row: (row[0], -(row[1] - row[0]), row[2].module_id))
        selected: list[tuple[int, int, ModuleDefinition, str]] = []
        occupied_until = -1
        for occurrence in occurrences:
            if occurrence[0] >= occupied_until:
                selected.append(occurrence)
                occupied_until = occurrence[1]
        candidates = []
        for index, (start, end, definition, alias) in enumerate(selected):
            segment_end = selected[index + 1][0] if index + 1 < len(selected) else len(raw)
            segment = raw[end:segment_end]
            value, unit_hint = self._value_from_segment(segment, definition)
            candidates.append(ParseCandidate(definition.module_id, resolved_date, value, raw, alias, unit_hint))
        if not candidates:
            raise _error("No active recordable Data Module alias was recognized.", "MODULE_NOT_RECOGNIZED")
        return candidates

    @staticmethod
    def _date_from_text(raw: str) -> str | None:
        match = DATE_RE.search(raw)
        if not match:
            if re.search(r"(?:今天|today)", raw, flags=re.IGNORECASE):
                return date.today().isoformat()
            return None
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3))).isoformat()
        except ValueError as exc:
            raise _error("Data Module input contains an invalid date.", "MODULE_DATE_INVALID") from exc

    @staticmethod
    def _value_from_segment(segment: str, definition: ModuleDefinition) -> tuple[Any, str]:
        if definition.data_type in {"number", "quantity", "rating", "duration"}:
            match = NUMBER_RE.search(segment)
            if not match:
                raise _error("A numeric value was not found after the module alias.", "MODULE_VALUE_MISSING", {"module_id": definition.module_id})
            value_text = match.group(0)
            value: Any = float(value_text)
            if value.is_integer():
                value = int(value)
            tail = segment[match.end():].strip()
            unit_hint = re.match(r"([A-Za-z%µμ]+)", tail)
            return value, unit_hint.group(1) if unit_hint else ""
        value = segment.strip().split()[0] if segment.strip() else ""
        return value, ""


def _record_id(module_id: str, record_date: str, ordinal: int = 0) -> str:
    return f"dm:{module_id}:{record_date}:{ordinal}"


class DataModuleEngine:
    """Lifecycle engine for registry-driven ordinary modules."""

    def __init__(self, registry: ModuleRegistry, data_file: Path, dictionary_file: Path | None = None, backup_dir: Path | None = None, command_service: Any | None = None, category_registry: CategoryRegistry | None = None, definition_issues: list[dict[str, Any]] | None = None):
        self.registry = registry
        self.data_file = Path(data_file)
        self.dictionary_file = Path(dictionary_file) if dictionary_file else None
        self.backup_dir = Path(backup_dir) if backup_dir else self.data_file.parent / "backups"
        self.command_service = command_service
        self.category_registry = category_registry or CategoryRegistry(CategoryDefinition.from_dict(item) for item in DEFAULT_CATEGORIES if item["category_id"] in registry.category_ids)
        self.definition_issues = list(definition_issues or [])
        self.parser = RegistryDrivenParser(registry)

    def _database(self) -> dict[str, Any]:
        if self.command_service is not None:
            database, _dictionary = self.command_service.load_state()
        else:
            database = _read_json(self.data_file, {"daily_records": [], "diet_records": [], "training_sessions": [], "movements": {}, "raw_entries": []})
        if not isinstance(database, dict):
            raise _error("Tracker root must be an object.", "MODULE_TRACKER_INVALID")
        database.setdefault("data_module_records", [])
        return database

    def _fingerprint(self, database: dict[str, Any] | None = None) -> str:
        database = database if database is not None else self._database()
        file_hash = hashlib.sha256(self.data_file.read_bytes()).hexdigest() if self.data_file.exists() else stable_hash(database)
        return stable_hash({"tracker_sha256": file_hash, "registry": self.registry.to_dict(), "categories": self.category_registry.to_dict()})

    def preview(self, raw_text: str, record_date: str | None = None) -> dict[str, Any]:
        database = self._database()
        candidates = self.parser.parse(raw_text, record_date)
        normalized = []
        for candidate in candidates:
            definition = self.registry.require(candidate.module_id)
            try:
                value = normalize_value(candidate.value, definition)
                if candidate.unit_hint and definition.actual_unit and candidate.unit_hint.casefold() not in {definition.actual_unit.casefold(), definition.display_unit.casefold(), *(str(x).casefold() for x in definition.validation_contract.get("unit_aliases", []))}:
                    candidate.warnings.append(f"unit hint {candidate.unit_hint} differs from actual unit {definition.actual_unit}")
                candidate.value = value
                candidate.status = "validated"
                normalized.append(candidate.to_dict())
            except DataModuleError as exc:
                candidate.status = "rejected"
                candidate.warnings.append(exc.code)
                normalized.append(candidate.to_dict())
        if any(item["status"] == "rejected" for item in normalized):
            raise _error("One or more Data Module candidates failed validation.", "MODULE_PREVIEW_INVALID", {"candidates": normalized})
        return {
            "schema": "fitness-ledger-data-module-preview-v1",
            "status": "preview_ready",
            "write_attempted": False,
            "raw_text": str(raw_text or ""),
            "candidates": normalized,
            "source_fingerprint": self._fingerprint(database),
        }

    def save_preview(self, preview: dict[str, Any], *, confirmed: bool = False, raw_entry_id: str | None = None) -> dict[str, Any]:
        if not confirmed:
            raise _error("A confirmed preview is required before saving.", "MODULE_CONFIRMATION_REQUIRED")
        if not isinstance(preview, dict) or preview.get("status") != "preview_ready":
            raise _error("Only a valid Data Module preview can be saved.", "MODULE_PREVIEW_REQUIRED")
        candidates = preview.get("candidates", [])
        if not isinstance(candidates, list) or not candidates:
            raise _error("Preview contains no candidates.", "MODULE_PREVIEW_EMPTY")
        if self._fingerprint() != str(preview.get("source_fingerprint", "")):
            raise _error("Data Module preview is stale; re-run preview.", "MODULE_PREVIEW_STALE")
        lock = self.command_service.write_lock() if self.command_service is not None else _NullContext()
        with lock:
            database = self._database()
            working = copy.deepcopy(database)
            records = working.setdefault("data_module_records", [])
            changed = []
            created_record_ids = []
            unchanged = []
            for raw_candidate in candidates:
                definition = self.registry.require(str(raw_candidate.get("module_id", "")))
                if definition.status != "active" or not definition.capabilities["recordable"]:
                    raise _error("Retired/inactive modules cannot accept new records.", "MODULE_NOT_RECORDABLE", {"module_id": definition.module_id})
                category = self.category_registry.get(definition.category_id)
                if category is None or category.status != "active":
                    raise _error("Module category is not active for new records.", "CATEGORY_NOT_RECORDABLE", {"category_id": definition.category_id})
                value = normalize_value(raw_candidate.get("value"), definition)
                record_date = validate_iso_date(raw_candidate.get("date"))
                matching = [row for row in records if isinstance(row, dict) and row.get("module_id") == definition.module_id and row.get("date") == record_date]
                behaviour = definition.recording_behavior
                if behaviour["kind"] != "scalar" or behaviour["cardinality"] != "one_per_day":
                    raise _error("This candidate supports only scalar one-per-day recording; the generic interface remains open for future kinds.", "MODULE_RECORDING_BEHAVIOR_NOT_IMPLEMENTED", {"module_id": definition.module_id})
                if matching:
                    current = matching[0]
                    if current.get("value") == value and current.get("definition_version") == definition.definition_version:
                        unchanged.append(str(current.get("record_id")))
                        continue
                    current.update(self._record_payload(definition, record_date, value, str(current.get("record_id")), raw_candidate.get("raw_text", "")))
                    changed.append(str(current["record_id"]))
                else:
                    record = self._record_payload(definition, record_date, value, _record_id(definition.module_id, record_date, len(records)), raw_candidate.get("raw_text", ""))
                    records.append(record)
                    changed.append(str(record["record_id"]))
                    created_record_ids.append(str(record["record_id"]))
            if not changed:
                return {"status": "NO_CHANGES", "changed": False, "unchanged_record_ids": unchanged, "write_attempted": False}
            raw_text = str(preview.get("raw_text", "")).strip()
            if raw_text:
                raw_entries = working.setdefault("raw_entries", [])
                entry_id = raw_entry_id or f"dmraw:{stable_hash({'raw': raw_text, 'records': changed})[:16]}"
                if not any(isinstance(item, dict) and str(item.get("id")) == entry_id for item in raw_entries):
                    raw_entries.append({"id": entry_id, "date": candidates[0].get("date", ""), "text": raw_text, "source": "data_module", "data_module_record_ids": changed})
            issues = self.data_check(database=working, focus_module_ids={str(item.get("module_id")) for item in candidates})
            blocking = [item for item in issues if item.get("severity") == "high"]
            if blocking:
                raise _error("Data Module in-memory validation failed; no data was written.", "MODULE_SAVE_VALIDATION_FAILED", {"issues": blocking})
            tracker_backup = dictionary_backup = None
            if self.command_service is not None:
                tracker_backup, dictionary_backup = self.command_service._checkpoint()
                try:
                    self.command_service._write_pair(working, self.command_service.load_state()[1], tracker_backup, dictionary_backup)
                except Exception:
                    raise
            else:
                before = self.data_file.read_bytes() if self.data_file.exists() else None
                try:
                    _write_json_atomic(self.data_file, working)
                except Exception:
                    if before is not None:
                        self.data_file.write_bytes(before)
                    raise
            created_count = len(created_record_ids)
            return {
                "status": "CREATED" if created_count == len(changed) else "UPDATED",
                "changed": True,
                "created_count": created_count,
                "updated_count": len(changed) - created_count,
                "changed_record_ids": changed,
                "unchanged_record_ids": unchanged,
                "raw_preserved": bool(raw_text),
                "checkpoint": str(tracker_backup) if tracker_backup else "",
                "undo": {"available": bool(tracker_backup), "checkpoint": str(tracker_backup) if tracker_backup else ""},
            }

    @staticmethod
    def _record_payload(definition: ModuleDefinition, record_date: str, value: Any, record_id: str, raw_text: str) -> dict[str, Any]:
        return {
            "record_id": record_id,
            "module_id": definition.module_id,
            "category_id": definition.category_id,
            "record_kind": definition.recording_behavior["kind"],
            "date": record_date,
            "value": copy.deepcopy(value),
            "actual_unit": definition.actual_unit,
            "definition_version": definition.definition_version,
            "definition_snapshot": definition.snapshot(),
            "source_raw_hash": stable_hash(raw_text) if raw_text else "",
        }

    def query(self, module_id: str, start: str = "", end: str = "", *, latest: bool = False, category_id: str = "") -> list[dict[str, Any]]:
        definition = self.registry.require(module_id)
        start = validate_iso_date(start) if start else ""
        end = validate_iso_date(end) if end else ""
        if start and end and start > end:
            raise _error("Query start must not be after end.", "MODULE_QUERY_RANGE_INVALID")
        rows = []
        for record in self._database().get("data_module_records", []) or []:
            if not isinstance(record, dict) or str(record.get("module_id")) != definition.module_id:
                continue
            record_date = str(record.get("date", ""))[:10]
            if start and record_date < start or end and record_date > end:
                continue
            if category_id and str(record.get("category_id")) != category_id:
                continue
            item = copy.deepcopy(record)
            item["module"] = definition.to_dict()
            item["display_value"] = definition.display_value(item.get("value"))
            item["display_unit"] = definition.display_unit
            rows.append(item)
        rows.sort(key=lambda item: (str(item.get("date", "")), str(item.get("record_id", ""))), reverse=True)
        return rows[:1] if latest else rows

    def history(self, module_id: str, start: str = "", end: str = "") -> dict[str, Any]:
        definition = self.registry.require(module_id)
        rows = self.query(module_id, start, end)
        return {"module": definition.to_dict(), "module_id": module_id, "status": definition.status, "history": rows, "latest": rows[0] if rows else None, "empty_state": None if rows else {"kind": "empty", "message": "暂无记录"}}

    def normal_export(self) -> dict[str, Any]:
        modules = [item for item in self.registry.all() if item.capabilities["exportable"]]
        module_ids = {item.module_id for item in modules}
        records = [copy.deepcopy(record) for record in self._database().get("data_module_records", []) or [] if isinstance(record, dict) and record.get("module_id") in module_ids]
        records.sort(key=lambda item: (str(item.get("date", "")), str(item.get("record_id", ""))))
        return {"schema": "fitness-ledger-data-module-export-v1", "categories": [item.to_dict() for item in self.category_registry.all()], "modules": [item.to_dict() for item in modules], "records": records}

    def analysis_catalog(self) -> dict[str, Any]:
        visible = [item for item in self.registry.all() if item.capabilities["analysis_visible"] and item.capabilities["exportable"]]
        return {
            "schema": "fitness-ledger-data-module-analysis-catalog-v1",
            "protocol": "AnalysisExportRequest-v1.1-boundary",
            "protocol_change_required_for_public_field": True,
            "modules": [{"module_id": item.module_id, "field_id": f"extension.{item.module_id}", "label": item.label, "data_type": item.data_type, "unit": item.actual_unit} for item in visible],
            "hidden_module_ids": [item.module_id for item in self.registry.all() if not item.capabilities["analysis_visible"]],
        }

    def analysis_preview(self, module_ids: Iterable[str]) -> dict[str, Any]:
        requested = [str(item) for item in module_ids]
        for module_id in requested:
            definition = self.registry.require(module_id)
            if not definition.capabilities["analysis_visible"]:
                raise _error("Module is hidden from Analysis Export.", "MODULE_ANALYSIS_HIDDEN", {"module_id": module_id})
        catalog = self.analysis_catalog()
        allowed = {item["module_id"] for item in catalog["modules"]}
        if not set(requested) <= allowed:
            raise _error("Module is missing an Analysis provider contract.", "MODULE_ANALYSIS_PROVIDER_MISSING")
        rows = []
        for record in self._database().get("data_module_records", []) or []:
            if record.get("module_id") not in requested:
                continue
            rows.append({"date": record.get("date"), f"extension.{record['module_id']}": record.get("value")})
        return {"status": "contract_preview_ready", "protocol": "AnalysisExportRequest-v1.1-boundary", "public_protocol_changed": False, "catalog": catalog, "module_ids": requested, "rows": rows}

    def data_check(self, database: dict[str, Any] | None = None, focus_module_ids: set[str] | None = None) -> list[dict[str, Any]]:
        database = copy.deepcopy(database if database is not None else self._database())
        issues = [*self.definition_issues, *self.registry.data_check_issues()]
        for category in self.category_registry.all():
            if category.status == "retired" and any(item.category_id == category.category_id and item.status != "retired" for item in self.registry.all()):
                issues.append(self._issue("medium", "category", category.category_id, "active module references a retired category", "Move the module or re-enable the category."))
        records = database.get("data_module_records", [])
        if not isinstance(records, list):
            issues.append(self._issue("high", "record", "", "data_module_records must be a list", "Restore the extension storage shape."))
            return issues
        for record in records:
            if not isinstance(record, dict):
                issues.append(self._issue("high", "record", "", "Data Module record must be an object", "Repair through a reviewed migration."))
                continue
            module_id = str(record.get("module_id", ""))
            if focus_module_ids and module_id not in focus_module_ids:
                continue
            definition = self.registry.get(module_id)
            if definition is None:
                issues.append(self._issue("high", "record", module_id, "orphan module value has no definition", "Restore the definition or remove the orphan through a reviewed migration."))
                continue
            category = self.category_registry.get(definition.category_id)
            if category is None:
                issues.append(self._issue("high", "category", module_id, "module references an unknown category", "Restore the category definition or run a reviewed migration."))
            elif category.status == "retired" and definition.status != "retired":
                issues.append(self._issue("medium", "category", module_id, "active module references a retired category", "Re-enable the category or retire/move the module."))
            try:
                validate_iso_date(record.get("date"))
            except DataModuleError as exc:
                issues.append(self._issue("high", "record", record.get("record_id", module_id), exc.code, str(exc)))
            try:
                normalize_value(record.get("value"), definition)
            except DataModuleError as exc:
                issues.append(self._issue("high", "record", record.get("record_id", module_id), exc.code, str(exc)))
            snapshot = record.get("definition_snapshot")
            version = record.get("definition_version")
            if not isinstance(snapshot, dict) or not isinstance(version, int):
                issues.append(self._issue("high", "version", record.get("record_id", module_id), "missing definition version or snapshot", "Preserve a definition snapshot during a reviewed write."))
            elif version > definition.definition_version:
                issues.append(self._issue("high", "version", record.get("record_id", module_id), "record refers to an unknown future definition version", "Register the definition version before reading the record."))
            elif version < definition.definition_version and not any(int(item.get("definition_version", -1)) == version for item in definition.definition_history):
                issues.append(self._issue("medium", "version", record.get("record_id", module_id), "record refers to an unknown historical definition version", "Restore the historical definition snapshot or run a reviewed migration."))
            if definition.status == "retired" and definition.capabilities["recordable"]:
                issues.append(self._issue("medium", "record", record.get("record_id", module_id), "record belongs to a retired module that remains recordable", "Disable new recording or explicitly re-enable the module."))
        return sorted(issues, key=lambda item: (item.get("severity", ""), item.get("target_type", ""), str(item.get("target_id", "")), item.get("issue", "")))

    @staticmethod
    def _issue(severity: str, target_type: str, target_id: Any, issue: str, action: str) -> dict[str, Any]:
        return {"severity": severity, "date": "", "area": "Data Modules", "issue": issue, "action": action, "target_type": target_type, "target_id": str(target_id), "module_id": str(target_id)}

    def build_cloud_payload(self, database: dict[str, Any] | None = None) -> dict[str, Any]:
        database = copy.deepcopy(database) if database is not None else self._database()
        issues = self.data_check(database)
        blocking = [item for item in issues if item.get("severity") == "high"]
        if blocking:
            raise _error("Cloud payload is blocked by Data Module integrity issues.", "MODULE_CLOUD_BLOCKED", {"issues": blocking})
        modules = [item for item in self.registry.all() if item.capabilities["cloud_syncable"]]
        module_ids = {item.module_id for item in modules}
        records = [{key: copy.deepcopy(value) for key, value in record.items() if key not in {"source_raw_hash", "raw_text", "private", "notes"}}
                   for record in database.get("data_module_records", []) or [] if record.get("module_id") in module_ids]
        modules_payload = [{"module_id": item.module_id, "label": item.label, "category_id": item.category_id, "data_type": item.data_type, "actual_unit": item.actual_unit, "status": item.status, "definition_version": item.definition_version} for item in modules]
        modules_payload.sort(key=lambda item: item["module_id"])
        records.sort(key=lambda item: (str(item.get("date", "")), str(item.get("record_id", ""))))
        collections = {"modules": modules_payload, "records": records}
        collection_hashes = {key: stable_hash(value) for key, value in collections.items()}
        payload_hash = stable_hash(collections)
        return {
            "schema": "fitness-ledger-data-module-cloud-v1",
            "modules": modules_payload,
            "records": records,
            "meta": {"payload_hash": payload_hash, "collection_hashes": collection_hashes, "source_fingerprint": self._fingerprint(), "raw_policy": "excluded", "network_request_made": False},
        }

    @staticmethod
    def verify_cloud_payload(payload: dict[str, Any]) -> dict[str, Any]:
        errors = []
        if not isinstance(payload, dict) or payload.get("schema") != "fitness-ledger-data-module-cloud-v1":
            errors.append("MODULE_CLOUD_SCHEMA_INVALID")
            return {"verified": False, "errors": errors, "network_request_made": False}
        modules = payload.get("modules", [])
        records = payload.get("records", [])
        meta = payload.get("meta", {})
        collections = {"modules": modules, "records": records}
        if meta.get("payload_hash") != stable_hash(collections):
            errors.append("MODULE_CLOUD_PAYLOAD_HASH_MISMATCH")
        if meta.get("collection_hashes") != {key: stable_hash(value) for key, value in collections.items()}:
            errors.append("MODULE_CLOUD_COLLECTION_HASH_MISMATCH")
        for record in records if isinstance(records, list) else []:
            if any(key in record for key in ("raw_text", "private", "notes", "source_raw_hash")):
                errors.append("MODULE_CLOUD_RAW_OR_PRIVATE_LEAK")
                break
        known_ids = {str(item.get("module_id")) for item in modules if isinstance(item, dict)}
        if any(str(item.get("module_id")) not in known_ids for item in records if isinstance(item, dict)):
            errors.append("MODULE_CLOUD_ORPHAN_RECORD")
        return {"verified": not errors, "errors": errors, "payload_hash": meta.get("payload_hash", ""), "network_request_made": False}

    @classmethod
    def cloud_roundtrip(cls, payload: dict[str, Any]) -> dict[str, Any]:
        verification = cls.verify_cloud_payload(payload)
        if not verification["verified"]:
            raise _error("Cloud payload roundtrip verification failed.", "MODULE_CLOUD_VERIFY_FAILED", verification)
        return {
            "schema": "fitness-ledger-data-module-cloud-roundtrip-v1",
            "verified": True,
            "modules": copy.deepcopy(payload["modules"]),
            "records": copy.deepcopy(payload["records"]),
            "payload_hash": verification["payload_hash"],
            "network_request_made": False,
        }

    def build_mini_program_contract(self, history_limit: int = 20) -> dict[str, Any]:
        modules = [item for item in self.registry.all() if item.capabilities["mini_program_visible"]]
        for item in modules:
            if item.renderer not in SUPPORTED_RENDERERS:
                raise _error("Mini Program renderer is unsupported.", "MODULE_MINI_RENDERER_UNSUPPORTED", {"module_id": item.module_id})
        cards = []
        for item in modules:
            history = self.history(item.module_id)["history"][:history_limit]
            cards.append({"module_id": item.module_id, "label": item.label, "category_id": item.category_id, "renderer": item.renderer, "status": item.status, "recording_enabled": item.status == "active" and item.capabilities["recordable"], "latest": history[0] if history else None, "history": history, "empty_state": None if history else {"kind": "empty", "message": "暂无记录"}})
        return {"schema": "fitness-ledger-mini-module-contract-v1", "page_required": False, "renderers": sorted({item.renderer for item in modules if item.renderer}), "modules": cards}

    def presentation_contract(self) -> dict[str, Any]:
        return {"schema": "fitness-ledger-presentation-contract-v1", "categories": [{"category_id": item.category_id, "label": item.label, "order": item.order, "status": item.status, "presentation": item.presentation} for item in self.category_registry.all()], "modules": [{"module_id": item.module_id, "category_id": item.category_id, "section": item.presentation["section"], "slot": item.presentation["slot"], "order": item.presentation["order"], "visible_by_default": item.presentation["visible_by_default"], "fallback": item.presentation["fallback"], "unsupported_behavior": item.presentation["unsupported_behavior"], "renderer": item.renderer} for item in self.registry.all()]}


class DataModuleMigrationService:
    """Plan/apply migrations to anonymous fixtures only; never formal data."""

    def __init__(self, registry: ModuleRegistry):
        self.registry = registry

    def preview(self, module_id: str, changes: dict[str, Any], database: dict[str, Any]) -> dict[str, Any]:
        current, candidate = self.registry.preview_update(module_id, changes, allow_actual_unit_change=True)
        before_records = copy.deepcopy(database.get("data_module_records", []) or [])
        after_records = copy.deepcopy(before_records)
        blockers = []
        operation = "METADATA_UPDATE"
        conversion = changes.get("value_migration")
        if current.actual_unit != candidate.actual_unit:
            operation = "ACTUAL_UNIT_MIGRATION"
            if not isinstance(conversion, dict):
                blockers.append({"code": "EXPLICIT_MIGRATION_REQUIRED", "message": "Actual unit change requires factor/offset conversion."})
            else:
                try:
                    factor = float(conversion["factor"])
                    offset = float(conversion.get("offset", 0))
                    if not math.isfinite(factor) or not math.isfinite(offset) or factor == 0:
                        raise ValueError
                except (KeyError, TypeError, ValueError) as exc:
                    blockers.append({"code": "MIGRATION_CONVERSION_INVALID", "message": "factor/offset must be finite and factor must be non-zero."})
                else:
                    for record in after_records:
                        if record.get("module_id") != module_id:
                            continue
                        record["value"] = round(_finite_number(record.get("value")) * factor + offset, 8)
                        record["actual_unit"] = candidate.actual_unit
                        record["definition_version"] = candidate.definition_version
                        record["definition_snapshot"] = candidate.snapshot()
        else:
            for record in after_records:
                if record.get("module_id") == module_id:
                    record["definition_version"] = candidate.definition_version
                    record["definition_snapshot"] = candidate.snapshot()
        plan = {
            "schema": "fitness-ledger-data-module-migration-plan-v1",
            "operation": operation,
            "module_id": module_id,
            "before_definition": current.to_dict(),
            "after_definition": candidate.to_dict(),
            "before_records_hash": stable_hash(before_records),
            "after_records_hash": stable_hash(after_records),
            "before_records": before_records,
            "after_records": after_records,
            "diff_count": sum(left != right for left, right in zip(before_records, after_records)),
            "blockers": blockers,
            "can_execute_on_fixture": not blockers,
            "formal_write_allowed": False,
        }
        plan["plan_identity"] = stable_hash({key: value for key, value in plan.items() if key not in {"plan_identity"}})
        return plan

    def apply_fixture(self, plan: dict[str, Any], registry: ModuleRegistry, database: dict[str, Any]) -> tuple[ModuleRegistry, dict[str, Any]]:
        if not plan.get("can_execute_on_fixture"):
            raise _error("Migration plan is blocked.", "MODULE_MIGRATION_BLOCKED", {"blockers": plan.get("blockers", [])})
        if stable_hash(database.get("data_module_records", []) or []) != plan.get("before_records_hash"):
            raise _error("Migration fixture is stale.", "MODULE_MIGRATION_STALE")
        updated_registry = registry.clone()
        current = updated_registry.require(plan["module_id"])
        if stable_hash(current.to_dict()) != stable_hash(plan.get("before_definition")):
            raise _error("Migration definition is stale.", "MODULE_MIGRATION_DEFINITION_STALE")
        candidate = ModuleDefinition.from_dict(plan["after_definition"], allowed_categories=set(updated_registry.category_ids))
        updated_registry.replace_fixture_definition(candidate)
        updated_database = copy.deepcopy(database)
        updated_database["data_module_records"] = copy.deepcopy(plan["after_records"])
        return updated_registry, updated_database

    def rollback_fixture(self, plan: dict[str, Any], registry: ModuleRegistry, database: dict[str, Any]) -> tuple[ModuleRegistry, dict[str, Any]]:
        if stable_hash(database.get("data_module_records", []) or []) != plan.get("after_records_hash"):
            raise _error("Migration rollback fixture is stale.", "MODULE_MIGRATION_ROLLBACK_STALE")
        current = registry.require(plan["module_id"])
        if stable_hash(current.to_dict()) != stable_hash(plan.get("after_definition")):
            raise _error("Migration rollback definition is stale.", "MODULE_MIGRATION_ROLLBACK_DEFINITION_STALE")
        restored_registry = registry.clone()
        restored_registry.replace_fixture_definition(ModuleDefinition.from_dict(plan["before_definition"], allowed_categories=set(restored_registry.category_ids)))
        restored_database = copy.deepcopy(database)
        restored_database["data_module_records"] = copy.deepcopy(plan["before_records"])
        return restored_registry, restored_database


class _NullContext:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def build_data_module_cloud_payload(engine: DataModuleEngine) -> dict[str, Any]:
    return engine.build_cloud_payload()


def build_data_module_mini_contract(engine: DataModuleEngine) -> dict[str, Any]:
    return engine.build_mini_program_contract()


__all__ = [
    "DataModuleError",
    "CategoryDefinition",
    "CategoryRegistry",
    "DataModuleDefinitionStore",
    "DataModuleEngine",
    "DataModuleMigrationService",
    "ModuleDefinition",
    "ModuleRegistry",
    "ParseCandidate",
    "RegistryDrivenParser",
    "build_data_module_cloud_payload",
    "build_data_module_mini_contract",
    "normalize_alias",
    "normalize_value",
    "stable_hash",
]
