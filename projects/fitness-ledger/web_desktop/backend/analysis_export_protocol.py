"""Read-only Analysis Export Request v1.1 protocol service.

The service is deliberately separate from the legacy ``/api/analysis-export``
command. It validates every request again at each boundary and only exports
through an injected read-only materializer provider. Formal files are connected
only through explicit environment configuration; otherwise the service fails
closed. Tests and the anonymous review server may inject the visibly synthetic
fixture provider.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Any, Mapping, Protocol

from fitness_ledger_core.analysis_export_materializer import (
    AnonymousFixtureMaterializer,
    MaterializationError,
)
from fitness_ledger_core.analysis_export_request import (
    REQUEST_SCHEMA_VERSION,
    RequestValidationResult,
    validate_request,
)
from fitness_ledger_core.formal_readonly_data_source import (
    FormalReadOnlyDataSource,
    FormalReadOnlyDataSourceError,
)


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


class AnalysisExportProviderUnavailable(RuntimeError):
    """Raised when no formal read-only source is connected in this worktree."""


class AnalysisExportProvider(Protocol):
    source_kind: str
    formal_data_available: bool

    def materialize(self, request: dict[str, Any]) -> dict[str, Any]: ...

    def materialize_with_exports(self, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]: ...

    def resolve(self, selector: dict[str, str]) -> list[dict[str, Any]]: ...


class ReadOnlyDataSource(Protocol):
    """Future formal adapter boundary; it must never expose a write method."""

    source_kind: str
    formal_data_available: bool

    def snapshot(self) -> Any: ...


class MaterializerProvider(Protocol):
    """Provider boundary for deterministic, read-only bundle materialization."""

    source_kind: str
    formal_data_available: bool

    def materialize(self, request: dict[str, Any]) -> dict[str, Any]: ...

    def materialize_with_exports(self, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]: ...

    def resolve(self, selector: dict[str, str]) -> list[dict[str, Any]]: ...


class FormalReadOnlyProvider:
    """Fail-closed placeholder when formal read-only inputs are not configured."""

    source_kind = "formal_read_only"
    formal_data_available = False

    def __init__(self, availability_status: str = "not_configured") -> None:
        self.availability_status = availability_status

    def _unavailable(self) -> None:
        raise AnalysisExportProviderUnavailable(
            "Formal read-only Analysis Export data source is not connected in this Web worktree."
        )

    def materialize(self, _request: dict[str, Any]) -> dict[str, Any]:
        self._unavailable()
        raise AssertionError("unreachable")

    def materialize_with_exports(self, _request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        self._unavailable()
        raise AssertionError("unreachable")

    def resolve(self, _selector: dict[str, str]) -> list[dict[str, Any]]:
        self._unavailable()
        raise AssertionError("unreachable")


class AnonymousFixtureProvider:
    """Explicitly labelled synthetic provider for tests and local review."""

    source_kind = "anonymous_synthetic_fixture"
    formal_data_available = False

    def __init__(self, fixture: dict[str, Any] | str | Path | None = None) -> None:
        self.materializer = AnonymousFixtureMaterializer(fixture)

    def materialize(self, request: dict[str, Any]) -> dict[str, Any]:
        return self.materializer.materialize(request)

    def materialize_with_exports(self, request: dict[str, Any]) -> tuple[dict[str, Any], dict[str, str]]:
        return self.materializer.materialize_with_exports(request)

    def resolve(self, selector: dict[str, str]) -> list[dict[str, Any]]:
        return [dict(item) for item in self.materializer._movement_matches(selector)]


@dataclass(frozen=True)
class StoredPreview:
    request: dict[str, Any]
    fingerprint: str
    context_id: str


class AnalysisExportProtocolService:
    """HTTP-facing protocol service with no executor/model/write capability."""

    def __init__(self, provider: AnalysisExportProvider | None = None) -> None:
        self.provider = provider or FormalReadOnlyProvider()
        self._previews: dict[str, StoredPreview] = {}
        self._artifacts: dict[str, dict[str, Any]] = {}

    @classmethod
    def from_environment(
        cls,
        environment: Mapping[str, str] | None = None,
    ) -> "AnalysisExportProtocolService":
        values = os.environ if environment is None else environment
        tracker = str(values.get("FITNESS_LEDGER_FORMAL_TRACKER_PATH", "")).strip()
        dictionary = str(
            values.get("FITNESS_LEDGER_FORMAL_MOVEMENT_DICTIONARY_PATH", "")
        ).strip()
        formal_dir = str(values.get("FITNESS_LEDGER_FORMAL_DIR", "")).strip()
        if formal_dir and not tracker and not dictionary:
            root = Path(formal_dir).expanduser()
            data_root = root / "data" if (root / "data").is_dir() else root
            tracker = str(data_root / "tracker.json")
            dictionary = str(data_root / "movement_dictionary.json")
        if not tracker and not dictionary:
            return cls(FormalReadOnlyProvider("not_configured"))
        if not tracker or not dictionary:
            return cls(FormalReadOnlyProvider("incomplete_configuration"))
        try:
            return cls(FormalReadOnlyDataSource(tracker, dictionary))
        except (FormalReadOnlyDataSourceError, OSError):
            return cls(FormalReadOnlyProvider("invalid_configuration"))

    @staticmethod
    def _request(payload: dict[str, Any]) -> dict[str, Any]:
        value = payload.get("request")
        if isinstance(value, dict):
            return value
        return payload if "request_version" in payload else {}

    @staticmethod
    def _errors(result: RequestValidationResult) -> list[dict[str, str]]:
        return [item.to_dict() for item in result.errors]

    @staticmethod
    def _execution() -> dict[str, bool]:
        return {"executor_called": False, "formal_data_written": False}

    @staticmethod
    def _structural_preview(result: RequestValidationResult) -> dict[str, Any]:
        normalized = result.normalized_request or {}
        datasets = []
        resolutions = []
        for dataset in normalized.get("datasets", []):
            selector = dataset.get("filters", {}).get("movement_selector")
            resolution = {"status": "pending", "selector": selector} if selector else {"status": "not_requested"}
            datasets.append({
                "dataset_id": dataset["dataset_id"],
                "type": dataset["type"],
                "time_range": dataset["time_range"],
                "fields": dataset["fields"],
                "filters": dataset["filters"],
                "notes_scope": dataset.get("notes_scope"),
                "resolution": resolution,
            })
            if selector:
                resolutions.append({"dataset_id": dataset["dataset_id"], **resolution})
        return {
            "status": "valid" if result.valid else "invalid_request",
            "dataset_count": len(datasets),
            "datasets": datasets,
            "movement_body_part_resolution": resolutions,
            "missing_information": [],
            "warnings": [],
            "progress_exclusion_count": 0,
            "raw": result.preview.get("raw", {"requested": False, "allowed": False, "status": "not_requested"}),
            "execution": AnalysisExportProtocolService._execution(),
            "source_kind": "not_materialized",
            "formal_data_available": False,
        }

    @staticmethod
    def _bundle_preview(bundle: dict[str, Any], provider: AnalysisExportProvider) -> dict[str, Any]:
        quality = bundle.get("quality_profile", {})
        datasets = []
        for item in quality.get("datasets", []):
            requested = next(
                (entry for entry in bundle.get("selected_datasets", []) if entry.get("dataset_id") == item.get("dataset_id")),
                {},
            )
            datasets.append({**requested, **item})
        resolutions = []
        for dataset in bundle.get("selected_datasets", []):
            selector = dataset.get("filters", {}).get("movement_selector")
            if selector:
                matches = provider.resolve(selector)
                resolutions.append({
                    "dataset_id": dataset["dataset_id"],
                    "selector": selector,
                    "status": "resolved" if len(matches) == 1 else "ambiguous" if len(matches) > 1 else "unresolved",
                    "matches": matches,
                })
        safety = bundle.get("safety_flags", {})
        return {
            "status": "preview_ready",
            "source_kind": bundle.get("provenance", {}).get("source_kind", provider.source_kind),
            "formal_data_available": provider.formal_data_available,
            "dataset_count": len(datasets),
            "datasets": datasets,
            "movement_body_part_resolution": resolutions,
            "missing_information": bundle.get("missing_information", []),
            "warnings": bundle.get("warnings", []),
            "progress_exclusion_count": bundle.get("quality_profile", {}).get("progress_exclusions", {}).get("excluded_record_count", 0),
            "raw": {"requested": False, "allowed": False, "status": "not_requested"},
            "record_count": bundle.get("manifest", {}).get("record_count", 0),
            "execution": {
                "executor_called": bool(safety.get("executor_called", False)),
                "formal_data_written": bool(safety.get("formal_data_written", False)),
            },
        }

    def validate(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = validate_request(self._request(payload))
        preview = self._structural_preview(result)
        return {
            "status": "valid" if result.valid else "invalid",
            "schema_version": REQUEST_SCHEMA_VERSION,
            "normalized_request": result.normalized_request or {},
            "errors": self._errors(result),
            "preview": preview,
            "execution": self._execution(),
            "request_interpreter_provider": {
                "provider_id": "local-qwen3",
                "enabled": False,
                "status": "not_connected",
            },
        }

    def preview(self, payload: dict[str, Any]) -> dict[str, Any]:
        request = self._request(payload)
        result = validate_request(request)
        if not result.valid or result.normalized_request is None:
            return {
                "status": "invalid_request",
                "schema_version": REQUEST_SCHEMA_VERSION,
                "normalized_request": {},
                "errors": self._errors(result),
                "preview": self._structural_preview(result),
                "execution": self._execution(),
            }
        normalized = result.normalized_request
        try:
            bundle = self.provider.materialize(normalized)
            preview = self._bundle_preview(bundle, self.provider)
        except MaterializationError as exc:
            status = "movement_resolution_required" if exc.code == "MOVEMENT_RESOLUTION_REQUIRED" else "safety_blocked"
            return {
                "status": status,
                "schema_version": REQUEST_SCHEMA_VERSION,
                "normalized_request": normalized,
                "errors": [{"code": exc.code, "path": "$.datasets", "message": str(exc), "candidates": exc.candidates}],
                "preview": {
                    **self._structural_preview(result),
                    "status": status,
                    "warnings": [str(exc)],
                    "movement_body_part_resolution": [{"status": "required", "candidates": exc.candidates}],
                },
                "execution": self._execution(),
            }
        except AnalysisExportProviderUnavailable:
            availability = getattr(
                self.provider,
                "availability_status",
                "unavailable",
            )
            return {
                "status": "formal_data_unavailable",
                "schema_version": REQUEST_SCHEMA_VERSION,
                "normalized_request": normalized,
                "errors": [],
                "preview": {
                    **self._structural_preview(result),
                    "status": "formal_data_unavailable",
                    "warnings": [
                        "Formal read-only data source is unavailable: "
                        + availability
                    ],
                },
                "execution": self._execution(),
            }
        fingerprint = hashlib.sha256(_canonical(normalized).encode("utf-8")).hexdigest()
        context_id = str(payload.get("preview_context_id", "") or "").strip()
        token = secrets.token_urlsafe(18)
        self._previews[token] = StoredPreview(normalized, fingerprint, context_id)
        return {
            "status": "preview_ready",
            "schema_version": REQUEST_SCHEMA_VERSION,
            "normalized_request": normalized,
            "errors": [],
            "preview": preview,
            "confirmation_token": token,
            "preview_context_id": context_id,
            "preview_fingerprint": fingerprint,
            "execution": self._execution(),
        }

    def resolve(self, payload: dict[str, Any]) -> dict[str, Any]:
        selector = payload.get("selector")
        if not isinstance(selector, dict) or selector.get("kind") not in {"movement_id", "movement_name", "body_part"}:
            return {"status": "invalid_request", "matches": [], "errors": [{"code": "INVALID_SELECTOR", "path": "$.selector", "message": "selector.kind must be movement_id, movement_name, or body_part"}]}
        try:
            matches = self.provider.resolve({"kind": str(selector["kind"]), "value": str(selector.get("value", ""))})
        except AnalysisExportProviderUnavailable:
            return {"status": "formal_data_unavailable", "matches": [], "errors": []}
        return {"status": "resolved" if len(matches) == 1 else "movement_resolution_required" if len(matches) > 1 else "unresolved", "matches": matches, "errors": []}

    def invalidate_preview_context(self, context_id: str) -> int:
        target = str(context_id or "").strip()
        if not target:
            return 0
        tokens = [token for token, stored in self._previews.items() if stored.context_id == target]
        for token in tokens:
            self._previews.pop(token, None)
        return len(tokens)

    def export(self, payload: dict[str, Any]) -> dict[str, Any]:
        token = str(payload.get("confirmation_token", ""))
        stored = self._previews.get(token)
        if payload.get("confirmed") is not True or stored is None:
            return {"status": "confirmation_mismatch", "errors": [{"code": "CONFIRMATION_MISMATCH", "path": "$.confirmation_token", "message": "A matching preview confirmation is required."}], "execution": self._execution()}
        context_id = str(payload.get("preview_context_id", "") or "").strip()
        if context_id != stored.context_id:
            return {"status": "confirmation_mismatch", "errors": [{"code": "CONFIRMATION_MISMATCH", "path": "$.preview_context_id", "message": "The Preview is no longer the active confirmation context."}], "execution": self._execution()}
        result = validate_request(self._request(payload))
        if not result.valid or result.normalized_request is None:
            return {"status": "invalid_request", "errors": self._errors(result), "execution": self._execution()}
        normalized = result.normalized_request
        fingerprint = hashlib.sha256(_canonical(normalized).encode("utf-8")).hexdigest()
        if fingerprint != stored.fingerprint:
            return {"status": "confirmation_mismatch", "errors": [{"code": "CONFIRMATION_MISMATCH", "path": "$.request", "message": "The request changed after Preview."}], "execution": self._execution()}
        try:
            bundle, exports = self.provider.materialize_with_exports(normalized)
        except MaterializationError as exc:
            status = "movement_resolution_required" if exc.code == "MOVEMENT_RESOLUTION_REQUIRED" else "safety_blocked"
            return {"status": status, "errors": [{"code": exc.code, "path": "$.request", "message": str(exc), "candidates": exc.candidates}], "execution": self._execution()}
        except AnalysisExportProviderUnavailable:
            return {"status": "formal_data_unavailable", "errors": [], "execution": self._execution()}
        bundle_json = exports.get("json", json.dumps(bundle, ensure_ascii=False, sort_keys=True))
        artifact_id = "artifact-" + hashlib.sha256(bundle_json.encode("utf-8")).hexdigest()[:24]
        self._artifacts[artifact_id] = {"bundle": bundle, "exports": exports}
        self._previews.pop(token, None)
        safety = bundle.get("safety_flags", {})
        return {
            "status": "bundle_ready",
            "artifact_id": artifact_id,
            "bundle_id": bundle.get("manifest", {}).get("bundle_id", ""),
            "record_count": bundle.get("manifest", {}).get("record_count", 0),
            "formats": sorted(exports),
            "sha256": {format_name: hashlib.sha256(content.encode("utf-8")).hexdigest() for format_name, content in exports.items()},
            "safety_flags": {
                "raw_included": bool(safety.get("raw_included", False)),
                "executor_called": bool(safety.get("executor_called", False)),
                "formal_data_written": bool(safety.get("formal_data_written", False)),
            },
        }

    def artifact(self, artifact_id: str, format_name: str) -> tuple[str, bytes] | None:
        item = self._artifacts.get(artifact_id)
        if not item or format_name not in {"json", "markdown"}:
            return None
        content = item["exports"].get(format_name)
        if content is None:
            return None
        content_type = "application/json; charset=utf-8" if format_name == "json" else "text/markdown; charset=utf-8"
        return content_type, content.encode("utf-8")
