from __future__ import annotations

from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
import re
import unicodedata
import uuid
from copy import deepcopy
from typing import Any, Iterable, Literal, Mapping, Sequence


Domain = Literal["body", "diet", "training", "movement_progress"]
TimeMode = Literal[
    "recent_days",
    "latest_matching_sessions",
    "all_available",
    "explicit_range",
    "days_before_target_session",
]


@dataclass(frozen=True)
class MovementEntry:
    movement_id: str
    movement_name: str
    aliases: tuple[str, ...] = ()
    body_part: str | None = None
    include_in_progress: bool = True
    record_count: int | None = None
    last_date: str | None = None


@dataclass
class TimeScope:
    mode: TimeMode
    days: int | None = None
    sessions: int | None = None
    start: str | None = None
    end: str | None = None
    days_before: int | None = None
    include_target_session_day: bool | None = None
    match_mode: str | None = None
    target_intent_id: str | None = None
    source: Literal["explicit_user_input", "default_rule", "derived"] = "explicit_user_input"
    rule_id: str | None = None


@dataclass
class RelationshipSpec:
    relationship_id: str
    training_intent_id: str
    diet_intent_id: str
    days_before: int
    include_target_session_day: bool
    match_mode: str = "each_matching_session"


@dataclass
class DiscoverySpec:
    mode: Literal[
        "formal_all",
        "recorded_only",
        "progress_eligible_only",
        "representative_ranked",
        "session_scoped",
    ]
    body_part: str | None = None
    count: int | None = None
    source_training_intent_id: str | None = None
    minimum_history_records: int | None = None


@dataclass
class DatasetIntent:
    intent_id: str
    domain: Domain
    field_profile: str
    time_scope: TimeScope
    fields: list[str]
    notes_scope: str | None = None
    filters: dict[str, Any] = field(default_factory=dict)
    movement_selector: dict[str, str] | None = None
    movement_name: str | None = None
    movement_resolution: dict[str, Any] | None = None
    discovery: DiscoverySpec | None = None
    explicit_constraints: list[dict[str, Any]] = field(default_factory=list)
    relationship_id: str | None = None


@dataclass
class SemanticExportPlan:
    plan_id: str
    plan_version: str
    request_kind: Literal[
        "direct_data_export",
        "planner_required",
        "no_export_required",
        "rejected_contract",
        "needs_clarification",
    ]
    original_user_input: str
    requested_domains: list[Domain] = field(default_factory=list)
    excluded_domains: list[Domain] = field(default_factory=list)
    explicit_constraints: dict[str, Any] = field(default_factory=dict)
    applied_rule_ids: list[str] = field(default_factory=list)
    dataset_intents: list[DatasetIntent] = field(default_factory=list)
    relationship_specs: list[RelationshipSpec] = field(default_factory=list)
    unresolved_movements: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rejection_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILE_FIELDS: dict[str, list[str]] = {
    "BODY_COMPLETE_V1": [
        "date",
        "weight_kg",
        "bowel_movement",
        "training_label",
        "cardio_summary",
    ],
    "DIET_BASIC_V1": [
        "date",
        "calories_kcal",
        "protein_g",
        "carbs_g",
        "fat_g",
    ],
    "DIET_COMPLETE_V1": [
        "date",
        "calories_kcal",
        "protein_g",
        "carbs_g",
        "fat_g",
        "food_summary",
    ],
    "TRAINING_COMPLETE_V1": [
        "date",
        "split",
        "standardized_summary",
    ],
    "MOVEMENT_NAME_LIST_V1": ["movement_name"],
    "MOVEMENT_GROWTH_COMPLETE_V1": [
        "date",
        "movement_id",
        "movement_name",
        "body_part",
        "variant",
        "order",
        "sets",
    ],
}

DEFAULT_RULES = {
    "body": (TimeScope(mode="recent_days", days=30, source="default_rule",
                       rule_id="TIME_RECENT_BODY_30D")),
    "diet": (TimeScope(mode="recent_days", days=14, source="default_rule",
                       rule_id="TIME_RECENT_DIET_14D")),
    "training": (TimeScope(mode="recent_days", days=30, source="default_rule",
                           rule_id="TIME_RECENT_TRAINING_30D")),
    "movement_progress": (
        TimeScope(mode="latest_matching_sessions", sessions=6,
                  source="default_rule", rule_id="TIME_RECENT_MOVEMENT_6S")
    ),
}

_BODY_PART_ALIASES = {
    "背": "背",
    "背部": "背",
    "背部训练": "背",
    "肩": "肩",
    "肩部": "肩",
    "肩部训练": "肩",
    "胸": "胸",
    "胸部": "胸",
    "胸部训练": "胸",
    "腿": "腿",
    "腿部": "腿",
    "腿部训练": "腿",
}

_CN_DIGITS = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}


DEFAULT_DATA_DOMAIN_ALIASES: dict[str, tuple[str, ...]] = {
    "body": (
        "身体数据", "身体记录", "身体档案", "体重数据", "体重记录",
        "体重变化", "体脂数据", "身体",
    ),
    "diet": (
        "饮食数据", "饮食记录", "完整饮食", "饮食档案", "营养数据",
        "热量数据", "宏量营养数据", "三大营养素", "饮食",
    ),
    "training": (
        "整体训练数据", "整体训练记录", "训练数据", "训练记录",
        "训练情况", "训练档案", "整体训练", "训练", "锻炼", "健身",
    ),
    "movement_progress": (
        "动作成长数据", "动作成长记录", "完整成长记录", "成长记录",
        "成长数据", "动作表现", "动作数据", "动作进展", "动作历史", "动作记录",
        "动作名称", "动作清单",
    ),
}

DEFAULT_DATA_FIELD_ALIASES: dict[str, dict[str, tuple[str, ...]]] = {
    "body": {
        "weight_kg": ("体重", "身体重量"),
        "bowel_movement": ("排便", "排便情况"),
        "training_label": ("训练标签", "当日训练"),
        "cardio_summary": ("有氧", "有氧摘要", "有氧记录"),
    },
    "diet": {
        "calories_kcal": ("热量", "卡路里", "大卡", "能量摄入"),
        "protein_g": ("蛋白质", "蛋白"),
        "carbs_g": ("碳水化合物", "碳水", "糖类"),
        "fat_g": ("脂肪", "脂质"),
        "food_summary": ("吃了什么", "食物摘要", "食物记录", "具体食物"),
    },
    "training": {
        "split": ("训练部位", "训练分化", "部位"),
        "standardized_summary": ("训练摘要", "动作摘要", "训练内容"),
    },
    "movement_progress": {
        "movement_name": ("动作名称", "动作名"),
        "variant": ("变式", "动作变式", "做法"),
        "order": ("动作顺序", "第几个动作", "顺序"),
        "sets": ("组次", "重量次数组数", "训练组", "组数"),
    },
}

_GENERIC_MOVEMENT_WORDS = {
    "导出", "整理", "列出", "看看", "查看", "动作", "数据", "记录", "完整",
    "成长", "表现", "最近", "全部", "所有", "历史", "现有", "只要",
    "从有记录以来", "有记录以来", "匹配场次", "次", "个",
}

_MATCH_NUMERAL_TRANSLATION = str.maketrans({
    "一": "1", "二": "2", "两": "2", "三": "3", "四": "4",
    "五": "5", "六": "6", "七": "7", "八": "8", "九": "9",
})



def _normalize_match_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower().translate(_MATCH_NUMERAL_TRANSLATION)
    value = re.sub(r"[\s\-_/·,，。；;:：()（）\[\]【】]+", "", value)
    return value


def _alias_present(text: str, aliases: Iterable[str]) -> bool:
    normalized = _normalize_match_text(text)
    return any(_normalize_match_text(alias) in normalized for alias in aliases)


def _has_explicit_time_expression(text: str) -> bool:
    number = _number_pattern()
    return bool(
        re.search(r"\d{4}年\d{1,2}月\d{1,2}日\s*(?:到|至|-)", text)
        or re.search(rf"最近\s*{number}\s*(?:天|个?月|次)", text)
        or _contains_any(text, ("从有记录以来", "有记录以来", "全部历史", "全部可用历史"))
    )


def _all_quantifier_present(text: str) -> bool:
    return bool(re.search(r"(?:全部|所有)(?:的)?", text))


def _is_name_list_clause(text: str) -> bool:
    return _contains_any(text, ("动作名称", "名称清单", "动作清单", "只要名称"))


def _all_available_requested(text: str, domain: Domain) -> bool:
    # Explicit calendar/session ranges always win over 全部/所有.
    if _has_explicit_time_expression(text):
        return _contains_any(text, ("从有记录以来", "有记录以来", "全部历史", "全部可用历史"))

    if domain == "movement_progress" and _is_name_list_clause(text):
        return False

    if _contains_any(text, ("从有记录以来", "有记录以来", "全部历史", "全部可用历史")):
        return True

    if re.search(r"(?:全部|所有)(?:的)?(?:身体|体重|饮食|训练|动作|成长)", text):
        return True
    if re.search(r"(?:身体|体重|饮食|训练|动作|成长)[^.;]*(?:全部|所有)(?:导出|记录|数据|历史)?", text):
        return True
    if re.search(r"(?:全部|所有)(?:的)?[^.;]*(?:数据|记录|成长记录)", text):
        return True
    if re.search(r"[^.;]*(?:全部|所有)导出", text):
        return True
    return False


def _coverage_constraint(text: str) -> dict[str, Any] | None:
    if _all_quantifier_present(text):
        return {
            "type": "coverage",
            "value": "all_matching_records",
            "source": "explicit_user_input",
        }
    return None


def _time_expression_count(text: str) -> int:
    number = _number_pattern()
    patterns = [
        rf"最近\s*{number}\s*天",
        rf"最近\s*{number}\s*个?月",
        rf"最近\s*{number}\s*次",
        r"\d{4}年\d{1,2}月\d{1,2}日\s*(?:到|至|-)",
        r"从有记录以来|有记录以来|全部历史|全部可用历史",
    ]
    return sum(len(re.findall(pattern, text)) for pattern in patterns)


def _looks_like_global_prefix_scope(text: str) -> bool:
    number = _number_pattern()
    return bool(
        re.match(
            rf"^(?:请|帮我|给我|把|导出|整理|列出|查看|看看)*"
            rf"(?:最近\s*{number}\s*(?:天|个?月|次)|从有记录以来|有记录以来|全部历史|全部可用历史|全部(?:的)?|所有(?:的)?)",
            text,
        )
        or re.search(r"(?:全部|所有)导出$", text)
    )


def _shared_scope_for_coordination(
    raw_clause: str,
    domains: Sequence[Domain],
) -> TimeScope | None:
    if len(domains) < 2:
        return None
    if _time_expression_count(raw_clause) > 1:
        return None
    if not _looks_like_global_prefix_scope(raw_clause):
        return None
    return _explicit_time(raw_clause, domains[0])


def _custom_fields(
    domain: Domain,
    clause: str,
    aliases: Mapping[str, Mapping[str, Sequence[str]]],
) -> list[str] | None:
    domain_aliases = aliases.get(domain, {})
    matched = [
        field_name
        for field_name, field_aliases in domain_aliases.items()
        if _alias_present(clause, field_aliases)
    ]
    if not matched:
        return None

    generic_domain_phrase = _alias_present(
        clause,
        DEFAULT_DATA_DOMAIN_ALIASES.get(domain, ()),
    )
    explicit_subset = _contains_any(clause, ("只要", "仅", "只导出", "分别导出"))
    field_list_style = bool(re.search(r"(?:和|、|及|与).*(?:数据|记录)", clause))

    if not explicit_subset and generic_domain_phrase and not field_list_style:
        return None

    ordered = [field_name for field_name in PROFILE_FIELDS.get(
        {
            "body": "BODY_COMPLETE_V1",
            "diet": "DIET_COMPLETE_V1",
            "training": "TRAINING_COMPLETE_V1",
            "movement_progress": "MOVEMENT_GROWTH_COMPLETE_V1",
        }[domain],
        [],
    ) if field_name in matched]

    # Dates are required for meaningful exported series except a pure name list.
    if domain != "movement_progress" or "movement_name" not in ordered:
        ordered = ["date", *ordered]
    return list(dict.fromkeys(ordered))


def _movement_fragments(clause: str) -> list[str]:
    cleaned = clause
    cleaned = re.sub(rf"最近\s*{_number_pattern()}\s*(?:次|天|个?月)", "", cleaned)
    cleaned = re.sub(r"从有记录以来|有记录以来|全部历史|全部可用历史", "", cleaned)
    cleaned = re.sub(
        r"导出|整理|列出|看看|查看|完整成长记录|成长记录|成长数据|动作表现|动作数据|"
        r"只要这(?:一|二|两|三|四|五|六|七|八|九|\d+)个动作|全部(?:的)?|所有(?:的)?",
        "",
        cleaned,
    )
    parts = re.split(r"[、,，和及与]", cleaned)
    result = []
    for part in parts:
        part = part.strip(" 的")
        normalized = _normalize_match_text(part)
        if len(normalized) < 3:
            continue
        if normalized in {_normalize_match_text(item) for item in _GENERIC_MOVEMENT_WORDS}:
            continue
        if _contains_any(part, ("身体", "饮食", "训练数据", "整体训练")):
            continue
        result.append(part)
    return result


def _fuzzy_score(left: str, right: str) -> float:
    left_n = _normalize_match_text(left)
    right_n = _normalize_match_text(right)
    if not left_n or not right_n:
        return 0.0
    ratio = SequenceMatcher(None, left_n, right_n).ratio()
    if left_n in right_n or right_n in left_n:
        containment = min(len(left_n), len(right_n)) / max(len(left_n), len(right_n))
        ratio = max(ratio, containment)
    return ratio

def _copy_time_scope(scope: TimeScope) -> TimeScope:
    return TimeScope(**asdict(scope))


def chinese_number(value: str) -> int | None:
    value = value.strip()
    if value.isdigit():
        return int(value)
    if value in _CN_DIGITS:
        return _CN_DIGITS[value]
    if value == "十":
        return 10
    if "十" in value:
        left, right = value.split("十", 1)
        tens = _CN_DIGITS.get(left, 1) if left else 1
        units = _CN_DIGITS.get(right, 0) if right else 0
        return tens * 10 + units
    return None


def _number_pattern() -> str:
    return r"[0-9一二两三四五六七八九十]+"


def _normalize(text: str) -> str:
    return (
        text.replace("，", ",")
        .replace("；", ";")
        .replace("。", ".")
        .replace("（", "(")
        .replace("）", ")")
        .strip()
    )


def _contains_any(text: str, values: Iterable[str]) -> bool:
    return any(value in text for value in values)


def _profile(domain: Domain, clause: str, excluded_fields: set[str]) -> tuple[str, str | None]:
    if domain == "body":
        return "BODY_COMPLETE_V1", "daily"
    if domain == "diet":
        complete = _contains_any(clause, ("完整饮食", "完整记录", "吃了什么", "食物摘要", "饮食备注"))
        profile = "DIET_COMPLETE_V1" if complete else "DIET_BASIC_V1"
        notes_scope = None if "diet_notes" in excluded_fields else ("diet" if complete else None)
        return profile, notes_scope
    if domain == "training":
        return "TRAINING_COMPLETE_V1", "training"
    name_list = _contains_any(clause, ("动作名称", "名称清单", "动作清单", "只要名称"))
    if name_list:
        return "MOVEMENT_NAME_LIST_V1", None
    notes_scope = None if "movement_notes" in excluded_fields else "movement"
    return "MOVEMENT_GROWTH_COMPLETE_V1", notes_scope


def _explicit_time(clause: str, domain: Domain) -> TimeScope:
    date_range = re.search(
        r"(?P<y1>\d{4})年(?P<m1>\d{1,2})月(?P<d1>\d{1,2})日"
        r"\s*(?:到|至|-)\s*"
        r"(?:(?P<y2>\d{4})年)?(?P<m2>\d{1,2})月(?P<d2>\d{1,2})日",
        clause,
    )
    if date_range:
        y1 = int(date_range.group("y1"))
        y2 = int(date_range.group("y2") or y1)
        start = f"{y1:04d}-{int(date_range.group('m1')):02d}-{int(date_range.group('d1')):02d}"
        end = f"{y2:04d}-{int(date_range.group('m2')):02d}-{int(date_range.group('d2')):02d}"
        return TimeScope(
            mode="explicit_range", start=start, end=end,
            source="explicit_user_input", rule_id="TIME_EXPLICIT_RANGE"
        )

    days = re.search(rf"最近\s*(?P<n>{_number_pattern()})\s*天", clause)
    if days:
        return TimeScope(
            mode="recent_days", days=chinese_number(days.group("n")),
            source="explicit_user_input", rule_id=f"TIME_EXPLICIT_{domain.upper()}_DAYS"
        )

    months = re.search(rf"最近\s*(?P<n>{_number_pattern()})\s*个?月", clause)
    if months:
        month_count = chinese_number(months.group("n"))
        return TimeScope(
            mode="recent_days", days=(month_count or 1) * 30,
            source="explicit_user_input", rule_id=f"TIME_EXPLICIT_{domain.upper()}_MONTHS"
        )

    sessions = re.search(rf"最近\s*(?P<n>{_number_pattern()})\s*次", clause)
    if sessions:
        return TimeScope(
            mode="latest_matching_sessions",
            sessions=chinese_number(sessions.group("n")),
            source="explicit_user_input",
            rule_id="TIME_EXPLICIT_MATCHING_SESSIONS",
        )

    if _all_available_requested(clause, domain):
        return TimeScope(
            mode="all_available", source="explicit_user_input",
            rule_id="SCOPE_ALL_AVAILABLE_SELECTED_DOMAIN"
        )

    if "最近少量" in clause:
        return TimeScope(
            mode="recent_days", days=7, source="default_rule",
            rule_id="QUANTITY_SMALL_DAILY_7D"
        )

    return _copy_time_scope(DEFAULT_RULES[domain])

def _extract_negative_constraints(text: str) -> tuple[set[Domain], set[str], list[str]]:
    negative_chunks: list[str] = []
    patterns = [
        r"不要(?P<value>[^.;]+)",
        r"不需要(?P<value>[^.;]+)",
        r"排除(?P<value>[^.;]+)",
        r"不包含(?P<value>[^.;]+)",
    ]
    for pattern in patterns:
        negative_chunks.extend(m.group("value") for m in re.finditer(pattern, text))

    joined = "、".join(negative_chunks)
    domains: set[Domain] = set()
    fields: set[str] = set()

    if re.search(r"(?:训练数据|整体训练|训练记录|训练)", joined):
        domains.add("training")
    if re.search(r"(?:动作成长|成长数据|动作表现|动作数据)", joined):
        domains.add("movement_progress")
    if re.search(r"(?:饮食数据|饮食记录)", joined) and "饮食备注" not in joined:
        domains.add("diet")
    if re.search(r"(?:身体数据|体重数据)", joined):
        domains.add("body")

    field_patterns = {
        "diet_notes": r"饮食备注",
        "movement_notes": r"动作备注",
        "daily_notes": r"(?:身体备注|每日备注)",
        "training_notes": r"训练备注",
        "date": r"日期",
        "weight": r"重量",
        "reps": r"次数",
        "sets": r"组数",
        "food_summary": r"(?:吃了什么|食物摘要)",
    }
    for field_name, pattern in field_patterns.items():
        if re.search(pattern, joined):
            fields.add(field_name)

    return domains, fields, negative_chunks


def _strip_negative_chunks(text: str) -> str:
    for pattern in (
        r"不要[^.;]+", r"不需要[^.;]+", r"排除[^.;]+", r"不包含[^.;]+"
    ):
        text = re.sub(pattern, "", text)
    return text


def _resolve_movements(
    clause: str,
    catalog: Sequence[MovementEntry],
    *,
    allow_fuzzy: bool = True,
) -> tuple[list[MovementEntry], list[dict[str, Any]], dict[str, dict[str, Any]]]:
    alias_map: dict[str, list[tuple[str, MovementEntry]]] = {}
    for entry in catalog:
        names = {entry.movement_id, entry.movement_name, *entry.aliases}
        for name in names:
            normalized = _normalize_match_text(name)
            if normalized:
                alias_map.setdefault(normalized, []).append((name, entry))

    normalized_clause = _normalize_match_text(clause)
    found: list[MovementEntry] = []
    unresolved: list[dict[str, Any]] = []
    resolutions: dict[str, dict[str, Any]] = {}
    seen_ids: set[str] = set()
    matched_aliases: set[str] = set()

    for normalized_alias in sorted(alias_map, key=len, reverse=True):
        if normalized_alias not in normalized_clause:
            continue
        alias_candidates = alias_map[normalized_alias]
        unique_by_id = {
            entry.movement_id: (source_alias, entry)
            for source_alias, entry in alias_candidates
        }
        if len(unique_by_id) == 1:
            source_alias, candidate = next(iter(unique_by_id.values()))
            if candidate.movement_id not in seen_ids:
                found.append(candidate)
                seen_ids.add(candidate.movement_id)
                matched_aliases.add(normalized_alias)
                resolutions[candidate.movement_id] = {
                    "source_text": source_alias,
                    "matched_alias": source_alias,
                    "match_type": "exact_alias",
                    "score": 1.0,
                }
        else:
            unresolved.append({
                "source_text": alias_candidates[0][0],
                "reason": "AMBIGUOUS_MOVEMENT_ALIAS",
                "candidates": [
                    {
                        "movement_id": entry.movement_id,
                        "movement_name": entry.movement_name,
                        "matched_alias": source_alias,
                        "score": 1.0,
                    }
                    for source_alias, entry in unique_by_id.values()
                ],
            })

    if not allow_fuzzy:
        return found, unresolved, resolutions

    for fragment in _movement_fragments(clause):
        fragment_n = _normalize_match_text(fragment)
        if any(alias in fragment_n or fragment_n in alias for alias in matched_aliases):
            continue
        if len(fragment_n) < 3:
            continue

        scored_by_id: dict[str, tuple[float, str, MovementEntry]] = {}
        for normalized_alias, records in alias_map.items():
            for source_alias, entry in records:
                score = _fuzzy_score(fragment, source_alias)
                current = scored_by_id.get(entry.movement_id)
                if current is None or score > current[0]:
                    scored_by_id[entry.movement_id] = (score, source_alias, entry)

        ranked = sorted(scored_by_id.values(), key=lambda item: item[0], reverse=True)
        if not ranked:
            continue
        best_score, best_alias, best_entry = ranked[0]
        second_score = ranked[1][0] if len(ranked) > 1 else 0.0
        auto_threshold = 0.96 if len(fragment_n) == 3 else (0.88 if len(fragment_n) == 4 else 0.82)
        margin = best_score - second_score

        if (
            best_score >= auto_threshold
            and margin >= 0.06
            and best_entry.movement_id not in seen_ids
        ):
            found.append(best_entry)
            seen_ids.add(best_entry.movement_id)
            resolutions[best_entry.movement_id] = {
                "source_text": fragment,
                "matched_alias": best_alias,
                "match_type": "fuzzy_alias",
                "score": round(best_score, 4),
                "margin": round(margin, 4),
            }
            continue

        if best_score >= 0.72:
            unresolved.append({
                "source_text": fragment,
                "reason": "FUZZY_MOVEMENT_CONFIRMATION_REQUIRED",
                "candidates": [
                    {
                        "movement_id": entry.movement_id,
                        "movement_name": entry.movement_name,
                        "matched_alias": alias,
                        "score": round(score, 4),
                    }
                    for score, alias, entry in ranked[:3]
                ],
            })

    return found, unresolved, resolutions

def _body_parts_from_text(
    text: str,
    body_part_aliases: Mapping[str, str] = _BODY_PART_ALIASES,
) -> list[str]:
    result: list[str] = []
    for alias, formal in body_part_aliases.items():
        if alias in text and formal not in result:
            result.append(formal)
    return result


def _split_top_level_clauses(text: str) -> list[str]:
    # Protect “X和Y最近N次…” movement lists and body-part lists by only splitting
    # around connectors that usually introduce a new dataset intent.
    text = re.sub(r"\s+", "", text)
    parts = re.split(r"(?:;|\.|另外|以及|同时|并且|再分别|再导出|再看看)", text)
    return [part.strip(",") for part in parts if part.strip(",")]


def _detect_domain(
    clause: str,
    catalog: Sequence[MovementEntry],
    domain_aliases: Mapping[str, Sequence[str]] = DEFAULT_DATA_DOMAIN_ALIASES,
    field_aliases: Mapping[str, Mapping[str, Sequence[str]]] = DEFAULT_DATA_FIELD_ALIASES,
) -> Domain | Literal["all_fitness"] | None:
    if _alias_present(clause, ("所有健身数据", "全部健身数据", "全部的健身数据")):
        return "all_fitness"

    for domain in ("body", "diet", "training", "movement_progress"):
        if _alias_present(clause, domain_aliases.get(domain, ())):
            return domain  # type: ignore[return-value]

    field_domains = []
    for domain, domain_fields in field_aliases.items():
        if any(
            _alias_present(clause, aliases)
            for aliases in domain_fields.values()
        ):
            field_domains.append(domain)
    if len(set(field_domains)) == 1:
        return field_domains[0]  # type: ignore[return-value]

    movements, _, _ = _resolve_movements(clause, catalog, allow_fuzzy=False)
    if movements:
        return "movement_progress"

    # Controlled typo tolerance for data concepts. Auto-resolve only at very high
    # confidence and only when one domain clearly wins.
    cleaned = re.sub(
        rf"导出|整理|列出|查看|看看|最近\s*{_number_pattern()}\s*(?:天|次|个?月)|全部(?:的)?|所有(?:的)?|数据|记录",
        "",
        clause,
    )
    fragments = [item for item in re.split(r"[、,，和及与]", cleaned) if len(_normalize_match_text(item)) >= 3]
    scores: list[tuple[float, str]] = []
    for domain, aliases in domain_aliases.items():
        best = max((_fuzzy_score(fragment, alias) for fragment in fragments for alias in aliases), default=0.0)
        scores.append((best, domain))
    scores.sort(reverse=True)
    if scores and scores[0][0] >= 0.92 and (len(scores) == 1 or scores[0][0] - scores[1][0] >= 0.08):
        return scores[0][1]  # type: ignore[return-value]
    return None

def _intent(
    intent_id: str,
    domain: Domain,
    clause: str,
    excluded_fields: set[str],
    time_scope: TimeScope | None = None,
    data_field_aliases: Mapping[str, Mapping[str, Sequence[str]]] = DEFAULT_DATA_FIELD_ALIASES,
) -> DatasetIntent:
    profile, notes_scope = _profile(domain, clause, excluded_fields)
    fields = list(PROFILE_FIELDS[profile])
    custom_fields = _custom_fields(domain, clause, data_field_aliases)
    if custom_fields:
        fields = custom_fields
        profile = f"{domain.upper()}_CUSTOM_V1"

    constraints = [{"type": "exclude_field", "value": name} for name in sorted(excluded_fields)]
    coverage = _coverage_constraint(clause)
    if coverage:
        constraints.append(coverage)

    return DatasetIntent(
        intent_id=intent_id,
        domain=domain,
        field_profile=profile,
        time_scope=time_scope or _explicit_time(clause, domain),
        fields=fields,
        notes_scope=notes_scope,
        explicit_constraints=constraints,
    )

def _parse_relationships(
    text: str,
    excluded_fields: set[str],
    next_intent_number: int,
    body_part_aliases: Mapping[str, str] = _BODY_PART_ALIASES,
) -> tuple[list[DatasetIntent], list[RelationshipSpec], set[str], list[tuple[int, int]]]:
    intents: list[DatasetIntent] = []
    relationships: list[RelationshipSpec] = []
    rules: set[str] = set()
    spans: list[tuple[int, int]] = []

    number = _number_pattern()
    patterns = [
        # 最近2次背部训练前1天的饮食，不包含训练当天
        re.compile(
            rf"最近(?P<sessions>{number})次(?P<parts>(?:背|肩|胸|腿)(?:部)?"
            rf"(?:[、和](?:背|肩|胸|腿)(?:部)?)*)训练前(?P<days>{number})天"
            rf"(?P<include>到训练当天)?(?:的)?饮食"
        ),
        # 背部最近2次训练前1天...
        re.compile(
            rf"(?P<parts>(?:背|肩|胸|腿)(?:部)?"
            rf"(?:[、和](?:背|肩|胸|腿)(?:部)?)*)最近(?P<sessions>{number})次"
            rf"训练前(?P<days>{number})天(?P<include>到训练当天)?(?:的)?饮食"
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(text):
            spans.append(match.span())
            sessions = chinese_number(match.group("sessions")) or 1
            days_before = chinese_number(match.group("days")) or 1
            explicit_exclusion = "不包含训练当天" in text[match.start():match.end()+12]
            include_target = bool(match.group("include")) and not explicit_exclusion
            raw_parts = re.split(r"[、和]", match.group("parts"))
            body_parts = []
            for raw_part in raw_parts:
                normalized = body_part_aliases.get(raw_part)
                if normalized and normalized not in body_parts:
                    body_parts.append(normalized)

            for body_part in body_parts:
                training_id = f"intent_training_{next_intent_number}"
                next_intent_number += 1
                diet_id = f"intent_diet_{next_intent_number}"
                next_intent_number += 1
                relationship_id = f"relationship_{len(relationships)+1}"

                training_scope = TimeScope(
                    mode="latest_matching_sessions",
                    sessions=sessions,
                    source="explicit_user_input",
                    rule_id="TIME_EXPLICIT_TRAINING_SESSIONS",
                )
                training = _intent(
                    training_id, "training", match.group(0), excluded_fields, training_scope
                )
                training.filters = {"body_part": body_part}
                training.relationship_id = relationship_id

                diet_scope = TimeScope(
                    mode="days_before_target_session",
                    days_before=days_before,
                    include_target_session_day=include_target,
                    match_mode="each_matching_session",
                    target_intent_id=training_id,
                    source="explicit_user_input",
                    rule_id="RELATION_PRE_TRAINING_EXPLICIT",
                )
                diet = _intent(diet_id, "diet", match.group(0), excluded_fields, diet_scope)
                diet.relationship_id = relationship_id

                intents.extend([training, diet])
                relationships.append(
                    RelationshipSpec(
                        relationship_id=relationship_id,
                        training_intent_id=training_id,
                        diet_intent_id=diet_id,
                        days_before=days_before,
                        include_target_session_day=include_target,
                    )
                )
                rules.update({"TIME_EXPLICIT_TRAINING_SESSIONS", "RELATION_PRE_TRAINING_EXPLICIT"})
    return intents, relationships, rules, spans


class RestrictedExportParser:
    """
    Deterministic parser for direct Fitness Ledger data-export requests.

    Deliberately unsupported:
    - causal/analytical questions ("是否因为低碳", "放纵餐合理频率")
    - arbitrary statistical transformations
    - mutations, deletions, raw database export
    - subjective representative-action selection without catalog context
    """

    def __init__(
        self,
        movement_catalog: Sequence[MovementEntry] = (),
        *,
        data_domain_aliases: Mapping[str, Sequence[str]] | None = None,
        data_field_aliases: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
        body_part_aliases: Mapping[str, str] | None = None,
    ) -> None:
        self.movement_catalog = tuple(movement_catalog)
        self.data_domain_aliases = data_domain_aliases or DEFAULT_DATA_DOMAIN_ALIASES
        self.data_field_aliases = data_field_aliases or DEFAULT_DATA_FIELD_ALIASES
        self.body_part_aliases = dict(body_part_aliases or _BODY_PART_ALIASES)

    def parse(self, user_text: str) -> SemanticExportPlan:
        text = _normalize(user_text)
        plan = SemanticExportPlan(
            plan_id=f"restricted_{uuid.uuid4().hex}",
            plan_version="restricted-v2",
            request_kind="direct_data_export",
            original_user_input=user_text,
        )

        if not text:
            plan.request_kind = "needs_clarification"
            plan.warnings.append("EMPTY_INPUT")
            return plan

        if _contains_any(text, ("删除", "删掉", "修改正式数据", "写入数据库", "覆盖记录", "覆盖正式数据", "覆盖数据")):
            plan.request_kind = "rejected_contract"
            plan.rejection_reason = "WRITE_OR_DELETE_NOT_SUPPORTED"
            return plan

        if _contains_any(text, ("原始数据库", "原始记录全部", "raw数据", "raw 数据")):
            plan.request_kind = "rejected_contract"
            plan.rejection_reason = "RAW_PERMISSION_REQUIRED"
            return plan

        analysis_terms = (
            "是否顺利", "有没有受到影响", "是不是", "为什么", "导致", "合理频率",
            "放纵餐对", "评估减脂", "分析减脂效果", "判断原因",
        )
        if _contains_any(text, analysis_terms) and not _contains_any(text, ("导出", "整理", "列出")):
            plan.request_kind = "planner_required"
            plan.warnings.append("ANALYSIS_PLANNING_NOT_SUPPORTED_BY_RESTRICTED_PARSER")
            return plan

        excluded_domains, excluded_fields, negative_chunks = _extract_negative_constraints(text)
        plan.excluded_domains = sorted(excluded_domains)
        plan.explicit_constraints = {
            "excluded_domains": sorted(excluded_domains),
            "excluded_fields": sorted(excluded_fields),
            "raw_negative_phrases": negative_chunks,
        }

        positive_text = _strip_negative_chunks(text)

        # Relationship intents are parsed before generic clauses.
        relationship_intents, relationships, relation_rules, relationship_spans = _parse_relationships(
            positive_text, excluded_fields, next_intent_number=1,
            body_part_aliases=self.body_part_aliases,
        )
        plan.dataset_intents.extend(relationship_intents)
        plan.relationship_specs.extend(relationships)
        plan.applied_rule_ids.extend(sorted(relation_rules))

        # Remove relationship spans from generic parsing to avoid duplicate diet/training intents.
        chars = list(positive_text)
        for start, end in relationship_spans:
            for index in range(start, end):
                chars[index] = " "
        remaining_text = "".join(chars)

        intent_number = len(plan.dataset_intents) + 1
        raw_clauses = _split_top_level_clauses(remaining_text)
        clause_specs: list[tuple[str, TimeScope | None]] = []
        for raw_clause in raw_clauses:
            candidate_parts = [item for item in re.split(r"[、及与和]", raw_clause) if item]
            candidate_domains = [
                _detect_domain(item, self.movement_catalog, self.data_domain_aliases, self.data_field_aliases)
                for item in candidate_parts
            ]
            non_null_domains = [item for item in candidate_domains if item is not None]
            distinct_domains = set(non_null_domains)

            split_multi_domain = (
                len(candidate_parts) > 1
                and len(non_null_domains) == len(candidate_parts)
                and len(distinct_domains) > 1
            )

            # Also split same-domain movement clauses when every side carries its
            # own explicit time, e.g. “卧推最近4次和引体全部历史”.
            split_independent_movements = (
                len(candidate_parts) > 1
                and len(non_null_domains) == len(candidate_parts)
                and distinct_domains == {"movement_progress"}
                and sum(_time_expression_count(item) > 0 for item in candidate_parts) >= 2
            )

            if split_multi_domain or split_independent_movements:
                inherited_scope = _shared_scope_for_coordination(
                    raw_clause,
                    [item for item in non_null_domains if item != "all_fitness"],
                )
                for candidate_part in candidate_parts:
                    part_domain = _detect_domain(
                        candidate_part,
                        self.movement_catalog,
                        self.data_domain_aliases,
                        self.data_field_aliases,
                    )
                    part_scope = None
                    if inherited_scope is not None and _time_expression_count(candidate_part) == 0:
                        part_scope = _copy_time_scope(inherited_scope)
                    clause_specs.append((candidate_part, part_scope))
            else:
                clause_specs.append((raw_clause, None))

        for clause, inherited_scope in clause_specs:
            if not clause:
                continue
            domain = _detect_domain(clause, self.movement_catalog, self.data_domain_aliases, self.data_field_aliases)
            if domain is None:
                continue

            if domain == "all_fitness":
                global_scope = _explicit_time(clause, "body")
                for current_domain in ("body", "diet", "training"):
                    if current_domain in excluded_domains:
                        continue
                    scope = _copy_time_scope(global_scope)
                    scope.rule_id = "TIME_RECENT_FITNESS_CUSTOM" if scope.source == "explicit_user_input" else scope.rule_id
                    current_intent = _intent(
                        f"intent_{current_domain}_{intent_number}",
                        current_domain,
                        clause,
                        excluded_fields,
                        scope,
                        self.data_field_aliases,
                    )
                    intent_number += 1
                    if current_domain == "diet" and "diet_notes" in excluded_fields:
                        current_intent.notes_scope = None
                    plan.dataset_intents.append(current_intent)
                plan.applied_rule_ids.append("CONCEPT_ALL_FITNESS_V1")
                if global_scope.rule_id:
                    plan.applied_rule_ids.append(global_scope.rule_id)
                continue

            if domain in excluded_domains:
                continue

            if domain != "movement_progress":
                current_intent = _intent(
                    f"intent_{domain}_{intent_number}",
                    domain,
                    clause,
                    excluded_fields,
                    inherited_scope,
                    self.data_field_aliases,
                )
                intent_number += 1
                if domain == "training":
                    body_parts = _body_parts_from_text(clause, self.body_part_aliases)
                    if len(body_parts) == 1:
                        current_intent.filters = {"body_part": body_parts[0]}
                if (
                    inherited_scope is not None
                    and inherited_scope.mode == "all_available"
                    and not any(
                        item.get("type") == "coverage"
                        for item in current_intent.explicit_constraints
                    )
                ):
                    current_intent.explicit_constraints.append({
                        "type": "coverage",
                        "value": "all_matching_records",
                        "source": "inherited_coordination_scope",
                    })
                plan.dataset_intents.append(current_intent)
                if current_intent.time_scope.rule_id:
                    plan.applied_rule_ids.append(current_intent.time_scope.rule_id)
                continue

            resolved, unresolved, resolution_map = _resolve_movements(clause, self.movement_catalog)
            plan.unresolved_movements.extend(unresolved)
            body_parts = _body_parts_from_text(clause, self.body_part_aliases)
            profile, _ = _profile("movement_progress", clause, excluded_fields)

            if resolved:
                shared_scope = inherited_scope or _explicit_time(clause, "movement_progress")
                for movement in resolved:
                    current_intent = _intent(
                        f"intent_movement_progress_{intent_number}",
                        "movement_progress",
                        clause,
                        excluded_fields,
                        _copy_time_scope(shared_scope),
                        self.data_field_aliases,
                    )
                    intent_number += 1
                    current_intent.movement_selector = {
                        "kind": "movement_id",
                        "value": movement.movement_id,
                    }
                    current_intent.movement_name = movement.movement_name
                    current_intent.movement_resolution = resolution_map.get(movement.movement_id)
                    current_intent.filters = {"body_part": movement.body_part} if movement.body_part else {}
                    if (
                        inherited_scope is not None
                        and inherited_scope.mode == "all_available"
                        and not any(
                            item.get("type") == "coverage"
                            for item in current_intent.explicit_constraints
                        )
                    ):
                        current_intent.explicit_constraints.append({
                            "type": "coverage",
                            "value": "all_matching_records",
                            "source": "inherited_coordination_scope",
                        })
                    plan.dataset_intents.append(current_intent)
                if shared_scope.rule_id:
                    plan.applied_rule_ids.append(shared_scope.rule_id)
                continue

            # Body-part/name-list/representative discovery.
            if body_parts or _contains_any(clause, ("一些动作", "主要训练动作", "代表性动作", "所有动作")):
                if "主要" in clause or "代表性" in clause:
                    count_match = re.search(rf"最近?(?P<n>{_number_pattern()})个", clause)
                    count = chinese_number(count_match.group("n")) if count_match else 3
                    discovery = DiscoverySpec(
                        mode="representative_ranked",
                        body_part=body_parts[0] if len(body_parts) == 1 else None,
                        count=count,
                    )
                    plan.applied_rule_ids.extend(
                        ["MOVEMENT_REPRESENTATIVE_TOP3_V1", "QUANTITY_SOME_MOVEMENTS_3"]
                    )
                else:
                    name_list = profile == "MOVEMENT_NAME_LIST_V1"
                    discovery = DiscoverySpec(
                        mode="formal_all" if name_list and "所有" in clause else "recorded_only",
                        body_part=body_parts[0] if len(body_parts) == 1 else None,
                        minimum_history_records=None if name_list and "所有" in clause else 1,
                    )
                    if name_list:
                        plan.applied_rule_ids.append("MOVEMENT_NAME_LIST_V1")

                current_intent = _intent(
                    f"intent_movement_progress_{intent_number}",
                    "movement_progress",
                    clause,
                    excluded_fields,
                    inherited_scope,
                    self.data_field_aliases,
                )
                intent_number += 1
                current_intent.discovery = discovery
                plan.dataset_intents.append(current_intent)
                if current_intent.time_scope.rule_id:
                    plan.applied_rule_ids.append(current_intent.time_scope.rule_id)
                continue

        # Stable de-duplication by movement_id.
        deduped: list[DatasetIntent] = []
        seen_movement_ids: set[str] = set()
        for item in plan.dataset_intents:
            selector = item.movement_selector
            movement_id = selector.get("value") if selector and selector.get("kind") == "movement_id" else None
            if movement_id:
                if movement_id in seen_movement_ids:
                    plan.warnings.append(f"DUPLICATE_MOVEMENT_REMOVED:{movement_id}")
                    continue
                seen_movement_ids.add(movement_id)
            deduped.append(item)
        plan.dataset_intents = deduped

        plan.requested_domains = sorted(
            {item.domain for item in plan.dataset_intents}
        )
        plan.applied_rule_ids = list(dict.fromkeys(plan.applied_rule_ids))

        # Body-part values used in executable filters/discovery must resolve to a
        # value present in the injected formal movement catalog. This prevents a
        # friendly alias such as “背部” from silently reaching materialization as
        # an unverified selector value.
        formal_body_parts = {
            item.body_part for item in self.movement_catalog if item.body_part
        }
        if formal_body_parts:
            unresolved_parts: list[str] = []
            for item in plan.dataset_intents:
                filter_part = item.filters.get("body_part")
                discovery_part = item.discovery.body_part if item.discovery else None
                for value in (filter_part, discovery_part):
                    if value and value not in formal_body_parts and value not in unresolved_parts:
                        unresolved_parts.append(value)
            for value in unresolved_parts:
                plan.unresolved_movements.append({
                    "source_text": value,
                    "reason": "BODY_PART_NOT_IN_FORMAL_CATALOG",
                    "candidates": sorted(formal_body_parts),
                })

        if plan.unresolved_movements:
            plan.request_kind = "needs_clarification"
        elif not plan.dataset_intents:
            if _contains_any(text, ("导出", "整理", "列出")):
                plan.request_kind = "needs_clarification"
                plan.warnings.append("NO_SUPPORTED_DATA_REQUEST")
            else:
                plan.request_kind = "no_export_required"

        return plan


def make_parser_from_catalog(
    catalog_rows: Sequence[Mapping[str, Any]],
    *,
    data_domain_aliases: Mapping[str, Sequence[str]] | None = None,
    data_field_aliases: Mapping[str, Mapping[str, Sequence[str]]] | None = None,
    body_part_aliases: Mapping[str, str] | None = None,
) -> RestrictedExportParser:
    movements = []
    for row in catalog_rows:
        raw_aliases: list[str] = []
        for key in ("aliases", "alias", "synonyms", "name_aliases", "alternate_names"):
            value = row.get(key)
            if isinstance(value, str):
                raw_aliases.append(value)
            elif isinstance(value, Sequence):
                raw_aliases.extend(str(item) for item in value)
        movements.append(
            MovementEntry(
                movement_id=str(row["movement_id"]),
                movement_name=str(row["movement_name"]),
                aliases=tuple(dict.fromkeys(raw_aliases)),
                body_part=row.get("body_part"),
                include_in_progress=bool(row.get("include_in_progress", True)),
                record_count=row.get("record_count"),
                last_date=row.get("last_date"),
            )
        )
    return RestrictedExportParser(
        movements,
        data_domain_aliases=data_domain_aliases,
        data_field_aliases=data_field_aliases,
        body_part_aliases=body_part_aliases,
    )


def apply_candidate_selection(
    plan: SemanticExportPlan,
    *,
    intent_id: str,
    selected_movement_ids: Sequence[str],
    catalog: Sequence[MovementEntry],
) -> SemanticExportPlan:
    """
    Replace one discovery intent with explicit movement_id intents.

    This is a structural patch only. It preserves time_scope, field_profile,
    exclusions and rule IDs; it never reparses natural language.
    """
    selected_unique = list(dict.fromkeys(str(item) for item in selected_movement_ids))
    catalog_by_id = {item.movement_id: item for item in catalog}
    unknown = [item for item in selected_unique if item not in catalog_by_id]
    if unknown:
        raise ValueError(f"Unknown movement IDs: {unknown}")

    patched = deepcopy(plan)
    target_index = next(
        (index for index, item in enumerate(patched.dataset_intents)
         if item.intent_id == intent_id),
        None,
    )
    if target_index is None:
        raise ValueError(f"Unknown intent_id: {intent_id}")

    target = patched.dataset_intents[target_index]
    if target.discovery is None:
        raise ValueError(f"Intent {intent_id} is not a discovery intent")

    replacements: list[DatasetIntent] = []
    for offset, movement_id in enumerate(selected_unique, start=1):
        movement = catalog_by_id[movement_id]
        replacement = deepcopy(target)
        replacement.intent_id = f"{target.intent_id}_selected_{offset}"
        replacement.discovery = None
        replacement.movement_selector = {"kind": "movement_id", "value": movement_id}
        replacement.movement_name = movement.movement_name
        replacement.movement_resolution = {
            "source_text": movement.movement_name,
            "matched_alias": movement.movement_name,
            "match_type": "catalog_selection",
            "score": 1.0,
        }
        replacement.filters = (
            {"body_part": movement.body_part} if movement.body_part else {}
        )
        replacements.append(replacement)

    patched.dataset_intents[target_index:target_index + 1] = replacements
    patched.requested_domains = sorted({item.domain for item in patched.dataset_intents})
    patched.plan_id = f"restricted_{uuid.uuid4().hex}"
    patched.warnings = [
        warning for warning in patched.warnings
        if not warning.startswith("DISCOVERY_REQUIRED:")
    ]
    return patched
