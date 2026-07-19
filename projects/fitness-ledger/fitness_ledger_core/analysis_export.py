from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import date


MIN_TREND_OCCURRENCES = 2
MAX_TREND_MOVEMENTS = 16
TREND_AREA_BY_MUSCLE_GROUP = {
    "Chest": "胸部",
    "Back": "背部",
    "Shoulder": "肩部",
    "Arms": "手臂",
    "Legs": "腿部",
    "Core": "核心 / 腹部",
}


def _text(value) -> str:
    return str(value or "").strip()


def _number(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _format_number(value) -> str:
    number = _number(value)
    if number is None:
        return ""
    return str(int(number)) if number.is_integer() else f"{number:.1f}".rstrip("0").rstrip(".")


def _format_weight(value) -> str:
    number = _number(value)
    return f"{number:.2f} kg" if number is not None else "暂无有效记录"


def _format_change(value) -> str:
    number = _number(value)
    return f"{number:+.2f} kg" if number is not None else "暂无有效记录"


def _date(value) -> str:
    return _text(value)[:10]


def _sets_text(history: dict) -> str:
    parts = []
    for item in history.get("sets", []) or []:
        weight_text = _text(item.get("weight_text"))
        weight = _number(item.get("weight"))
        if not weight_text:
            weight_text = "自重" if weight == 0 else _format_number(item.get("weight"))
        reps, sets = _format_number(item.get("reps")), _format_number(item.get("sets"))
        values = [part for part in (weight_text, reps, sets) if part]
        if values:
            parts.append(" × ".join(values))
    return "；".join(parts) or "暂无有效记录"


def _order_value(history: dict, index: int) -> tuple[int, int]:
    order = _number(history.get("order"))
    return (0, int(order)) if order is not None else (1, index)


def _bowel(value) -> str:
    normalized = re.sub(r"[\s,，。.]+", "", _text(value).lower())
    if not normalized:
        return "unrecorded"
    if normalized in {"有", "是", "正常", "少量", "称重后有", "是称重后少量", "称重后少量", "yes", "y"}:
        return "yes"
    if normalized in {"无", "否", "no", "n"}:
        return "no"
    return "unknown"


def _is_non_strength_activity(value) -> bool:
    """Recognize only explicit formal labels for a day without strength work."""
    normalized = re.sub(r"\s+", "", _text(value).lower())
    normalized = normalized.translate(str.maketrans({"／": "/", "、": "/", "，": "/", "。": "/", "；": "/", "：": "/", ":": "/"})).strip("/")
    return normalized in {"休息", "无力量训练", "步行/无力量训练", "无力量训练/步行"}


def _normalized_note(value: str) -> str:
    return re.sub(r"[\s，,。；;：:！!？?]+", "", _text(value)).lower()


def _note_parts(value: str) -> list[str]:
    return [part.strip() for part in re.split(r"(?<=[。！？!?；;])\s*|\n+", _text(value)) if part.strip()]


def _is_generic_note_part(value: str) -> bool:
    """Remove only bounded, repeatable analysis explanations and generic advice."""
    normalized = _normalized_note(value)
    patterns = (
        r".*(?:高碳|碳水).*(?:糖原|水分).*(?:变化|波动).*",
        r".*高钠.*(?:水分潴留|水分变化).*",
        r".*未排便.*(?:次日)?体重.*(?:影响|波动).*",
        r".*(?:胃肠内容物|肠胃内容物).*(?:体重|波动).*",
        r".*(?:单日|次日).*体重.*(?:不宜|不应|不能).*?(?:脂肪增加|真实脂肪变化).*",
        r".*蛋白质.*(?:有利于|满足).*(?:恢复|恢复需求).*",
        r".*(?:训练日)?碳水.*(?:有利于|适合|支持).*(?:训练输出|供能).*",
        r".*(?:符合|处于).*(?:减脂目标|减脂期).*",
        r".*适合作为.*高碳训练日.*",
        r".*(?:整体)?恢复供能充足.*",
        r".*(?:明日建议|建议|后续建议).*(?:高蛋白.*低油|中低碳|回归正常饮食|补充蛋白).*",
        r".*(?:不需要|无需).*(?:极端断食|断食补偿).*",
    )
    return any(re.fullmatch(pattern, normalized) for pattern in patterns)


def _strip_low_value_fragments(value: str) -> str:
    """Remove bounded, exporter-only commentary already represented by structured fields."""
    patterns = (
        r"(?:今日|当天)为[^。；;，]*?(?:高碳日|低碳日|训练日)[，、。；;]?\s*",
        r"整体训练容量较高[，、]?\s*",
        r"今日胸肩训练整体表现为[^。；;]*?(?:未达完全力竭状态)[。；;]?\s*",
        r"饮食结构呈现[^。；;]*?特征[，、]?\s*",
        r"脂肪主要来源于[^。；;]*?(?:叠加|构成)[。；;]?\s*",
        r"当前体重较前日下降[^。；;]*?而非真实脂肪变化[。；;]?\s*",
        r"当前体重较前日下降[^。；;]*?水分波动[。；;]?\s*",
        r"(?:全天)?蛋白(?:质)?(?:摄入)?(?:达到|预期达到)[^。；;]*?(?:恢复需求|以上)[。；;]?\s*",
        r"蛋白粉[^。；;]*?(?:恢复需求|以上)[。；;]?\s*",
        r"整体热量控制较克制[，、]?\s*",
        r"低碳日脂肪相对较高[^。；;]*?(?:记录)[。；;]?\s*",
        r"饮食方面[，、]?\s*",
        r"早餐和练前[^。；;]*?继续补充蛋白与碳水[。；;]?\s*",
        r"今日总碳水约[^。；;]*?(?:高碳背部训练日安排)[。；;]?\s*",
        r"蛋白质主要来自[^。；;]*?(?:蛋白粉)[。；;]?\s*",
        r"但由于[^。；;]*?烹调用油[^。；;]*?脂肪[^。；;]*?上修[。；;]?\s*",
        r"由于前一日为高碳背部训练日[^。；;]*?练前摄入[^，。；;]*，[ ]*",
        r"考虑与[^。；;]*?有关，因此[ ]*",
        r"今日未进行跑步机爬坡[^。；;]*?散步[。；;]?\s*",
    )
    result = _text(value)
    for pattern in patterns:
        result = re.sub(pattern, "", result)
    result = re.sub(r"\s+", " ", result)
    result = re.sub(r"^[，、；;：:\s]+|[，、；;：:\s]+$", "", result)
    result = re.sub(r"([。！？!?])\s*[，、；;]+", r"\1", result)
    result = re.sub(r"^[。！？!?]+\s*", "", result)
    return result.strip()


def _split_action_note(value: str) -> tuple[str, str] | None:
    match = re.fullmatch(r"\s*([^：:；;。！？!?]+)\s*[：:]\s*(.+?)\s*[。！？!?]?\s*", value, re.S)
    return (match.group(1), match.group(2)) if match else None


def _clean_note(value: str, action_notes: dict[str, set[str]]) -> str:
    kept = []
    for part in _note_parts(value):
        part = _strip_low_value_fragments(part)
        if not part:
            continue
        action_item = _split_action_note(part)
        if action_item:
            name, note = action_item
            if _normalized_note(note) in action_notes.get(_normalized_note(name), set()):
                continue
        if not _is_generic_note_part(part):
            kept.append(part)
    return " ".join(kept)


def _daily_notes(
    body: dict | None,
    diet: dict | None,
    training: dict | None,
    histories: list[dict],
) -> list[str]:
    action_notes: dict[str, set[str]] = defaultdict(set)
    for history in histories:
        note = _normalized_note(history.get("notes"))
        name = _normalized_note(history.get("_display_name"))
        if note and name:
            action_notes[name].add(note)
    values = [
        ("身体", _clean_note(_text((body or {}).get("Notes")), action_notes)),
        ("饮食", _clean_note(_text((diet or {}).get("Notes")), action_notes)),
        ("训练", _clean_note(_text((training or {}).get("Notes")), action_notes)),
    ]
    nonempty = [(label, value) for label, value in values if value]
    if not nonempty:
        return []
    unique = {value for _label, value in nonempty}
    if len(unique) == 1:
        return [nonempty[0][1]]
    return [f"- {label}：{value}" for label, value in nonempty]


def _trend_sort_key(candidate: dict) -> tuple[int, int, str]:
    return (-len(candidate["rows"]), -date.fromisoformat(candidate["recent_date"]).toordinal(), candidate["name"])


def _select_trend_movements(movement_rows: list[dict]) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in movement_rows:
        if row["_movement_id"]:
            grouped[row["_movement_id"]].append(row)
    candidates = []
    for movement_id, rows in grouped.items():
        if len(rows) < MIN_TREND_OCCURRENCES:
            continue
        rows.sort(key=lambda row: (_date(row.get("date")), _order_value(row, row["_index"])))
        candidates.append({
            "movement_id": movement_id,
            "name": rows[0]["_display_name"],
            "area": TREND_AREA_BY_MUSCLE_GROUP.get(rows[0].get("_muscle_group", ""), ""),
            "recent_date": _date(rows[-1].get("date")),
            "rows": rows,
        })
    candidates.sort(key=_trend_sort_key)
    selected_ids = set()
    for area in TREND_AREA_BY_MUSCLE_GROUP.values():
        representative = next((item for item in candidates if item["area"] == area), None)
        if representative:
            selected_ids.add(representative["movement_id"])
    for candidate in candidates:
        if len(selected_ids) >= MAX_TREND_MOVEMENTS:
            break
        selected_ids.add(candidate["movement_id"])
    return [candidate for candidate in candidates if candidate["movement_id"] in selected_ids]


def _max_weight(histories: list[dict]) -> str:
    kinds, weights = set(), []
    for history in histories:
        for item in history.get("sets", []) or []:
            weight_text, weight = _text(item.get("weight_text")), _number(item.get("weight"))
            if weight_text == "自重" or (not weight_text and weight == 0):
                kinds.add("bodyweight")
            elif weight is not None and weight > 0 and not weight_text:
                kinds.add("numeric")
                weights.append(weight)
            else:
                kinds.add("other")
    if kinds == {"bodyweight"}:
        return "自重"
    if kinds == {"numeric"} and weights:
        return _format_number(max(weights))
    return "不适合统一比较"


def _range_days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days + 1


def render_markdown(payload: dict) -> str:
    period = payload["range"]
    start, end = period["start"], period["end"]
    body_by_date = {_date(row.get("Date")): row for row in payload.get("body", []) if _date(row.get("Date"))}
    diet_by_date = {_date(row.get("Date")): row for row in payload.get("diet", []) if _date(row.get("Date"))}
    training_by_date = {_date(row.get("Date")): row for row in payload.get("training", []) if _date(row.get("Date"))}
    histories_by_date: dict[str, list[dict]] = defaultdict(list)
    movement_rows = []
    for movement in payload.get("movements", []):
        for index, history in enumerate(movement.get("history", [])):
            occurrence = {**history, "_display_name": _text(movement.get("display_name")) or _text(history.get("display_name")) or "未命名动作", "_index": index}
            histories_by_date[_date(history.get("date"))].append(occurrence)
            movement_rows.append({
                **occurrence,
                "_movement_id": _text(movement.get("movement_id")),
                "_muscle_group": _text(movement.get("muscle_group")),
            })

    record_dates = sorted(set(body_by_date) | set(diet_by_date) | set(training_by_date))
    training_dates = set()
    for day in record_dates:
        body, session = body_by_date.get(day, {}), training_by_date.get(day, {})
        training_text = _text(body.get("Training")) or next((_text(session.get(key)) for key in ("Split", "Standardized Summary", "Raw Record", "Notes") if _text(session.get(key))), "")
        if histories_by_date.get(day) or (training_text and not _is_non_strength_activity(training_text)):
            training_dates.add(day)
    weights = [(day, _number(row.get("Weight (kg)"))) for day, row in body_by_date.items()]
    weights = [(day, value) for day, value in weights if value is not None]
    weights.sort()
    first_window_end = min(date.fromisoformat(end), date.fromisoformat(start).fromordinal(date.fromisoformat(start).toordinal() + 6)).isoformat()
    last_window_start = max(date.fromisoformat(start), date.fromisoformat(end).fromordinal(date.fromisoformat(end).toordinal() - 6)).isoformat()
    first = [value for day, value in weights if start <= day <= first_window_end]
    last = [value for day, value in weights if last_window_start <= day <= end]
    days_count = _range_days(start, end)
    bowel_counts = defaultdict(int)
    for row in body_by_date.values():
        bowel_counts[_bowel(row.get("Bowel Movement"))] += 1

    lines = ["# Fitness Ledger 阶段分析导出", "", "## 日期范围", "", f"开始：{start}", f"结束：{end}", "", "---", "", "# 阶段汇总", "", "## 数据规模", "", f"- 记录天数：{len(record_dates)}", f"- 有体重记录天数：{len(weights)}", f"- 力量训练次数：{len(training_dates)}", f"- 休息日：{days_count - len(training_dates)}", f"- 动作记录数：{len(movement_rows)}", "", "## 体重", "", f"- 起始体重：{_format_weight(weights[0][1]) if weights else '暂无有效记录'}", f"- 结束体重：{_format_weight(weights[-1][1]) if weights else '暂无有效记录'}", f"- 直接变化：{_format_change(weights[-1][1] - weights[0][1]) if weights else '暂无有效记录'}", f"- 首7日平均体重：{_format_weight(sum(first) / len(first)) if first else '暂无有效记录'}", f"- 首7日有效记录：{len(first)}天", f"- 末7日平均体重：{_format_weight(sum(last) / len(last)) if last else '暂无有效记录'}", f"- 末7日有效记录：{len(last)}天"]
    lines.append(f"- 首末7日均值变化：{_format_change(sum(last) / len(last) - sum(first) / len(first))}" if days_count >= 14 and first and last else "- 首末7日均值变化：窗口重叠，不作阶段比较" if days_count < 14 else "- 首末7日均值变化：暂无有效记录")
    lines.extend(["", "## 平均营养摄入", ""])
    for field, label, unit in (("Calories (kcal)", "平均热量", "kcal/day"), ("Protein (g)", "平均蛋白质", "g/day"), ("Carbs (g)", "平均碳水", "g/day"), ("Fat (g)", "平均脂肪", "g/day")):
        values = [_number(row.get(field)) for row in diet_by_date.values()]
        values = [value for value in values if value is not None]
        if not values:
            lines.append(f"- {label}：暂无有效记录")
        else:
            suffix = "" if len(values) == len(record_dates) else f"（{len(values)}天有效记录）"
            lines.append(f"- {label}：{_format_number(sum(values) / len(values))} {unit}{suffix}")
    lines.extend(["", "## 排便", "", f"- 排便天数：{bowel_counts['yes']}", f"- 未排便天数：{bowel_counts['no']}", f"- 未记录天数：{bowel_counts['unrecorded']}"])
    if bowel_counts["unknown"]:
        lines.append(f"- 未归类：{bowel_counts['unknown']}天")

    lines.extend(["", "# 每日记录"])
    for day in record_dates:
        body, diet, session = body_by_date.get(day), diet_by_date.get(day), training_by_date.get(day)
        histories = sorted(histories_by_date.get(day, []), key=lambda row: _order_value(row, row["_index"]))
        lines.extend(["", f"## {day}", ""])
        if body and _number(body.get("Weight (kg)")) is not None:
            lines.append(f"weight: {_format_number(body.get('Weight (kg)'))}")
        if body and _text(body.get("Weight Notes")):
            lines.extend(["weight notes:", _text(body.get("Weight Notes"))])
        if body and _text(body.get("Bowel Movement")):
            lines.append(f"排便: {_text(body.get('Bowel Movement'))}")
        for field, label in (("Calories (kcal)", "calories"), ("Protein (g)", "protein"), ("Carbs (g)", "carbs"), ("Fat (g)", "fat")):
            if diet and _number(diet.get(field)) is not None:
                lines.append(f"{label}: {_format_number(diet.get(field))}")
        title = _text((body or {}).get("Training")) or _text((session or {}).get("Split"))
        if not title and histories:
            title = _text((session or {}).get("Standardized Summary")) or "训练"
        if title:
            lines.append(f"training: {title}")
        elif body or diet or session:
            lines.append("training: 休息")
        for history in histories:
            lines.extend([f" {history['_display_name']}", f" { _sets_text(history)}"])
            if _text(history.get("notes")):
                lines.append(f" notes: {_text(history.get('notes'))}")
            if bool(history.get("exclude_from_progress", False)):
                lines.append(" exclude_from_progress: true")
        if body and _text(body.get("Cardio")):
            lines.extend(["cardio:", _text(body.get("Cardio"))])
        scoped_notes = (
            ("daily_notes", (body or {}).get("daily_notes", (body or {}).get("Notes", ""))),
            ("diet_notes", (diet or {}).get("diet_notes", (diet or {}).get("Notes", ""))),
            ("training_notes", (session or {}).get("training_notes", (session or {}).get("Notes", ""))),
        )
        if any(key in (body or {}) or key in (diet or {}) or key in (session or {}) for key, _value in scoped_notes):
            for key, value in scoped_notes:
                cleaned = _clean_note(_text(value), {})
                if cleaned:
                    lines.append(f"{key}: {cleaned}")
        else:
            notes = _daily_notes(body, diet, session, histories)
            if notes:
                lines.extend(["notes:", *notes])

    frequent = _select_trend_movements(movement_rows)
    lines.extend([
        "", "# 高频动作趋势", "", "## 统计规则", "",
        "- 纳入训练次数不少于2次的动作。",
        "- 优先保证有有效候选动作的正式训练部位获得代表趋势，再按训练频率和最近日期补充。",
        "- 最多展示16个动作。",
        "- 最终按训练次数、最近训练日期和正式名称稳定排序。",
        "- 保留每次训练日期、动作顺序、训练数据和原始备注。",
        "- 当前没有额外训练的结构化标记，因此动作顺序按正式 order 输出，额外补充情况通过原始 notes 保留。",
    ])
    for candidate in frequent:
        name, rows = candidate["name"], candidate["rows"]
        first_row, last_row = rows[0], rows[-1]
        lines.extend(["", f"## {name}", "", f"- 训练次数：{len(rows)}", f"- 最大重量：{_max_weight(rows)}", f"- 首次记录：{_sets_text(first_row)}", f"- 最近记录：{_sets_text(last_row)}", "", "### 历史"])
        for row in rows:
            order = _number(row.get("order"))
            order_text = f"第{int(order)}个动作" if order is not None else "未记录"
            lines.extend(["", f"#### {_date(row.get('date'))}", "", f"- 当日动作顺序：{order_text}", f"- {_sets_text(row)}"])
    lines.extend(["", "# 导出说明", "", "- 每日饮食默认仅保留热量、蛋白质、碳水和脂肪汇总。", "- 不导出早餐、练前、练后、晚餐和加餐的逐项食物明细。", "- Daily、Diet、Training 和 Movement Notes 按作用域分别保留。", "- 默认不包含原始输入文本。", "- 高频动作仅包含日期范围内重复出现的动作，优先覆盖正式训练部位，最多展示16个，并保留完整训练历史。"])
    return "\n".join(lines).strip() + "\n"


def build_export(view_models, request: dict) -> dict:
    payload = view_models.analysis(start=str(request.get("start", "")), end=str(request.get("end", "")), days=int(request.get("days", 14)), include_raw_preview=bool(request.get("include_raw_preview", False)))
    return {"payload": payload, "markdown": render_markdown(payload), "json": json.dumps(payload, ensure_ascii=False, indent=2)}
