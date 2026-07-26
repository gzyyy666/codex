"""Read-only materialization into the existing EvidenceProfile contract."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from types import SimpleNamespace
from typing import Any

from .analysis_evidence import EvidenceProfile, build_evidence_profile
from .analysis_registry import CLAIM_POLICIES, FIELD_REGISTRY, TaskExpansion

CAPABILITY_MODULES = {
    "body_history": "body",
    "diet_macros": "diet",
    "training_context": "training",
    "movement_progress": "movement_history",
    "notes_context": "notes",
}


@dataclass(frozen=True)
class MaterializedRecord:
    record_id: str
    module_id: str
    date: str
    values: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MaterializedEvidence:
    """The new object is a wrapper; ``profile`` is the existing contract."""

    profile: EvidenceProfile
    records: list[MaterializedRecord]
    missing_fields: list[str]
    quality_warnings: list[str]
    comparison_group_counts: dict[str, int]
    variant_consistency: bool | None
    schema_version: str = "fitness-ledger-materialized-evidence-v1"

    def to_dict(self, include_records: bool = False) -> dict[str, Any]:
        result = self.profile.to_dict()
        result.update({
            "schema_version": self.schema_version,
            "missing_fields": list(self.missing_fields),
            "quality_warnings": list(self.quality_warnings),
            "comparison_group_counts": dict(self.comparison_group_counts),
            "variant_consistency": self.variant_consistency,
        })
        if include_records:
            result["materialized_records"] = [record.to_dict() for record in self.records]
        return result


def _record_values(record: Any) -> dict[str, Any]:
    values = dict(getattr(record, "factual_summary", {}) or {})
    values.setdefault("Date", getattr(record, "date", ""))
    values.setdefault("date", getattr(record, "date", ""))
    return values


def _canonical_value(field_id: str, record: Any) -> Any:
    definition = FIELD_REGISTRY[field_id]
    if definition.module_id != getattr(record, "module_id", ""):
        return None
    values = _record_values(record)
    for source in definition.source_fields:
        if values.get(source) not in (None, "", []):
            return values[source]
    # Movement cards keep group-level values under ``sets``.  Preserve the
    # nested source object as evidence; no aggregate is invented here.
    if definition.module_id == "movement_history" and "sets" in values:
        return values["sets"]
    return None


class EvidenceMaterializer:
    """Materialize only CandidatePackage cards, never formal or Raw records."""

    def materialize(self, candidate_package: Any, expansion: TaskExpansion) -> MaterializedEvidence:
        selected_modules = list(dict.fromkeys(
            CAPABILITY_MODULES[capability]
            for capability in expansion.required_capabilities
            if capability in CAPABILITY_MODULES
        ))
        authorized_modules = [module for module in selected_modules if module != "notes"]
        cards = [
            card for card in getattr(candidate_package, "candidate_records", [])
            if card.module_id in selected_modules
        ]
        records: list[MaterializedRecord] = []
        for card in cards:
            values = {
                field_id: value
                for field_id in expansion.required_fields
                if (value := _canonical_value(field_id, card)) is not None
            }
            records.append(MaterializedRecord(str(card.candidate_record_id), str(card.module_id), str(card.date), values))

        selected_fields = {
            module.module_id: sorted(module.field_coverage)
            for module in getattr(candidate_package, "modules", [])
            if module.module_id in selected_modules
        }
        draft = SimpleNamespace(
            selected_modules=selected_modules,
            candidate_record_ids=[card.candidate_record_id for card in cards],
            selected_fields=selected_fields,
        )
        mapping = SimpleNamespace(notes_scope_status="not_selected")
        catalog = SimpleNamespace(
            modules=getattr(candidate_package, "modules", []),
            candidate_records=cards,
        )
        profile = build_evidence_profile(catalog, draft, mapping)
        profile = EvidenceProfile(
            profile.available_modules,
            profile.selected_modules,
            [module for module in profile.authorized_modules if module in authorized_modules],
            profile.candidate_record_count,
            len(records),
            None,
            profile.module_candidate_counts,
            profile.selected_dates_by_module,
            profile.aligned_day_count,
            profile.field_completeness,
            profile.provenance,
            profile.quality_flags,
        )
        missing_fields: list[str] = []
        for field_id in expansion.required_fields:
            eligible = [card for card in cards if FIELD_REGISTRY[field_id].module_id == card.module_id]
            observed = sum(field_id in record.values for record in records if record.module_id == FIELD_REGISTRY[field_id].module_id)
            if not eligible or observed == 0:
                missing_fields.append(field_id)
        dates: dict[str, set[str]] = {}
        for record in records:
            dates.setdefault(record.module_id, set()).add(record.date)
        aligned = len(dates.get("diet", set()) & dates.get("training", set()))
        quality_warnings = list(profile.quality_flags)
        if "training.set.load" in missing_fields:
            quality_warnings.append("training_group_level_fields_missing")
        if "training.exercise.variant_id" in missing_fields:
            quality_warnings.append("movement_variant_unavailable")
        for key, minimum in expansion.minimum_evidence.items():
            observed = aligned if key == "aligned_days" else len(records) if key == "records" else sum(record.module_id == "movement_history" for record in records) if key == "comparable_sessions" else 0
            if observed < minimum:
                quality_warnings.append(f"{key}_below_minimum:{observed}<{minimum}")
        variants = {
            record.values.get("training.exercise.variant_id")
            for record in records
            if record.values.get("training.exercise.variant_id") is not None
        }
        return MaterializedEvidence(
            profile,
            records,
            list(dict.fromkeys(missing_fields)),
            list(dict.fromkeys(quality_warnings)),
            {},
            None if not variants else len(variants) == 1,
        )


class EvidenceProfileConsistencyValidator:
    def validate(self, evidence: MaterializedEvidence | EvidenceProfile) -> list[str]:
        profile = evidence.profile if isinstance(evidence, MaterializedEvidence) else evidence
        errors: list[str] = []
        if profile.materialized_record_count is not None and profile.materialized_record_count > profile.candidate_record_count:
            errors.append("materialized_count_exceeds_candidate_count")
        if profile.exported_record_count is not None and profile.materialized_record_count is not None and profile.exported_record_count > profile.materialized_record_count:
            errors.append("exported_count_exceeds_materialized_count")
        if "raw_entries" in profile.authorized_modules:
            errors.append("raw_entries_authorized")
        return errors


def evaluate_materialized_evidence(expansion: TaskExpansion, evidence: MaterializedEvidence, confirmation_missing: list[str] | None = None) -> dict[str, Any]:
    missing = list(evidence.missing_fields)
    confirmations = list(confirmation_missing or [])
    policy = CLAIM_POLICIES.get(expansion.allowed_claim_mode, CLAIM_POLICIES["none"])
    forbidden = list(dict.fromkeys(policy.forbidden_claim_codes + tuple(expansion.forbidden_claim_codes)))
    aligned = evidence.profile.aligned_day_count or 0
    comparable = sum(record.module_id == "movement_history" for record in evidence.records)
    observed = {"records": len(evidence.records), "aligned_days": aligned, "comparable_sessions": comparable, "sessions_per_condition": 0}
    for key, minimum in expansion.minimum_evidence.items():
        if observed.get(key, 0) < minimum:
            missing.append(f"minimum:{key}>={minimum} observed={observed.get(key, 0)}")
    if confirmations:
        status, answerability, mode, allowed, next_action = "needs_confirmation", "needs_resolution", "none", [], "resolve_confirmations"
    elif missing:
        status, answerability, mode, allowed, next_action = "insufficient_evidence", "insufficient_evidence", expansion.allowed_claim_mode, ["OBSERVED_COVERAGE"], "downgrade_to_coverage_or_request_more_data"
    elif evidence.quality_warnings:
        status, answerability, mode, allowed, next_action = "ready_with_limits", "ready_with_limits", expansion.allowed_claim_mode, list(policy.allowed_claim_codes), "return_limited_claims"
    else:
        status, answerability, mode, allowed, next_action = "ready_for_package", "ready", expansion.allowed_claim_mode, list(policy.allowed_claim_codes), "build_preview_package"
    return {
        "schema_version": "fitness-ledger-evidence-evaluation-v1",
        "status": status,
        "answerability": answerability,
        "allowed_claim_mode": mode,
        "allowed_claim_codes": allowed,
        "forbidden_claim_codes": forbidden,
        "missing_information": list(dict.fromkeys(missing)),
        "next_action": next_action,
        "evidence_profile": evidence.profile.to_dict(),
    }
