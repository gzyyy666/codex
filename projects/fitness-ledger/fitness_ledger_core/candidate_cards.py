"""Candidate recall and compression for the intelligent export planner."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date

from .data_catalog import MovementResolver, resolve_windows
from .intelligent_export_models import CandidateRecordCard, CandidateWindow, DataCatalog, IntentSpec, ModuleCard, MovementCard, NotesCard, stable_hash
from .movement_target_scope import MovementTargetScopeResolver, ResolvedMovementTargetScope


@dataclass(frozen=True)
class CandidatePackage:
    catalog_id: str
    source_snapshot_id: str
    windows: list[CandidateWindow]
    modules: list[ModuleCard]
    movements: list[MovementCard]
    notes: list[NotesCard]
    candidate_records: list[CandidateRecordCard]
    allowed_modules: list[str]
    allowed_fields: dict[str, list[str]]
    allowed_ids: dict[str, list[str]]
    movement_matches: list[dict]
    target_scope: ResolvedMovementTargetScope
    movement_roles: dict[str, str]
    budget_mode: str
    budget: dict

    def to_prompt_dict(self) -> dict:
        return {
            "catalog_id": self.catalog_id,
            "source_snapshot_id": self.source_snapshot_id,
            "windows": [item.to_dict() for item in self.windows],
            "modules": [item.to_dict() for item in self.modules],
            "movements": [item.to_dict() for item in self.movements],
            "notes": [item.to_dict() for item in self.notes],
            "candidate_records": [item.to_dict() for item in self.candidate_records],
            "allowed_modules": self.allowed_modules,
            "allowed_fields": self.allowed_fields,
            "allowed_ids": self.allowed_ids,
            "movement_matches": self.movement_matches,
            "target_scope": self.target_scope.to_dict(),
            "movement_roles": dict(self.movement_roles),
            "budget_mode": self.budget_mode,
            "budget": self.budget,
        }

    def to_planning_prompt_dict(self) -> dict:
        """Compact, selection-only view; IDs remain separately enumerable."""
        return {
            "windows": [{"window_id": w.window_id, "requested_start": w.requested_start, "requested_end": w.requested_end, "resolved_start": w.resolved_start, "resolved_end": w.resolved_end, "anchor": w.anchor, "modules": w.modules, "missing_data_warnings": w.missing_data_warnings} for w in self.windows],
            "modules": [{"module_id": m.module_id, "available": m.available, "record_count": m.record_count, "fields": sorted(m.field_coverage)} for m in self.modules],
            "movements": [{"movement_id": m.movement_id, "canonical_name": m.canonical_name, "body_part": m.body_part, "body_part_id": m.body_part_id, "candidate_role": self.movement_roles.get(m.movement_id, "GENERAL_FALLBACK"), "progress_history_count": m.progress_history_count, "excluded_history_count": m.excluded_history_count, "latest_valid_progress_date": m.latest_valid_progress_date} for m in self.movements],
            "notes": [{"note_candidate_id": n.note_candidate_id, "date": n.date, "note_type": n.note_type, "scope": n.scope, "movement_id": n.movement_id} for n in self.notes],
            "candidate_records": [{"candidate_record_id": r.candidate_record_id, "module_id": r.module_id, "date": r.date, "record_kind": r.record_kind, "flags": r.flags, "related_movement_ids": r.related_movement_ids} for r in self.candidate_records],
            "movement_matches": self.movement_matches[:12],
            "target_scope": self.target_scope.to_dict(),
        }


BUDGETS = {
    "concise": {"records": 250, "movements": 3, "notes": 12, "raw": 0, "output_bytes": 80_000},
    "standard": {"records": 800, "movements": 6, "notes": 30, "raw": 20, "output_bytes": 250_000},
    "complete": {"records": 2500, "movements": 12, "notes": 60, "raw": 60, "output_bytes": 1_000_000},
}


def _terms(value: str) -> set[str]:
    return {item for item in re.findall(r"[\u4e00-\u9fff]{2,}|[a-zA-Z]{3,}", str(value or "").lower()) if item}


class CandidateSummarizer:
    def __init__(self, catalog: DataCatalog, resolver: MovementResolver) -> None:
        self.catalog = catalog
        self.resolver = resolver

    def build(self, request: str, intent: IntentSpec, budget_mode: str = "standard") -> CandidatePackage:
        budget = dict(BUDGETS.get(budget_mode, BUDGETS["standard"]))
        windows = resolve_windows(self.catalog, intent, request)
        window = windows[0] if windows else None
        data_window = windows[-1] if windows else None
        start, end = (data_window.resolved_start, data_window.resolved_end) if data_window else ("", "")
        in_range = lambda value: bool(value) and (not start or start <= value <= end)
        movement_matches = []
        for mention_index, mention in enumerate(intent.movement_mentions):
            matches = self.resolver.resolve(mention, self.catalog.movements)
            movement_matches.extend({**item, "mention_text": mention.text, "mention_index": mention_index} for item in matches[:4])
            # Recall a small, explainable candidate set even when the match is
            # not decisive; the Planning model and validator decide whether
            # an ambiguous mention is useful, never the resolver alone.
        window_ids = {item.candidate_record_id for item in self.catalog.candidate_records if in_range(item.date)}
        available_movement_ids = {movement_id for item in self.catalog.candidate_records if item.candidate_record_id in window_ids for movement_id in item.related_movement_ids}
        target_scope = MovementTargetScopeResolver().resolve(intent, self.catalog.movements, movement_matches, available_movement_ids)
        direct_ids = set(target_scope.direct_target_ids)
        all_sorted = sorted(self.catalog.movements, key=lambda item: self._target_sort_key(item, available_movement_ids))
        if direct_ids:
            direct_order = [item for item in all_sorted if item.movement_id in direct_ids]
            context_order = [item for item in all_sorted if item.movement_id not in direct_ids]
            movements = (direct_order + context_order)[:budget["movements"]]
            context_ids = [item.movement_id for item in movements if item.movement_id not in direct_ids]
            target_scope = ResolvedMovementTargetScope(target_scope.direct_body_part_ids, target_scope.direct_movement_ids, target_scope.expanded_direct_movement_ids, context_ids, [], target_scope.unresolved_movement_mentions, target_scope.resolution_evidence, target_scope.warnings)
        else:
            movements = all_sorted[:budget["movements"]]
            fallback_ids = [item.movement_id for item in movements]
            target_scope = ResolvedMovementTargetScope(target_scope.direct_body_part_ids, target_scope.direct_movement_ids, target_scope.expanded_direct_movement_ids, [], fallback_ids, target_scope.unresolved_movement_mentions, target_scope.resolution_evidence, target_scope.warnings)
        movement_ids = {item.movement_id for item in movements}
        roles = {item.movement_id: ("EXPLICIT_TARGET" if item.movement_id in target_scope.direct_movement_ids else "BODY_PART_TARGET" if item.movement_id in target_scope.expanded_direct_movement_ids else "CONTEXT" if item.movement_id in target_scope.context_movement_ids else "GENERAL_FALLBACK") for item in movements}
        modules = [item for item in self.catalog.modules if item.module_id in set(intent.catalog_requirements) or not intent.catalog_requirements]
        if not modules:
            modules = list(self.catalog.modules)
        records = [item for item in self.catalog.candidate_records if in_range(item.date) and (item.module_id != "movement_history" or not movement_ids or next((mid for mid in item.related_movement_ids if mid in movement_ids), None))]
        # Keep the planning prompt comfortably below the configured context
        # window.  The executor still reads the complete local projection
        # after validation; this cap only limits model-visible candidates.
        prompt_record_cap = {"concise": 12, "standard": 24, "complete": 48}.get(budget_mode, 24)
        records = records[: min(budget["records"], prompt_record_cap)]
        keywords = _terms(request)
        notes = [item for item in self.catalog.notes if in_range(item.date) and (not movement_ids or not item.movement_id or item.movement_id in movement_ids)]
        if keywords:
            notes.sort(key=lambda item: (not bool(keywords & _terms(item.short_fragment)), -item.date.count("-"), item.note_candidate_id))
        unique = []
        seen = set()
        for note in notes:
            if note.dedup_hash in seen:
                continue
            seen.add(note.dedup_hash)
            unique.append(note)
        notes = unique[: min(budget["notes"], 8 if budget_mode == "concise" else 16)]
        allowed_fields = {module.module_id: sorted(module.field_coverage) for module in modules}
        allowed_ids = {
            "window_ids": [item.window_id for item in windows],
            "movement_ids": sorted(movement_ids),
            "note_candidate_ids": [item.note_candidate_id for item in notes],
            "candidate_record_ids": [item.candidate_record_id for item in records],
        }
        return CandidatePackage(self.catalog.catalog_id, self.catalog.source_snapshot_id, windows, modules, movements, notes, records, [item.module_id for item in modules], allowed_fields, allowed_ids, movement_matches, target_scope, roles, budget_mode, budget)

    @staticmethod
    def _target_sort_key(item: MovementCard, available_movement_ids: set[str]) -> tuple:
        try:
            latest = date.fromisoformat(str(item.latest_valid_progress_date or "")[:10]).toordinal()
        except ValueError:
            latest = 0
        return (-int(item.movement_id in available_movement_ids and item.progress_history_count > 0), -latest, -item.progress_history_count, -item.history_count, item.movement_id)


def package_hash(package: CandidatePackage) -> str:
    return stable_hash(package.to_prompt_dict())
