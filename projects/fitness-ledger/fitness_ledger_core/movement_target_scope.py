"""Deterministic target-body-part scope resolution for export candidates."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date

from .intelligent_export_models import BODY_PART_IDS, IntentSpec, MovementCard


MUSCLE_GROUP_TO_BODY_PART_ID = {
    "Chest": "CHEST",
    "Back": "BACK",
    "Shoulder": "SHOULDER",
    "Arms": "ARMS",
    "Core": "CORE",
    "Legs": "LEGS",
}


def body_part_id_for_muscle_group(value: str) -> str | None:
    """Map only the approved formal metadata values; never guess unknown values."""
    return MUSCLE_GROUP_TO_BODY_PART_ID.get(str(value or "").strip())


@dataclass(frozen=True)
class ResolvedMovementTargetScope:
    direct_body_part_ids: list[str] = field(default_factory=list)
    direct_movement_ids: list[str] = field(default_factory=list)
    expanded_direct_movement_ids: list[str] = field(default_factory=list)
    context_movement_ids: list[str] = field(default_factory=list)
    general_fallback_movement_ids: list[str] = field(default_factory=list)
    unresolved_movement_mentions: list[str] = field(default_factory=list)
    resolution_evidence: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def direct_target_ids(self) -> list[str]:
        return list(dict.fromkeys(self.direct_movement_ids + self.expanded_direct_movement_ids))

    def to_dict(self) -> dict:
        value = asdict(self)
        value["direct_target_ids"] = self.direct_target_ids
        return value


class MovementTargetScopeResolver:
    """Consume validated canonical targets and resolver matches without NLP."""

    def resolve(
        self,
        intent: IntentSpec,
        movement_cards: list[MovementCard],
        movement_matches: list[dict],
        available_movement_ids: set[str],
    ) -> ResolvedMovementTargetScope:
        cards = {item.movement_id: item for item in movement_cards}
        direct_body_parts = list(dict.fromkeys(getattr(intent, "target_body_part_ids", None) or getattr(intent, "target_body_parts", []) or []))
        direct_ids = list(dict.fromkeys(str(value) for value in (getattr(intent, "explicit_movement_ids", []) or [])))
        evidence = []
        mentions = list(getattr(intent, "explicit_movement_mentions", []) or [])
        legacy_mentions = list(getattr(intent, "movement_mentions", []) or [])
        if not mentions:
            mentions = [item.text if hasattr(item, "text") else str(item) for item in legacy_mentions]
        for mention in mentions:
            matches = [item for item in movement_matches if item.get("mention_text") == mention]
            best = next((item for item in matches if item.get("score", 0) >= 0.55), None)
            if best and best.get("movement_id") in cards:
                movement_id = str(best["movement_id"])
                if movement_id not in direct_ids:
                    direct_ids.append(movement_id)
                evidence.append({"source_type": "explicit_movement", "source_value": str(mention)[:80], "resolution_type": best.get("match_type", "exact"), "resolved_movement_id": movement_id, "reason_code": "EXPLICIT_MOVEMENT_MATCH"})
            else:
                evidence.append({"source_type": "explicit_movement", "source_value": str(mention)[:80], "resolution_type": "unresolved", "resolved_movement_id": "", "reason_code": "UNRESOLVED_MOVEMENT_MENTION"})
        expanded = []
        for body_part_id in direct_body_parts:
            part_cards = [item for item in movement_cards if item.body_part_id == body_part_id and item.movement_id in available_movement_ids]
            part_cards.sort(key=lambda item: self._sort_key(item, available_movement_ids))
            for card in part_cards:
                if card.movement_id not in expanded and card.movement_id not in direct_ids:
                    expanded.append(card.movement_id)
                    evidence.append({"source_type": "body_part", "source_id": body_part_id, "resolution_type": "body_part_expansion", "resolved_movement_id": card.movement_id, "reason_code": "BODY_PART_TARGET_DATA"})
            if not part_cards:
                evidence.append({"source_type": "body_part", "source_id": body_part_id, "resolution_type": "unresolved", "resolved_movement_id": "", "reason_code": "TARGET_BODY_PART_HAS_NO_DIRECT_MOVEMENT_DATA"})
        warnings = []
        if direct_body_parts and not expanded and not direct_ids:
            warnings.append("TARGET_BODY_PART_HAS_NO_DIRECT_MOVEMENT_DATA")
        unresolved = list(getattr(intent, "unresolved_movement_mentions", []) or [])
        unresolved.extend(mention for mention in mentions if mention not in {item.get("source_value") for item in evidence if item.get("resolved_movement_id")})
        unresolved = list(dict.fromkeys(unresolved))
        return ResolvedMovementTargetScope(direct_body_parts, direct_ids, expanded, [], [], unresolved, evidence, warnings)

    @staticmethod
    def _sort_key(card: MovementCard, available_ids: set[str]) -> tuple:
        try:
            latest = date.fromisoformat(str(card.latest_valid_progress_date or "")[:10]).toordinal()
        except ValueError:
            latest = 0
        return (-int(card.progress_history_count > 0), -latest, -card.progress_history_count, -card.history_count, card.movement_id)
