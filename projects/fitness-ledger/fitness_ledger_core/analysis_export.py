from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import date


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


def _daily_notes(body: dict | None, diet: dict | None, training: dict | None) -> list[str]:
    values = [("身体", _text((body or {}).get("Notes"))), ("饮食", _text((diet or {}).get("Notes"))), ("训练", _text((training or {}).get("Notes")))]
    nonempty = [(label, value) for label, value in values if value]
    if not nonempty:
        return []
    unique = {value for _label, value in nonempty}
    if len(unique) == 1:
        return [nonempty[0][1]]
    return [f"- {label}：{value}" for label, value in nonempty]


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
            movement_rows.append({**occurrence, "_movement_id": _text(movement.get("movement_id"))})

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
        if body and _text(body.get("Cardio")):
            lines.extend(["cardio:", _text(body.get("Cardio"))])
        notes = _daily_notes(body, diet, session)
        if notes:
            lines.extend(["notes:", *notes])

    grouped = defaultdict(list)
    for row in movement_rows:
        if row["_movement_id"]:
            grouped[row["_movement_id"]].append(row)
    frequent = []
    for movement_id, rows in grouped.items():
        if len(rows) >= 2:
            rows.sort(key=lambda row: (_date(row.get("date")), _order_value(row, row["_index"])))
            frequent.append((rows[0]["_display_name"], rows))
    frequent.sort(key=lambda item: (-len(item[1]), -date.fromisoformat(_date(item[1][-1].get("date"))).toordinal(), item[0]))
    lines.extend(["", "# 高频动作趋势", "", "## 统计规则", "", "- 纳入训练次数不少于2次的动作。", "- 最多展示训练频率最高的12个动作。", "- 按训练次数从高到低排列。", "- 同频时，最近训练日期较新的动作优先。", "- 保留每次训练日期、动作顺序、训练数据和原始备注。", "- 当前没有额外训练的结构化标记，因此动作顺序按正式 order 输出，额外补充情况通过原始 notes 保留。"])
    for name, rows in frequent[:12]:
        first_row, last_row = rows[0], rows[-1]
        lines.extend(["", f"## {name}", "", f"- 训练次数：{len(rows)}", f"- 最大重量：{_max_weight(rows)}", f"- 首次记录：{_sets_text(first_row)}", f"- 最近记录：{_sets_text(last_row)}", "", "### 历史"])
        for row in rows:
            order = _number(row.get("order"))
            order_text = f"第{int(order)}个动作" if order is not None else "未记录"
            lines.extend(["", f"#### {_date(row.get('date'))}", "", f"- 当日动作顺序：{order_text}", f"- {_sets_text(row)}"])
            if _text(row.get("notes")):
                lines.append(f"- notes: {_text(row.get('notes'))}")
    lines.extend(["", "# 导出说明", "", "- 每日饮食默认仅保留热量、蛋白质、碳水和脂肪汇总。", "- 不导出早餐、练前、练后、晚餐和加餐的逐项食物明细。", "- 特殊饮食情况通过每日 notes 保留。", "- 默认不包含原始输入文本。", "- 高频动作仅包含日期范围内重复出现的动作，并保留完整训练历史。"])
    return "\n".join(lines).strip() + "\n"


def build_export(view_models, request: dict) -> dict:
    payload = view_models.analysis(start=str(request.get("start", "")), end=str(request.get("end", "")), days=int(request.get("days", 14)), include_raw_preview=bool(request.get("include_raw_preview", False)))
    return {"payload": payload, "markdown": render_markdown(payload), "json": json.dumps(payload, ensure_ascii=False, indent=2)}
