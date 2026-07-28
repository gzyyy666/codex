"""Deterministic semantic-integrity checks for schema-valid Intent objects."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from .intelligent_export_models import BODY_PART_IDS, SEMANTIC_HINT_DIMENSIONS, SemanticHints


_PLACEHOLDERS = {"?", "??", "???", "unknown", "n/a", "na", "none", "null", "placeholder"}
_QUESTION_MARKS = {"?", "？"}
_HINT_TERMS = {
    "body_state": ("体重", "体脂", "身体", "身材", "体型", "减脂", "减重", "weight", "body"),
    "diet_macros": ("饮食", "低碳", "碳水", "热量", "卡路里", "蛋白", "脂肪", "宏量", "摄入", "diet", "macro", "carb", "calorie", "intake"),
    "training_context": ("训练", "锻炼", "健身", "训练状态", "training", "workout", "performance", "表现", "影响", "受影响", "导致"),
    "movement_progress": ("进步", "增长", "下降", "表现", "动作", "movement", "progress", "bench press"),
}
_GENERIC_HINTS = {"最近", "近期", "情况", "看看", "怎么样", "分析", "变化", "最近的情况", "recent", "lately"}


def _meaningful_chars(value: str) -> list[str]:
    return [char for char in str(value or "") if unicodedata.category(char).startswith(("L", "N"))]


def _safe_summary(value: Any) -> dict:
    text = value if isinstance(value, str) else str(value or "")
    meaningful = _meaningful_chars(text)
    question_count = sum(text.count(mark) for mark in _QUESTION_MARKS)
    replacement_count = text.count("\ufffd")
    classes = sorted({unicodedata.category(char)[0] for char in text if char and char not in _QUESTION_MARKS})
    return {
        "length": len(text),
        "meaningful_character_count": len(meaningful),
        "question_mark_count": question_count,
        "replacement_character_count": replacement_count,
        "character_class_summary": classes,
    }


def _field_invalid(value: Any, minimum: int = 1) -> tuple[bool, list[str]]:
    if not isinstance(value, str):
        return True, ["INTENT_PLACEHOLDER_ONLY"]
    text = value.strip()
    summary = _safe_summary(text)
    if summary["replacement_character_count"]:
        return True, ["INTENT_REPLACEMENT_CHARACTER"]
    lowered = re.sub(r"\s+", "", text).lower()
    if not lowered or lowered in _PLACEHOLDERS or summary["meaningful_character_count"] < minimum:
        return True, ["INTENT_GOAL_EMPTY" if not lowered else "INTENT_PLACEHOLDER_ONLY"]
    if summary["question_mark_count"] >= 2 and summary["meaningful_character_count"] == 0:
        return True, ["INTENT_PLACEHOLDER_ONLY"]
    if all(unicodedata.category(char).startswith("P") or char.isspace() for char in text):
        return True, ["INTENT_PLACEHOLDER_ONLY"]
    return False, []


@dataclass(frozen=True)
class IntentSemanticValidationResult:
    is_valid: bool
    error_codes: list[str]
    invalid_field_paths: list[str]
    diagnostics: dict[str, dict]

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "error_codes": list(self.error_codes),
            "invalid_field_paths": list(self.invalid_field_paths),
            "diagnostics": dict(self.diagnostics),
        }


class IntentSemanticValidator:
    """Reject only deterministic placeholder/corruption patterns."""

    def validate(self, intent: Any) -> IntentSemanticValidationResult:
        value = intent.to_dict() if hasattr(intent, "to_dict") else dict(intent or {})
        errors: list[str] = []
        paths: list[str] = []
        diagnostics: dict[str, dict] = {}

        dimensions = value.get("dimensions", []) or []
        for index, item in enumerate(dimensions):
            invalid, codes = _field_invalid(item, minimum=1)
            diagnostics[f"dimensions[{index}]"] = _safe_summary(item)
            if invalid:
                paths.append(f"dimensions[{index}]")
                errors.extend("INTENT_DIMENSION_CORRUPTED" if code not in {"INTENT_REPLACEMENT_CHARACTER"} else code for code in codes)

        excluded = value.get("excluded_dimensions", []) or []
        if not isinstance(excluded, list) or set(dimensions).intersection(excluded):
            paths.append("excluded_dimensions")
            errors.append("INTENT_SCOPE_CONFLICT")

        target_parts = value.get("target_body_parts", [])
        diagnostics["target_body_parts"] = {"length": len(target_parts) if isinstance(target_parts, list) else 0, "values": [str(item) for item in target_parts] if isinstance(target_parts, list) else []}
        if not isinstance(target_parts, list) or len(target_parts) != len(set(target_parts)) or any(item not in BODY_PART_IDS for item in target_parts):
            paths.append("target_body_parts")
            errors.append("INTENT_TARGET_BODY_PART_INVALID")

        mentions = value.get("movement_mentions", []) or []
        for index, item in enumerate(mentions):
            text = item if isinstance(item, str) else ""
            invalid, codes = _field_invalid(text, minimum=1)
            diagnostics[f"movement_mentions[{index}]"] = _safe_summary(text)
            if invalid:
                paths.append(f"movement_mentions[{index}]")
                errors.extend("INTENT_MOVEMENT_MENTION_CORRUPTED" if code not in {"INTENT_REPLACEMENT_CHARACTER"} else code for code in codes)

        raw_mentions = value.get("date_text", []) or []
        for index, item in enumerate(raw_mentions):
            invalid, codes = _field_invalid(item, minimum=1)
            diagnostics[f"date_text[{index}]"] = _safe_summary(item)
            if invalid:
                paths.append(f"date_text[{index}]")
                errors.extend("INTENT_DATE_MENTION_CORRUPTED" if code not in {"INTENT_REPLACEMENT_CHARACTER"} else code for code in codes)

        return IntentSemanticValidationResult(not errors, sorted(set(errors)), sorted(set(paths)), diagnostics)


@dataclass(frozen=True)
class GroundingValidationResult:
    hints: SemanticHints
    rejected: list[dict]

    def to_dict(self) -> dict:
        return {"hints": self.hints.to_dict(), "rejected": list(self.rejected)}


class GroundingValidator:
    """Keep only model hints grounded in the original request and closed facts."""

    @staticmethod
    def validate(hints: SemanticHints, request: str, context: dict | None = None) -> GroundingValidationResult:
        text = str(request or "")
        context = dict(context or {})
        excluded = set(context.get("excluded_dimensions", []))
        only = set(context.get("only_dimensions", []))
        movement_unique = bool(context.get("movement_unique", False))
        accepted = []
        rejected = []
        for item in hints.hints:
            evidence = item.evidence.strip()
            lowered = re.sub(r"\s+", "", evidence).casefold()
            code = ""
            if not evidence or evidence not in text:
                code = "HINT_EVIDENCE_NOT_IN_REQUEST"
            elif lowered in {re.sub(r"\s+", "", value).casefold() for value in _GENERIC_HINTS}:
                code = "HINT_GENERIC_EVIDENCE"
            elif item.dimension in excluded:
                code = "HINT_EXCLUDED_DIMENSION"
            elif only and item.dimension not in only:
                code = "HINT_OUTSIDE_ONLY_SCOPE"
            elif item.dimension == "movement_progress" and not movement_unique:
                code = "HINT_MOVEMENT_NOT_UNIQUE"
            elif item.dimension in SEMANTIC_HINT_DIMENSIONS and not any(term.casefold() in evidence.casefold() for term in _HINT_TERMS[item.dimension]):
                code = "HINT_DIMENSION_EVIDENCE_MISMATCH"
            if code:
                rejected.append({"dimension": item.dimension, "evidence": evidence[:120], "code": code})
            else:
                accepted.append(item)
        return GroundingValidationResult(SemanticHints(accepted), rejected)


def _snapshot(value: Any) -> dict:
    text = value if isinstance(value, str) else str(value or "")
    summary = _safe_summary(text)
    return {
        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "length": summary["length"],
        "meaningful_character_count": summary["meaningful_character_count"],
    }


def repair_diff(before: dict, after: dict, semantic_codes_before: list[str] | None = None, semantic_codes_after: list[str] | None = None, schema_failed: bool = False) -> dict:
    """Return a safe, text-free diff for Intent repair evidence."""
    paths = ["interpreted_goal", "target_body_parts"]
    paths += [f"analysis_dimensions[{i}]" for i in range(max(len(before.get("analysis_dimensions", [])), len(after.get("analysis_dimensions", []))))]
    paths += [f"movement_mentions[{i}].text" for i in range(max(len(before.get("movement_mentions", [])), len(after.get("movement_mentions", []))))]
    paths += [f"date_intent.raw_date_mentions[{i}]" for i in range(max(len((before.get("date_intent") or {}).get("raw_date_mentions", [])), len((after.get("date_intent") or {}).get("raw_date_mentions", []))))]

    def get(value: dict, path: str) -> Any:
        if path == "interpreted_goal":
            return value.get(path, "")
        if path == "target_body_parts":
            return value.get(path, [])
        match = re.match(r"(.+?)\[(\d+)\](?:\.text)?$", path)
        if not match:
            return ""
        arr = (value.get("date_intent", {}) or {}).get("raw_date_mentions", []) if match.group(1) == "date_intent.raw_date_mentions" else value.get(match.group(1), [])
        index = int(match.group(2))
        item = arr[index] if index < len(arr) else ""
        return item.get("text", "") if isinstance(item, dict) else item

    changed = []
    snapshots = {}
    for path in paths:
        old, new = get(before, path), get(after, path)
        if old != new:
            changed.append(path)
            snapshots[path] = {"before": _snapshot(old), "after": _snapshot(new)}
    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    before_codes = list(semantic_codes_before or [])
    after_codes = list(semantic_codes_after or [])
    reason = "schema_and_semantic" if schema_failed and before_codes else ("semantic" if before_codes else "schema")
    return {"repair_reason": reason, "changed_field_paths": changed, "fields_added": added, "fields_removed": removed,
            "semantic_codes_before": before_codes, "semantic_codes_after": after_codes, "field_snapshots": snapshots}
