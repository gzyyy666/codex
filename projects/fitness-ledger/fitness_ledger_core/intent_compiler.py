"""Deterministic request grounding and compilation into an export plan draft."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, replace

from .candidate_cards import CandidatePackage, CandidateSummarizer
from .data_catalog import DataCatalog, DateRangeResolver, MovementResolver
from .intelligent_export_models import DateIntent, ExportPlanDraft, INTENT_DIMENSIONS, IntentSpec, MovementMention, SemanticHints
from .query_scope import QueryScope, QueryScopeResolver


class IntentCompileError(ValueError):
    def __init__(self, message: str, code: str = "NO_SAFE_SCOPE") -> None:
        super().__init__(message)
        self.code = code


DIMENSION_MODULES = {
    "body_state": {"body": ("Date", "Weight (kg)")},
    "diet_macros": {"diet": ("Date", "Calories (kcal)", "Protein (g)", "Carbs (g)", "Fat (g)")},
    "training_context": {"training": ("Date", "Split", "Standardized Summary")},
    "movement_progress": {"movement_progress": ("date", "movement_id", "sets", "order")},
    "daily_notes": {"notes": ("date", "scope", "note_candidate_id")},
    "diet_notes": {"notes": ("date", "scope", "note_candidate_id")},
    "training_notes": {"notes": ("date", "scope", "note_candidate_id")},
    "movement_notes": {"notes": ("date", "scope", "note_candidate_id")},
    "raw_trace": {"raw_entries": ("date", "preview")},
}

NOTE_TYPES = {
    "daily_notes": "daily",
    "diet_notes": "diet",
    "training_notes": "training",
    "movement_notes": "movement",
}

_EXCLUDE = re.compile(r"(?:不要|不看|不分析|排除|不包含|without|exclude|not)\s*([^，,。；;]+)", re.I)
_ONLY = re.compile(r"(?:只看|只分析|仅看|仅分析|只想看|only|just)\s*([^，,。；;]+)", re.I)
_INCLUDE = re.compile(r"(?:包括|包含|需要|include|including)\s*([^，,。；;]+)", re.I)
_DATE_WORDS = ("最近一个月", "最近一周", "最近几个月", "最近两个月", "最近四周", "最近八周", "最近十二周", "这几个月", "上周", "这周", "本周", "最近", "近期")
_BODY_TERMS = ("体重", "体脂", "身体", "身材", "体型", "减脂", "减重", "weight", "body")
_DIET_TERMS = ("饮食", "低碳", "碳水", "热量", "卡路里", "蛋白", "脂肪", "宏量", "摄入", "diet", "macro", "carb", "calorie", "intake")
_TRAINING_TERMS = ("训练", "锻炼", "健身", "训练状态", "training", "workout")
_PROGRESS_TERMS = ("进步", "增长", "下降", "表现", "进展", "progress", "performance")
_IMPACT_TERMS = ("影响", "受影响", "导致", "关系", "相关", "whether", "impact")
_NOTE_TERMS = ("备注", "笔记", "便签", "notes", "note", "总结记录", "每日总结")


@dataclass(frozen=True)
class ScopeOperation:
    operator: str
    target: str
    span: str
    clause_index: int


@dataclass(frozen=True)
class CommandDate:
    raw_text: str = ""
    kind: str = "none"


@dataclass(frozen=True)
class AnalysisExportCommand:
    """Closed, deterministic request protocol used by the MVP parser."""

    request_kind: str
    domains: list[str]
    layers: list[str]
    notes_scopes: list[str]
    scope_operations: list[ScopeOperation]
    date: CommandDate
    movement_mentions: list[str]
    body_parts: list[str]
    status: str
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "request_kind": self.request_kind,
            "domains": list(self.domains),
            "layers": list(self.layers),
            "notes_scopes": list(self.notes_scopes),
            "scope_operations": [
                {"operator": item.operator, "target": item.target, "span": item.span, "clause_index": item.clause_index}
                for item in self.scope_operations
            ],
            "date": {"raw_text": self.date.raw_text, "kind": self.date.kind},
            "movement_mentions": list(self.movement_mentions),
            "body_parts": list(self.body_parts),
            "status": self.status,
            "errors": list(self.errors or []),
        }


_ANALYSIS_MARKERS = (
    "分析", "看", "查看", "看看", "对比", "比较", "总结", "评估", "趋势", "变化", "走势", "表现", "进步",
    "增长", "下降", "导出", "整理相关数据", "回看", "拿出来", "归纳", "汇总", "概览", "数据", "日志", "截至", "曲线", "轨迹", "总量", "怎么样", "如何", "吗",
)
_UNSUPPORTED_OPERATION_MARKERS = (
    "删除", "删掉", "清理数据", "修改", "改掉", "改成", "保存", "录入", "新增", "同步", "上传", "发布", "恢复", "合并", "生成模板", "创建模板",
)
_RAW_MARKERS = ("原始记录", "原始输入", "原始数据", "原文追溯", "追溯原始", "原始记录文本", "raw record", "raw input", "raw trace")
_AMBIGUOUS_MOVEMENT_ALIASES = ("BP", "卧推", "下斜推", "推胸", "推举")
_DATE_RELATIVE_TEXT = (
    "最近几天", "最近一周", "最近一个月", "最近几个月", "这几个月", "这阵子", "这段时间", "上周", "本周", "这周",
    "上个月", "这个月", "最近", "近期", "一段时间", "最近几次训练", "上个训练周期", "一整个月",
)
_SCOPE_TARGETS = ("body", "diet", "training", "movement", "daily_notes", "diet_notes", "training_notes", "movement_notes", "raw")


def _has_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = str(text or "").casefold()
    return any(str(term).casefold() in lowered for term in terms)


class AnalysisExportCommandParser:
    """Parse a finite-domain read request before IntentCompiler touches data."""

    def __init__(self, resolver: QueryScopeResolver, catalog: DataCatalog) -> None:
        self.resolver = resolver
        self.catalog = catalog

    @staticmethod
    def _clauses(text: str) -> list[str]:
        return [part.strip() for part in re.split(r"[，,。；;]", text) if part.strip()]

    @staticmethod
    def _target_tokens(fragment: str) -> set[str]:
        value = str(fragment or "")
        lowered = value.casefold()
        targets: set[str] = set()
        has_note_marker = _has_any(value, ("备注", "笔记", "便签", "notes", "note", "日记"))
        if _has_any(value, _RAW_MARKERS) or "raw" in lowered:
            targets.add("raw")
        if _has_any(value, ("备注", "笔记", "便签", "notes", "note", "日记")):
            if _has_any(value, ("每日总结", "日记", "daily")):
                targets.add("daily_notes")
            if _has_any(value, ("饮食", "吃", "食物", "摄入", "diet")):
                targets.add("diet_notes")
            if _has_any(value, ("训练", "健身", "锻炼", "training", "workout")):
                targets.add("training_notes")
            if _has_any(value, ("动作", "movement")):
                targets.add("movement_notes")
            if not targets.intersection({"daily_notes", "diet_notes", "training_notes", "movement_notes"}):
                targets.update({"daily_notes", "diet_notes", "training_notes", "movement_notes"})
        if not has_note_marker and _has_any(value, ("体重", "体脂", "身体", "减脂", "减重", "身材", "体型", "weight", "body")):
            targets.add("body")
        if not has_note_marker and _has_any(value, ("饮食", "吃法", "吃的", "食物", "营养", "低碳", "碳水", "热量", "卡路里", "蛋白", "脂肪", "宏量", "摄入", "diet", "macro", "carb", "calorie", "intake")):
            targets.add("diet")
        if not has_note_marker and _has_any(value, ("训练", "锻炼", "健身", "训练状态", "训练概况", "训练表现", "training", "workout", "练得", "练习")):
            targets.add("training")
        if "动作" in value or "movement" in lowered:
            targets.add("movement")
        return targets

    @staticmethod
    def _date(text: str) -> CommandDate:
        explicit = DateRangeResolver.extract_raw_date_mentions(text)
        if explicit:
            return CommandDate(explicit[0], "explicit_calendar")
        for value in sorted(_DATE_RELATIVE_TEXT, key=len, reverse=True):
            if value in text:
                if value in {"最近几次训练", "上个训练周期"}:
                    return CommandDate(value, "record_relative")
                if value == "一整个月":
                    return CommandDate(value, "incomplete")
                return CommandDate(value, "calendar_relative")
        return CommandDate()

    @classmethod
    def _scope_operations(cls, text: str) -> list[ScopeOperation]:
        operations: list[ScopeOperation] = []
        clause_index = lambda position: text[:position].count("，") + text[:position].count(",") + text[:position].count("；") + text[:position].count(";")
        patterns = (
            ("only", r"(?:只看|只分析|只保留|只需要|只想知道|仅看|仅分析|就看|主要看|重点看|单独看)\s*([^，,。；;]+)"),
            ("include", r"(?:包括|包含|加上|连同|同时看|一并分析|放进来)\s*([^，,。；;]+)"),
            ("exclude", r"(?:不要带|不带|不要|不看|不分析|排除|不包含|忽略|先别管|先不管|不展开|暂时不考虑|剔除|别带|别看|跳过|不用)\s*([^，,。；;]+)"),
        )
        for operator, pattern in patterns:
            for match in re.finditer(pattern, text, re.I):
                fragment = match.group(1).strip()
                for target in sorted(cls._target_tokens(fragment).intersection(_SCOPE_TARGETS)):
                    operations.append(ScopeOperation(operator, target, match.group(0).strip(), clause_index(match.start())))
        for match in re.finditer(r"([^，,。；;]+?)\s*(?:放一边|暂时忽略|先别管|先不管|暂时不看|不用看)", text):
            fragment = match.group(1).strip()
            for target in sorted(cls._target_tokens(fragment).intersection(_SCOPE_TARGETS)):
                operations.append(ScopeOperation("exclude", target, match.group(0).strip(), clause_index(match.start())))
        for match in re.finditer(r"([^，,。；;]+?)\s*(?:不要带|不带|别看|跳过)", text):
            fragment = match.group(1).strip()
            if not _has_any(fragment, ("备注", "笔记", "便签", "notes", "note", "日记")):
                continue
            for target in sorted(cls._target_tokens(fragment).intersection(_SCOPE_TARGETS)):
                operations.append(ScopeOperation("exclude", target, match.group(0).strip(), clause_index(match.start())))
        # “饮食不用”“训练不用” bind the target on the left of the operator.
        for match in re.finditer(r"([^，,。；;]+?)\s*不用(?:看|分析)?(?:了)?", text):
            fragment = match.group(1).strip()
            for target in sorted(cls._target_tokens(fragment).intersection(_SCOPE_TARGETS)):
                operations.append(ScopeOperation("exclude", target, match.group(0).strip(), clause_index(match.start())))
        unique = {}
        for item in operations:
            unique[(item.operator, item.target, item.span, item.clause_index)] = item
        return list(unique.values())

    @staticmethod
    def _note_scopes(text: str) -> tuple[set[str], set[str]]:
        value = str(text or "")
        requested: set[str] = set()
        if _has_any(value, ("每日总结", "日记", "daily summary")):
            requested.add("daily")
        if _has_any(value, ("饮食备注", "饮食笔记", "饮食便签", "饮食 notes", "吃饭日志", "食物记录", "宏量 notes")):
            requested.add("diet")
        if _has_any(value, ("训练备注", "训练笔记", "训练便签", "训练 notes", "健身日志")):
            requested.add("training")
        if _has_any(value, ("动作备注", "动作笔记", "动作 notes")):
            requested.add("movement")
        generic = _has_any(value, ("备注", "笔记", "便签", "notes", "note"))
        return requested, (requested if requested else ({"daily", "diet", "training", "movement"} if generic else set()))

    def parse(self, request: str) -> AnalysisExportCommand:
        text = str(request or "").strip()[:2000]
        operations = self._scope_operations(text)
        unsupported = [term for term in _UNSUPPORTED_OPERATION_MARKERS if term.casefold() in text.casefold()]
        read_intent = _has_any(text, _ANALYSIS_MARKERS) or _has_any(text, _RAW_MARKERS)
        if unsupported:
            status = "conflict" if read_intent else "unsupported_operation"
            return AnalysisExportCommand("unsupported_operation", [], [], [], operations, self._date(text), [], [], status, ["UNSUPPORTED_OPERATION"])

        scope = self.resolver.resolve(text, self.catalog)
        movement_mentions = list(scope.explicit_movement_mentions)
        unresolved = list(scope.unresolved_movement_mentions)
        for alias in _AMBIGUOUS_MOVEMENT_ALIASES:
            if alias.casefold() in text.casefold() and alias not in movement_mentions:
                unresolved.append(alias)
        movement_mentions.extend(item for item in unresolved if item not in movement_mentions)
        note_scopes, note_scope_targets = self._note_scopes(text)
        note_surface = re.sub(r"(?:饮食|吃饭|食物)记录|吃饭日志|健身日志|(?:饮食|训练|动作|每日)?(?:备注|笔记|便签|notes?|日记)", " ", text, flags=re.I)
        base: set[str] = set()
        if _has_any(note_surface, _BODY_TERMS):
            base.add("body")
        if _has_any(note_surface, ("饮食", "吃法", "吃的", "食物", "营养", "低碳", "碳水", "热量", "卡路里", "蛋白", "脂肪", "宏量", "摄入", "减脂", "减重", "diet", "macro", "carb", "calorie", "intake")):
            base.add("diet")
        if _has_any(note_surface, ("训练", "锻炼", "健身", "训练状态", "训练概况", "训练表现", "training", "workout", "练得", "练习")):
            base.add("training")
        if movement_mentions and not note_scopes and not _has_any(text, ("不要具体动作", "不分析具体动作", "别展开动作历史")):
            base.add("movement")
        if note_scope_targets:
            base.update({"notes"})
        if scope.target_body_part_ids and not movement_mentions and _has_any(text, ("训练", "训练概览", "总量", "整体", "练得", "表现", "够不够", "怎么样", "如何")):
            base.add("training")
        if _has_any(text, _RAW_MARKERS):
            base.add("raw")
        if not read_intent and not base:
            return AnalysisExportCommand("unknown", [], [], sorted(note_scopes), operations, self._date(text), movement_mentions, list(scope.target_body_part_ids), "clarification_required", ["NO_READ_INTENT"])

        target_dims = {"body": {"body_state"}, "diet": {"diet_macros"}, "training": {"training_context"}, "movement": {"movement_progress"}, "daily_notes": {"daily_notes"}, "diet_notes": {"diet_notes"}, "training_notes": {"training_notes"}, "movement_notes": {"movement_notes"}, "raw": {"raw_trace"}}
        base_dims: set[str] = set()
        if "body" in base: base_dims.update(target_dims["body"])
        if "diet" in base: base_dims.update(target_dims["diet"])
        if "training" in base: base_dims.update(target_dims["training"])
        if "movement" in base: base_dims.update(target_dims["movement"])
        if "raw" in base: base_dims.update(target_dims["raw"])
        for scope_name in note_scopes:
            base_dims.add({"daily": "daily_notes", "diet": "diet_notes", "training": "training_notes", "movement": "movement_notes"}[scope_name])
        only_dims: set[str] = set()
        include_dims: set[str] = set()
        exclude_dims: set[str] = set()
        for item in operations:
            values = target_dims.get(item.target, set())
            if item.operator == "only": only_dims.update(values)
            elif item.operator == "include": include_dims.update(values)
            else: exclude_dims.update(values)
        if only_dims:
            base_dims.update(only_dims)
            base_dims.intersection_update(only_dims | include_dims)
        base_dims.update(include_dims)
        conflicts: list[str] = []
        if only_dims.intersection(exclude_dims): conflicts.append("ONLY_EXCLUDE_SAME_TARGET")
        if "raw_trace" in base_dims and "raw_trace" in exclude_dims: conflicts.append("RAW_SCOPE_CONFLICT")
        if "movement_progress" in base_dims and "movement_progress" in exclude_dims: conflicts.append("MOVEMENT_SCOPE_CONFLICT")
        if only_dims and not (base_dims - exclude_dims): conflicts.append("EMPTY_ONLY_SCOPE")
        final_dims = [item for item in INTENT_DIMENSIONS if item in base_dims and item not in exclude_dims]
        date = self._date(text)
        if date.kind in {"incomplete", "record_relative"}:
            conflicts.append("DATE_REQUIRES_CLARIFICATION")
        if movement_mentions and any(item in movement_mentions for item in unresolved):
            conflicts.append("MOVEMENT_REQUIRES_CLARIFICATION")
        if not final_dims:
            conflicts.append("EMPTY_SCOPE")
        if conflicts:
            status = "conflict" if any(item.endswith("CONFLICT") or item.startswith("ONLY_") or item == "EMPTY_ONLY_SCOPE" for item in conflicts) or ("movement_progress" in exclude_dims and bool(movement_mentions)) else "clarification_required"
        else:
            status = "resolved"
        domains = [item for item in ("body", "diet", "training", "movement") if item in base or (item == "movement" and "movement_progress" in final_dims)]
        layers = []
        if any(item in final_dims for item in ("body_state", "diet_macros", "training_context", "movement_progress")): layers.append("structured")
        if any(item.endswith("_notes") for item in final_dims): layers.append("notes")
        if "raw_trace" in final_dims: layers.append("raw")
        return AnalysisExportCommand("raw_trace" if "raw_trace" in final_dims and not (set(final_dims) - {"raw_trace"}) else "analysis_export", domains, layers, sorted(note_scopes), operations, date, movement_mentions, list(scope.target_body_part_ids), status, conflicts)


@dataclass(frozen=True)
class DeterministicRequestFacts:
    request: str
    query_scope: QueryScope
    dimensions: list[str]
    excluded_dimensions: list[str]
    only_dimensions: list[str]
    include_dimensions: list[str]
    exclude_dimensions: list[str]
    date_text: list[str]
    notes_requested: bool
    notes_scopes: list[str]
    raw_requested: bool
    movement_unique: bool
    movement_ambiguous: bool
    command: AnalysisExportCommand | None = None

    def to_model_context(self) -> dict:
        """Only non-sensitive facts and original surface text go to the model."""
        return {
            "scope": {
                "only": bool(self.only_dimensions),
                "include": bool(self.include_dimensions),
                "exclude": bool(self.exclude_dimensions),
                "excluded_dimensions": list(self.exclude_dimensions),
                "only_dimensions": list(self.only_dimensions),
            },
            "recognized_entities": {
                "date_expressions": list(self.date_text),
                "body_parts": list(self.query_scope.target_body_part_ids),
                "movement_mentions": list(self.query_scope.explicit_movement_mentions),
                "movement_unique": self.movement_unique,
                "movement_ambiguous": self.movement_ambiguous,
                "notes_requested": self.notes_requested,
                "notes_scopes": list(self.notes_scopes),
                "raw_requested": self.raw_requested,
            },
            "deterministic_dimensions": list(self.dimensions),
            "command": self.command.to_dict() if self.command else {},
        }


def _lexical_dimensions(text: str, *, query_scope: QueryScope | None = None, notes_requested: bool | None = None) -> set[str]:
    value = str(text or "")
    lowered = value.casefold()
    notes = bool(notes_requested) if notes_requested is not None else any(term.casefold() in lowered for term in _NOTE_TERMS)
    dimensions: set[str] = set()
    if any(term.casefold() in lowered for term in _BODY_TERMS):
        dimensions.add("body_state")
    if any(term.casefold() in lowered for term in _DIET_TERMS) or any(term in value for term in ("减脂", "减重")):
        dimensions.add("diet_macros")
    if any(term.casefold() in lowered for term in _TRAINING_TERMS):
        dimensions.add("training_context")
    if query_scope and any(str(mention).casefold() in lowered for mention in query_scope.explicit_movement_mentions):
        dimensions.add("movement_progress")
    if any(term.casefold() in lowered for term in _PROGRESS_TERMS) and query_scope and query_scope.explicit_movement_mentions:
        dimensions.add("movement_progress")

    if notes:
        dimensions.difference_update({"diet_macros", "training_context", "movement_progress"})
        if any(term.casefold() in lowered for term in ("每日", "日记", "daily", "总结记录", "每日总结")):
            dimensions.add("daily_notes")
        if any(term.casefold() in lowered for term in _DIET_TERMS):
            dimensions.add("diet_notes")
        if any(term.casefold() in lowered for term in _TRAINING_TERMS):
            dimensions.add("training_notes")
        if query_scope and query_scope.explicit_movement_mentions or "动作" in value:
            dimensions.add("movement_notes")
    return dimensions


class ScopeFence:
    """Generic include/exclude/only fence; explicit request scope wins."""

    @staticmethod
    def _dimensions(text: str) -> set[str]:
        return _lexical_dimensions(text)

    @classmethod
    def apply(cls, request: str, intent: IntentSpec) -> IntentSpec:
        text = str(request or "")
        excluded = set(intent.excluded_dimensions)
        included = set(intent.dimensions)
        only_dims: set[str] = set()
        explicit_include: set[str] = set()
        for match in _EXCLUDE.finditer(text):
            excluded.update(cls._dimensions(match.group(1)))
        for match in _ONLY.finditer(text):
            only_dims.update(cls._dimensions(match.group(1)))
        for match in _INCLUDE.finditer(text):
            explicit_include.update(cls._dimensions(match.group(1)))
        if only_dims:
            included.intersection_update(only_dims)
            excluded.update(set(INTENT_DIMENSIONS) - only_dims)
        included.update(explicit_include)
        included.difference_update(excluded)
        return replace(
            intent,
            dimensions=[item for item in INTENT_DIMENSIONS if item in included],
            excluded_dimensions=[item for item in INTENT_DIMENSIONS if item in excluded],
        )


class IntentCompiler:
    def __init__(self, views) -> None:
        self.views = views
        self.movement_resolver = MovementResolver(views)
        self.date_resolver = DateRangeResolver()
        self.query_scope_resolver = QueryScopeResolver(views=views)
        self.command_parser: AnalysisExportCommandParser | None = None

    @staticmethod
    def _date_text(request: str) -> list[str]:
        explicit = DateRangeResolver.extract_raw_date_mentions(request)
        if explicit:
            return explicit
        text = str(request or "")
        return [term for term in _DATE_WORDS if term in text]

    @staticmethod
    def _date_intent(request: str) -> DateIntent:
        relative = DateRangeResolver.infer_relative_range(request)
        if relative == "all_available":
            return DateIntent("all_available", "all_available", False, [])
        if relative:
            return DateIntent("relative", relative, False, [])
        explicit = DateRangeResolver.extract_raw_date_mentions(request)
        if explicit:
            return DateIntent("explicit", None, False, explicit)
        return DateIntent("unspecified", None, False, [])

    @staticmethod
    def _explicit_raw(request: str) -> bool:
        text = str(request or "").casefold()
        return any(term in text for term in ("原始记录", "原始输入", "原始数据", "原文追溯", "追溯原始", "raw record", "raw input", "raw trace"))

    def prepare(self, request: str, catalog: DataCatalog) -> DeterministicRequestFacts:
        text = str(request or "")[:2000]
        self.command_parser = AnalysisExportCommandParser(self.query_scope_resolver, catalog)
        command = self.command_parser.parse(text)
        query_scope = self.query_scope_resolver.resolve(text, catalog)
        notes_requested = any(term.casefold() in text.casefold() for term in _NOTE_TERMS)
        notes_scopes = sorted({
            scope for scope, terms in {
                "daily": ("每日", "日记", "daily", "总结记录", "每日总结"),
                "diet": _DIET_TERMS,
                "training": _TRAINING_TERMS,
                "movement": ("动作", "movement"),
            }.items() if notes_requested and any(term.casefold() in text.casefold() for term in terms)
        })
        dimension_map = {
            "body": "body_state", "diet": "diet_macros", "training": "training_context",
            "movement": "movement_progress", "daily_notes": "daily_notes", "diet_notes": "diet_notes",
            "training_notes": "training_notes", "movement_notes": "movement_notes", "raw": "raw_trace",
        }
        dimensions = {dimension_map[item] for item in command.domains if item in dimension_map}
        for scope_name in command.notes_scopes:
            dimensions.add({"daily": "daily_notes", "diet": "diet_notes", "training": "training_notes", "movement": "movement_notes"}[scope_name])
        dimensions = set(item for item in INTENT_DIMENSIONS if item in dimensions)
        only_dims = {dimension_map[item.target] for item in command.scope_operations if item.operator == "only" and item.target in dimension_map}
        include_dims = {dimension_map[item.target] for item in command.scope_operations if item.operator == "include" and item.target in dimension_map}
        exclude_dims = {dimension_map[item.target] for item in command.scope_operations if item.operator == "exclude" and item.target in dimension_map}
        explicit_exclude_dims = set(exclude_dims)
        if only_dims:
            dimensions.intersection_update(only_dims | include_dims)
        dimensions.update(include_dims)
        dimensions.difference_update(explicit_exclude_dims)

        movement_unique = bool(query_scope.explicit_movement_mentions)
        movement_ambiguous = bool(query_scope.unresolved_movement_mentions)
        cards = list(catalog.movements)
        for mention in query_scope.explicit_movement_mentions:
            matches = self.movement_resolver.resolve(MovementMention(mention, 1.0), cards)
            if len(matches) != 1 or matches[0].get("score", 0) < 0.55:
                movement_unique = False
                movement_ambiguous = True
        return DeterministicRequestFacts(
            text, query_scope, [item for item in INTENT_DIMENSIONS if item in dimensions],
            [item for item in INTENT_DIMENSIONS if item in explicit_exclude_dims],
            [item for item in INTENT_DIMENSIONS if item in only_dims],
            [item for item in INTENT_DIMENSIONS if item in include_dims],
            [item for item in INTENT_DIMENSIONS if item in exclude_dims],
            list(command.date.raw_text for _ in [0] if command.date.raw_text) or self._date_text(text), notes_requested, notes_scopes, self._explicit_raw(text), movement_unique, movement_ambiguous,
            command,
        )

    def compile(self, request: str, hints: SemanticHints | IntentSpec, catalog: DataCatalog, budget_mode: str = "standard", facts: DeterministicRequestFacts | None = None) -> tuple[IntentSpec, CandidatePackage, ExportPlanDraft]:
        facts = facts or self.prepare(request, catalog)
        # The formal command parser is authoritative.  SemanticHints and old
        # IntentSpec arguments remain accepted only for compatibility with
        # unit fixtures; they never expand or reduce the deterministic scope.
        merged_dimensions = set(facts.dimensions)
        preliminary = IntentSpec(
            dimensions=[item for item in INTENT_DIMENSIONS if item in merged_dimensions],
            excluded_dimensions=list(facts.excluded_dimensions), date_text=list(facts.date_text),
            movement_mentions=list(facts.query_scope.explicit_movement_mentions),
            target_body_parts=list(facts.query_scope.target_body_part_ids), ambiguous=False,
        )
        # ScopeFence is retained as a compatibility helper for older callers;
        # the formal command parser has already bound every operation with a
        # clause index and is the only scope source for the MVP path.
        fenced = preliminary
        if facts.command and facts.command.status != "resolved":
            if "DATE_REQUIRES_CLARIFICATION" in (facts.command.errors or []):
                code = "INCOMPLETE_DATE_RANGE"
            elif facts.command.request_kind == "unsupported_operation":
                code = "UNSUPPORTED_OPERATION"
            elif "MOVEMENT_REQUIRES_CLARIFICATION" in (facts.command.errors or []):
                code = "UNRESOLVED_REQUIRED_MOVEMENT"
            else:
                code = "REQUEST_NOT_UNDERSTOOD"
            raise IntentCompileError("Request cannot be compiled into a safe export scope", code)
        fenced = replace(fenced, date_text=list(facts.date_text), date_intent=self._date_intent(request), interpreted_goal=str(request or "")[:2000], movement_mentions=list(facts.query_scope.explicit_movement_mentions), target_body_parts=list(facts.query_scope.target_body_part_ids))
        if facts.raw_requested and "raw_trace" not in fenced.dimensions:
            fenced = replace(fenced, dimensions=[*fenced.dimensions, "raw_trace"])
        if not fenced.dimensions:
            raise IntentCompileError("Intent is ambiguous or has no usable dimension", "REQUEST_NOT_UNDERSTOOD")
        if "raw_trace" in fenced.dimensions and not facts.raw_requested:
            fenced = replace(fenced, dimensions=[item for item in fenced.dimensions if item != "raw_trace"], excluded_dimensions=list(dict.fromkeys([*fenced.excluded_dimensions, "raw_trace"])))
        if not fenced.dimensions:
            raise IntentCompileError("No safe dimension remains after scope fence", "NO_SAFE_SCOPE")

        if facts.movement_ambiguous and "movement_progress" in fenced.dimensions:
            raise IntentCompileError("Movement target is ambiguous or unresolved", "UNRESOLVED_REQUIRED_MOVEMENT")

        movement_matches = []
        selected_movement_ids = list(dict.fromkeys(facts.query_scope.explicit_movement_ids))
        cards = list(catalog.movements)
        for text in fenced.movement_mentions:
            matches = self.movement_resolver.resolve(MovementMention(text, 1.0), cards)
            if len(matches) != 1 or matches[0].get("score", 0) < 0.55:
                raise IntentCompileError(f"Movement mention cannot be resolved safely: {text}", "UNRESOLVED_REQUIRED_MOVEMENT")
            selected_movement_ids.append(str(matches[0]["movement_id"]))
            movement_matches.extend({**item, "mention_text": text} for item in matches)
        selected_movement_ids = list(dict.fromkeys(selected_movement_ids))
        if "movement_progress" in fenced.dimensions and not selected_movement_ids:
            raise IntentCompileError("Movement progress requires one uniquely resolved movement", "UNRESOLVED_REQUIRED_MOVEMENT")

        modules: list[str] = []
        fields: dict[str, list[str]] = {}
        for dimension in fenced.dimensions:
            for module, module_fields in DIMENSION_MODULES[dimension].items():
                if module not in modules:
                    modules.append(module)
                fields[module] = list(module_fields)
        legacy = replace(fenced, catalog_requirements=[item for item in modules if item in {"body", "diet", "training", "movement_history", "raw_entries"}])
        package = CandidateSummarizer(catalog, self.movement_resolver).build(request, legacy, budget_mode)
        windows = self.date_resolver.resolve(legacy, catalog, request)
        if not windows:
            raise IntentCompileError("Date expression has no valid data intersection", "NO_VALID_WINDOW")
        allowed_movement_ids = set(package.allowed_ids.get("movement_ids", []))
        selected_movement_ids = [item for item in selected_movement_ids if item in allowed_movement_ids]
        if "movement_progress" in fenced.dimensions and not selected_movement_ids:
            raise IntentCompileError("No resolved movement remains in the selected date range", "NO_SAFE_SCOPE")
        selected_note_types = {NOTE_TYPES[item] for item in fenced.dimensions if item in NOTE_TYPES}
        selected_note_ids = [item.note_candidate_id for item in package.notes if item.note_type in selected_note_types]
        in_range = lambda value: bool(value) and windows[0].resolved_start <= str(value)[:10] <= windows[0].resolved_end
        selected_records = []
        for record in package.candidate_records:
            if not in_range(record.date):
                continue
            if record.module_id in {"body", "diet", "training"} and record.module_id in modules:
                selected_records.append(record.candidate_record_id)
            elif record.module_id == "movement_history" and str(record.related_movement_ids[0] if record.related_movement_ids else "") in selected_movement_ids and ("excluded_from_progress" not in record.flags or "movement_notes" in fenced.dimensions):
                selected_records.append(record.candidate_record_id)
            elif set(record.related_note_ids).intersection(selected_note_ids):
                selected_records.append(record.candidate_record_id)
        raw_allowed = "raw_entries" in modules and facts.raw_requested
        if "raw_entries" in modules and not raw_allowed:
            modules.remove("raw_entries")
            fields.pop("raw_entries", None)
        draft = ExportPlanDraft(
            interpreted_goal=str(request or "")[:2000], analysis_dimensions=list(fenced.dimensions),
            date_range=windows[0].to_dict(), selected_modules=modules, selected_fields=fields,
            selected_movements=selected_movement_ids, notes_selection=selected_note_ids,
            candidate_record_ids=list(dict.fromkeys(selected_records)), include_raw_entries=raw_allowed,
            include_excluded_history=False, excluded_history_usage="none", use_progress_history_for_metrics=True,
            inclusion_reasons={module: "deterministic grounded scope" for module in modules},
            exclusion_reasons={}, missing_data_warnings=list(windows[0].missing_data_warnings),
            planner_confidence=1.0, planning_decision="ready", fallback_reason_codes=[], priority=list(modules),
        )
        return fenced, package, draft
