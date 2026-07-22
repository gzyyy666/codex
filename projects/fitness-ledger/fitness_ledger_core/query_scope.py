"""Deterministic request scope resolution for Intelligent Export.

This module deliberately resolves only closed entities (dates, body parts and
dictionary movements).  Value selection remains the responsibility of the
single Planning model call.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .data_catalog import DateRangeResolver, MovementResolver, _normalize
from .intelligent_export_models import DateIntent, MovementCard, stable_hash


BODY_PART_TERMS = {
    "CHEST": ("胸部", "胸肌", "胸"),
    "BACK": ("背部", "背肌", "背"),
    "SHOULDER": ("三角肌", "肩膀", "肩部", "前束", "中束", "后束", "肩"),
    "ARMS": ("肱二头", "肱三头", "二头肌", "三头肌", "手臂", "二头", "三头", "臂"),
    "CORE": ("腹部", "腹肌", "核心", "腹"),
    "LEGS": ("股四头", "腘绳肌", "腿部", "下肢", "腘绳", "股四", "腿"),
}


@dataclass(frozen=True)
class QueryScope:
    original_request: str
    date_request: DateIntent
    target_body_part_ids: list[str] = field(default_factory=list)
    explicit_movement_ids: list[str] = field(default_factory=list)
    explicit_movement_mentions: list[str] = field(default_factory=list)
    unresolved_movement_mentions: list[str] = field(default_factory=list)
    scope_warning_codes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "original_request": self.original_request,
            "date_request": {
                "mode": self.date_request.mode,
                "relative_range": self.date_request.relative_range,
                "raw_date_mentions": list(self.date_request.raw_date_mentions),
            },
            "target_body_part_ids": list(self.target_body_part_ids),
            "explicit_movement_ids": list(self.explicit_movement_ids),
            "explicit_movement_mentions": list(self.explicit_movement_mentions),
            "unresolved_movement_mentions": list(self.unresolved_movement_mentions),
            "scope_warning_codes": list(self.scope_warning_codes),
        }

    @property
    def movement_mentions(self) -> list:
        """Compatibility view for old candidate/diagnostic consumers."""
        from .intelligent_export_models import MovementMention
        return [MovementMention(text, 1.0) for text in self.explicit_movement_mentions]

    @property
    def target_body_parts(self) -> list[str]:
        return list(self.target_body_part_ids)

    @property
    def catalog_requirements(self) -> list[str]:
        return []


class QueryScopeResolver:
    def __init__(self, catalog=None, views=None) -> None:
        self.catalog = catalog
        self.views = views

    def resolve(self, request: str, catalog=None) -> QueryScope:
        catalog = catalog or self.catalog
        text = str(request or "").strip()
        date_mentions = DateRangeResolver.extract_raw_date_mentions(text)
        relative = DateRangeResolver.infer_relative_range(text)
        if date_mentions:
            date_request = DateIntent("explicit", None, False, date_mentions)
        elif relative == "all_available":
            date_request = DateIntent("all_available", "all_available", False, [])
        elif relative:
            date_request = DateIntent("relative", relative, False, [])
        else:
            date_request = DateIntent("unspecified", None, False, [])

        cards = list(getattr(catalog, "movements", []) or [])
        explicit, consumed, unresolved = self._resolve_movements(text, cards)
        body_parts = self._resolve_body_parts(text, consumed)
        warnings = []
        if unresolved:
            warnings.append("UNRESOLVED_MOVEMENT_MENTION")
        return QueryScope(
            original_request=text,
            date_request=date_request,
            target_body_part_ids=body_parts,
            explicit_movement_ids=[item["movement_id"] for item in explicit],
            explicit_movement_mentions=[item["mention"] for item in explicit],
            unresolved_movement_mentions=unresolved,
            scope_warning_codes=warnings,
        )

    @staticmethod
    def _resolve_movements(text: str, cards: list[MovementCard]):
        normalized = _normalize(text)
        candidates = []
        for card in cards:
            terms = [card.canonical_name, *card.aliases]
            for term in terms:
                value = _normalize(term)
                body_term_values = {_normalize(item) for values in BODY_PART_TERMS.values() for item in values}
                if not value or value in body_term_values:
                    continue
                start = normalized.find(value)
                while start >= 0:
                    candidates.append({"start": start, "end": start + len(value), "term": term, "value": value, "movement_id": card.movement_id, "canonical": card.canonical_name, "exact": value == _normalize(card.canonical_name)})
                    start = normalized.find(value, start + 1)
        # Longest span first, then canonical before alias and stable ID.
        candidates.sort(key=lambda item: (-(item["end"] - item["start"]), -int(item["exact"]), item["movement_id"], item["term"]))
        chosen = []
        for item in candidates:
            if any(item["start"] < other["end"] and other["start"] < item["end"] for other in chosen):
                continue
            same_span = [candidate for candidate in candidates if candidate["start"] == item["start"] and candidate["end"] == item["end"]]
            ids = {candidate["movement_id"] for candidate in same_span}
            if len(ids) > 1:
                # Ambiguous exact/partial span is retained as unresolved, not guessed.
                continue
            chosen.append(item)
        explicit = []
        for item in sorted(chosen, key=lambda value: value["start"]):
            if item["movement_id"] not in {entry["movement_id"] for entry in explicit}:
                explicit.append({"movement_id": item["movement_id"], "mention": item["term"], "start": item["start"], "end": item["end"]})

        unresolved = []
        # Short, unambiguous exercise-like phrases that look like a movement
        # but did not resolve are surfaced only when explicitly introduced.
        for match in re.finditer(r"动作[:：]\s*([\u4e00-\u9fffA-Za-z0-9]{2,20})", text):
            phrase = match.group(1).strip()
            if phrase and not any(_normalize(phrase) == _normalize(item["mention"]) for item in explicit):
                unresolved.append(phrase)
        return explicit, chosen, list(dict.fromkeys(unresolved))

    @staticmethod
    def _resolve_body_parts(text: str, consumed: list[dict]) -> list[str]:
        normalized = _normalize(text)
        parts = []
        for body_part, terms in BODY_PART_TERMS.items():
            for term in sorted(terms, key=len, reverse=True):
                value = _normalize(term)
                start = normalized.find(value)
                while start >= 0:
                    end = start + len(value)
                    if not any(start < item["end"] and item["start"] < end for item in consumed):
                        parts.append((start, -len(value), body_part))
                    start = normalized.find(value, start + 1)
        # A stable left-to-right/longest order prevents duplicate aliases.
        result = []
        for _start, _length, body_part in sorted(parts):
            if body_part not in result:
                result.append(body_part)
        return result
