"""Deterministic natural-language export compiler.

This module is the Phase-One production boundary.  It deliberately does not
import a model adapter.  Natural language is reduced to a finite, auditable
``SemanticExportPlan`` and then to one or more frozen Analysis Export Request
v1.1 objects.  The existing request validator and read-only materializer stay
the only authority for data access and Bundle creation.
"""

from __future__ import annotations

import calendar
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from .analysis_export_request import validate_request


MAX_DATASETS_PER_BATCH = 8
SCHEMA_VERSION = "fitness-ledger-pure-core-v1"

RULE_SMALL_DIET_7D = "QUANTITY_SMALL_DAILY_7D"
RULE_RECENT_DIET_14D = "TIME_RECENT_DIET_14D"
RULE_RECENT_MOVEMENT_6S = "TIME_RECENT_MOVEMENT_6S"
RULE_RECENT_TRAINING_14D = "TIME_RECENT_TRAINING_14D"
RULE_RECENT_TRAINING_3S = "TIME_RECENT_TRAINING_3S"
RULE_ALL_FITNESS = "CONCEPT_ALL_FITNESS_V1"
RULE_ALL_SELECTED = "SCOPE_ALL_AVAILABLE_SELECTED_DOMAIN"
RULE_MOVEMENT_ALL = "SCOPE_ALL_AVAILABLE_SELECTED_MOVEMENT"
RULE_PRE_TRAINING_3D = "RELATION_PRE_TRAINING_3D"
RULE_PRE_TRAINING_EXPLICIT = "RELATION_PRE_TRAINING_EXPLICIT"
RULE_TARGET_SESSION_DAY = "RELATION_TARGET_SESSION_DAY"
RULE_POST_TRAINING_1D = "RELATION_POST_TRAINING_1D"
RULE_POST_TRAINING_EXPLICIT = "RELATION_POST_TRAINING_EXPLICIT"
RULE_SOME_MOVEMENTS_3 = "QUANTITY_SOME_MOVEMENTS_3"
RULE_REPRESENTATIVE_TOP3 = "MOVEMENT_REPRESENTATIVE_TOP3_V1"
RULE_MAJOR_PER_BODY_PART = "MOVEMENT_MAJOR_PER_BODY_PART_V1"
RULE_EXPLICIT_MOVEMENTS = "QUANTITY_EXPLICIT_MOVEMENTS_V1"
RULE_NAME_LIST = "MOVEMENT_NAME_LIST_V1"

PROFILE_BODY_BASIC = "BODY_BASIC_V1"
PROFILE_BODY_COMPLETE = "BODY_COMPLETE_V1"
PROFILE_DIET_BASIC = "DIET_BASIC_V1"
PROFILE_DIET_COMPLETE = "DIET_COMPLETE_V1"
PROFILE_TRAINING_BASIC = "TRAINING_BASIC_V1"
PROFILE_TRAINING_COMPLETE = "TRAINING_COMPLETE_V1"
PROFILE_MOVEMENT_NAME = "MOVEMENT_NAME_LIST_V1"
PROFILE_MOVEMENT_GROWTH = "MOVEMENT_GROWTH_COMPLETE_V1"

BODY_FIELDS = ("date", "weight_kg")
BODY_COMPLETE_FIELDS = ("date", "weight_kg", "bowel_movement", "training_label", "cardio_summary")
DIET_FIELDS = ("date", "calories_kcal", "protein_g", "carbs_g", "fat_g")
DIET_COMPLETE_FIELDS = DIET_FIELDS + ("food_summary",)
TRAINING_FIELDS = ("date", "split", "standardized_summary")
MOVEMENT_NAME_FIELDS = ("movement_name",)
MOVEMENT_GROWTH_FIELDS = ("date", "movement_id", "movement_name", "body_part", "variant", "order", "sets")

_DIGITS = {"零": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNITS = {"十": 10, "百": 100, "千": 1000}
_NUMBER = r"(?:\d+|[零一二两三四五六七八九十百千]+)"
_RAW_TERMS = ("raw", "原始记录", "原始输入", "原始数据", "数据库原始")
_WRITE_TERMS = ("删除", "修改", "写入", "新增", "保存", "同步", "上传", "清理掉")
_BODY_TERMS = ("体重", "身体数据", "身体记录", "身体变化", "身体", "体脂", "体成分")
_DIET_TERMS = ("饮食", "热量", "卡路里", "蛋白", "碳水", "脂肪", "食物", "吃了什么", "吃什么", "吃了", "吃的东西", "吃过什么", "摄入", "营养", "餐")
_TRAINING_TERMS = ("训练记录", "训练数据", "训练情况", "训练表现", "训练次数", "训练状态", "训练", "锻炼", "胸训", "背训", "肩训", "腿训")
_MOVEMENT_TERMS = ("动作成长", "成长记录", "动作表现", "动作历史", "动作名称", "动作清单", "动作")
_ANALYSIS_TERMS = ("分析", "比较", "判断", "评估", "是否", "有没有变化", "趋势", "影响", "保持稳定", "稳定性")
_TRAINING_RELATION_PREFIX = r"(?:训练|胸训|背训|肩训|腿训)"
_TRAINING_ARRANGEMENT_TERMS = ("动作安排", "安排了什么动作", "练了什么动作", "练了哪些动作", "做了哪些动作", "做了什么动作", "包含哪些动作")
_MAJOR_MOVEMENT_TERMS = ("主要动作", "代表性动作", "最常练", "最常做", "最常出现")
_BODY_PARTS = {
    "胸部": ("Chest", "胸"), "胸": ("Chest", "胸"),
    "背部": ("Back", "背"), "背": ("Back", "背"),
    "肩部": ("Shoulder", "肩"), "肩": ("Shoulder", "肩"),
    "手臂": ("Arms", "手臂"), "腿部": ("Legs", "腿"), "腿": ("Legs", "腿"),
    "核心": ("Core", "核心"), "腹部": ("Core", "核心"),
}


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]", "", str(value or "").casefold())


def _number(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    total, current = 0, 0
    for char in value:
        if char in _DIGITS:
            current = _DIGITS[char]
        elif char in _UNITS:
            total += (current or 1) * _UNITS[char]
            current = 0
        else:
            return None
    return total + current


def _date_text(value: Any) -> str:
    return str(value or "")[:10]


def _contains_negative(text: str, terms: tuple[str, ...]) -> bool:
    return any(
        re.search(rf"(?:不要|不含|不包括|排除|不看|不需要)[^。；;，,。]{{0,12}}{re.escape(term)}", text)
        or re.search(rf"{re.escape(term)}[^。；;，,。]{{0,8}}(?:不要|不含|不包括|排除|不看)", text)
        for term in terms
    )


def _has_training_relation(text: str) -> bool:
    return bool(re.search(rf"{_TRAINING_RELATION_PREFIX}(?:前|之前|当天|后|之后)", text))


def _has_training_arrangement(text: str) -> bool:
    return any(term in text for term in _TRAINING_ARRANGEMENT_TERMS)


def _has_major_movement_scope(text: str) -> bool:
    return any(term in text for term in _MAJOR_MOVEMENT_TERMS)


def _first_date_range(text: str) -> dict[str, Any] | None:
    match = re.search(r"(\d{4}-\d{2}-\d{2})\s*(?:到|至|—|~)\s*(\d{4}-\d{2}-\d{2})", text)
    if not match:
        return None
    try:
        start, end = date.fromisoformat(match.group(1)), date.fromisoformat(match.group(2))
    except ValueError:
        return None
    return {"mode": "explicit_range", "start": match.group(1), "end": match.group(2)} if start <= end else None


def _chinese_date_range(text: str, anchor: date) -> dict[str, Any] | None:
    match = re.search(
        rf"(?:(\d{{4}})年)?\s*({_NUMBER})月\s*({_NUMBER})日?\s*(?:到|至|—|~)\s*(?:(\d{{4}})年)?\s*({_NUMBER})月\s*({_NUMBER})日",
        text,
    )
    if not match:
        short = re.search(
            rf"(?:(\d{{4}})年)?\s*({_NUMBER})月\s*({_NUMBER})日?\s*(?:到|至|—|~)\s*({_NUMBER})日",
            text,
        )
        if not short:
            return None
        year = int(short.group(1)) if short.group(1) else anchor.year
        month = _number(short.group(2))
        start_day = _number(short.group(3))
        end_day = _number(short.group(4))
        end_year, end_month = year, month
    else:
        year = int(match.group(1)) if match.group(1) else anchor.year
        month = _number(match.group(2))
        start_day = _number(match.group(3))
        end_year = int(match.group(4)) if match.group(4) else year
        end_month = _number(match.group(5))
        end_day = _number(match.group(6))
    try:
        start = date(year, int(month), int(start_day))
        end = date(end_year, int(end_month), int(end_day))
    except (TypeError, ValueError):
        return None
    if start > end:
        return None
    return {"mode": "explicit_range", "start": start.isoformat(), "end": end.isoformat()}


def _month_range(text: str, anchor: date) -> dict[str, Any] | None:
    match = re.search(rf"(?:(\d{{4}})年)?\s*({_NUMBER})月(?:份)?", text)
    if not match:
        return None
    month = _number(match.group(2))
    year = int(match.group(1)) if match.group(1) else anchor.year
    if month is None or not 1 <= month <= 12:
        return None
    last_day = calendar.monthrange(year, month)[1]
    return {"mode": "explicit_range", "start": f"{year:04d}-{month:02d}-01", "end": f"{year:04d}-{month:02d}-{last_day:02d}"}


def _recent_days(text: str) -> int | None:
    if "最近一段时间" in text:
        return 30
    match = re.search(rf"(?:最近|近|过去)\s*({_NUMBER})\s*(天|日|周|星期|个月|月)", text)
    if match:
        value = _number(match.group(1))
        if value is not None:
            return value * (7 if match.group(2) in {"周", "星期"} else 30 if match.group(2) in {"月", "个月"} else 1)
    match = re.search(rf"最近\s*({_NUMBER})\s*(?:天|日)", text)
    if match:
        return _number(match.group(1))
    fixed = {
        "最近一周": 7, "最近一个月": 30, "最近一月": 30, "最近两个月": 60,
        "最近四周": 28, "最近六周": 42, "最近八周": 56, "最近十二周": 84,
    }
    for phrase, days in fixed.items():
        if phrase in text:
            return days
    return None


def _recent_sessions(text: str) -> int | None:
    match = re.search(rf"最近\s*({_NUMBER})\s*(?:次|场|回|个(?:匹配)?场次)", text)
    return _number(match.group(1)) if match else None


def _has_recent_few_sessions(text: str) -> bool:
    return bool(re.search(r"最近\s*几\s*(?:次|场|回)", text))


def _last_data_date(tracker: dict[str, Any]) -> date:
    values: list[str] = []
    for key in ("daily_records", "diet_records", "training_sessions"):
        values.extend(_date_text(item.get("Date")) for item in tracker.get(key, []) if isinstance(item, dict))
    for movement in tracker.get("movements", {}).values():
        if isinstance(movement, dict):
            values.extend(_date_text(item.get("date")) for item in movement.get("history", []) if isinstance(item, dict))
    parsed = [date.fromisoformat(value) for value in values if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)]
    return max(parsed) if parsed else date.today()


def _range_for_all(rows: list[dict[str, Any]], anchor: date) -> dict[str, Any]:
    dates = [_date_text(item.get("date") or item.get("Date")) for item in rows]
    dates = [value for value in dates if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value)]
    return {"mode": "explicit_range", "start": min(dates) if dates else anchor.isoformat(), "end": max(dates) if dates else anchor.isoformat()}


@dataclass(frozen=True)
class CatalogItem:
    movement_id: str
    movement_name: str
    body_part: str
    aliases: tuple[str, ...]
    history_count: int
    recent_date: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "movement_id": self.movement_id,
            "movement_name": self.movement_name,
            "body_part": self.body_part,
            "aliases": list(self.aliases),
            "history_count": self.history_count,
            "recent_date": self.recent_date,
            "counts_toward_growth": self.history_count > 0,
        }


@dataclass(frozen=True)
class CompileOutput:
    status: str
    plan: dict[str, Any]
    requests: tuple[dict[str, Any], ...] = ()
    candidates: tuple[dict[str, Any], ...] = ()
    errors: tuple[dict[str, str], ...] = ()
    confirmations: tuple[str, ...] = ()

    def to_response(self) -> dict[str, Any]:
        response: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "status": self.status,
            "semantic_plan": self.plan,
            "model_calls": 0,
            "requests": list(self.requests),
            "request": self.requests[0] if len(self.requests) == 1 else None,
            "candidates": list(self.candidates),
            "errors": list(self.errors),
            "confirmations": list(self.confirmations),
            "warnings": (
                [{"code": "ANALYSIS_EVIDENCE_ONLY", "message": self.plan["analysis_boundary"]["message"]}]
                if self.plan.get("analysis_boundary", {}).get("analysis_requested")
                else []
            ),
            "execution": {
                "allowed": False,
                "executor_called": False,
                "formal_data_written": False,
                "raw_allowed": False,
            },
        }
        if len(self.requests) > 1:
            response["request_batches"] = list(self.requests)
            response["batch"] = {
                "batch_count": len(self.requests),
                "max_datasets": MAX_DATASETS_PER_BATCH,
                "dataset_counts": [len(item.get("datasets", [])) for item in self.requests],
            }
        return response


class PureCoreExportCompiler:
    """Compile a user request using only local snapshot facts and rules."""

    def __init__(self, views: Any) -> None:
        self.views = views
        self.tracker, self.dictionary = views.snapshot()
        self.anchor = _last_data_date(self.tracker)
        self.catalog = self._build_catalog()

    def _build_catalog(self) -> tuple[CatalogItem, ...]:
        histories = self.tracker.get("movements", {})
        rows: list[CatalogItem] = []
        for item in self.dictionary.get("movements", []) or []:
            if not isinstance(item, dict) or not item.get("movement_id") or item.get("active", True) is False:
                continue
            movement_id = str(item["movement_id"])
            movement = histories.get(movement_id, {}) if isinstance(histories, dict) else {}
            history = [row for row in movement.get("history", []) if isinstance(row, dict)]
            recent = max((_date_text(row.get("date")) for row in history), default="")
            aliases = tuple(str(value) for value in (item.get("aliases") or []) if str(value).strip())
            rows.append(CatalogItem(movement_id, str(item.get("display_name") or item.get("english_name") or movement_id), str(item.get("muscle_group") or ""), aliases, len(history), recent))
        return tuple(rows)

    def _catalog_matches(self, phrase: str) -> list[CatalogItem]:
        key = _normalize(phrase)
        exact = [item for item in self.catalog if _normalize(item.movement_name) == key or any(_normalize(alias) == key for alias in item.aliases)]
        if exact:
            return exact
        return [item for item in self.catalog if key and (key in _normalize(item.movement_name) or any(key in _normalize(alias) for alias in item.aliases))]

    def _movement_mentions(self, text: str) -> list[tuple[str, list[CatalogItem]]]:
        found: list[tuple[int, str, list[CatalogItem]]] = []
        for item in self.catalog:
            terms = (item.movement_name,) + item.aliases
            for term in terms:
                if term and term in text:
                    found.append((text.find(term), term, self._catalog_matches(term)))
        unique: dict[str, tuple[int, str, list[CatalogItem]]] = {}
        for index, term, matches in sorted(found, key=lambda value: (value[0], -len(value[1]))):
            unique.setdefault(_normalize(term), (index, term, matches))
        return [(term, matches) for _index, term, matches in sorted(unique.values(), key=lambda value: value[0])]

    def _body_part(self, text: str) -> tuple[str, str] | None:
        for term, value in sorted(_BODY_PARTS.items(), key=lambda pair: len(pair[0]), reverse=True):
            if term in text:
                return value
        return None

    def _scoped_days(self, text: str, domain: str, fallback: int | None) -> int | None:
        matches = list(re.finditer(rf"最近\s*({_NUMBER})\s*(?:天|日)", text))
        if not matches:
            return fallback
        candidates: list[tuple[int, int]] = []
        terms = {"body": _BODY_TERMS, "diet": _DIET_TERMS, "training": _TRAINING_TERMS, "movement_progress": _MOVEMENT_TERMS}[domain]
        for match in matches:
            window = text[max(0, match.start() - 14): min(len(text), match.end() + 18)]
            if any(term in window for term in terms):
                value = _number(match.group(1))
                if value is not None:
                    candidates.append((abs(window.find(next((term for term in terms if term in window), ""))), value))
        return candidates[0][1] if candidates else fallback

    def _excluded_domains(self, text: str) -> list[str]:
        excluded: list[str] = []
        for domain, terms in (("body", _BODY_TERMS), ("diet", _DIET_TERMS), ("training", _TRAINING_TERMS), ("movement_progress", _MOVEMENT_TERMS)):
            notes_terms = {
                "body": ("身体备注", "每日备注"),
                "diet": ("饮食备注", "饮食笔记"),
                "training": ("训练备注", "训练笔记"),
                "movement_progress": ("动作备注", "动作笔记", "movement notes"),
            }[domain]
            notes_only = any(_contains_negative(text, (term,)) for term in notes_terms)
            if domain == "diet" and notes_only:
                notes_only = not bool(re.search(r"(?:不要|不含|排除)[^。；;，,。]{0,8}饮食(?:和|、|与).*(?:训练|动作)", text))
            if _contains_negative(text, terms) and not notes_only:
                excluded.append(domain)
        return excluded

    def _requested_domains(self, text: str, excluded: set[str]) -> tuple[list[str], list[str]]:
        all_fitness = bool(re.search(r"(?:全部|所有|整体|全量)?(?:健身|健身数据|健身记录)", text)) and any(term in text for term in ("全部", "所有", "最近", "整理", "导出"))
        domains: list[str] = ["body", "diet", "training"] if all_fitness else []
        movement_signal = any(term in text for term in _MOVEMENT_TERMS) or bool(self._movement_mentions(text))
        training_signal = any(term in text for term in _TRAINING_TERMS)
        relation_signal = _has_training_relation(text)
        training_evidence_signal = any(term in text for term in ("训练记录", "训练数据", "训练情况", "整体训练")) or _has_training_arrangement(text)
        if any(term in text for term in _BODY_TERMS):
            domains.append("body")
        if any(term in text for term in _DIET_TERMS):
            domains.append("diet")
        if training_signal and not (movement_signal and not training_evidence_signal):
            domains.append("training")
        if movement_signal:
            domains.append("movement_progress")
        if relation_signal and "diet" in domains:
            domains.append("training")
        ordered = [domain for domain in ("body", "diet", "training", "movement_progress") if domain in domains and domain not in excluded]
        return ordered, sorted(set(excluded))

    def _profile(self, domain: str, text: str, name_list: bool = False) -> tuple[str, tuple[str, ...], str | None]:
        if domain == "body":
            complete = "完整" in text or "全部字段" in text
            return (PROFILE_BODY_COMPLETE if complete else PROFILE_BODY_BASIC, BODY_COMPLETE_FIELDS if complete else BODY_FIELDS, "daily" if complete else None)
        if domain == "diet":
            complete = "完整饮食" in text or "完整记录" in text or "全部字段" in text or any(term in text for term in ("吃了什么", "吃的东西", "吃过什么", "食物"))
            notes = None if _contains_negative(text, ("饮食备注", "饮食笔记")) else ("diet" if complete or "饮食备注" in text or "饮食笔记" in text else None)
            return (PROFILE_DIET_COMPLETE if complete else PROFILE_DIET_BASIC, DIET_COMPLETE_FIELDS if complete else DIET_FIELDS, notes)
        if domain == "training":
            complete = "完整训练" in text or "完整记录" in text
            return (PROFILE_TRAINING_COMPLETE if complete else PROFILE_TRAINING_BASIC, TRAINING_FIELDS, "training" if complete or "训练备注" in text or "训练笔记" in text else None)
        if name_list:
            return PROFILE_MOVEMENT_NAME, MOVEMENT_NAME_FIELDS, None
        notes = None if _contains_negative(text, ("动作备注", "动作笔记", "movement notes")) else "movement"
        return PROFILE_MOVEMENT_GROWTH, MOVEMENT_GROWTH_FIELDS, notes

    def _field_constraints(self, domain: str, fields: tuple[str, ...], text: str) -> tuple[str, ...]:
        excluded_terms = {
            "body": {"weight_kg": ("体重",), "bowel_movement": ("排便",), "training_label": ("训练标签",), "cardio_summary": ("有氧",)},
            "diet": {"calories_kcal": ("热量", "卡路里"), "protein_g": ("蛋白",), "carbs_g": ("碳水",), "fat_g": ("脂肪",), "food_summary": ("食物", "吃了什么")},
            "training": {"split": ("分化",), "standardized_summary": ("训练摘要", "训练概况")},
            "movement_progress": {"movement_id": ("动作ID", "动作 id"), "movement_name": ("动作名称",), "body_part": ("部位",), "variant": ("变式",), "order": ("顺序",), "sets": ("组数", "次数", "重量", "负重")},
        }.get(domain, {})
        kept = []
        for field in fields:
            terms = excluded_terms.get(field, ())
            if terms and any(_contains_negative(text, (term,)) for term in terms):
                continue
            kept.append(field)
        return tuple(kept)

    def _time_scope(self, text: str, domain: str, *, all_available: bool = False, relation: dict[str, Any] | None = None) -> tuple[dict[str, Any], str, str]:
        if relation is not None:
            if relation["mode"] == "target_session_day":
                rule = RULE_TARGET_SESSION_DAY
            elif relation["mode"] == "days_after_target_session":
                rule = RULE_POST_TRAINING_EXPLICIT if relation["days_after"] != 1 else RULE_POST_TRAINING_1D
            else:
                rule = RULE_PRE_TRAINING_EXPLICIT if relation["days_before"] != 3 else RULE_PRE_TRAINING_3D
            return relation, "relation", rule
        explicit = _first_date_range(text)
        if explicit:
            return explicit, "explicit_user_range", "TIME_EXPLICIT_RANGE"
        explicit = _chinese_date_range(text, self.anchor)
        if explicit:
            return explicit, "explicit_user_range", "TIME_EXPLICIT_RANGE"
        month = _month_range(text, self.anchor)
        if month:
            return month, "explicit_user_month", "TIME_EXPLICIT_MONTH"
        if all_available:
            rows: list[dict[str, Any]] = []
            if domain == "body": rows = list(self.tracker.get("daily_records", []))
            elif domain == "diet": rows = list(self.tracker.get("diet_records", []))
            elif domain == "training": rows = list(self.tracker.get("training_sessions", []))
            else:
                rows = [row for movement in self.tracker.get("movements", {}).values() for row in movement.get("history", [])]
            return _range_for_all(rows, self.anchor), "all_available", RULE_ALL_SELECTED
        days = self._scoped_days(text, domain, _recent_days(text))
        if days is not None:
            rule = "TIME_RECENT_CONTEXT_30D" if "最近一段时间" in text else "TIME_RECENT_CUSTOM"
            source = "product_default" if "最近一段时间" in text else "explicit_recent_days"
            return {"mode": "recent_days", "days": days}, source, rule
        sessions = _recent_sessions(text)
        if sessions is not None and domain in {"training", "movement_progress"}:
            return {"mode": "latest_matching_sessions", "sessions": sessions}, "explicit_recent_sessions", "TIME_EXPLICIT_MOVEMENT_SESSIONS"
        if domain == "diet" and "少量" in text:
            return {"mode": "recent_days", "days": 7}, "default_quantity", RULE_SMALL_DIET_7D
        if domain == "diet":
            return {"mode": "recent_days", "days": 14}, "product_default", RULE_RECENT_DIET_14D
        if domain == "movement_progress":
            return {"mode": "latest_matching_sessions", "sessions": 6}, "product_default", RULE_RECENT_MOVEMENT_6S
        if domain == "training":
            return {"mode": "recent_days", "days": 14}, "product_default", RULE_RECENT_TRAINING_14D
        return {"mode": "recent_days", "days": 14}, "product_default", "TIME_RECENT_BODY_14D"

    def _relation(self, text: str, training_id: str) -> dict[str, Any] | None:
        match_mode = "single_latest_matching_session" if ("上一次" in text or "上次" in text) else "each_matching_session"
        post_phrase = re.search(rf"{_TRAINING_RELATION_PREFIX}(?:后|之后)", text)
        target_day_phrase = re.search(rf"{_TRAINING_RELATION_PREFIX}当天", text)
        pre_phrase = re.search(rf"{_TRAINING_RELATION_PREFIX}(?:前|之前)", text)
        if post_phrase:
            match = re.search(rf"{_TRAINING_RELATION_PREFIX}(?:后|之后)\s*({_NUMBER})\s*(?:天|日)", text)
            days = _number(match.group(1)) if match else 1
            excludes_day = bool(re.search(rf"(?:不包含|不含|排除|不要)[^。；;，,。]{{0,6}}(?:{_TRAINING_RELATION_PREFIX})?当天", text))
            include = not excludes_day and (bool(target_day_phrase) or "到当天" in text or "包含当天" in text)
            return {"mode": "days_after_target_session", "days_after": days or 1, "target_dataset_id": training_id, "match_mode": match_mode, "include_target_session_day": include}
        if target_day_phrase and not pre_phrase:
            return {"mode": "target_session_day", "target_dataset_id": training_id, "match_mode": match_mode}
        if not pre_phrase:
            return None
        match = re.search(rf"{_TRAINING_RELATION_PREFIX}(?:前|之前)\s*({_NUMBER})\s*(?:天|日)", text)
        days = _number(match.group(1)) if match else 3
        excludes_day = bool(re.search(rf"(?:不包含|不含|排除|不要)[^。；;，,。]{{0,6}}(?:{_TRAINING_RELATION_PREFIX})?当天", text))
        include = not excludes_day and (bool(target_day_phrase) or "到当天" in text or "包含当天" in text)
        return {"mode": "days_before_target_session", "days_before": days or 3, "target_dataset_id": training_id, "match_mode": match_mode, "include_target_session_day": include}

    def _movement_selection(self, text: str) -> tuple[list[CatalogItem], list[dict[str, Any]], bool]:
        mentions = self._movement_mentions(text)
        selected: list[CatalogItem] = []
        ambiguous: list[dict[str, Any]] = []
        for phrase, matches in mentions:
            if len(matches) == 1:
                selected.append(matches[0])
            elif matches:
                ambiguous.extend(item.to_dict() for item in matches)
            else:
                ambiguous.append({"movement_name": phrase, "movement_id": "", "body_part": "", "history_count": 0, "recent_date": ""})
        all_parts_scope = any(term in text for term in ("各部位", "各个部位", "每个部位", "全身各部位"))
        if all_parts_scope and _has_major_movement_scope(text):
            grouped: dict[str, list[CatalogItem]] = {}
            for item in self.catalog:
                if item.body_part and item.history_count > 0:
                    grouped.setdefault(item.body_part, []).append(item)
            selected = [
                sorted(items, key=lambda item: (-item.history_count, item.movement_name))[0]
                for _body_part, items in sorted(grouped.items())
            ]
            ambiguous = []
        part = self._body_part(text)
        if part and ("所有动作" in text or "全部动作" in text or "动作名称" in text or "动作清单" in text or "哪些动作" in text or _has_training_arrangement(text) or _has_major_movement_scope(text)):
            candidates = [item for item in self.catalog if item.body_part.casefold() == part[0].casefold() and item.history_count > 0]
            if _has_major_movement_scope(text):
                candidates = sorted(candidates, key=lambda item: (-item.history_count, item.movement_name))[:3]
            selected = candidates
            ambiguous = [item.to_dict() for item in candidates]
        return selected, ambiguous, bool(mentions or part)

    def _base_plan(self, text: str, domains: list[str], excluded: list[str]) -> dict[str, Any]:
        plan_id = "sep_" + hashlib.sha256(text.encode("utf-8")).hexdigest()[:24]
        analysis_terms = [term for term in _ANALYSIS_TERMS if term in text]
        analysis_requested = bool(analysis_terms)
        return {
            "schema_version": SCHEMA_VERSION,
            "plan_id": plan_id,
            "request_kind": "analysis_evidence_export" if analysis_requested else "direct_data_export",
            "analysis_boundary": {
                "analysis_requested": analysis_requested,
                "matched_terms": analysis_terms,
                "core_capability": "evidence_export_only" if analysis_requested else "data_export",
                "analysis_result_generated": False,
                "message": "Pure Core 仅规划并导出分析所需证据，不生成分析结论。" if analysis_requested else "",
            },
            "requested_domains": domains,
            "excluded_domains": excluded,
            "dataset_intents": [],
            "explicit_constraints": {"source_text": text, "raw": False, "excluded_domains": excluded},
            "applied_rule_ids": [],
            "selected_movement_ids": [],
            "relationship_specs": [],
            "batches": [],
        }

    def compile(self, user_text: str, selected_movement_ids: list[str] | tuple[str, ...] | None = None) -> CompileOutput:
        text = re.sub(r"\s+", " ", str(user_text or "").strip())
        excluded = self._excluded_domains(text)
        domains, excluded = self._requested_domains(text, set(excluded))
        plan = self._base_plan(text, domains, excluded)
        if not text:
            return CompileOutput("needs_confirmation", plan, confirmations=("请输入需要导出的数据范围。",))
        lowered = text.casefold()
        if any(term in lowered for term in _RAW_TERMS):
            return CompileOutput("unsupported", plan, errors=({"code": "RAW_PERMISSION_REQUIRED", "message": "原始数据库记录不进入只读结构化导出。"},))
        if any(term in text for term in _WRITE_TERMS):
            return CompileOutput("unsupported", plan, errors=({"code": "UNSUPPORTED_OPERATION", "message": "导出 Core 不执行删除、写入、同步或清理操作。"},))
        if not domains:
            return CompileOutput("needs_confirmation", plan, confirmations=("请说明要导出的数据类型，例如身体、饮食、训练或动作成长。",))

        if "健身" in text and any(term in text for term in ("全部", "所有", "整体", "最近", "整理", "导出")):
            plan["applied_rule_ids"].append(RULE_ALL_FITNESS)
        has_explicit_window = _first_date_range(text) is not None or _chinese_date_range(text, self.anchor) is not None or _month_range(text, self.anchor) is not None or _recent_days(text) is not None
        all_available = any(term in text for term in ("从有记录以来", "全部成长", "完整成长", "全部可用历史")) or (not has_explicit_window and ("全部" in text or "所有" in text) and "动作名称" not in text and "动作清单" not in text)
        name_list = any(term in text for term in ("动作名称", "动作清单", "列出所有动作", "列出动作", "哪些动作", "练了哪些动作", "安排了什么动作", "练了什么动作")) and "成长" not in text and "表现" not in text
        movement_selection, candidates, movement_signal = self._movement_selection(text)
        selected_id_set = {str(value).strip() for value in (selected_movement_ids or ()) if str(value).strip()}
        if selected_id_set:
            movement_selection = [item for item in self.catalog if item.movement_id in selected_id_set]
            candidates = []
            plan["explicit_constraints"]["selected_movement_ids"] = sorted(selected_id_set)
        if "movement_progress" in domains and not movement_selection and not candidates and (any(term in text for term in ("一些", "少量", "主要", "代表性")) or _has_major_movement_scope(text)):
            count_match = re.search(rf"(?:最近|导出|列出)?\s*({_NUMBER})\s*(?:个|项)?\s*(?:主要|代表性)?\s*(?:训练)?\s*动作", text)
            requested_count = _number(count_match.group(1)) if count_match else 3
            movement_selection = sorted(self.catalog, key=lambda item: (-item.history_count, item.movement_name))[: max(1, requested_count or 3)]
            if "一些" in text or "少量" in text:
                plan["applied_rule_ids"].append(RULE_SOME_MOVEMENTS_3)
        body_part_scope = self._body_part(text) and (any(term in text for term in ("动作名称", "动作清单", "所有动作", "全部动作", "哪些动作")) or _has_training_arrangement(text))
        if body_part_scope and "movement_progress" in domains and not selected_id_set:
            plan["selected_movement_ids"] = [item.movement_id for item in movement_selection]
            plan["applied_rule_ids"] = [RULE_NAME_LIST if name_list else "MOVEMENT_CATALOG_DISCOVERY"]
            return CompileOutput("candidate_confirmation_required", plan, candidates=tuple(item.to_dict() for item in movement_selection), confirmations=("请确认 Data Catalog 中的正式动作候选后再生成导出计划。",))
        if movement_signal and "movement_progress" in domains and candidates and (not movement_selection or any(not item.get("movement_id") for item in candidates)):
            plan["selected_movement_ids"] = [item["movement_id"] for item in candidates if item.get("movement_id")]
            plan["applied_rule_ids"] = [RULE_NAME_LIST if name_list else "MOVEMENT_RESOLVER_REQUIRED"]
            return CompileOutput("candidate_confirmation_required", plan, candidates=tuple(candidates), confirmations=("请先确认正式动作候选，Core 不会随机选择或合并 movement_id。",))
        if movement_signal and "movement_progress" in domains and not movement_selection:
            return CompileOutput("candidate_confirmation_required", plan, confirmations=("没有找到可唯一解析的正式动作，请从 Data Catalog 选择。",))

        selected_ids = [item.movement_id for item in movement_selection]
        deduped_selection: list[CatalogItem] = []
        seen_movement_ids: set[str] = set()
        for item in movement_selection:
            if item.movement_id not in seen_movement_ids:
                deduped_selection.append(item)
                seen_movement_ids.add(item.movement_id)
        movement_selection = deduped_selection
        selected_ids = [item.movement_id for item in movement_selection]
        if "some" in text or "一些" in text or "少数" in text:
            if "movement_progress" in domains and not selected_ids:
                movement_selection = sorted(self.catalog, key=lambda item: (-item.history_count, item.movement_name))[:3]
                selected_ids = [item.movement_id for item in movement_selection]
                plan["applied_rule_ids"].append(RULE_SOME_MOVEMENTS_3)
        all_parts_scope = any(term in text for term in ("各部位", "各个部位", "每个部位", "全身各部位"))
        count_match_for_rule = re.search(rf"({_NUMBER})\s*(?:个|项)?\s*(?:主要|代表性)?\s*(?:训练)?\s*动作", text)
        if all_parts_scope and _has_major_movement_scope(text):
            plan["applied_rule_ids"].append(RULE_MAJOR_PER_BODY_PART)
        elif count_match_for_rule and ("主要" in text or "代表性" in text):
            plan["applied_rule_ids"].append(RULE_EXPLICIT_MOVEMENTS)
        elif _has_major_movement_scope(text):
            plan["applied_rule_ids"].append(RULE_REPRESENTATIVE_TOP3)
        plan["selected_movement_ids"] = selected_ids
        if "movement_progress" in domains and "所有动作" in text and not movement_selection:
            return CompileOutput("candidate_confirmation_required", plan, candidates=tuple(item.to_dict() for item in self.catalog), confirmations=("该范围没有可用的正式动作候选。",))

        training_needed_for_relation = "diet" in domains and _has_training_relation(text)
        if training_needed_for_relation and "training" not in domains:
            domains.append("training")
            plan["requested_domains"] = domains
        dataset_specs: list[tuple[str, dict[str, Any], str, tuple[str, ...], str | None, dict[str, Any]]] = []
        movement_items = movement_selection if "movement_progress" in domains else []
        if "movement_progress" in domains and not movement_items and not name_list:
            return CompileOutput("candidate_confirmation_required", plan, confirmations=("动作请求需要正式 movement resolver 结果。",))
        domain_order = [domain for domain in ("body", "diet", "training") if domain in domains]
        if "movement_progress" in domains:
            domain_order.append("movement_progress")
        training_id = "training_1" if "training" in domains else ""
        for domain in domain_order:
            profile, fields, notes_scope = self._profile(domain, text, name_list)
            fields = self._field_constraints(domain, fields, text)
            if not fields:
                return CompileOutput("needs_confirmation", plan, confirmations=(f"{domain} 的字段被全部排除，请至少保留一个结构化字段。",))
            if domain == "movement_progress":
                for index, item in enumerate(movement_items, 1):
                    scope, source, rule = self._time_scope(text, domain, all_available=all_available)
                    dataset_id = f"movement_{index}"
                    dataset_specs.append((dataset_id, scope, profile, fields, notes_scope, {"movement_id": item.movement_id, "movement_name": item.movement_name, "source": source, "rule": rule}))
                continue
            relation = self._relation(text, training_id) if domain == "diet" and training_needed_for_relation else None
            scope, source, rule = self._time_scope(text, domain, all_available=all_available, relation=relation)
            filters: dict[str, Any] = {}
            if domain == "training":
                part = self._body_part(text)
                if part:
                    filters["body_part"] = part[1]
                sessions = _recent_sessions(text)
                if sessions is None and ("上一次" in text or "上次" in text):
                    sessions = 1
                if sessions is None and _has_recent_few_sessions(text):
                    sessions = 3
                if sessions is not None:
                    scope = {"mode": "latest_matching_sessions", "sessions": sessions}
                    if _recent_sessions(text) is not None or "上一次" in text or "上次" in text:
                        source, rule = "explicit_recent_sessions", "TIME_EXPLICIT_TRAINING_SESSIONS"
                    else:
                        source, rule = "product_default", RULE_RECENT_TRAINING_3S
            dataset_specs.append((f"{domain}_1", scope, profile, fields, notes_scope, {"filters": filters, "source": source, "rule": rule, "relation": relation}))

        requests: list[dict[str, Any]] = []
        for batch_index in range(0, len(dataset_specs), MAX_DATASETS_PER_BATCH):
            chunk = dataset_specs[batch_index:batch_index + MAX_DATASETS_PER_BATCH]
            datasets: list[dict[str, Any]] = []
            id_map = {item[0]: f"batch_{len(requests) + 1}_{item[0]}" for item in chunk}
            for dataset_id, scope, profile, fields, notes_scope, meta in chunk:
                dataset = {"dataset_id": id_map[dataset_id], "type": dataset_id.split("_")[0] if dataset_id.startswith(("body_", "diet_", "training_")) else "movement_progress", "time_range": dict(scope), "filters": dict(meta.get("filters", {})), "fields": list(fields)}
                if dataset["type"] == "movement_progress":
                    dataset["filters"] = {"movement_selector": {"kind": "movement_id", "value": meta["movement_id"]}}
                if meta.get("relation") is not None:
                    relation = dict(meta["relation"])
                    relation["target_dataset_id"] = id_map.get("training_1", relation.get("target_dataset_id"))
                    dataset["time_range"] = relation
                if notes_scope:
                    dataset["notes_scope"] = notes_scope
                datasets.append(dataset)
                intent = {
                    "intent_id": f"intent_{len(plan['dataset_intents']) + 1}",
                    "domain": dataset["type"],
                    "field_profile": profile,
                    "time_scope": dataset["time_range"],
                    "time_scope_source": meta.get("source", "product_default"),
                    "movement_id": meta.get("movement_id"),
                    "relationship_id": f"relation_{dataset['dataset_id']}" if meta.get("relation") is not None else None,
                }
                plan["dataset_intents"].append(intent)
                if meta.get("rule"):
                    plan["applied_rule_ids"].append(meta["rule"])
                if meta.get("relation") is not None:
                    plan["relationship_specs"].append({"relationship_id": intent["relationship_id"], "mode": relation["mode"], "target_dataset_id": relation["target_dataset_id"], "dependent_dataset_id": dataset["dataset_id"], "days_before": relation.get("days_before"), "days_after": relation.get("days_after"), "include_target_session_day": relation.get("include_target_session_day", False)})
            request = {"request_version": "1.1", "purpose": text[:500], "datasets": datasets, "raw": False, "output": {"formats": ["json", "markdown"]}}
            validation = validate_request(request)
            if not validation.valid or validation.normalized_request is None:
                return CompileOutput("needs_confirmation", plan, errors=tuple(item.to_dict() for item in validation.errors), confirmations=("Core 生成的请求未通过 v1.1 Validator。",))
            requests.append(validation.normalized_request)
            plan["batches"].append({"batch_index": len(requests), "dataset_ids": [item["dataset_id"] for item in validation.normalized_request["datasets"]], "dataset_count": len(validation.normalized_request["datasets"])})
        plan["applied_rule_ids"] = list(dict.fromkeys(plan["applied_rule_ids"]))
        plan["explicit_constraints"]["excluded_notes_scopes"] = ["diet"] if _contains_negative(text, ("饮食备注", "饮食笔记")) else []
        return CompileOutput("ready", plan, tuple(requests))


__all__ = ["PureCoreExportCompiler", "CompileOutput", "SCHEMA_VERSION", "MAX_DATASETS_PER_BATCH"]
