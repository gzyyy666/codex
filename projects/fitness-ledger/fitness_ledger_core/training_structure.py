"""Small, deterministic helpers for complex sets and Session organization.

The module deliberately does not model an advanced training engine.  It keeps
legacy scalar set rows intact and adds only the two facts needed by this task:
ordered segments inside one set and explicit Session-level superset members.
"""
from __future__ import annotations

import re
from typing import Any


class TrainingStructureError(ValueError):
    def __init__(self, message: str, code: str = "INVALID_TRAINING_STRUCTURE"):
        super().__init__(message)
        self.code = code


_NUMBER = r"\d+(?:\.\d+)?"
_LOAD = rf"(?:自重|body\s*weight|bw|{_NUMBER})(?:\s*(?:kg|公斤|千克))?"
_SEGMENT = re.compile(rf"(?P<weight>{_LOAD})\s*[x×*]\s*(?P<reps>\d+)", re.I)
_COMPACT = re.compile(
    rf"\((?P<weights>[^()]+)\)\s*[-–]\s*\((?P<reps>[^()]+)\)\s*[-–]\s*(?P<sets>\d+)",
    re.I,
)
_UNEQUAL = re.compile(r"(?:^|\n)\s*sets\s*[:：]\s*(?P<body>[^\n]+)", re.I)
_SUPERSET = re.compile(
    r"^\s*superset\s*[:：]\s*(?P<label>[A-Za-z0-9_-]+)\s*=\s*(?P<members>.+?)\s*$",
    re.I,
)


def _weight(value: str) -> dict[str, Any]:
    text = str(value).strip()
    if re.fullmatch(rf"{_NUMBER}", text):
        return {"weight": float(text)}
    return {"weight": 0.0, "weight_text": "自重"}


def _segments_from_pairs(text: str) -> list[dict[str, Any]]:
    matches = list(_SEGMENT.finditer(str(text).replace("－", "-")))
    compact = re.sub(r"\s+", "", str(text))
    if not re.fullmatch(rf"{_LOAD}[x×*]\d+(?:\+{_LOAD}[x×*]\d+)+", compact, re.I):
        raise TrainingStructureError("complex set 必须是多个明确的 weight x reps，并使用 + 连接。", "SEGMENT_PARSE_FAILED")
    if not matches:
        raise TrainingStructureError("每个 complex set 必须包含至少两个 weight x reps segment。", "SEGMENT_PARSE_FAILED")
    if len(matches) < 2 or "+" not in compact:
        raise TrainingStructureError("complex set segment 必须使用 + 明确连接。", "SEGMENT_MARKER_REQUIRED")
    segments = []
    for match in matches:
        item = _weight(match.group("weight"))
        item["reps"] = int(match.group("reps"))
        segments.append(item)
    return segments


def parse_segmented_blocks(text: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Return segmented set rows and deterministic parse issues.

    Compact rows preserve the existing repetition count in ``sets``.  The
    explicit ``sets: a; b; c`` form creates one row per unequal set.
    """
    value = str(text or "")
    blocks: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for match in _COMPACT.finditer(value):
        weights = [part.strip() for part in match.group("weights").split("+")]
        reps = [part.strip() for part in match.group("reps").split("+")]
        if len(weights) != len(reps):
            issues.append({"code": "SEGMENT_COUNT_MISMATCH", "message": "复杂组的重量段数量必须与次数段数量一致。"})
            continue
        try:
            segments = []
            for weight, repetition in zip(weights, reps):
                if not re.fullmatch(_NUMBER, weight) or not repetition.isdigit():
                    raise TrainingStructureError("复杂组只接受确定的数字重量与次数。", "SEGMENT_PARSE_FAILED")
                segments.append({"weight": float(weight), "reps": int(repetition)})
            if len(segments) < 2:
                raise TrainingStructureError("复杂组至少需要两个 segment。", "SEGMENT_MARKER_REQUIRED")
            blocks.append({"segments": segments, "sets": int(match.group("sets"))})
        except TrainingStructureError as exc:
            issues.append({"code": exc.code, "message": str(exc)})
    for match in _UNEQUAL.finditer(value):
        rows = [row.strip() for row in re.split(r"[;；|｜]", match.group("body")) if row.strip()]
        if not rows:
            issues.append({"code": "SEGMENT_PARSE_FAILED", "message": "逐组 complex set 不能为空。"})
            continue
        for row in rows:
            try:
                blocks.append({"segments": _segments_from_pairs(row), "sets": 1})
            except TrainingStructureError as exc:
                issues.append({"code": exc.code, "message": str(exc)})
    return blocks, issues


def has_segmented_syntax(text: str) -> bool:
    value = str(text or "")
    return bool(_COMPACT.search(value) or _UNEQUAL.search(value) or re.search(r"\([^()]+\)\s*[-–]\s*\([^()]+\)", value))


def set_volume(item: dict[str, Any]) -> float:
    segments = item.get("segments")
    if isinstance(segments, list) and segments:
        count = float(item.get("sets") or 1)
        return sum(float(segment.get("weight") or 0) * int(segment.get("reps") or 0) for segment in segments) * count
    try:
        return float(item.get("weight") or 0) * int(item.get("reps") or 0) * int(item.get("sets") or 0)
    except (TypeError, ValueError):
        return 0.0


def set_total_reps(item: dict[str, Any]) -> int:
    segments = item.get("segments")
    if isinstance(segments, list) and segments:
        return sum(int(segment.get("reps") or 0) for segment in segments) * int(item.get("sets") or 1)
    try:
        return int(item.get("reps") or 0) * int(item.get("sets") or 0)
    except (TypeError, ValueError):
        return 0


def format_set_item(item: dict[str, Any], *, group_suffix: bool = True) -> str:
    segments = item.get("segments")
    if isinstance(segments, list) and segments:
        parts = []
        for segment in segments:
            weight = segment.get("weight_text") or (f"{segment.get('weight'):g}kg" if segment.get("weight") not in (None, "") else "自重")
            parts.append(f"{weight} × {segment.get('reps', '-')}")
        result = " + ".join(parts)
        count = int(item.get("sets") or 1)
        return f"{result} × {count}组" if group_suffix and count != 1 else result
    weight = item.get("weight_text") or (f"{item.get('weight'):g}kg" if item.get("weight") not in (None, "") else "自重")
    return f"{weight} × {item.get('reps', '-')} × {item.get('sets', '-')}"


def parse_superset_directives(text: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    directives: list[dict[str, Any]] = []
    issues: list[dict[str, str]] = []
    for line in str(text or "").splitlines():
        if not line.strip().lower().startswith("superset"):
            continue
        match = _SUPERSET.match(line)
        if not match:
            issues.append({"code": "SUPERSET_SYNTAX_INVALID", "message": "超级组必须使用 superset: A = movement 1, movement 2 格式。"})
            continue
        members = []
        for token in match.group("members").split(","):
            member = re.fullmatch(r"\s*movement\s+(\d+)\s*", token, re.I)
            if not member:
                issues.append({"code": "SUPERSET_MEMBER_INVALID", "message": "超级组成员必须明确写为 movement N。"})
                members = []
                break
            members.append(int(member.group(1)))
        if len(members) < 2 or len(set(members)) != len(members):
            issues.append({"code": "SUPERSET_MEMBER_COUNT_INVALID", "message": "一个超级组至少需要两个不同的 movement。"})
            continue
        directives.append({"label": match.group("label"), "orders": members})
    return directives, issues


def relation_specs(directives: list[dict[str, Any]], movement_items: list[dict[str, Any]], session_id: str) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    by_order: dict[int, dict[str, Any]] = {}
    duplicate_orders: set[int] = set()
    for item in movement_items:
        if not str(item.get("order", "")).isdigit():
            continue
        order = int(item["order"])
        if order in by_order:
            duplicate_orders.add(order)
        by_order[order] = item
    relations, issues = [], []
    labels: set[str] = set()
    for directive in directives:
        label = str(directive.get("label", "")).strip()
        if label in labels:
            issues.append({"code": "SUPERSET_LABEL_DUPLICATE", "message": f"超级组标签 {label} 重复。"})
            continue
        labels.add(label)
        if any(order in duplicate_orders for order in directive.get("orders", [])):
            issues.append({"code": "SUPERSET_MEMBER_AMBIGUOUS", "message": f"超级组 {label} 的 movement 序号不唯一。"})
            continue
        members = [by_order.get(order) for order in directive.get("orders", [])]
        if any(item is None for item in members):
            issues.append({"code": "SUPERSET_MEMBER_NOT_FOUND", "message": f"超级组 {directive.get('label')} 的 movement 成员无法对应本次 Session。"})
            continue
        refs = [str(item.get("movement_instance_id") or item.get("id") or "") for item in members]
        if not all(refs):
            issues.append({"code": "SUPERSET_MEMBER_ID_MISSING", "message": "超级组成员缺少 movement instance identity。"})
            continue
        relations.append({"id": f"superset:{session_id}:{directive.get('label')}", "type": "superset", "label": str(directive.get("label")), "members": refs})
    return relations, issues


def relation_for_item(session: dict[str, Any], item_id: str) -> list[dict[str, Any]]:
    result = []
    for relation in session.get("organization_relations", []) or []:
        if isinstance(relation, dict) and item_id in [str(value) for value in relation.get("members", []) or []]:
            result.append(relation)
    return result


__all__ = [
    "TrainingStructureError", "parse_segmented_blocks", "has_segmented_syntax",
    "set_volume", "set_total_reps", "format_set_item", "parse_superset_directives",
    "relation_specs", "relation_for_item",
]
