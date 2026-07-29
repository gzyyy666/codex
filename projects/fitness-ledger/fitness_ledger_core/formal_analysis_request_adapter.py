"""Natural-language adapter that stops at a validated formal Request preview."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from .analysis_export_request import DATASET_FIELDS, RequestValidationResult, validate_request
from .formal_local_semantic_hint import (
    SemanticHint,
    SemanticHintError,
    SemanticHintRequest,
    parse_json_strict,
    validate_semantic_hint,
)
from .formal_local_semantic_provider import (
    InferenceProvider,
    ProviderConfigurationError,
    ProviderError,
    ProviderOutputError,
    ProviderUnavailableError,
)


PREVIEW_SCHEMA_VERSION = "fitness-ledger-formal-analysis-request-preview-v1"

_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNITS = {"十": 10, "百": 100, "千": 1000}
_NUMBER = r"(?:\d+|[零一二两三四五六七八九十百千]+)"
_MAX_DATASETS_PER_BATCH = 8
_WRITE_TERMS = ("删除", "修改", "写入", "新增", "保存", "同步", "上传", "合并", "改成")
_PLAN_TERMS = ("制定训练计划", "安排训练计划", "生成训练计划", "下周训练计划")
_RAW_TERMS = ("raw", "原始记录", "原始输入", "原始数据", "原文追溯")
_BODY_TERMS = ("体重", "身体状态", "身体数据", "身体记录", "身体", "排便", "有氧")
_DIET_TERMS = ("饮食", "热量", "卡路里", "蛋白", "碳水", "脂肪", "食物")
_TRAINING_TERMS = ("训练", "锻炼", "健身", "分化")
_MOVEMENT_TERMS = ("动作进展", "动作表现", "动作历史", "动作", "负重", "组数", "次数", "卧推", "深蹲", "硬拉", "划船", "下拉", "推举", "侧平举", "夹胸")
_BROAD_SCOPE_TERMS = ("全部", "所有", "全量", "完整历史", "整个历史", "所有记录", "所有数据")
_NO_EXPORT_QUESTION_TERMS = (
    "为什么", "什么是", "原理", "原则", "有何作用", "有什么作用", "有什么好处",
    "一般来说", "通常", "应该", "怎么安排", "如何安排", "怎么做", "如何改善",
    "怎么改善", "如何提高", "怎么提高", "是否重要", "是否影响",
)
_EXPORT_INTENT_TERMS = ("导出", "整理", "汇总", "列出", "查看", "获取", "提取", "下载", "给我", "我要")
_COMPARISON_TERMS = ("比较", "对比", "跨动作", "动作之间", "不同动作")
_KNOWN_MOVEMENT_NAMES = (
    "杠铃卧推", "哑铃卧推", "上斜哑铃卧推", "卧推", "深蹲", "硬拉",
    "引体向上", "高位下拉", "坐姿划船", "杠铃划船", "肩推", "推举",
    "侧平举", "腿举", "腿屈伸", "腿弯举",
)
_MOVEMENT_NAME_CANONICALIZATION = {
    "杠铃卧推": "卧推",
}
_BODY_PARTS = {
    "胸": "Chest", "背": "Back", "肩": "Shoulder", "手臂": "Arms",
    "腿": "Legs", "核心": "Core", "腹": "Core",
}
_FIELD_TERMS = {
    "body": {
        "date": ("日期",), "weight_kg": ("体重",), "bowel_movement": ("排便",),
        "training_label": ("训练标签",), "cardio_summary": ("有氧",),
    },
    "diet": {
        "date": ("日期",), "calories_kcal": ("热量", "卡路里"), "protein_g": ("蛋白",),
        "carbs_g": ("碳水",), "fat_g": ("脂肪",), "food_summary": ("食物", "吃了什么"),
    },
    "training": {
        "date": ("日期",), "split": ("分化",), "standardized_summary": ("训练", "锻炼", "健身"),
    },
    "movement_progress": {
        "date": ("日期",), "movement_id": ("动作ID",), "movement_name": ("动作",),
        "body_part": ("部位",), "variant": ("变式",), "order": ("顺序",), "sets": ("组数", "次数", "负重"),
    },
}
_DEFAULT_FIELDS = {
    "body": ("date", "weight_kg"),
    "diet": ("date", "calories_kcal", "protein_g", "carbs_g", "fat_g"),
    "training": ("date", "split", "standardized_summary"),
    "movement_progress": ("date", "movement_name", "body_part", "variant", "order", "sets"),
}


@dataclass(frozen=True)
class _ParsedIntent:
    datasets: tuple[str, ...]
    evidence: dict[str, str]
    time_range: dict[str, Any] | None
    notes_scopes: dict[str, str]
    filters: dict[str, dict[str, Any]]
    days_before: int | None
    explicit_fields: dict[str, tuple[str, ...]]
    semantic_hint_required: bool
    planner_required: bool
    confirmations: tuple[str, ...]


def _number(text: str) -> int | None:
    if text.isdigit():
        return int(text)
    total = 0
    current = 0
    for char in text:
        if char in _DIGITS:
            current = _DIGITS[char]
        elif char in _UNITS:
            total += (current or 1) * _UNITS[char]
            current = 0
        else:
            return None
    return total + current


def _first_term(text: str, terms: tuple[str, ...]) -> str | None:
    matches = [(text.find(term), term) for term in terms if term in text]
    return min(matches)[1] if matches else None


def _has_explicit_date(text: str) -> bool:
    return bool(re.search(r"\d{4}-\d{2}-\d{2}", text))


def _is_no_export_required(text: str) -> bool:
    """Keep general principle questions away from both export routes."""
    if not any(term in text for term in _NO_EXPORT_QUESTION_TERMS):
        return False
    if any(term in text for term in _EXPORT_INTENT_TERMS):
        return False
    return _time_range(text) is None and not _has_explicit_date(text)


def _explicit_dataset_count(text: str) -> int | None:
    """Read only an explicit batch size; never infer a count from data types."""
    lowered = text.casefold()
    if re.search(r"(?:超过|多于|大于)\s*(?:8|八)\s*(?:个)?\s*(?:数据集|组数据|datasets?)", lowered):
        return _MAX_DATASETS_PER_BATCH + 1
    match = re.search(
        rf"(?P<number>{_NUMBER})\s*(?:个|组)?\s*(?:数据集|组数据|datasets?)",
        lowered,
    )
    if match:
        return _number(match["number"])
    return None


def _has_broad_scope(text: str) -> bool:
    return any(term in text for term in _BROAD_SCOPE_TERMS) and _time_range(text) is None and not _has_explicit_date(text)


def _cross_action_comparison(text: str) -> bool:
    if not any(term in text for term in _COMPARISON_TERMS):
        return False
    canonical_names = {
        _MOVEMENT_NAME_CANONICALIZATION.get(name, name)
        for name in _KNOWN_MOVEMENT_NAMES
        if name in text
    }
    return len(canonical_names) >= 2 or any(term in text for term in ("跨动作", "动作之间", "不同动作"))


def _time_range(text: str) -> dict[str, Any] | None:
    match = re.search(r"(?P<start>\d{4}-\d{2}-\d{2})\s*(?:到|至|—|~)\s*(?P<end>\d{4}-\d{2}-\d{2})", text)
    if match:
        try:
            if date.fromisoformat(match["start"]) <= date.fromisoformat(match["end"]):
                return {"mode": "explicit_range", "start": match["start"], "end": match["end"]}
        except ValueError:
            return None
    match = re.search(rf"最近(?P<number>{_NUMBER})(?:天|日)", text)
    if match and (value := _number(match["number"])) is not None:
        return {"mode": "recent_days", "days": value}
    relative_days = {
        "最近一周": 7, "最近一个月": 30, "最近一月": 30,
        "最近两个月": 60, "最近四周": 28, "最近八周": 56, "最近十二周": 84,
    }
    for term, days in relative_days.items():
        if term in text:
            return {"mode": "recent_days", "days": days}
    match = re.search(rf"最近(?P<number>{_NUMBER})次", text)
    if match and (value := _number(match["number"])) is not None:
        return {"mode": "latest_matching_sessions", "sessions": value}
    return None


def _days_before(text: str) -> int | None:
    match = re.search(
        rf"(?:每次|各次)?(?:训练|胸训|腿训|背训|肩训)?前(?P<number>{_NUMBER})天",
        text,
    )
    if match is None:
        return None
    return _number(match["number"])


def _parse(text: str) -> _ParsedIntent:
    datasets: list[str] = []
    evidence: dict[str, str] = {}
    for kind, terms in (
        ("body", _BODY_TERMS),
        ("diet", _DIET_TERMS),
        ("training", _TRAINING_TERMS),
        ("movement_progress", _MOVEMENT_TERMS),
    ):
        if term := _first_term(text, terms):
            datasets.append(kind)
            evidence[kind] = term
    if "movement_progress" in datasets and "training" in datasets and not any(term in text for term in ("训练概况", "训练分化", "整体训练")):
        datasets.remove("training")
        evidence.pop("training", None)

    notes: dict[str, str] = {}
    for kind, scope, terms in (
        ("body", "daily", ("每日笔记", "每日备注", "日常笔记")),
        ("diet", "diet", ("饮食笔记", "饮食备注")),
        ("training", "training", ("训练笔记", "训练备注")),
        ("movement_progress", "movement", ("动作笔记", "动作备注")),
    ):
        if any(term in text for term in terms):
            notes[kind] = scope

    confirmations: list[str] = []
    if any(term in text for term in ("笔记", "备注")) and not notes:
        confirmations.append("请明确 Notes 范围：daily、diet、training 或 movement")
    resolved_time = _time_range(text)
    days_before = _days_before(text)
    if datasets and resolved_time is None:
        confirmations.append("请明确日期范围、最近天数或最近次数")
    if resolved_time and resolved_time["mode"] == "latest_matching_sessions" and days_before is None:
        unsupported = [kind for kind in datasets if kind not in {"training", "movement_progress"}]
        if unsupported:
            confirmations.append("最近次数只适用于 training 或 movement_progress")

    filters: dict[str, dict[str, Any]] = {kind: {} for kind in datasets}
    for surface, canonical in _BODY_PARTS.items():
        if surface in text:
            if "training" in filters:
                filters["training"]["body_part"] = canonical
            if "movement_progress" in filters:
                filters["movement_progress"]["movement_selector"] = {"kind": "body_part", "value": canonical}
            break
    if "movement_progress" in filters:
        movement_name = next((name for name in _KNOWN_MOVEMENT_NAMES if name in text), None)
        if movement_name is not None:
            filters["movement_progress"]["movement_selector"] = {
                "kind": "movement_name",
                "value": _MOVEMENT_NAME_CANONICALIZATION.get(
                    movement_name,
                    movement_name,
                ),
            }
    explicit_fields: dict[str, tuple[str, ...]] = {}
    for kind in datasets:
        fields = [
            field for field, terms in _FIELD_TERMS[kind].items()
            if any(term in text for term in terms)
        ]
        explicit_fields[kind] = tuple(dict.fromkeys(fields))

    broad_comparison = (
        len(datasets) >= 2
        and any(term in text for term in ("分析", "比较", "对比"))
        and all(not explicit_fields[kind] or explicit_fields[kind] == ("standardized_summary",) for kind in datasets)
        and resolved_time is not None
    )
    open_question = any(term in text for term in ("是否影响", "为什么", "怎么改善", "判断我", "处于什么状态", "需要准备哪些数据"))
    return _ParsedIntent(
        tuple(datasets), evidence, resolved_time, notes, filters, days_before, explicit_fields,
        broad_comparison and not open_question, open_question, tuple(confirmations),
    )


class FormalAnalysisRequestAdapter:
    """Produce a validated Request preview without reading or materializing data."""

    def __init__(self, provider: InferenceProvider | None = None) -> None:
        self.provider = provider

    @staticmethod
    def _base(status: str, route: str, *, provider_called: bool = False) -> dict[str, Any]:
        return {
            "schema_version": PREVIEW_SCHEMA_VERSION,
            "status": status,
            "route": route,
            "provider_called": provider_called,
            "request": None,
            "validation": None,
            "confirmations": [],
            "errors": [],
            "semantic_hint": None,
            "resolution": None,
            "batch": None,
            "execution": {
                "allowed": False,
                "executor_called": False,
                "formal_data_written": False,
                "raw_allowed": False,
            },
        }

    @staticmethod
    def _hint_request(text: str, intent: _ParsedIntent) -> SemanticHintRequest:
        evidence = next(term for term in ("分析", "比较", "对比") if term in text)
        return SemanticHintRequest(
            text,
            {"requested_information": ("cross_dataset_analysis",)},
            {"requested_information": (evidence,)},
            ("requested_information",),
        )

    @staticmethod
    def _fields(intent: _ParsedIntent, hint: SemanticHint | None) -> dict[str, tuple[str, ...]]:
        if hint is None:
            return {
                kind: intent.explicit_fields[kind] or tuple(_DEFAULT_FIELDS[kind])
                for kind in intent.datasets
            }
        # A validated analysis-profile hint unlocks only deterministic field profiles.
        return {kind: tuple(_DEFAULT_FIELDS[kind]) for kind in intent.datasets}

    @staticmethod
    def _assemble(text: str, intent: _ParsedIntent, fields: dict[str, tuple[str, ...]]) -> dict[str, Any]:
        dataset_ids = {
            kind: f"{kind}_{index}"
            for index, kind in enumerate(intent.datasets, 1)
        }
        datasets: list[dict[str, Any]] = []
        for kind in intent.datasets:
            time_range = dict(intent.time_range or {})
            if (
                kind == "diet"
                and intent.days_before is not None
                and "training" in dataset_ids
            ):
                time_range = {
                    "mode": "days_before_target_session",
                    "days_before": intent.days_before,
                    "target_dataset_id": dataset_ids["training"],
                    "match_mode": "each_matching_session",
                    "include_target_session_day": False,
                }
            elif time_range.get("mode") == "latest_matching_sessions" and kind not in {"training", "movement_progress"}:
                raise ValueError("LATEST_MATCHING_SESSIONS_DATASET_MISMATCH")
            dataset = {
                "dataset_id": dataset_ids[kind],
                "type": kind,
                "time_range": time_range,
                "filters": dict(intent.filters.get(kind, {})),
                "fields": list(fields[kind]),
            }
            if kind in intent.notes_scopes:
                dataset["notes_scope"] = intent.notes_scopes[kind]
            datasets.append(dataset)
        return {
            "request_version": "1.1",
            "purpose": text.strip()[:500],
            "datasets": datasets,
            "raw": False,
            "output": {"formats": ["json", "markdown"]},
        }

    @staticmethod
    def _validated_response(
        response: dict[str, Any],
        validation: RequestValidationResult,
    ) -> dict[str, Any]:
        response["validation"] = validation.to_dict()
        if validation.valid:
            response["status"] = "ready"
            response["request"] = validation.normalized_request
        else:
            response["status"] = "invalid_model_output" if response["provider_called"] else "needs_confirmation"
            response["errors"] = [item.code for item in validation.errors]
        return response

    def _movement_resolution_response(
        self,
        text: str,
        intent: _ParsedIntent,
        selector: dict[str, Any],
    ) -> dict[str, Any]:
        response = self._base("PREVIEW_READY_RESOLUTION_REQUIRED", "movement_resolver")
        request_value = self._assemble(text, intent, self._fields(intent, None))
        validation = validate_request(request_value)
        response["validation"] = validation.to_dict()
        if validation.valid:
            response["request"] = validation.normalized_request
        else:
            response["status"] = "needs_confirmation"
            response["route"] = "deterministic"
            response["errors"] = [item.code for item in validation.errors]
        response["resolution"] = {
            "status": "required",
            "kind": "movement_name",
            "selector": selector,
            "next": "movement_resolver_or_user_confirmation",
        }
        response["confirmations"] = ["动作名称尚未完成正式动作解析，请先由 movement resolver 或人工确认对应动作"]
        return response

    def preview(self, user_text: str) -> dict[str, Any]:
        text = str(user_text or "").strip()
        if not text:
            response = self._base("needs_confirmation", "deterministic")
            response["confirmations"] = ["请输入需要导出的数据问题"]
            return response
        lowered = text.casefold()
        if any(term in lowered for term in _RAW_TERMS):
            response = self._base("unsupported", "deterministic")
            response["errors"] = ["RAW_PERMISSION_REQUIRED"]
            return response
        if any(term in text for term in (*_WRITE_TERMS, *_PLAN_TERMS)):
            response = self._base("unsupported", "deterministic")
            response["errors"] = ["UNSUPPORTED_OPERATION"]
            return response

        explicit_dataset_count = _explicit_dataset_count(text)
        if explicit_dataset_count is not None and explicit_dataset_count > _MAX_DATASETS_PER_BATCH:
            response = self._base("BATCH_SPLIT_REQUIRED", "deterministic")
            response["errors"] = ["DATASET_BATCH_LIMIT_EXCEEDED"]
            response["batch"] = {
                "requested_dataset_count": explicit_dataset_count,
                "max_datasets": _MAX_DATASETS_PER_BATCH,
                "minimum_batches": (explicit_dataset_count + _MAX_DATASETS_PER_BATCH - 1) // _MAX_DATASETS_PER_BATCH,
            }
            response["confirmations"] = [
                f"本次请求包含 {explicit_dataset_count} 个 Dataset，单批最多 {_MAX_DATASETS_PER_BATCH} 个，请拆分后再导出"
            ]
            return response

        if _is_no_export_required(text):
            response = self._base("NO_EXPORT_REQUIRED", "no_export")
            response["confirmations"] = ["这是一般原理或建议问题，不需要导出本地数据；如需分析个人记录，请补充数据类型和时间范围"]
            return response

        intent = _parse(text)
        if _has_broad_scope(text):
            response = self._base("NEEDS_CLARIFICATION", "deterministic")
            response["errors"] = ["SCOPE_TOO_BROAD"]
            response["confirmations"] = [
                "“全部/所有”范围超过单次只读预览边界，请限定 Dataset 和时间范围，例如最近30天身体与饮食数据"
            ]
            return response
        if not intent.datasets:
            response = self._base("planner_required", "gpt_json_planner")
            response["confirmations"] = ["普通 GPT JSON Planner 需要明确所需 Dataset"]
            return response
        if _cross_action_comparison(text):
            response = self._base("unsupported", "deterministic")
            response["errors"] = ["UNSUPPORTED_CROSS_ACTION_COMPARISON"]
            response["confirmations"] = ["暂不支持跨动作比较；请一次选择一个动作，再分别导出其进展数据"]
            return response

        movement_selector = intent.filters.get("movement_progress", {}).get("movement_selector")
        if movement_selector and movement_selector.get("kind") == "body_part":
            response = self._base("TWO_STAGE_EXPORT_REQUIRED", "movement_discovery")
            response["resolution"] = {
                "status": "required",
                "kind": "body_part_action_discovery",
                "selector": movement_selector,
                "next": "discover_actions_then_export_one_action",
            }
            response["confirmations"] = [
                "该部位包含多个动作，需要先发现动作列表，再选择一个动作进行补充导出"
            ]
            return response
        if movement_selector and movement_selector.get("kind") == "movement_name":
            if intent.confirmations:
                response = self._base("NEEDS_CLARIFICATION", "deterministic")
                response["confirmations"] = list(intent.confirmations)
                return response
            return self._movement_resolution_response(text, intent, movement_selector)
        if intent.planner_required:
            return self._base("planner_required", "gpt_json_planner")
        if intent.confirmations:
            response = self._base("needs_confirmation", "deterministic")
            response["confirmations"] = list(intent.confirmations)
            return response

        hint: SemanticHint | None = None
        response = self._base("ready", "deterministic")
        if intent.semantic_hint_required:
            response = self._base("ready", "semantic_hint", provider_called=self.provider is not None)
            if self.provider is None:
                response["status"] = "needs_confirmation"
                response["route"] = "gpt_json_planner"
                response["errors"] = ["MODEL_UNAVAILABLE"]
                response["confirmations"] = ["请确认每个 Dataset 需要的字段，或转交 GPT JSON Planner"]
                return response
            request = self._hint_request(text, intent)
            try:
                hint = validate_semantic_hint(parse_json_strict(self.provider.infer_semantic_hint(request)), request)
            except (SemanticHintError, ProviderOutputError) as exc:
                response["status"] = "invalid_model_output"
                response["errors"] = [str(exc)]
                return response
            except (ProviderUnavailableError, ProviderConfigurationError, ProviderError) as exc:
                response["status"] = "needs_confirmation"
                response["route"] = "gpt_json_planner"
                response["errors"] = [str(exc)]
                response["confirmations"] = ["请确认每个 Dataset 需要的字段，或转交 GPT JSON Planner"]
                return response
            response["semantic_hint"] = hint.to_summary()
            if hint.ambiguities:
                response["status"] = "needs_confirmation"
                response["confirmations"] = [item["reason"] for item in hint.ambiguities]
                return response

        try:
            request_value = self._assemble(text, intent, self._fields(intent, hint))
        except ValueError as exc:
            response["status"] = "needs_confirmation"
            response["errors"] = [str(exc)]
            return response
        return self._validated_response(response, validate_request(request_value))


__all__ = ["FormalAnalysisRequestAdapter", "PREVIEW_SCHEMA_VERSION"]
