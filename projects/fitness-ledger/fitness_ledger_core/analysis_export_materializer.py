"""Deterministic materialization of legal AnalysisExportRequest v1.1 requests.

This module is deliberately fixture-only.  It never discovers or opens formal
Fitness Ledger data, Raw records, a model, an Executor, or an ExportPlan.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import date, timedelta
import hashlib
import json
from pathlib import Path
from typing import Any

from .analysis_export_request import validate_request


BUNDLE_VERSION = "1.1"
MATERIALIZER_VERSION = "anonymous-materializer-1.1.0"
DEFAULT_FIXTURE = Path(__file__).resolve().parents[1] / "tools" / "fixtures" / "analysis_export_anonymous" / "fixture.json"
_NOTE_FIELD = {
    "daily": "daily_notes",
    "diet": "diet_notes",
    "training": "training_notes",
    "movement": "movement_notes",
}
_FIELD_TYPES = {
    "date": "date",
    "weight_kg": "number",
    "bowel_movement": "string",
    "training_label": "string",
    "cardio_summary": "string",
    "calories_kcal": "number",
    "protein_g": "number",
    "carbs_g": "number",
    "fat_g": "number",
    "food_summary": "string",
    "split": "string",
    "standardized_summary": "string",
    "movement_id": "string",
    "movement_name": "string",
    "body_part": "string",
    "variant": "string",
    "order": "integer",
    "sets": "array",
    "notes": "string",
}


class MaterializationError(ValueError):
    """Raised when a request is invalid or a fixture cannot be materialized."""

    def __init__(
        self,
        message: str,
        *,
        validation: Any = None,
        code: str = "MATERIALIZATION_ERROR",
        candidates: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.validation = validation
        self.code = code
        self.candidates = candidates or []


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _iso(value: Any) -> str:
    return str(value or "")[:10]


def _parse_date(value: str) -> date:
    return date.fromisoformat(value)


def _casefold(value: Any) -> str:
    return str(value or "").strip().casefold()


def _field_definition(dataset_id: str, field: str) -> dict[str, Any]:
    return {
        "field_id": f"{dataset_id}.{field}",
        "label": field,
        "type": _FIELD_TYPES.get(field, "unknown"),
        "nullable": True,
    }


class AnonymousFixtureMaterializer:
    """Resolve v1.1 requests against one committed synthetic fixture."""

    def __init__(self, fixture: dict[str, Any] | str | Path | None = None) -> None:
        if fixture is None:
            fixture = DEFAULT_FIXTURE
        if isinstance(fixture, (str, Path)):
            fixture_path = Path(fixture)
            self.fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
            self.fixture_path = fixture_path
        else:
            self.fixture = deepcopy(fixture)
            self.fixture_path = None
        if not isinstance(self.fixture, dict):
            raise MaterializationError("Anonymous fixture root must be an object")
        if not str(self.fixture.get("fixture_version", "")).startswith("anonymous-"):
            raise MaterializationError("Only visibly anonymous fixtures are supported")
        self.fixture_version = str(self.fixture["fixture_version"])
        self.anchor_date = _parse_date(str(self.fixture["anchor_date"]))
        self.generated_at = str(self.fixture["generated_at"])
        self.datasets = self.fixture.get("datasets", {})
        self.movement_catalog = self.fixture.get("movement_catalog", [])
        if not isinstance(self.datasets, dict):
            raise MaterializationError("Anonymous fixture datasets must be an object")

    def _rows(self, dataset_type: str) -> list[dict[str, Any]]:
        values = self.datasets.get(dataset_type, [])
        if not isinstance(values, list) or not all(isinstance(item, dict) for item in values):
            raise MaterializationError(f"Fixture dataset {dataset_type} must contain objects")
        return values

    def _movement_matches(self, selector: dict[str, str]) -> list[dict[str, Any]]:
        kind, value = selector["kind"], selector["value"]
        if kind == "movement_id":
            return [
                item for item in self.movement_catalog
                if str(item.get("movement_id")) == value
            ]
        if kind == "movement_name":
            return [
                item
                for item in self.movement_catalog
                if _casefold(item.get("movement_name")) == _casefold(value)
                or any(_casefold(alias) == _casefold(value) for alias in item.get("aliases", []))
            ]
        return [
            item
            for item in self.movement_catalog
            if _casefold(item.get("body_part")) == _casefold(value)
        ]

    def _apply_static_filters(self, dataset: dict[str, Any], rows: list[dict[str, Any]], warnings: list[str]) -> list[dict[str, Any]]:
        filters = dataset.get("filters", {})
        if dataset["type"] == "training":
            for key in ("body_part", "split"):
                if key in filters:
                    if key == "body_part":
                        # Training rows store the human split label (for
                        # example ``肩胸背综合``), while Request v1.1 uses
                        # ``body_part`` as the semantic filter name.  Match
                        # the selected part inside that label; exact split
                        # filters remain exact.
                        expected = _casefold(filters[key])
                        rows = [row for row in rows if expected and expected in _casefold(row.get("split"))]
                    else:
                        rows = [row for row in rows if _casefold(row.get(key)) == _casefold(filters[key])]
        elif dataset["type"] == "movement_progress" and "movement_selector" in filters:
            selector = filters["movement_selector"]
            matches = self._movement_matches(selector)
            if selector["kind"] == "movement_name" and len(matches) > 1:
                candidates = [
                    {
                        "movement_id": str(item.get("movement_id")),
                        "movement_name": item.get("movement_name"),
                        "body_part": item.get("body_part"),
                    }
                    for item in matches
                ]
                raise MaterializationError(
                    f"Movement name {selector['value']} has multiple anonymous candidates",
                    code="MOVEMENT_RESOLUTION_REQUIRED",
                    candidates=candidates,
                )
            movement_ids = {str(item.get("movement_id")) for item in matches}
            if not movement_ids:
                warnings.append(
                    f"{dataset['dataset_id']}: movement selector {selector['kind']}={selector['value']} did not resolve in the anonymous catalog"
                )
            rows = [row for row in rows if str(row.get("movement_id")) in movement_ids]
        return rows

    def _time_filter(self, dataset: dict[str, Any], rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        time_range = dataset["time_range"]
        mode = time_range["mode"]
        if mode == "all_available":
            return list(rows)
        if mode == "recent_days":
            end = self.anchor_date
            start = end - timedelta(days=time_range["days"] - 1)
            return [row for row in rows if start <= _parse_date(_iso(row.get("date"))) <= end]
        if mode == "explicit_range":
            start, end = _parse_date(time_range["start"]), _parse_date(time_range["end"])
            return [row for row in rows if start <= _parse_date(_iso(row.get("date"))) <= end]
        if mode == "latest_matching_sessions":
            dates = sorted({_iso(row.get("date")) for row in rows}, reverse=True)[: time_range["sessions"]]
            return [row for row in rows if _iso(row.get("date")) in dates]
        raise MaterializationError("Relation time ranges are resolved separately")

    def _progress_excluded(self, row: dict[str, Any]) -> tuple[bool, str | None]:
        """Apply the website's progress-only visibility state to one row."""
        movement_id = str(row.get("movement_id", ""))
        definition = next(
            (item for item in self.movement_catalog if str(item.get("movement_id", "")) == movement_id),
            {},
        )
        if bool(definition.get("exclude_from_progress", False)):
            return True, "movement"
        if bool(row.get("exclude_from_progress", False)):
            return True, "history"
        return False, None

    def _progress_exclusion_summary(self, rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """Exclude progress rows without removing them from other datasets."""
        included: list[dict[str, Any]] = []
        excluded_by_movement: dict[str, dict[str, Any]] = {}
        for row in rows:
            excluded, scope = self._progress_excluded(row)
            if not excluded:
                included.append(row)
                continue
            movement_id = str(row.get("movement_id", ""))
            item = excluded_by_movement.setdefault(
                movement_id,
                {"movement_id": movement_id, "scopes": [], "excluded_record_count": 0},
            )
            if scope and scope not in item["scopes"]:
                item["scopes"].append(scope)
            item["excluded_record_count"] += 1
        return included, {
            "excluded_record_count": len(rows) - len(included),
            "excluded_movement_count": len(excluded_by_movement),
            "excluded_movements": [excluded_by_movement[key] for key in sorted(excluded_by_movement)],
        }

    def _resolve_dataset(
        self,
        dataset: dict[str, Any],
        resolved: dict[str, list[dict[str, Any]]],
        warnings: list[str],
        missing: list[str],
        resolving: set[str],
    ) -> list[dict[str, Any]]:
        dataset_id = dataset["dataset_id"]
        if dataset_id in resolved:
            return resolved[dataset_id]
        if dataset_id in resolving:
            raise MaterializationError(f"Cyclic target dataset reference: {dataset_id}")
        resolving.add(dataset_id)
        source_rows = self._rows(dataset["type"])
        rows = self._apply_static_filters(dataset, list(source_rows), warnings)
        self._stage_counts[dataset_id] = {"candidate_record_count": len(rows)}
        time_range = dataset["time_range"]
        if time_range["mode"] not in {"days_before_target_session", "target_session_day", "days_after_target_session"}:
            rows = self._time_filter(dataset, rows)
        else:
            target_dates: list[str] = []
            if "target_dataset_id" in time_range:
                target = next(
                    item for item in self._requested_datasets if item["dataset_id"] == time_range["target_dataset_id"]
                )
                target_rows = self._resolve_dataset(target, resolved, warnings, missing, resolving)
                target_dates = sorted({_iso(row.get("date")) for row in target_rows}, reverse=True)
                if time_range["match_mode"] == "single_latest_matching_session":
                    target_dates = target_dates[:1]
            else:
                target_dates = [time_range["target_date"]]
                if not any(_iso(row.get("date")) == target_dates[0] for row in self._rows("training")):
                    warnings.append(f"{dataset_id}: target_date {target_dates[0]} has no matching fixture training session")
            relation_rows: list[dict[str, Any]] = []
            for target_date in target_dates:
                target_day = _parse_date(target_date)
                mode = time_range["mode"]
                if mode == "target_session_day":
                    start = end = target_day
                elif mode == "days_after_target_session":
                    start = target_day if time_range["include_target_session_day"] else target_day + timedelta(days=1)
                    end = target_day + timedelta(days=time_range["days_after"])
                else:
                    start = target_day - timedelta(days=time_range["days_before"])
                    end = target_day if time_range["include_target_session_day"] else target_day - timedelta(days=1)
                for row in rows:
                    row_date = _parse_date(_iso(row.get("date")))
                    if start <= row_date <= end:
                        copied = deepcopy(row)
                        copied["_relation"] = {
                            "target_session_date": target_date,
                            "target_dataset_id": time_range.get("target_dataset_id"),
                            "target_date": time_range.get("target_date"),
                        }
                        relation_rows.append(copied)
            rows = relation_rows
            if not target_dates:
                warnings.append(f"{dataset_id}: no target sessions were available for the diet window")
        rows.sort(key=lambda row: (_iso(row.get("date")), _canonical(row.get("_relation", {}))))
        self._stage_counts[dataset_id]["resolved_record_count"] = len(rows)
        resolved[dataset_id] = rows
        resolving.remove(dataset_id)
        return rows

    def _project_rows(
        self,
        dataset: dict[str, Any],
        rows: list[dict[str, Any]],
        missing: list[str],
        warnings: list[str],
    ) -> list[dict[str, Any]]:
        fields = dataset["fields"]
        note_scope = dataset.get("notes_scope")
        note_field = _NOTE_FIELD.get(note_scope or "")
        roles = set(dataset.get("set_roles", []))
        output: list[dict[str, Any]] = []
        had_resolved_rows = bool(rows)
        if dataset["type"] == "movement_progress":
            rows, exclusion_summary = self._progress_exclusion_summary(rows)
        else:
            exclusion_summary = {
                "excluded_record_count": 0,
                "excluded_movement_count": 0,
                "excluded_movements": [],
            }
        self._exclusion_summaries[dataset["dataset_id"]] = exclusion_summary
        if note_field and not any(note_field in source for source in self._rows(dataset["type"])):
            warnings.append(
                f"{dataset['dataset_id']}: Notes scope {note_scope} is unavailable in the anonymous fixture"
            )
        for source in rows:
            record: dict[str, Any] = {"dataset_id": dataset["dataset_id"], "type": dataset["type"]}
            for field in fields:
                if field not in source:
                    record[field] = None
                    missing.append(f"{dataset['dataset_id']}: field {field} missing on {_iso(source.get('date'))}")
                else:
                    value = deepcopy(source[field])
                    if field == "sets" and roles:
                        value = [item for item in value if item.get("role") in roles]
                    record[field] = value
            if note_scope:
                if note_field not in source:
                    record["notes"] = None
                else:
                    record["notes"] = deepcopy(source[note_field])
            if "_relation" in source:
                record["relation"] = deepcopy(source["_relation"])
            output.append(record)
        if not output and not had_resolved_rows:
            missing.append(f"{dataset['dataset_id']}: no matching records")
        return output

    def materialize(self, request: dict[str, Any]) -> dict[str, Any]:
        validation = validate_request(request)
        if not validation.valid or validation.normalized_request is None:
            errors = "; ".join(f"{item.code} at {item.path}" for item in validation.errors)
            raise MaterializationError(f"Request rejected by AnalysisExportRequest v1.1 Validator: {errors}", validation=validation)
        normalized = validation.normalized_request
        self._requested_datasets = normalized["datasets"]
        self._stage_counts: dict[str, dict[str, int]] = {}
        self._exclusion_summaries: dict[str, dict[str, Any]] = {}
        resolved: dict[str, list[dict[str, Any]]] = {}
        warnings: list[str] = []
        missing: list[str] = []
        projected: list[dict[str, Any]] = []
        quality_datasets: list[dict[str, Any]] = []
        field_definitions: list[dict[str, Any]] = []
        for dataset in normalized["datasets"]:
            rows = self._resolve_dataset(dataset, resolved, warnings, missing, set())
            projected_rows = self._project_rows(dataset, rows, missing, warnings)
            projected.extend(projected_rows)
            exclusion_summary = self._exclusion_summaries[dataset["dataset_id"]]
            if not projected_rows and not exclusion_summary["excluded_record_count"]:
                warnings.append(f"{dataset['dataset_id']}: empty selection is reported explicitly")
            quality_datasets.append({
                "dataset_id": dataset["dataset_id"],
                "type": dataset["type"],
                "candidate_record_count": self._stage_counts[dataset["dataset_id"]]["candidate_record_count"],
                "resolved_record_count": self._stage_counts[dataset["dataset_id"]]["resolved_record_count"],
                "materialized_record_count": len(projected_rows),
                "excluded_record_count": self._exclusion_summaries[dataset["dataset_id"]]["excluded_record_count"],
                "excluded_movement_count": self._exclusion_summaries[dataset["dataset_id"]]["excluded_movement_count"],
                "excluded_movements": self._exclusion_summaries[dataset["dataset_id"]]["excluded_movements"],
                "missing_fields": sorted({item.split(": field ", 1)[1].split(" missing on ", 1)[0] for item in missing if item.startswith(dataset["dataset_id"] + ": field ")}),
            })
            field_definitions.extend(_field_definition(dataset["dataset_id"], field) for field in dataset["fields"])
            if dataset.get("notes_scope"):
                field_definitions.append(_field_definition(dataset["dataset_id"], "notes"))

        projected.sort(key=lambda row: (row["dataset_id"], _iso(row.get("date")), _canonical(row.get("relation", {}))))
        counts = {
            "validated_request_count": 1,
            "candidate_record_count": sum(item["candidate_record_count"] for item in quality_datasets),
            "resolved_record_count": sum(item["resolved_record_count"] for item in quality_datasets),
            "materialized_record_count": len(projected),
            "exported_artifact_count": len(normalized["output"]["formats"]),
        }
        bundle_seed = {
            "request": normalized,
            "fixture_version": self.fixture_version,
            "materializer_version": MATERIALIZER_VERSION,
        }
        bundle_id = "bundle-" + hashlib.sha256(_canonical(bundle_seed).encode("utf-8")).hexdigest()[:20]
        provenance = {
            "source_kind": "anonymous_synthetic_fixture",
            "source_snapshot_id": self.fixture_version,
            "fixture_version": self.fixture_version,
            "request_schema_version": normalized["request_version"],
            "materializer_version": MATERIALIZER_VERSION,
            "counts": counts,
            "fixture_path_policy": "committed fixture only; no formal paths opened",
        }
        bundle = {
            "bundle_version": BUNDLE_VERSION,
            "request": normalized,
            "manifest": {
                "bundle_id": bundle_id,
                "generated_at": self.generated_at,
                "source_snapshot_id": self.fixture_version,
                "record_count": len(projected),
            },
            "selected_datasets": [deepcopy(dataset) for dataset in normalized["datasets"]],
            "records": projected,
            "field_definitions": field_definitions,
            "quality_profile": {
                "status": (
                    "materialized"
                    if projected
                    else "empty_after_progress_exclusion"
                    if any(item["excluded_record_count"] for item in quality_datasets)
                    else "empty_selection"
                ),
                "dataset_count": len(normalized["datasets"]),
                "record_count": len(projected),
                "progress_exclusions": {
                    "excluded_record_count": sum(item["excluded_record_count"] for item in quality_datasets),
                    "excluded_movement_count": len({
                        entry["movement_id"]
                        for item in quality_datasets
                        for entry in item["excluded_movements"]
                    }),
                },
                "datasets": quality_datasets,
            },
            "missing_information": sorted(set(missing)),
            "warnings": sorted(set(warnings)),
            "provenance": provenance,
            "safety_flags": {
                "raw_included": False,
                "executor_called": False,
                "formal_data_written": False,
            },
        }
        return bundle

    @staticmethod
    def export_json(bundle: dict[str, Any]) -> str:
        return json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"

    @staticmethod
    def export_markdown(bundle: dict[str, Any]) -> str:
        manifest = bundle["manifest"]
        provenance = bundle["provenance"]
        lines = [
            "# AnalysisExportBundle v1.1",
            "",
            "## Manifest",
            "",
            f"- Bundle ID: `{manifest['bundle_id']}`",
            f"- Generated at: `{manifest['generated_at']}`",
            f"- Source snapshot: `{manifest['source_snapshot_id']}`",
            f"- Record count: `{manifest['record_count']}`",
            "",
            "## Request",
            "",
            f"Purpose: {bundle['request']['purpose']}",
            "",
            "```json",
            AnonymousFixtureMaterializer.export_json(bundle["request"]).rstrip(),
            "```",
            "",
            "## Counts",
            "",
        ]
        for key, value in provenance["counts"].items():
            lines.append(f"- {key}: `{value}`")
        exclusions = bundle["quality_profile"]["progress_exclusions"]
        lines.extend([
            "",
            "## Progress exclusions",
            "",
            "Progress-only exclusions apply to movement_progress; training/day-level records remain available.",
            f"- Excluded records: {exclusions['excluded_record_count']}",
            f"- Excluded movements: {exclusions['excluded_movement_count']}",
            "",
            "## Selected datasets",
            "",
        ])
        for dataset in bundle["selected_datasets"]:
            lines.append(f"- `{dataset['dataset_id']}` ({dataset['type']}): {', '.join(dataset['fields'])}")
        lines.extend(["", "## Records", "", "```json", json.dumps(bundle["records"], ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
        lines.extend(["## Missing information", ""])
        lines.extend(f"- {item}" for item in bundle["missing_information"] or ["None"])
        lines.extend(["", "## Warnings", ""])
        lines.extend(f"- {item}" for item in bundle["warnings"] or ["None"])
        lines.extend(["", "## Provenance and safety", "", "```json", json.dumps({"provenance": provenance, "safety_flags": bundle["safety_flags"]}, ensure_ascii=False, indent=2, sort_keys=True), "```", ""])
        return "\n".join(lines)

    def materialize_with_exports(self, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        bundle = self.materialize(request)
        formats = bundle["request"]["output"]["formats"]
        exports: dict[str, str] = {}
        if "json" in formats:
            exports["json"] = self.export_json(bundle)
        if "markdown" in formats:
            exports["markdown"] = self.export_markdown(bundle)
        return bundle, exports
