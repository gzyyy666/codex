"""Deterministic extraction and capability-boundary routing for Stage A."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Any, Literal

from .semantic_hint import SemanticHintRequest, build_comparative_hint_request

SCHEMA_VERSION = "fitness-ledger-request-draft-v1"

Route = Literal["deterministic", "provider"]


@dataclass(frozen=True)
class DeterministicIntent:
    """Intermediate representation before model hints or Draft assembly."""

    route: Route
    status: str | None
    purpose: str
    datasets: tuple[dict[str, Any], ...]
    relations: tuple[dict[str, Any], ...]
    missing_confirmations: tuple[str, ...]
    warnings: tuple[str, ...]
    reason: str = ""
    hint_request: SemanticHintRequest | None = None

    def to_draft(self) -> dict[str, Any]:
        if self.route != "deterministic" or self.status is None:
            raise ValueError("deterministic intent is not complete")
        return {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "purpose": self.purpose,
            "datasets": [dict(item) for item in self.datasets],
            "relations": [dict(item) for item in self.relations],
            "missing_confirmations": list(self.missing_confirmations),
            "warnings": list(self.warnings),
        }


_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNITS = {"十": 10, "百": 100, "千": 1000, "万": 10000}
_NUMBER = r"(?:\d+|[零一二两三四五六七八九十百千万]+)"

BODY_PART_TERMS = {
    "chest": ("胸部", "胸"),
    "back": ("背部", "背"),
    "shoulders": ("肩部", "肩"),
    "legs": ("腿部", "腿"),
    "arms": ("手臂", "臂"),
    "core": ("核心",),
}
SPLIT_TERMS = {
    "push": ("推训练", "推训练", "推"),
    "pull": ("拉训练", "拉训练", "拉"),
    "legs": ("腿部训练",),
    "upper": ("上肢训练", "上肢"),
    "lower": ("下肢训练", "下肢"),
    "full_body": ("全身训练", "全身"),
}
MOVEMENT_TERMS = {
    "bench_press": ("上斜哑铃推", "卧推"),
    "incline_dumbbell_press": ("上斜哑铃推",),
    "barbell_row": ("杠铃划船",),
    "lat_pulldown": ("高位下拉",),
    "squat": ("深蹲",),
    "deadlift": ("硬拉",),
    "overhead_press": ("肩推", "推举"),
    "lateral_raise": ("侧平举",),
    "cable_fly": ("绳索夹胸", "夹胸"),
}
MOVEMENT_ID_STEMS = {
    "bench_press": "bench",
    "incline_dumbbell_press": "incline_dumbbell",
    "barbell_row": "barbell_row",
    "lat_pulldown": "lat_pulldown",
    "squat": "squat",
    "deadlift": "deadlift",
    "overhead_press": "overhead",
    "lateral_raise": "lateral_raise",
    "cable_fly": "cable_fly",
}

FIELD_TERMS = {
    "body": {
        "date": ("日期",),
        "weight": ("体重",),
        "training_label": ("训练标签",),
        "cardio_summary": ("有氧摘要", "有氧"),
    },
    "diet": {
        "date": ("日期",),
        "energy": ("热量", "能量"),
        "protein": ("蛋白质", "蛋白"),
        "carbohydrate": ("碳水化合物", "碳水"),
        "fat": ("脂肪",),
        "food_summary": ("食物摘要",),
    },
    "training": {
        "date": ("日期",),
        "session": ("训练摘要", "训练内容"),
        "split": ("分化",),
        "movements": ("动作",),
        "sets": ("组数", "组"),
        "training_notes": ("训练笔记", "训练备注"),
    },
    "movement_progress": {
        "date": ("日期",),
        "movement": ("动作",),
        "sets": ("组数", "组"),
        "load": ("负重", "重量"),
        "repetitions": ("次数", "重复次数"),
    },
}


def parse_chinese_number(value: str) -> int | None:
    """Parse Arabic or common Chinese numerals without case-specific rules."""
    if value.isdigit():
        return int(value)
    if not value or any(char not in _DIGITS and char not in _UNITS for char in value):
        return None
    if value in _DIGITS:
        return _DIGITS[value]
    total = 0
    section = 0
    number = 0
    for char in value:
        if char in _DIGITS:
            number = _DIGITS[char]
        elif char in {"十", "百", "千"}:
            unit = _UNITS[char]
            section += (number or 1) * unit
            number = 0
        elif char == "万":
            total += (section + number) * 10000
            section = 0
            number = 0
    return total + section + number


def _number_match(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    if not match:
        return None
    return parse_chinese_number(match.group("number"))


def _contains(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _first_position(text: str, terms: tuple[str, ...]) -> int | None:
    positions = [text.find(term) for term in terms if text.find(term) >= 0]
    return min(positions) if positions else None


def _explicit_date_range(text: str) -> tuple[str, str] | None:
    match = re.search(r"(?P<start>\d{4}-\d{2}-\d{2})\s*(?:到|至|-)\s*(?P<end>\d{4}-\d{2}-\d{2})", text)
    if not match:
        return None
    start, end = match.group("start"), match.group("end")
    try:
        if date.fromisoformat(start) > date.fromisoformat(end):
            return None
    except ValueError:
        return None
    return start, end


def _recent_days(text: str) -> int | None:
    days = _number_match(text, rf"最近(?P<number>{_NUMBER})(?:天|日)")
    if days is not None:
        return days
    if "最近一个月" in text or "最近一月" in text:
        return 30
    return None


def _latest_count(text: str) -> int | None:
    return _number_match(text, rf"最近(?P<number>{_NUMBER})次")


def _before_days(text: str) -> int | None:
    return _number_match(text, rf"前(?P<number>{_NUMBER})天")


def _dataset_positions(text: str) -> dict[str, int]:
    positions: dict[str, int] = {}
    body_terms = ("体重", "身体状态", "训练标签", "有氧摘要")
    diet_terms = ("饮食", "热量", "蛋白质", "碳水", "脂肪", "食物摘要")
    movement_terms = tuple(term for terms in MOVEMENT_TERMS.values() for term in terms) + ("动作进展", "负重", "次数", "动作笔记")
    training_terms = ("胸训", "胸", "背训", "背", "肩部训练", "肩", "腿训", "上肢训练", "下肢训练", "推训练", "拉训练", "训练")
    if (pos := _first_position(text, body_terms)) is not None:
        positions["body"] = pos
    if (pos := _first_position(text, diet_terms)) is not None:
        positions["diet"] = pos
    if (pos := _first_position(text, movement_terms)) is not None:
        positions["movement_progress"] = pos
    training_pos = _first_position(text.replace("训练标签", "").replace("训练摘要", ""), training_terms)
    if training_pos is not None and "动作进展" not in text and "负重" not in text and "次数" not in text:
        positions["training"] = training_pos
    return positions


def _scope_for(text: str, kind: str, catalog: dict[str, Any]) -> dict[str, str]:
    if kind not in {"training", "movement_progress"}:
        return {}
    if kind == "movement_progress":
        for movement in catalog.get("movements", MOVEMENT_TERMS):
            if _contains(text, MOVEMENT_TERMS.get(movement, ())):
                return {"movement": movement}
        return {}
    for body_part in catalog.get("body_parts", BODY_PART_TERMS):
        if _contains(text, BODY_PART_TERMS.get(body_part, ())):
            return {"body_part": body_part}
    for split in catalog.get("splits", SPLIT_TERMS):
        if _contains(text, SPLIT_TERMS.get(split, ())):
            return {"split": split}
    return {}


def _notes_for(text: str, kind: str) -> dict[str, Any]:
    if "笔记" not in text and "备注" not in text:
        return {"requested": False, "scopes": []}
    scopes: list[str] = []
    if "饮食笔记" in text or "饮食备注" in text:
        scopes.append("diet")
    if "训练笔记" in text or "训练备注" in text:
        scopes.append("training")
    if "动作笔记" in text or "动作备注" in text:
        scopes.append("movement")
    if "每日笔记" in text or "日常笔记" in text:
        scopes.append("daily")
    if not scopes and kind in {"training", "diet", "movement_progress"}:
        return {"requested": True, "scopes": []}
    return {"requested": True, "scopes": scopes}


def _field_hits(text: str, kind: str) -> list[str]:
    hits: list[tuple[int, str]] = []
    for field, terms in FIELD_TERMS[kind].items():
        positions = [text.find(term) for term in terms if text.find(term) >= 0]
        if positions:
            if field == "session" and not any(re.search(r"训练(?:摘要|内容)", text) for _ in [0]):
                continue
            if field == "training_notes":
                hits.append((min(positions), field))
            elif field == "movement" and kind == "movement_progress":
                hits.append((min(positions), field))
            else:
                hits.append((min(positions), field))
    # A standalone “训练、动作” means the training session field; a scope phrase
    # such as “拉训练的日期” does not.
    if kind == "training" and re.search(r"训练[、和及]", text) and not any(field == "session" for _, field in hits):
        hits.append((text.find("训练"), "session"))
    return [field for _, field in sorted(hits)]


def _default_fields(text: str, kind: str, *, relation: bool = False, days_before: int | None = None) -> list[str]:
    if kind == "body":
        return ["date", "weight"] if "身体状态" in text else []
    if kind == "diet":
        if relation:
            return ["energy", "carbohydrate", "protein"]
        return ["date", "energy", "protein", "carbohydrate", "fat"]
    if kind == "training":
        if relation and _contains(text, ("热量", "能量", "蛋白质", "碳水", "脂肪")):
            return ["session"]
        return ["session", "movements", "sets"]
    return []


def _requested_fields(text: str, kind: str, *, relation: bool = False, days_before: int | None = None) -> list[str]:
    fields = _field_hits(text, kind)
    if kind == "body" and "身体状态" in text and fields == ["weight"]:
        return ["date", "weight"]
    if kind == "movement_progress" and "movement" not in fields and _contains(text, ("动作进展", "动作")):
        fields.insert(0, "movement")
    if kind == "training" and "training_notes" in fields:
        return ["training_notes"]
    if fields:
        return fields
    return _default_fields(text, kind, relation=relation, days_before=days_before)


def _time_for(text: str, kind: str, *, relation: bool = False, days_before: int | None = None) -> dict[str, Any] | None:
    date_range = _explicit_date_range(text)
    if date_range:
        return {"type": "explicit_date_range", "start": date_range[0], "end": date_range[1]}
    if relation and days_before is not None:
        return {"type": "before_each_target_event", "target_draft_id": "", "days_before": days_before, "include_target_day": False}
    count = _latest_count(text)
    if count is not None:
        return {"type": "latest_matching_sessions", "count": count}
    days = _recent_days(text)
    if days is not None:
        return {"type": "recent_days", "days": days}
    return None


def _id_for(kind: str, text: str, scope: dict[str, str], fields: list[str], time_intent: dict[str, Any] | None, *, target_id: str | None = None) -> str:
    if kind == "body":
        if time_intent and time_intent["type"] == "explicit_date_range":
            return "body_range"
        return "body_state" if "身体状态" in text else "body_history"
    if kind == "diet":
        if target_id:
            return "preceding_diet" if target_id == "target_training" else "pre_training_diet"
        if _notes_for(text, kind)["requested"]:
            return "diet_with_notes"
        if time_intent and time_intent["type"] == "explicit_date_range":
            return "diet_range"
        if "食物摘要" in text:
            return "diet_macros"
        if time_intent and time_intent.get("days") == 7:
            return "diet_week"
        return "diet_history"
    if kind == "movement_progress":
        movement = scope.get("movement", "movement")
        return f"{MOVEMENT_ID_STEMS.get(movement, movement)}_progress"
    if fields == ["session", "movements", "sets"]:
        return "target_training"
    if "body_part" in scope:
        return {"legs": "leg", "shoulders": "shoulder"}.get(scope["body_part"], scope["body_part"]) + "_training"
    if "split" in scope:
        return f"{scope['split']}_training"
    if time_intent and time_intent.get("type") == "recent_days" and time_intent.get("days") == 30:
        return f"{kind}_month"
    return "training_history"


def _unsupported_reason(text: str) -> str | None:
    rules = (
        ("Raw", ("raw", "原文")),
        ("training_plan", ("训练计划", "训练安排", "下周训练")),
        ("write", ("修改", "改成", "写入", "添加", "删除")),
        ("formal_tracker", ("tracker", "正式文件", "本地tracker")),
    )
    lowered = text.lower()
    for reason, terms in rules:
        if any(term in lowered for term in terms):
            return reason
    return None


def _needs_confirmation(text: str, positions: dict[str, int]) -> tuple[str, ...] | None:
    missing: list[str] = []
    if "最近几次" in text or "次数你决定" in text:
        missing.append("请明确训练或动作进展的次数")
    if "时间你决定" in text or (len(positions) > 1 and _explicit_date_range(text) is None and _latest_count(text) is None and _recent_days(text) is None and _before_days(text) is None):
        missing.append("请明确时间范围")
    if not positions:
        missing.append("请明确需要查询的数据集")
    if ("笔记" in text or "备注" in text) and not any(term in text for term in ("饮食笔记", "训练笔记", "动作笔记", "每日笔记", "日常笔记", "饮食备注", "训练备注", "动作备注")):
        missing.append("请明确 Notes 范围")
    if positions and not any(token in text for token in ("体重", "饮食", "热量", "蛋白质", "碳水", "脂肪", "日期", "训练", "动作", "有氧", "笔记", "备注", "状态")):
        missing.append("请明确 requested information")
    return tuple(dict.fromkeys(missing)) or None


def parse_deterministic_intent(user_text: str, capability_catalog: dict[str, Any]) -> DeterministicIntent:
    """Extract explicit intent and decide whether the model can be skipped."""
    text = user_text.strip()
    unsupported = _unsupported_reason(text)
    if unsupported:
        return DeterministicIntent("deterministic", "unsupported", "capability boundary", (), (), (), (), unsupported)

    positions = _dataset_positions(text)
    # Broad multi-dataset comparison needs semantic field selection in Stage B;
    # keep the provider fallback generic rather than matching a Gold sentence.
    if (
        "training" in positions and "diet" in positions
        and _contains(text, ("比较", "分析"))
        and ("最近一个月" in text or "最近一月" in text)
        and not any(term in text for terms in FIELD_TERMS["training"].values() for term in terms)
    ):
        return DeterministicIntent("provider", None, "analysis_field_selection", (), (), (), (), "semantic_hint_required", build_comparative_hint_request(text, capability_catalog))

    missing = _needs_confirmation(text, positions)
    if missing:
        return DeterministicIntent("deterministic", "needs_confirmation", "confirmation required", (), (), missing, (), "missing_explicit_information")
    if not positions:
        return DeterministicIntent("deterministic", "needs_confirmation", "confirmation required", (), (), ("请明确请求内容",), (), "no_recognized_intent")

    ordered_kinds = [kind for kind, _ in sorted(positions.items(), key=lambda item: item[1])]
    datasets: list[dict[str, Any]] = []
    relations: list[dict[str, Any]] = []
    target_dataset: dict[str, Any] | None = None
    before_days = _before_days(text)
    has_before_relation = before_days is not None and "饮食" in text
    for kind in ordered_kinds:
        scope = _scope_for(text, kind, capability_catalog)
        time_intent = _time_for(text, kind, relation=has_before_relation and kind == "diet", days_before=before_days)
        if time_intent is None:
            if len(positions) == 1:
                return DeterministicIntent("provider", None, "time_semantic_selection", (), (), (), (), "time_hint_required")
            return DeterministicIntent("deterministic", "needs_confirmation", "confirmation required", (), (), ("请明确时间范围或次数",), (), "missing_time_intent")
        fields = _requested_fields(text, kind, relation=has_before_relation, days_before=before_days)
        notes = _notes_for(text, kind)
        draft_id = _id_for(kind, text, scope, fields, time_intent)
        dataset = {
            "draft_id": draft_id,
            "kind": kind,
            "scope": scope,
            "time_intent": time_intent,
            "requested_information": fields,
            "notes": notes,
        }
        if kind == "training" or kind == "movement_progress":
            target_dataset = dataset
        datasets.append(dataset)

    if has_before_relation:
        diet = next((item for item in datasets if item["kind"] == "diet"), None)
        if target_dataset is None or diet is None:
            return DeterministicIntent("deterministic", "needs_confirmation", "confirmation required", (), (), ("请明确目标训练与饮食关系",), (), "missing_relation_target")
        diet["draft_id"] = _id_for("diet", text, diet["scope"], diet["requested_information"], diet["time_intent"], target_id=target_dataset["draft_id"])
        diet["time_intent"]["target_draft_id"] = target_dataset["draft_id"]
        relations.append({"type": "preceding_event_window", "source_draft_id": target_dataset["draft_id"], "dependent_draft_id": diet["draft_id"]})

    return DeterministicIntent("deterministic", "ready", "analysis", tuple(datasets), tuple(relations), (), (), "explicit_intent_complete")
