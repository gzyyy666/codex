"""Narrow read-only adapter for the formal Fitness Ledger JSON files.

The adapter projects only the structured fields required by the frozen
AnalysisExportRequest v1.1 materializer.  It delegates validation, resolution,
time-window handling, projection, and export rendering to the accepted
``AnonymousFixtureMaterializer`` chain.  The two formal files are never opened
for writing and no unstructured source fields are copied into the projection.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any

from .analysis_export_materializer import AnonymousFixtureMaterializer, MATERIALIZER_VERSION, MaterializationError


class FormalReadOnlyDataSourceError(ValueError):
    """Raised when the two explicit formal read-only inputs are unusable."""


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _require_file(path: str | Path, label: str) -> Path:
    resolved = Path(path).expanduser().resolve()
    if not resolved.is_file():
        raise FormalReadOnlyDataSourceError(f"{label} must be an existing regular file: {resolved}")
    return resolved


def _fingerprint(path: Path) -> dict[str, Any]:
    stat = path.stat()
    payload = path.read_bytes()
    modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
    return {
        "path": str(path),
        "size": stat.st_size,
        "sha256": hashlib.sha256(payload).hexdigest(),
        "modified_time_utc": modified,
        "modified_time_ns": stat.st_mtime_ns,
    }


def _read_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise FormalReadOnlyDataSourceError(f"Unable to read {label} as UTF-8 JSON: {path}") from error
    if not isinstance(value, dict):
        raise FormalReadOnlyDataSourceError(f"{label} root must be a JSON object")
    return value


def _mapped_record(source: dict[str, Any], mapping: dict[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for target, source_key in mapping.items():
        if source_key in source:
            result[target] = deepcopy(source[source_key])
    return result


def _structured_sets(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    allowed = {"role", "weight", "weight_text", "reps", "sets"}
    return [
        {key: deepcopy(item[key]) for key in sorted(set(item) & allowed)}
        for item in value
        if isinstance(item, dict)
    ]


class FormalReadOnlyDataSource:
    """Adapt exactly two formal JSON files to the accepted materializer chain."""

    _BODY_FIELDS = {
        "date": "Date",
        "weight_kg": "Weight (kg)",
        "bowel_movement": "Bowel Movement",
        "training_label": "Training",
        "cardio_summary": "Cardio",
        "daily_notes": "Notes",
    }
    _DIET_FIELDS = {
        "date": "Date",
        "calories_kcal": "Calories (kcal)",
        "protein_g": "Protein (g)",
        "carbs_g": "Carbs (g)",
        "fat_g": "Fat (g)",
        "food_summary": "Food Summary",
        "diet_notes": "Notes",
    }
    _TRAINING_FIELDS = {
        "date": "Date",
        "split": "Split",
        "standardized_summary": "Standardized Summary",
        "training_notes": "Notes",
    }

    def __init__(self, tracker_path: str | Path, movement_dictionary_path: str | Path) -> None:
        self.tracker_path = _require_file(tracker_path, "tracker.json")
        self.movement_dictionary_path = _require_file(movement_dictionary_path, "movement_dictionary.json")
        self._before = self.file_fingerprints()
        tracker = _read_json(self.tracker_path, "tracker.json")
        dictionary = _read_json(self.movement_dictionary_path, "movement_dictionary.json")
        fixture = self._to_materializer_fixture(tracker, dictionary)
        self.snapshot_id = "formal-readonly-" + hashlib.sha256(
            _canonical({key: value["sha256"] for key, value in self._before.items()}).encode("utf-8")
        ).hexdigest()[:24]
        fixture["fixture_version"] = "anonymous-formal-readonly-" + self.snapshot_id.rsplit("-", 1)[-1]
        fixture["generated_at"] = max(
            datetime.fromtimestamp(value["modified_time_ns"] / 1_000_000_000, tz=timezone.utc)
            for value in self._before.values()
        ).isoformat()
        self.anchor_date = fixture["anchor_date"]
        self.generated_at = fixture["generated_at"]
        self._materializer = AnonymousFixtureMaterializer(fixture)

    def file_fingerprints(self) -> dict[str, dict[str, Any]]:
        return {
            "tracker": _fingerprint(self.tracker_path),
            "movement_dictionary": _fingerprint(self.movement_dictionary_path),
        }

    @staticmethod
    def _to_materializer_fixture(tracker: dict[str, Any], dictionary: dict[str, Any]) -> dict[str, Any]:
        daily = tracker.get("daily_records", [])
        diet = tracker.get("diet_records", [])
        training = tracker.get("training_sessions", [])
        movements = tracker.get("movements", {})
        dictionary_items = dictionary.get("movements", [])
        if not all(isinstance(items, list) for items in (daily, diet, training, dictionary_items)):
            raise FormalReadOnlyDataSourceError("Formal structured collections must be arrays")
        if not isinstance(movements, dict):
            raise FormalReadOnlyDataSourceError("Formal movement histories must be an object")

        body_rows = [_mapped_record(item, FormalReadOnlyDataSource._BODY_FIELDS) for item in daily if isinstance(item, dict)]
        diet_rows = [_mapped_record(item, FormalReadOnlyDataSource._DIET_FIELDS) for item in diet if isinstance(item, dict)]
        training_rows = [_mapped_record(item, FormalReadOnlyDataSource._TRAINING_FIELDS) for item in training if isinstance(item, dict)]
        dictionary_by_id = {
            str(item.get("movement_id")): item
            for item in dictionary_items
            if isinstance(item, dict) and item.get("movement_id")
        }
        movement_catalog: list[dict[str, Any]] = []
        for item in dictionary_items:
            if not isinstance(item, dict) or not item.get("movement_id"):
                continue
            movement_catalog.append({
                "movement_id": str(item["movement_id"]),
                "movement_name": deepcopy(item.get("display_name") or item.get("english_name") or ""),
                "body_part": deepcopy(item.get("muscle_group") or ""),
                "aliases": deepcopy(item.get("aliases") or []),
            })

        movement_rows: list[dict[str, Any]] = []
        for movement_id, movement in movements.items():
            if not isinstance(movement, dict) or not isinstance(movement.get("history", []), list):
                continue
            movement_id = str(movement_id)
            catalog_item = dictionary_by_id.get(movement_id, {})
            for history in movement.get("history", []):
                if not isinstance(history, dict):
                    continue
                row: dict[str, Any] = {
                    "movement_id": movement_id,
                    "movement_name": deepcopy(catalog_item.get("display_name") or catalog_item.get("english_name") or movement.get("name") or ""),
                    "body_part": deepcopy(catalog_item.get("muscle_group") or ""),
                }
                for field in ("date", "order"):
                    if field in history:
                        row[field] = deepcopy(history[field])
                if "sets" in history:
                    row["sets"] = _structured_sets(history["sets"])
                if "notes" in history:
                    row["movement_notes"] = deepcopy(history["notes"])
                movement_rows.append(row)

        dates = [
            str(item["date"])[:10]
            for items in (body_rows, diet_rows, training_rows, movement_rows)
            for item in items
            if item.get("date")
        ]
        if not dates:
            raise FormalReadOnlyDataSourceError("Formal structured data contains no usable dates")
        return {
            "fixture_version": "anonymous-formal-readonly-staging",
            "anchor_date": max(dates),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "datasets": {
                "body": body_rows,
                "diet": diet_rows,
                "training": training_rows,
                "movement_progress": movement_rows,
            },
            "movement_catalog": movement_catalog,
        }

    def _formalize_bundle(self, bundle: dict[str, Any]) -> dict[str, Any]:
        result = deepcopy(bundle)
        result["manifest"]["source_snapshot_id"] = self.snapshot_id
        result["manifest"]["bundle_id"] = "bundle-" + hashlib.sha256(
            _canonical({
                "request": result["request"],
                "source_snapshot_id": self.snapshot_id,
                "materializer_version": MATERIALIZER_VERSION,
            }).encode("utf-8")
        ).hexdigest()[:20]
        provenance = result["provenance"]
        provenance.pop("fixture_version", None)
        provenance.pop("fixture_path_policy", None)
        provenance.update({
            "source_kind": "formal_local_json_read_only",
            "source_snapshot_id": self.snapshot_id,
            "formal_paths": ["data/tracker.json", "data/movement_dictionary.json"],
            "formal_access": "read_only; structured allowlist projection",
            "source_path_policy": "explicit formal files opened read-only; structured allowlist projection only",
            "materializer_version": MATERIALIZER_VERSION,
        })
        for dataset in result["request"]["datasets"]:
            if dataset.get("set_roles") and any(
                isinstance(item, dict) and item.get("sets") and any("role" not in set_item for set_item in item["sets"])
                for item in self._materializer.fixture["datasets"]["movement_progress"]
            ):
                result["warnings"].append(
                    f"{dataset['dataset_id']}: formal set-role metadata is unavailable; no set-role inference was applied"
                )
        result["warnings"] = sorted(set(result["warnings"]))
        return result

    def materialize(self, request: dict[str, Any]) -> dict[str, Any]:
        return self._formalize_bundle(self._materializer.materialize(request))

    def materialize_with_exports(self, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        bundle = self.materialize(request)
        formats = bundle["request"]["output"]["formats"]
        exports: dict[str, str] = {}
        if "json" in formats:
            exports["json"] = AnonymousFixtureMaterializer.export_json(bundle)
        if "markdown" in formats:
            exports["markdown"] = AnonymousFixtureMaterializer.export_markdown(bundle)
        return bundle, exports

    def reference_movement_id(self) -> str:
        rows = self._materializer.fixture["datasets"]["movement_progress"]
        return sorted({str(row["movement_id"]) for row in rows if row.get("movement_id")})[0]

    def reference_body_part(self) -> str:
        catalog = self._materializer.fixture["movement_catalog"]
        return sorted({str(item["body_part"]) for item in catalog if item.get("body_part")})[0]

    def ambiguous_movement_name(self) -> str:
        matches: dict[str, set[str]] = {}
        for item in self._materializer.fixture["movement_catalog"]:
            for value in [item.get("movement_name"), *item.get("aliases", [])]:
                if value:
                    matches.setdefault(str(value).strip().casefold(), set()).add(str(item["movement_id"]))
        candidates = sorted(name for name, ids in matches.items() if len(ids) > 1)
        if not candidates:
            raise FormalReadOnlyDataSourceError("Formal movement dictionary has no ambiguous name/alias case")
        return candidates[0]

    @property
    def before_fingerprints(self) -> dict[str, dict[str, Any]]:
        return deepcopy(self._before)


__all__ = ["FormalReadOnlyDataSource", "FormalReadOnlyDataSourceError", "MaterializationError"]
