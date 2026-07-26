"""Deterministic task routing and canonical analysis metadata.

The existing ``analysis_evidence`` task definitions remain authoritative for
evidence fields and claim prose.  This module adds only the routing metadata
needed by the registry-convergence preview; it does not define a second
evidence contract or a second capability vocabulary.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import re
from typing import Any

from .analysis_evidence import TASK_REGISTRY as EVIDENCE_TASK_REGISTRY

REGISTRY_SCHEMA_VERSION = "fitness-ledger-registry-convergence-v1"
INTENT_AST_SCHEMA_VERSION = "fitness-ledger-intent-ast-v1"
CAPABILITY_IDS = (
    "body_history",
    "diet_macros",
    "training_context",
    "movement_progress",
    "notes_context",
    "raw_trace",
)


def normalize_string_list(value: Any, name: str, *, max_items: int = 64) -> list[str]:
    if isinstance(value, str):
        values = [value]
    elif isinstance(value, (list, tuple, set)):
        values = value
    else:
        raise TypeError(f"{name} must be string or sequence")
    result: list[str] = []
    for item in values:
        if not isinstance(item, str):
            raise TypeError(f"{name} must contain strings")
        item = item.strip()
        if item and item not in result:
            result.append(item)
    if len(result) > max_items:
        raise ValueError(f"{name} exceeds {max_items}")
    return result


@dataclass(frozen=True)
class FieldDefinition:
    field_id: str
    module_id: str
    source_fields: tuple[str, ...]
    value_type: str = "string"
    nullable: bool = True
    source_contract: str = "DataCatalogBuilder"
    privacy_level: str = "aggregate"

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["source_fields"] = list(self.source_fields)
        return result


def _field(field_id: str, module_id: str, *source_fields: str, **kwargs: Any) -> FieldDefinition:
    return FieldDefinition(field_id, module_id, tuple(source_fields), **kwargs)


FIELD_REGISTRY = {
    item.field_id: item
    for item in (
        _field("body.measurement.date", "body", "Date", value_type="date", nullable=False),
        _field("body.measurement.weight", "body", "Weight (kg)", value_type="number", nullable=False),
        _field("body.measurement.context", "body", "Notes", source_contract="DataCatalogBuilder.notes", privacy_level="notes"),
        _field("diet.day.date", "diet", "Date", value_type="date", nullable=False),
        _field("diet.day.calories", "diet", "Calories (kcal)", value_type="number"),
        _field("diet.day.protein", "diet", "Protein (g)", value_type="number"),
        _field("diet.day.carbs", "diet", "Carbs (g)", value_type="number"),
        _field("diet.day.fat", "diet", "Fat (g)", value_type="number"),
        _field("diet.intake.source", "diet", "Food Summary"),
        _field("diet.preworkout_carbs", "diet", "preworkout_carbs", value_type="number"),
        _field("training.session.date", "training", "Date", value_type="date", nullable=False),
        _field("training.session.split", "training", "Split"),
        _field("training.session.datetime", "training", "DateTime", value_type="datetime"),
        _field("training.session.notes", "training", "Notes", source_contract="DataCatalogBuilder.notes", privacy_level="notes"),
        _field("training.exercise.movement_id", "movement_history", "movement_id", nullable=False, source_contract="MovementResolver"),
        _field("training.exercise.bodypart", "movement_history", "bodypart", source_contract="MovementResolver"),
        _field("training.exercise.variant_id", "movement_history", "variant", source_contract="MovementResolver"),
        _field("training.exercise.order", "movement_history", "order", value_type="integer"),
        _field("training.set.load", "movement_history", "load", value_type="number"),
        _field("training.set.reps", "movement_history", "reps", value_type="integer"),
        _field("training.set.type", "movement_history", "set_type"),
        _field("training.set.rir", "movement_history", "RIR", value_type="number"),
        _field("notes.daily", "notes", "daily", source_contract="DataCatalogBuilder.notes", privacy_level="notes"),
        _field("notes.diet", "notes", "diet", source_contract="DataCatalogBuilder.notes", privacy_level="notes"),
        _field("notes.training", "notes", "training", source_contract="DataCatalogBuilder.notes", privacy_level="notes"),
    )
}


@dataclass(frozen=True)
class MetricDefinition:
    metric_id: str
    required_fields: tuple[str, ...]
    minimum_records: int
    calculation: str
    allowed_claim_modes: tuple[str, ...]
    forbidden_claim_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        for key in ("required_fields", "allowed_claim_modes", "forbidden_claim_codes"):
            result[key] = list(result[key])
        return result


METRIC_REGISTRY = {
    item.metric_id: item
    for item in (
        MetricDefinition("weight_direction", ("body.measurement.date", "body.measurement.weight"), 3, "ordered first/last and range", ("descriptive",), ("CAUSAL_FORBIDDEN",)),
        MetricDefinition("weight_record_coverage", ("body.measurement.date",), 1, "observed dates / requested dates", ("descriptive",), ("MISSING_AS_ZERO",)),
        MetricDefinition("diet_macro_snapshot", ("diet.day.date", "diet.day.calories", "diet.day.protein", "diet.day.carbs", "diet.day.fat"), 1, "descriptive macro values", ("descriptive",), ("MISSING_AS_ZERO",)),
        MetricDefinition("diet_record_coverage", ("diet.day.date",), 1, "observed diet dates", ("descriptive",), ("LONG_TERM_INFERENCE",)),
        MetricDefinition("session_frequency", ("training.session.date",), 2, "sessions per interval", ("descriptive",), ("PERFORMANCE_FROM_SUMMARY",)),
        MetricDefinition("split_distribution", ("training.session.date", "training.session.split"), 1, "count by split", ("descriptive",), ("PERFORMANCE_FROM_SUMMARY",)),
        MetricDefinition("same_movement_load_rep_change", ("training.exercise.movement_id", "training.set.load", "training.set.reps"), 2, "same movement comparison", ("comparative",), ("VARIANT_MERGE",)),
        MetricDefinition("topset_change", ("training.set.load", "training.set.reps", "training.set.type"), 2, "top-set comparison", ("comparative",), ("SINGLE_PROGRESS_SCORE",)),
        MetricDefinition("backoff_volume_change", ("training.set.load", "training.set.reps", "training.set.type"), 2, "backoff load*reps", ("comparative",), ("SINGLE_PROGRESS_SCORE",)),
        MetricDefinition("aligned_day_coverage", ("diet.day.date", "training.session.date"), 1, "date intersection", ("descriptive", "association_hypothesis"), ("CAUSAL_FORBIDDEN",)),
        MetricDefinition("condition_group_descriptive_difference", ("diet.preworkout_carbs", "training.set.load", "training.set.reps"), 6, "descriptive groups", ("comparative", "association_hypothesis"), ("CAUSAL_FORBIDDEN",)),
        MetricDefinition("variant_consistency", ("training.exercise.movement_id", "training.exercise.variant_id"), 2, "group by variant", ("comparative",), ("VARIANT_MERGE",)),
    )
}


@dataclass(frozen=True)
class ClaimPolicy:
    claim_mode: str
    allowed_claim_codes: tuple[str, ...]
    forbidden_claim_codes: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["allowed_claim_codes"] = list(self.allowed_claim_codes)
        result["forbidden_claim_codes"] = list(self.forbidden_claim_codes)
        return result


CLAIM_POLICIES = {
    "descriptive": ClaimPolicy("descriptive", ("OBSERVED_COVERAGE", "OBSERVED_DIRECTION", "OBSERVED_DISTRIBUTION"), ("CAUSAL_FORBIDDEN", "LONG_TERM_INFERENCE", "PERFORMANCE_FROM_SUMMARY")),
    "comparative": ClaimPolicy("comparative", ("COMPARABLE_GROUP_DIFFERENCE", "SAME_MOVEMENT_CHANGE"), ("CAUSAL_FORBIDDEN", "VARIANT_MERGE", "SINGLE_PROGRESS_SCORE")),
    "association_hypothesis": ClaimPolicy("association_hypothesis", ("OBSERVATIONAL_ASSOCIATION_HYPOTHESIS", "SAMPLE_AND_LIMITS"), ("CAUSAL_FORBIDDEN", "UNREGISTERED_METRIC")),
    "none": ClaimPolicy("none", (), ("ALL_ANALYSIS_CLAIMS",)),
}


# These are routing metadata only.  Field/claim prose stays in the existing
# AnalysisTaskDefinition objects from analysis_evidence.py.
TASK_ROUTE = {
    "weight_trend": {"aliases": ("体重变化", "体重走势", "掉秤", "weight"), "caps": ("body_history",), "slots": ("time_window",), "metrics": ("weight_direction", "weight_record_coverage"), "mode": "descriptive", "minimum": {"records": 3}, "forbidden": ("CAUSAL_FORBIDDEN", "LONG_TERM_INFERENCE"), "base": "weight_trend"},
    "diet_trend": {"aliases": ("最近饮食", "饮食趋势", "宏量", "热量", "碳水", "diet"), "caps": ("diet_macros",), "slots": ("time_window",), "metrics": ("diet_macro_snapshot", "diet_record_coverage"), "mode": "descriptive", "minimum": {"records": 3}, "forbidden": ("MISSING_AS_ZERO", "LONG_TERM_INFERENCE"), "base": "macro_trend"},
    "training_schedule": {"aliases": ("训练安排", "训练频率", "训练日", "split"), "caps": ("training_context",), "slots": ("time_window",), "metrics": ("session_frequency", "split_distribution"), "mode": "descriptive", "minimum": {"records": 2}, "forbidden": ("PERFORMANCE_FROM_SUMMARY",), "base": "training_record_coverage"},
    "training_performance": {"aliases": ("训练表现", "训练容量", "表现下降", "后续容量"), "caps": ("training_context",), "slots": ("time_window",), "metrics": ("same_movement_load_rep_change",), "mode": "comparative", "minimum": {"records": 2}, "forbidden": ("PERFORMANCE_FROM_SUMMARY", "VARIANT_MERGE"), "base": "overall_performance_comparison"},
    "fat_loss_synthesis": {"aliases": ("减脂效果", "减重效果", "身体状态综合"), "caps": ("body_history", "diet_macros", "training_context"), "optional": ("notes_context",), "slots": ("time_window",), "metrics": ("weight_direction", "diet_macro_snapshot", "session_frequency"), "mode": "descriptive", "minimum": {"records": 7}, "forbidden": ("CAUSAL_FORBIDDEN", "LONG_TERM_INFERENCE"), "base": "fat_loss_evidence_synthesis"},
    "diet_training_association": {"aliases": ("饮食是否影响训练", "饮食影响训练", "饮食和训练关系"), "caps": ("diet_macros", "training_context"), "optional": ("notes_context",), "slots": ("time_window",), "metrics": ("aligned_day_coverage",), "mode": "association_hypothesis", "minimum": {"aligned_days": 4}, "forbidden": ("CAUSAL_FORBIDDEN", "UNREGISTERED_METRIC", "PERFORMANCE_FROM_SUMMARY"), "base": "diet_training_alignment"},
    "lagged_carb_capacity": {"aliases": ("前两三天碳水", "碳水偏低", "后续容量", "滞后"), "caps": ("diet_macros", "training_context"), "slots": ("time_window", "event_anchor"), "time": "event_relative_lag", "metrics": ("aligned_day_coverage", "backoff_volume_change"), "mode": "association_hypothesis", "minimum": {"comparable_sessions": 3}, "forbidden": ("CAUSAL_FORBIDDEN", "UNREGISTERED_METRIC"), "base": "lagged_carb_context"},
    "preworkout_condition_comparison": {"aliases": ("练前快碳", "有糖运动饮料", "条件比较"), "caps": ("diet_macros", "training_context"), "slots": ("time_window", "condition_groups"), "time": "condition_grouped_sessions", "metrics": ("condition_group_descriptive_difference",), "mode": "comparative", "minimum": {"sessions_per_condition": 3}, "forbidden": ("CAUSAL_FORBIDDEN", "UNREGISTERED_METRIC"), "base": "condition_group_comparison"},
    "movement_progress": {"aliases": ("动作进步", "卧推进步", "动作表现"), "caps": ("movement_progress",), "slots": ("movement_identity", "time_window"), "confirms": ("movement_identity",), "metrics": ("same_movement_load_rep_change", "variant_consistency"), "mode": "comparative", "minimum": {"records": 2}, "forbidden": ("VARIANT_MERGE",), "base": "movement_load_rep_progress"},
    "bodypart_progress": {"aliases": ("胸部整体", "身体部位进步", "胸部进步"), "caps": ("training_context", "movement_progress"), "slots": ("bodypart_scope", "time_window"), "confirms": ("movement_or_bodypart_scope",), "metrics": ("same_movement_load_rep_change", "variant_consistency"), "mode": "comparative", "minimum": {"records": 3}, "forbidden": ("VARIANT_MERGE",), "base": "bodypart_progress_synthesis"},
    "topset_backoff_comparison": {"aliases": ("最佳组", "回退组", "top set", "backoff"), "caps": ("movement_progress", "training_context"), "slots": ("movement_identity", "time_window"), "confirms": ("movement_identity",), "metrics": ("topset_change", "backoff_volume_change"), "mode": "comparative", "minimum": {"records": 2}, "forbidden": ("SINGLE_PROGRESS_SCORE", "VARIANT_MERGE"), "base": "top_set_vs_backoff_capacity"},
    "notes_state_context": {"aliases": ("训练 Notes", "状态波动", "备注状态"), "caps": ("training_context", "notes_context"), "slots": ("notes_scope", "time_window"), "confirms": ("notes_scope",), "mode": "association_hypothesis", "minimum": {"records": 2}, "forbidden": ("CAUSAL_FORBIDDEN",), "base": "training_state_notes_synthesis"},
    "fat_source_context": {"aliases": ("脂肪来源", "动物脂肪", "烹调用油"), "caps": ("diet_macros", "notes_context"), "slots": ("notes_scope", "time_window"), "confirms": ("notes_scope",), "metrics": ("diet_macro_snapshot",), "mode": "association_hypothesis", "minimum": {"records": 3}, "forbidden": ("CAUSAL_FORBIDDEN", "UNREGISTERED_METRIC"), "base": "fat_source_context"},
}

TASK_REGISTRY = {task_id: EVIDENCE_TASK_REGISTRY[route["base"]] for task_id, route in TASK_ROUTE.items()}

SOURCE_TO_CANONICAL_FIELD = {
    "body.Date": "body.measurement.date", "body.Weight (kg)": "body.measurement.weight", "body.measurement_context": "body.measurement.context",
    "diet.Date": "diet.day.date", "diet.Calories (kcal)": "diet.day.calories", "diet.Protein (g)": "diet.day.protein", "diet.Carbs (g)": "diet.day.carbs", "diet.Fat (g)": "diet.day.fat", "diet.preworkout_carbs": "diet.preworkout_carbs",
    "training.Date": "training.session.date", "training.Split": "training.session.split", "training.DateTime": "training.session.datetime", "training.session_notes": "training.session.notes", "training.Standardized Summary": "training.session.split",
    "training.exercise_order": "training.exercise.order", "training.movements.bodypart": "training.exercise.bodypart", "training.movements.identity": "training.exercise.movement_id", "training.movements.variant": "training.exercise.variant_id", "training.movements.sets.load": "training.set.load", "training.movements.sets.reps": "training.set.reps", "training.movements.sets.set_type": "training.set.type", "training.movements.sets.RIR": "training.set.rir",
    "movement_history.movement_id": "training.exercise.movement_id", "movement_history.variant": "training.exercise.variant_id", "movement_history.Date": "training.session.date", "movement_history.load": "training.set.load", "movement_history.reps": "training.set.reps", "notes.training": "notes.training", "notes.diet.food_sources": "notes.diet",
}


class AnalysisOperation(str, Enum):
    ANALYZE = "analyze"
    RAW_READ = "raw_read"
    WRITE = "write"
    DELETE = "delete"
    SYNC = "sync"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class IntentAST:
    operation: str
    analysis_target: list[str]
    explicit_only: list[str]
    explicit_include: list[str]
    explicit_exclude: list[str]
    time_expression: dict[str, Any]
    movement_expression: dict[str, Any]
    bodypart_expression: dict[str, Any]
    notes_expression: dict[str, Any]
    raw_expression: dict[str, Any]
    condition_groups: list[dict[str, Any]]
    comparison_expression: dict[str, Any]
    user_input: str
    schema_version: str = INTENT_AST_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IntentASTParser:
    raw = re.compile(r"raw|原始记录|原文|原始输入", re.I)
    delete = re.compile(r"删除|删掉|清空|delete", re.I)
    sync = re.compile(r"同步|上传|sync", re.I)
    write = re.compile(r"写入|保存|修改|更新|录入|新增|添加|发布|save|update", re.I)
    analyze = re.compile(r"分析|查看|看看|比较|趋势|进步|表现|是否|最近|只看|只分析|综合|比上次|最佳组|回退组|后续容量", re.I)

    @staticmethod
    def targets(text: str) -> list[str]:
        groups = {"body": ("体重", "身体", "减脂", "减重"), "diet": ("饮食", "热量", "蛋白", "碳水", "脂肪", "快碳", "宏量"), "training": ("训练", "频率", "训练日", "训练安排", "容量", "split"), "movement": ("卧推", "推胸", "动作", "movement"), "bodypart": ("胸部整体", "身体部位", "胸部"), "notes": ("notes", "备注", "状态波动")}
        folded = text.casefold()
        return [key for key, values in groups.items() if any(value.casefold() in folded for value in values)]

    @staticmethod
    def parse(user_input: str) -> IntentAST:
        text = str(user_input or "").strip()[:2000]
        if IntentASTParser.raw.search(text):
            operation = AnalysisOperation.RAW_READ.value
        elif IntentASTParser.delete.search(text):
            operation = AnalysisOperation.DELETE.value
        elif IntentASTParser.sync.search(text):
            operation = AnalysisOperation.SYNC.value
        elif IntentASTParser.write.search(text):
            operation = AnalysisOperation.WRITE.value
        elif IntentASTParser.analyze.search(text):
            operation = AnalysisOperation.ANALYZE.value
        else:
            operation = AnalysisOperation.UNKNOWN.value
        targets = IntentASTParser.targets(text)
        only = targets if re.search(r"只(?:看|分析|查看)", text) else []
        include = targets if ("结合" in text or "包括" in text) else []
        excluded: list[str] = []
        for part in re.findall(r"(?:不要|排除|不结合|忽略)([^，。,；;。]*)", text):
            excluded.extend(IntentASTParser.targets(part))
        dates = re.findall(r"\d{1,4}[年/-]\d{1,2}(?:月|/-)\d{1,2}[日号]?", text)
        if dates:
            time = {"kind": "explicit_calendar_range", "raw": dates}
        elif re.search(r"前\s*[两二三2-3]+\s*天", text):
            time = {"kind": "event_relative_lag", "lookback_days": [1, 2, 3]}
        elif re.search(r"最近\s*(?:两|二|2)\s*次", text):
            time = {"kind": "last_n_matching_sessions", "n": 2}
        elif "最近" in text or "这段时间" in text:
            time = {"kind": "recent_available"}
        else:
            time = {"kind": "unspecified"}
        mentions = [item for item in ("卧推", "推胸") if item in text]
        movement = {"mentions": mentions, "resolution": "ambiguous" if "推胸" in mentions else "unresolved" if mentions else "none"}
        bodyparts = [item for item in ("胸部", "肩部", "腿部") if item in text]
        bodypart = {"mentions": bodyparts, "scope": "bodypart" if bodyparts else "none"}
        notes = {"requested": bool(re.search(r"Notes|备注|状态波动", text, re.I)), "scope": "unresolved"}
        raw = {"requested": bool(IntentASTParser.raw.search(text)), "explicit": bool(IntentASTParser.raw.search(text))}
        conditions: list[dict[str, Any]] = []
        if any(item in text for item in ("有糖", "快碳", "碳水")):
            conditions.append({"condition_id": "preworkout_carbs", "label": "with_carbs"})
        if any(item in text for item in ("不喝", "不吃", "无糖")):
            conditions.append({"condition_id": "preworkout_carbs", "label": "without_carbs"})
        if "是否影响" in text or "会不会" in text:
            comparison = {"kind": "association_question"}
        elif "比较" in text or "比上次" in text:
            comparison = {"kind": "comparison"}
        elif "进步" in text or "下降" in text:
            comparison = {"kind": "progress"}
        else:
            comparison = {"kind": "none"}
        return IntentAST(operation, targets, only, include, list(dict.fromkeys(excluded)), time, movement, bodypart, notes, raw, conditions, comparison, text)


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class TaskExpansion:
    task_ids: list[str]
    task_source: str
    required_capabilities: list[str]
    optional_capabilities: list[str]
    forbidden_capabilities: list[str]
    required_slots: list[str]
    required_confirmations: list[str]
    time_semantics: dict[str, Any]
    required_fields: list[str]
    recommended_fields: list[str]
    minimum_evidence: dict[str, int]
    metric_ids: list[str]
    allowed_claim_mode: str
    forbidden_claim_codes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TaskRegistry:
    def __init__(self, tasks: dict[str, Any] | None = None):
        self.tasks = dict(tasks or TASK_REGISTRY)
        for task_id, definition in self.tasks.items():
            if task_id not in TASK_ROUTE or TASK_ROUTE[task_id]["base"] != definition.task_id:
                raise RegistryError(f"task route mismatch: {task_id}")
            route = TASK_ROUTE[task_id]
            capabilities = tuple(route.get("caps", ())) + tuple(route.get("optional", ()))
            if set(capabilities) - set(CAPABILITY_IDS) or "raw_trace" in capabilities:
                raise RegistryError(f"invalid capability route: {task_id}")
            if set(route.get("metrics", ())) - set(METRIC_REGISTRY):
                raise RegistryError(f"unknown metric route: {task_id}")

    def resolve(self, ast: IntentAST) -> list[str]:
        if ast.operation != AnalysisOperation.ANALYZE.value:
            return []
        text = ast.user_input.casefold()
        def has(task_id: str) -> bool:
            return any(alias.casefold() in text for alias in TASK_ROUTE[task_id]["aliases"])
        if has("fat_source_context"):
            return ["fat_source_context"]
        if has("notes_state_context"):
            return ["notes_state_context"]
        if len(ast.condition_groups) >= 2 and any(item in text for item in ("快碳", "有糖", "条件")):
            return ["preworkout_condition_comparison"]
        if ast.time_expression.get("kind") == "event_relative_lag" and "碳水" in text:
            return ["lagged_carb_capacity"]
        if has("topset_backoff_comparison"):
            return ["topset_backoff_comparison"]
        if ast.bodypart_expression.get("scope") == "bodypart" and ast.comparison_expression.get("kind") == "progress":
            return ["bodypart_progress"]
        if ast.movement_expression.get("mentions") and ast.comparison_expression.get("kind") == "progress":
            return ["movement_progress"]
        if ast.time_expression.get("kind") == "last_n_matching_sessions" and "胸" in text:
            return ["bodypart_progress"]
        if "影响" in text and {"diet", "training"}.issubset(ast.analysis_target):
            return ["diet_training_association"]
        if ("减脂" in text or "减重" in text) and {"body", "diet", "training"}.issubset(ast.analysis_target):
            return ["fat_loss_synthesis"]
        if any(item in text for item in ("表现", "下降", "容量")) and "training" in ast.analysis_target:
            return ["training_performance"]
        if any(item in text for item in ("训练安排", "频率", "训练日")):
            return ["training_schedule"]
        if any(item in text for item in ("体重", "掉秤")):
            return ["weight_trend"]
        if any(item in text for item in ("饮食", "热量", "宏量")):
            return ["diet_trend"]
        if "训练" in text:
            return ["training_schedule"]
        return []

    def expand(self, task_ids: list[str], ast: IntentAST) -> TaskExpansion:
        if not task_ids or any(task_id not in self.tasks for task_id in task_ids):
            raise RegistryError("no task resolved")
        routes = [TASK_ROUTE[task_id] for task_id in task_ids]
        definitions = [self.tasks[task_id] for task_id in task_ids]
        required = list(dict.fromkeys(capability for route in routes for capability in route.get("caps", ())))
        optional = [capability for capability in dict.fromkeys(capability for route in routes for capability in route.get("optional", ())) if capability not in required]
        slots = list(dict.fromkeys(slot for route in routes for slot in route.get("slots", ())))
        confirmations = list(dict.fromkeys(item for route in routes for item in route.get("confirms", ())))
        if ast.movement_expression.get("mentions") and "movement_identity" not in confirmations:
            confirmations.append("movement_identity")
        if ast.notes_expression.get("requested") and "notes_scope" not in confirmations:
            confirmations.append("notes_scope")
        fields: list[str] = []
        recommended: list[str] = []
        for task_id, definition in zip(task_ids, definitions):
            for source in definition.required_fields:
                canonical = SOURCE_TO_CANONICAL_FIELD.get(source)
                if canonical and canonical not in fields:
                    fields.append(canonical)
            for source in definition.recommended_fields:
                canonical = SOURCE_TO_CANONICAL_FIELD.get(source)
                if canonical and canonical not in fields and canonical not in recommended:
                    recommended.append(canonical)
        minimum: dict[str, int] = {}
        for route in routes:
            for key, value in route.get("minimum", {}).items():
                minimum[key] = max(minimum.get(key, 0), value)
        metrics = list(dict.fromkeys(metric for route in routes for metric in route.get("metrics", ())))
        forbidden = list(dict.fromkeys(code for route in routes for code in route.get("forbidden", ())))
        time = dict(ast.time_expression)
        if time.get("kind") == "unspecified":
            time = {"kind": routes[0].get("time", "recent_available")}
        return TaskExpansion(task_ids, "deterministic_alias", required, optional, [], slots, confirmations, time, fields, recommended, minimum, metrics, routes[0].get("mode", "descriptive"), forbidden)


class ConfirmationState(str, Enum):
    GATED = "GATED"
    TASK_RESOLVED = "TASK_RESOLVED"
    NEEDS_ANALYSIS_TARGET = "NEEDS_ANALYSIS_TARGET"
    NEEDS_MOVEMENT_CONFIRMATION = "NEEDS_MOVEMENT_CONFIRMATION"
    NEEDS_NOTES_SCOPE = "NEEDS_NOTES_SCOPE"
    NEEDS_RAW_PERMISSION = "NEEDS_RAW_PERMISSION"
    EVIDENCE_REQUIREMENTS_READY = "EVIDENCE_REQUIREMENTS_READY"
    DATA_MATERIALIZED = "DATA_MATERIALIZED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    READY_WITH_LIMITS = "READY_WITH_LIMITS"
    READY = "READY"
    BLOCKED = "BLOCKED"


TRANSITIONS = {
    "START": {"gate": "GATED"},
    "GATED": {"task_resolved": "TASK_RESOLVED", "needs_analysis_target": "NEEDS_ANALYSIS_TARGET", "needs_movement_confirmation": "NEEDS_MOVEMENT_CONFIRMATION", "needs_notes_scope": "NEEDS_NOTES_SCOPE", "needs_raw_permission": "NEEDS_RAW_PERMISSION", "blocked": "BLOCKED"},
    "TASK_RESOLVED": {"needs_movement_confirmation": "NEEDS_MOVEMENT_CONFIRMATION", "needs_notes_scope": "NEEDS_NOTES_SCOPE", "evidence_ready": "EVIDENCE_REQUIREMENTS_READY"},
    "EVIDENCE_REQUIREMENTS_READY": {"materialized": "DATA_MATERIALIZED", "insufficient": "INSUFFICIENT_EVIDENCE"},
    "DATA_MATERIALIZED": {"ready": "READY", "limited": "READY_WITH_LIMITS", "insufficient": "INSUFFICIENT_EVIDENCE"},
}


class ConfirmationStateMachine:
    def __init__(self):
        self.state = "START"
        self.history: list[dict[str, str]] = []

    def advance(self, event: str) -> str:
        next_state = TRANSITIONS.get(self.state, {}).get(event)
        if not next_state:
            raise RegistryError(f"invalid transition {self.state} -> {event}")
        self.history.append({"from": self.state, "event": event, "to": next_state})
        self.state = next_state
        return next_state

    def to_dict(self) -> dict[str, Any]:
        return {"state": self.state, "history": list(self.history)}


def registry_snapshot() -> dict[str, Any]:
    return {
        "schema_version": REGISTRY_SCHEMA_VERSION,
        "capability_ids": list(CAPABILITY_IDS),
        "fields": [item.to_dict() for item in FIELD_REGISTRY.values()],
        "tasks": [{"task_id": task_id, "base_task_id": route["base"], **{key: value for key, value in route.items() if key != "base"}} for task_id, route in TASK_ROUTE.items()],
        "metrics": [item.to_dict() for item in METRIC_REGISTRY.values()],
        "claim_policies": [item.to_dict() for item in CLAIM_POLICIES.values()],
    }
