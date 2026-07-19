"""Candidate recall and compression for the intelligent export planner."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .data_catalog import MovementResolver, resolve_windows
from .intelligent_export_models import CandidateRecordCard, CandidateWindow, DataCatalog, IntentSpec, ModuleCard, MovementCard, NotesCard, stable_hash


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
            "budget_mode": self.budget_mode,
            "budget": self.budget,
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
        windows = resolve_windows(self.catalog, intent)
        window = windows[0] if windows else None
        start, end = (window.resolved_start, window.resolved_end) if window else ("", "")
        in_range = lambda value: bool(value) and (not start or start <= value <= end)
        movement_matches = []
        matched_ids: set[str] = set()
        for mention in intent.movement_mentions:
            matches = self.resolver.resolve(mention, self.catalog.movements)
            movement_matches.extend(matches[:4])
            # Recall a small, explainable candidate set even when the match is
            # not decisive; the Planning model and validator decide whether
            # an ambiguous mention is useful, never the resolver alone.
            if matches and matches[0]["score"] >= 0.55:
                matched_ids.add(matches[0]["movement_id"])
        movements = [item for item in self.catalog.movements if item.movement_id in matched_ids or not intent.movement_mentions]
        movements = sorted(movements, key=lambda item: (-item.progress_history_count, -item.history_count, item.canonical_name))[: max(budget["movements"] * 2, budget["movements"])]
        movement_ids = {item.movement_id for item in movements}
        modules = [item for item in self.catalog.modules if item.module_id in set(intent.catalog_requirements) or not intent.catalog_requirements]
        if not modules:
            modules = list(self.catalog.modules)
        records = [item for item in self.catalog.candidate_records if in_range(item.date) and (item.module_id != "movement_history" or not movement_ids or next((mid for mid in item.related_movement_ids if mid in movement_ids), None))]
        # Keep the planning prompt comfortably below the configured context
        # window.  The executor still reads the complete local projection
        # after validation; this cap only limits model-visible candidates.
        prompt_record_cap = {"concise": 24, "standard": 48, "complete": 96}.get(budget_mode, 48)
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
        notes = unique[: budget["notes"]]
        allowed_fields = {module.module_id: sorted(module.field_coverage) for module in modules}
        allowed_ids = {
            "window_ids": [item.window_id for item in windows],
            "movement_ids": sorted(movement_ids),
            "note_candidate_ids": [item.note_candidate_id for item in notes],
            "candidate_record_ids": [item.candidate_record_id for item in records],
        }
        return CandidatePackage(self.catalog.catalog_id, self.catalog.source_snapshot_id, windows, modules, movements, notes, records, [item.module_id for item in modules], allowed_fields, allowed_ids, movement_matches, budget_mode, budget)


def package_hash(package: CandidatePackage) -> str:
    return stable_hash(package.to_prompt_dict())
