"""Deterministic evidence requirements and claim-boundary validation.

This layer sits after capability mapping and before any future analysis call.
It does not create an ExportPlan, read Raw data, choose Notes scope, or call a
model.  The task registry is deliberately based on fields already exposed by
the current Fitness Ledger view models and Core projections.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
import re
from typing import Any, Iterable


EVIDENCE_REQUIREMENT_SCHEMA_VERSION = "fitness-ledger-evidence-requirement-v1"
EVIDENCE_PROFILE_SCHEMA_VERSION = "fitness-ledger-evidence-profile-v1"
EVIDENCE_EVALUATION_SCHEMA_VERSION = "fitness-ledger-evidence-evaluation-v1"

TIME_SEMANTICS = {
    "recent_available",
    "explicit_calendar_range",
    "last_n_matching_sessions",
    "recent_matching_bodypart_sessions",
    "event_relative_lag",
    "condition_grouped_sessions",
    "unspecified",
}
ANSWERABILITY = {"ready", "ready_with_limits", "insufficient_evidence", "needs_resolution"}
CLAIM_MODES = {
    "descriptive",
    "comparative",
    "association_hypothesis",
    "comparative_association",
    "contextual_hypothesis",
    "multi_source_descriptive",
    "none",
}
EVALUATION_STATUSES = {
    "ready_for_review",
    "needs_confirmation",
    "ready_for_package",
    "insufficient_evidence",
    "ready_with_limits",
}


@dataclass(frozen=True)
class AnalysisTaskDefinition:
    task_id: str
    description: str
    required_fields: tuple[str, ...] = ()
    recommended_fields: tuple[str, ...] = ()
    required_quality_fields: tuple[str, ...] = ()
    minimums: dict[str, int] = field(default_factory=dict)
    alignment: dict[str, Any] = field(default_factory=dict)
    allowed_claim_mode: str = "descriptive"
    allowed_claims: tuple[str, ...] = ()
    forbidden_claims: tuple[str, ...] = ()
    quality_requirements: tuple[str, ...] = ()
    movement_variant_requirements: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "required_fields": list(self.required_fields),
            "recommended_fields": list(self.recommended_fields),
            "required_quality_fields": list(self.required_quality_fields),
            "minimums": dict(self.minimums),
            "alignment": dict(self.alignment),
            "allowed_claim_mode": self.allowed_claim_mode,
            "allowed_claims": list(self.allowed_claims),
            "forbidden_claims": list(self.forbidden_claims),
            "quality_requirements": list(self.quality_requirements),
            "movement_variant_requirements": list(self.movement_variant_requirements),
        }


def _task(task_id: str, description: str, **kwargs: Any) -> AnalysisTaskDefinition:
    return AnalysisTaskDefinition(task_id, description, **kwargs)


TASK_REGISTRY: dict[str, AnalysisTaskDefinition] = {
    "weight_trend": _task(
        "weight_trend", "描述身体重量历史方向和覆盖", required_fields=("body.Date", "body.Weight (kg)"),
        recommended_fields=("body.measurement_context",), required_quality_fields=("body.measurement_context",), minimums={"comparable_records": 3},
        allowed_claims=("描述已记录体重点的方向和范围",),
        forbidden_claims=("宣称稳定减脂趋势", "估算脂肪下降速度", "把波动归因于饮食或训练"),
        quality_requirements=("测量条件一致性", "记录跨度和缺失率"),
    ),
    "body_record_coverage": _task(
        "body_record_coverage", "评估 body 记录覆盖", required_fields=("body.Date",),
        recommended_fields=("body.measurement_context",), allowed_claims=("描述记录覆盖",),
        forbidden_claims=("把缺失日当作稳定趋势",),
    ),
    "macro_trend": _task(
        "macro_trend", "描述每日宏量营养素历史", required_fields=("diet.Date", "diet.Calories (kcal)", "diet.Protein (g)", "diet.Carbs (g)", "diet.Fat (g)"),
        required_quality_fields=("diet.completeness", "diet.value_provenance"), minimums={"days": 3},
        allowed_claims=("描述已记录日的热量和宏量差异",),
        forbidden_claims=("把缺失日当作零摄入", "评价长期热量缺口"),
        quality_requirements=("完整饮食日", "数值来源可追溯"),
    ),
    "diet_record_coverage": _task(
        "diet_record_coverage", "评估饮食记录覆盖", required_fields=("diet.Date",),
        recommended_fields=("diet.completeness",), allowed_claims=("描述饮食记录覆盖",),
        forbidden_claims=("用稀疏记录代表长期饮食"),
    ),
    "session_frequency": _task(
        "session_frequency", "描述训练频率", required_fields=("training.Date",), minimums={"sessions": 2},
        allowed_claims=("描述训练日数量和频率",), forbidden_claims=("凭训练日数量判断训练表现",),
    ),
    "split_distribution": _task(
        "split_distribution", "描述训练 Split 分布", required_fields=("training.Date", "training.Split"),
        allowed_claims=("描述 Split 分布",), forbidden_claims=("把 Split 分布当作动作进步",),
    ),
    "training_record_coverage": _task(
        "training_record_coverage", "评估训练摘要覆盖", required_fields=("training.Date", "training.Split", "training.Standardized Summary"),
        minimums={"sessions": 2}, allowed_claims=("描述训练安排和覆盖",),
        forbidden_claims=("凭训练摘要评价重量、次数或容量",),
    ),
    "overall_performance_comparison": _task(
        "overall_performance_comparison", "比较可比训练表现", required_fields=(
            "training.Date", "training.Split", "training.movements.sets.load", "training.movements.sets.reps",
            "training.movements.sets.set_type", "training.exercise_order",
        ), recommended_fields=("training.movements.sets.RIR", "training.session_notes"),
        minimums={"comparable_sessions": 2}, allowed_claim_mode="comparative",
        allowed_claims=("分别比较可比动作的重量、次数和组型",),
        forbidden_claims=("仅凭训练摘要评价表现", "把不同动作公斤数直接相加"),
        quality_requirements=("动作身份可比", "训练顺序一致性"),
        movement_variant_requirements=("动作 variant 必须分组"),
    ),
    "training_data_sufficiency": _task(
        "training_data_sufficiency", "判断训练表现字段是否充分", required_fields=(
            "training.movements.sets.load", "training.movements.sets.reps", "training.movements.sets.set_type",
        ), recommended_fields=("training.movements.identity",),
        allowed_claims=("说明当前数据能否判断表现",), forbidden_claims=("以摘要字段替代组级表现",),
    ),
    "fat_loss_evidence_synthesis": _task(
        "fat_loss_evidence_synthesis", "综合身体、饮食和训练证据", required_fields=(
            "body.Date", "body.Weight (kg)", "diet.Date", "diet.Calories (kcal)", "diet.Protein (g)",
            "diet.Carbs (g)", "diet.Fat (g)", "training.Date", "training.Split",
        ), required_quality_fields=("body.measurement_context", "diet.completeness"), minimums={"days": 7},
        allowed_claim_mode="multi_source_descriptive", allowed_claims=("综合描述体重、饮食和训练覆盖",),
        forbidden_claims=("把短期体重下降等同于脂肪下降", "直接做因果归因"),
        quality_requirements=("测量条件", "完整饮食日", "观察窗口"),
    ),
    "macro_context": _task("macro_context", "提供减脂问题的饮食上下文", required_fields=("diet.Date", "diet.Calories (kcal)", "diet.Protein (g)", "diet.Carbs (g)", "diet.Fat (g)")),
    "training_consistency": _task("training_consistency", "提供训练一致性上下文", required_fields=("training.Date", "training.Split"), minimums={"sessions": 2}),
    "diet_training_alignment": _task(
        "diet_training_alignment", "按日期对齐饮食与训练", required_fields=(
            "diet.Date", "diet.Protein (g)", "diet.Carbs (g)", "diet.Fat (g)", "training.Date", "training.Split",
        ), minimums={"aligned_training_days": 4}, alignment={"kind": "same_or_aligned_date"},
        allowed_claim_mode="association_hypothesis", allowed_claims=("描述饮食与训练日期的覆盖关系",),
        forbidden_claims=("计算未注册的饮食-训练相关性指数", "仅凭训练摘要计算表现相关性", "做因果结论"),
    ),
    "association_hypothesis": _task(
        "association_hypothesis", "限制个人观察数据的关联性结论", required_fields=("training.Date",),
        minimums={"aligned_training_days": 4}, allowed_claim_mode="association_hypothesis",
        allowed_claims=("报告预先注册指标的方向、样本数和不确定性",),
        forbidden_claims=("使用导致、证明等因果措辞", "生成未注册综合指数"),
    ),
    "coverage_check": _task("coverage_check", "检查饮食训练覆盖", required_fields=("diet.Date", "training.Date"), allowed_claims=("描述对齐日期覆盖",)),
    "lagged_carb_context": _task(
        "lagged_carb_context", "围绕目标训练日检查前 1–3 天碳水", required_fields=("diet.Date", "diet.Carbs (g)", "training.DateTime"),
        minimums={"comparable_sessions": 3}, alignment={"kind": "event_relative_lag", "lookback_days": [1, 2, 3]},
        allowed_claim_mode="association_hypothesis", allowed_claims=("比较目标训练与历史可比训练",),
        forbidden_claims=("断言低碳造成容量下降",), quality_requirements=("训练日锚点", "睡眠和恢复混杂因素"),
    ),
    "top_set_vs_backoff_capacity": _task(
        "top_set_vs_backoff_capacity", "分层比较最佳组与回退组容量", required_fields=(
            "training.movements.identity", "training.movements.sets.load", "training.movements.sets.reps", "training.movements.sets.set_type",
        ), recommended_fields=("training.movements.sets.RIR",), allowed_claim_mode="comparative",
        allowed_claims=("分别评价强度端和容量端",), forbidden_claims=("压缩成单一进步分数",),
        movement_variant_requirements=("动作版本和组型必须保留",),
    ),
"confounder_review": _task("confounder_review", "列出训练比较的混杂因素", recommended_fields=("notes.training", "notes.daily", "training.rest_intervals"), allowed_claim_mode="association_hypothesis", forbidden_claims=("忽略睡眠、恢复、顺序和休息",)),
    "condition_group_comparison": _task(
        "condition_group_comparison", "比较不同练前碳水条件", required_fields=("diet.training_day_timing", "diet.preworkout_carbs", "training.DateTime", "training.exercise_order"),
        minimums={"sessions_per_condition": 3}, alignment={"kind": "condition_grouped_sessions"}, allowed_claim_mode="comparative_association",
        allowed_claims=("比较两组后半段容量的描述性差异",), forbidden_claims=("断言快碳有效或无效",),
    ),
    "late_session_capacity": _task("late_session_capacity", "评价训练后半段容量", required_fields=("training.movements.sets.load", "training.movements.sets.reps", "training.movements.sets.set_type"), allowed_claim_mode="comparative", forbidden_claims=("把不同动作组合总公斤数直接比较",)),
    "fat_amount_trend": _task("fat_amount_trend", "描述脂肪总量趋势", required_fields=("diet.Date", "diet.Fat (g)"), minimums={"days": 7}),
    "fat_source_context": _task("fat_source_context", "在已确认 Notes 后评估脂肪来源上下文", required_fields=("diet.Date", "diet.Fat (g)", "notes.diet.food_sources"), allowed_claim_mode="contextual_hypothesis", forbidden_claims=("仅凭脂肪总量识别来源", "越过 Notes 或 Raw 权限")),
    "training_context_synthesis": _task("training_context_synthesis", "综合训练上下文", required_fields=("training.Date", "training.Split")),
    "top_set_progress": _task("top_set_progress", "比较最佳组进步", required_fields=("training.movements.identity", "training.movements.variant", "training.movements.sets.load", "training.movements.sets.reps", "training.movements.sets.set_type"), minimums={"comparable_sessions": 2}, allowed_claim_mode="comparative", forbidden_claims=("只看重量得出整体进步",)),
    "backoff_capacity": _task("backoff_capacity", "比较回退组容量", required_fields=("training.movements.sets.load", "training.movements.sets.reps", "training.movements.sets.set_type"), allowed_claim_mode="comparative"),
    "session_context_comparison": _task("session_context_comparison", "比较训练会话上下文", required_fields=("training.Date", "training.exercise_order")),
    "bodypart_session_comparison": _task("bodypart_session_comparison", "比较身体部位训练会话", required_fields=("training.Date", "training.movements.bodypart", "training.movements.identity", "training.movements.sets.load", "training.movements.sets.reps"), minimums={"comparable_sessions": 2}, alignment={"kind": "last_n_matching_sessions"}, allowed_claim_mode="comparative", forbidden_claims=("把不同动作公斤数直接相加",)),
    "movement_mix_normalization": _task("movement_mix_normalization", "区分动作池变化", required_fields=("training.movements.bodypart", "training.movements.identity", "training.exercise_order"), allowed_claim_mode="comparative"),
    "bodypart_progress_synthesis": _task("bodypart_progress_synthesis", "综合身体部位进步", required_fields=("training.movements.bodypart", "training.movements.identity", "training.movements.sets.load", "training.movements.sets.reps"), minimums={"comparable_sessions": 3}, allowed_claim_mode="comparative", forbidden_claims=("把身体部位聚合当作单一动作身份",)),
    "movement_coverage": _task("movement_coverage", "检查身体部位动作覆盖", required_fields=("training.movements.bodypart", "training.movements.identity")),
    "movement_load_rep_progress": _task("movement_load_rep_progress", "比较已解析动作的重量次数", required_fields=("movement_history.movement_id", "movement_history.variant", "movement_history.Date", "movement_history.load", "movement_history.reps"), minimums={"comparable_records": 2}, alignment={"kind": "same_movement_recent_history"}, allowed_claim_mode="comparative", forbidden_claims=("忽略动作 variant",)),
    "comparable_session_check": _task("comparable_session_check", "检查动作可比会话", required_fields=("movement_history.movement_id", "movement_history.variant"), minimums={"comparable_records": 2}),
    "training_state_notes_synthesis": _task("training_state_notes_synthesis", "在已确认 Training Notes 后分析状态上下文", required_fields=("training.Date", "training.Split", "notes.training"), minimums={"sessions": 2}, allowed_claim_mode="contextual_hypothesis", forbidden_claims=("把主观 Notes 当作客观表现", "自动扩大 Notes 作用域")),
}


def task_registry() -> dict[str, dict[str, Any]]:
    return {key: value.to_dict() for key, value in TASK_REGISTRY.items()}


@dataclass(frozen=True)
class EvidenceRequirement:
    analysis_task_ids: list[str]
    required_capabilities: list[str]
    time_semantics: dict[str, Any]
    required_confirmations: list[str]
    required_fields: list[str]
    recommended_fields: list[str]
    required_quality_fields: list[str]
    minimums: dict[str, int]
    alignment: dict[str, Any]
    quality_requirements: list[str]
    movement_variant_requirements: list[str]
    allowed_claim_mode: str
    allowed_claims: list[str]
    forbidden_claims: list[str]
    required_next_action: str
    ignored_model_derived_metrics: list[str]
    schema_version: str = EVIDENCE_REQUIREMENT_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceProfile:
    available_modules: list[str]
    selected_modules: list[str]
    authorized_modules: list[str]
    candidate_record_count: int
    materialized_record_count: int | None
    exported_record_count: int | None
    module_candidate_counts: dict[str, int]
    selected_dates_by_module: dict[str, int]
    aligned_day_count: int | None
    field_completeness: dict[str, float]
    provenance: dict[str, str]
    quality_flags: list[str]
    schema_version: str = EVIDENCE_PROFILE_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EvidenceEvaluation:
    status: str
    answerability: str
    allowed_claim_mode: str
    allowed_claims: list[str]
    forbidden_claims: list[str]
    missing_information: list[str]
    required_next_action: str
    evidence_requirements: EvidenceRequirement
    evidence_profile: EvidenceProfile
    schema_version: str = EVIDENCE_EVALUATION_SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "answerability": self.answerability,
            "allowed_claim_mode": self.allowed_claim_mode,
            "allowed_claims": list(self.allowed_claims),
            "forbidden_claims": list(self.forbidden_claims),
            "missing_information": list(self.missing_information),
            "required_next_action": self.required_next_action,
            "evidence_requirements": self.evidence_requirements.to_dict(),
            "evidence_profile": self.evidence_profile.to_dict(),
        }


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def _goal_text(requirement: Any, user_goal: str) -> str:
    return " ".join([str(user_goal or ""), str(getattr(requirement, "analysis_goal", "") or ""), *getattr(requirement, "questions_to_answer", [])]).casefold()


def _time_semantics(goal: str, facts: Any | None) -> dict[str, Any]:
    date_text = list(getattr(facts, "date_text", []) or [])
    explicit_date_text = [item for item in date_text if re.search(r"\d{4}[-/]?\d{1,2}[-/]?\d{1,2}|\d{1,2}月\d{1,2}[日号]", str(item))]
    if explicit_date_text or re.search(r"\d{4}[-/]?\d{1,2}[-/]?\d{1,2}|\d{1,2}月\d{1,2}[日号]", goal):
        return {"kind": "explicit_calendar_range", "source": "user_input", "formal_dates": False}
    if any(token in goal for token in ("前两三天", "前1-3天", "滞后", "之前几天")):
        return {"kind": "event_relative_lag", "anchor": "target_training_session", "lookback_days": [1, 2, 3]}
    if any(token in goal for token in ("运动饮料", "练前快碳", "不喝", "条件")):
        return {"kind": "condition_grouped_sessions", "conditions": ["user_defined_condition_a", "user_defined_condition_b"]}
    if any(token in goal for token in ("最近两次", "最近两场", "最后两次")):
        return {"kind": "last_n_matching_sessions", "n": 2, "match": "deterministic_core"}
    if "胸训" in goal or "胸部整体" in goal or "肩部整体" in goal:
        return {"kind": "recent_matching_bodypart_sessions", "match": "deterministic_core"}
    return {"kind": "recent_available", "resolver": "deterministic_core"}


def _select_tasks(requirement: Any, user_goal: str, facts: Any | None) -> list[str]:
    capabilities = {item.capability_id for item in getattr(requirement, "required_capabilities", [])}
    capabilities.update(item.capability_id for item in getattr(requirement, "optional_capabilities", []))
    goal = _goal_text(requirement, user_goal)
    tasks: list[str] = []
    bodypart_session_compare = any(token in goal for token in ("最近两次", "最近两场", "最后两次")) and any(token in goal for token in ("胸训", "胸部", "肩部"))

    def add(*task_ids: str) -> None:
        for task_id in task_ids:
            if task_id not in tasks:
                tasks.append(task_id)

    if {"body_history", "diet_macros", "training_context"}.issubset(capabilities) and any(token in goal for token in ("减脂", "减重", "整体")):
        add("fat_loss_evidence_synthesis", "weight_trend", "macro_context", "training_consistency")
    else:
        if "body_history" in capabilities:
            add("weight_trend", "body_record_coverage")
        if "diet_macros" in capabilities:
            if "training_context" in capabilities:
                add("diet_training_alignment", "coverage_check")
                if any(token in goal for token in ("影响", "相关", "低碳", "碳水", "快碳", "饮料")):
                    add("association_hypothesis")
            else:
                add("macro_trend", "diet_record_coverage")
        if "training_context" in capabilities:
            if bodypart_session_compare:
                add("bodypart_session_comparison", "movement_mix_normalization")
            elif any(token in goal for token in ("表现", "下降", "提高", "进步", "容量", "最佳组")) or (
                "diet_macros" in capabilities and any(token in goal for token in ("影响", "相关", "低碳", "碳水", "快碳", "饮料"))
            ):
                add("overall_performance_comparison", "training_data_sufficiency")
            else:
                add("session_frequency", "split_distribution", "training_record_coverage")
        if "movement_progress" in capabilities:
            if bodypart_session_compare:
                pass
            elif any(token in goal for token in ("胸部整体", "肩部整体", "身体部位", "整体")):
                add("bodypart_progress_synthesis", "movement_coverage")
            else:
                add("movement_load_rep_progress", "comparable_session_check")
        if "notes_context" in capabilities:
            add("training_state_notes_synthesis")

    if any(token in goal for token in ("最佳组", "回退组", "后续容量")):
        add("top_set_progress", "backoff_capacity", "top_set_vs_backoff_capacity", "session_context_comparison")
    if any(token in goal for token in ("前两三天", "低碳", "训练容量")):
        add("lagged_carb_context", "top_set_vs_backoff_capacity", "confounder_review")
    if any(token in goal for token in ("运动饮料", "练前快碳")):
        add("condition_group_comparison", "late_session_capacity", "confounder_review")
    if any(token in goal for token in ("脂肪来源", "动物脂肪", "烹调用油")):
        add("fat_amount_trend", "fat_source_context", "training_context_synthesis")
    if "结合" in goal and "notes_context" in capabilities:
        add("training_state_notes_synthesis")
    return tasks


class EvidenceRequirementCompiler:
    """Compile model output into registered, deterministic analysis tasks."""

    def compile(self, requirement: Any, user_goal: str = "", facts: Any | None = None) -> EvidenceRequirement:
        task_ids = _select_tasks(requirement, user_goal, facts)
        if not task_ids:
            task_ids = ["coverage_check"]
        definitions = [TASK_REGISTRY[item] for item in task_ids]
        capabilities = _unique([item.capability_id for item in getattr(requirement, "required_capabilities", [])])
        required = _unique(field for item in definitions for field in item.required_fields)
        recommended = _unique(field for item in definitions for field in item.recommended_fields if field not in required)
        quality_fields = _unique(field for item in definitions for field in item.required_quality_fields)
        minimums: dict[str, int] = {}
        for item in definitions:
            for key, value in item.minimums.items():
                minimums[key] = max(minimums.get(key, 0), value)
        alignments = [item.alignment for item in definitions if item.alignment]
        goal = _goal_text(requirement, user_goal)
        confirmations = []
        if "notes_context" in capabilities:
            confirmations.append("notes_scope")
        if "movement_progress" in capabilities and (getattr(facts, "movement_ambiguous", False) or (getattr(facts, "movement_mentions", []) and not getattr(facts, "movement_unique", False))):
            confirmations.append("movement_identity")
        if any(item.kind == "explicit_user_phrase" for item in []):
            confirmations.append("date_range")
        claim_mode = "descriptive"
        if "movement_progress" in capabilities or any(item.allowed_claim_mode == "comparative" for item in definitions):
            claim_mode = "comparative"
        if "diet_macros" in capabilities and "training_context" in capabilities:
            claim_mode = "association_hypothesis"
        if {"body_history", "diet_macros", "training_context"}.issubset(set(capabilities)):
            claim_mode = "multi_source_descriptive"
        if "notes_context" in capabilities and len(capabilities) == 1:
            claim_mode = "contextual_hypothesis"
        allowed = _unique(claim for item in definitions for claim in item.allowed_claims)
        forbidden = _unique(claim for item in definitions for claim in item.forbidden_claims)
        quality = _unique(quality for item in definitions for quality in item.quality_requirements)
        variants = _unique(value for item in definitions for value in item.movement_variant_requirements)
        ignored = [str(item.name) for item in getattr(requirement, "derived_metrics", [])]
        return EvidenceRequirement(
            task_ids,
            capabilities,
            _time_semantics(goal, facts),
            _unique(confirmations),
            required,
            recommended,
            quality_fields,
            minimums,
            {"rules": alignments},
            quality,
            variants,
            claim_mode,
            allowed,
            forbidden,
            "resolve_evidence_requirements",
            ignored,
        )


def _module_for_field(field_name: str) -> str:
    return field_name.split(".", 1)[0]


def build_evidence_profile(catalog: Any, draft: Any, mapping: Any) -> EvidenceProfile:
    available = [item.module_id for item in catalog.modules if item.available]
    selected = list(dict.fromkeys(draft.selected_modules))
    authorized = [item for item in selected if item != "raw_entries"]
    if getattr(mapping, "notes_scope_status", "not_selected") != "confirmed":
        authorized = [item for item in authorized if item != "notes"]
    cards = {item.candidate_record_id: item for item in catalog.candidate_records}
    counts = Counter(cards[item].module_id for item in draft.candidate_record_ids if item in cards)
    dates: dict[str, set[str]] = defaultdict(set)
    for record_id in draft.candidate_record_ids:
        record = cards.get(record_id)
        if record and record.date:
            dates[record.module_id].add(record.date)
    selected_dates = {module: len(values) for module, values in dates.items()}
    aligned = None
    if "diet" in dates and "training" in dates:
        aligned = len(dates["diet"].intersection(dates["training"]))
    completeness: dict[str, float] = {}
    for module in selected:
        card = next((item for item in catalog.modules if item.module_id == module), None)
        if not card:
            continue
        for field_name, value in card.field_coverage.items():
            completeness[f"{module}.{field_name}"] = float(value)
        if card.record_count and card.date_start:
            completeness[f"{module}.Date"] = 1.0
    quality_flags = []
    if any("Standardized Summary" in fields for fields in draft.selected_fields.values()):
        quality_flags.append("training_summary_only")
    if not draft.candidate_record_ids:
        quality_flags.append("no_candidate_records")
    return EvidenceProfile(
        available,
        selected,
        authorized,
        len(draft.candidate_record_ids),
        None,
        None,
        dict(counts),
        selected_dates,
        aligned,
        completeness,
        {module: "deterministic_view_model" for module in selected},
        quality_flags,
    )


def _field_available(field_name: str, draft: Any, profile: EvidenceProfile) -> bool:
    module = _module_for_field(field_name)
    if module == "notes":
        return module in profile.authorized_modules
    if module == "movement_history":
        return "movement_history" in profile.authorized_modules and any(record_id.startswith("movement-history:") for record_id in draft.candidate_record_ids)
    bare = field_name.split(".", 1)[-1]
    selected = set(draft.selected_fields.get(module, []))
    if bare in selected:
        return True
    if field_name.endswith("Date") and module in profile.selected_modules:
        return bool(profile.selected_dates_by_module.get(module))
    return False


def evaluate_evidence(requirement: EvidenceRequirement, profile: EvidenceProfile, draft: Any) -> EvidenceEvaluation:
    missing: list[str] = []
    for field_name in requirement.required_fields:
        if not _field_available(field_name, draft, profile):
            missing.append(field_name)
    missing_quality = [field_name for field_name in requirement.required_quality_fields if not _field_available(field_name, draft, profile)]
    missing_counts: list[str] = []
    for key, minimum in requirement.minimums.items():
        if key == "comparable_records":
            observed = profile.candidate_record_count
        elif key in {"days", "sessions"}:
            observed = max(profile.selected_dates_by_module.values(), default=0)
        elif key == "aligned_training_days":
            observed = profile.aligned_day_count or 0
        else:
            observed = 0
        if observed < minimum:
            missing_counts.append(f"{key}>={minimum} (observed {observed})")
    if missing_quality:
        missing.extend(f"quality:{item}" for item in missing_quality)
    if missing_counts:
        missing.extend(f"count:{item}" for item in missing_counts)
    if requirement.required_confirmations:
        answerability = "needs_resolution"
        status = "needs_confirmation"
        next_action = "resolve_confirmations"
    elif missing:
        hard_missing = [item for item in missing if not item.startswith("quality:")]
        answerability = "insufficient_evidence" if hard_missing else "ready_with_limits"
        status = "insufficient_evidence" if hard_missing else "ready_with_limits"
        next_action = "downgrade_to_coverage_report" if hard_missing else "return_analysis_with_limits"
    else:
        answerability = "ready"
        status = "ready_for_review" if profile.materialized_record_count is None else "ready_for_package"
        next_action = "resolve_evidence_requirements"
    allowed = list(requirement.allowed_claims)
    if answerability == "insufficient_evidence":
        allowed = _unique(["描述当前已有字段和记录覆盖", "明确说明当前数据不足以回答原问题", *allowed])
    forbidden = list(requirement.forbidden_claims)
    if missing:
        forbidden = _unique([*forbidden, "把缺失字段当作零或已观测", "把路由成功当作分析结论"])
    return EvidenceEvaluation(status, answerability, requirement.allowed_claim_mode if answerability != "needs_resolution" else "none", allowed, forbidden, _unique(missing), next_action, requirement, profile)


def compile_and_evaluate(requirement: Any, user_goal: str, facts: Any, catalog: Any, draft: Any, mapping: Any) -> EvidenceEvaluation:
    requirement_spec = EvidenceRequirementCompiler().compile(requirement, user_goal, facts)
    profile = build_evidence_profile(catalog, draft, mapping)
    return evaluate_evidence(requirement_spec, profile, draft)
