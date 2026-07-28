"""Composition boundary for a future Web intelligent-preview route."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .formal_analysis_request_adapter import FormalAnalysisRequestAdapter
from .formal_local_semantic_provider import (
    LlamaCppCliSemanticHintProvider,
    ProviderError,
    load_runtime_bundle,
)


class FormalAnalysisRequestPreviewService:
    """Preview a formal Request; never reads data, materializes exports, or executes."""

    def __init__(
        self,
        adapter: FormalAnalysisRequestAdapter,
        *,
        provider_configuration_error: str | None = None,
    ) -> None:
        self._adapter = adapter
        self.provider_configuration_error = provider_configuration_error

    @classmethod
    def from_runtime_config(
        cls,
        config_path: str | Path,
    ) -> "FormalAnalysisRequestPreviewService":
        try:
            provider = LlamaCppCliSemanticHintProvider(load_runtime_bundle(config_path))
        except ProviderError as exc:
            return cls(
                FormalAnalysisRequestAdapter(),
                provider_configuration_error=type(exc).__name__,
            )
        return cls(FormalAnalysisRequestAdapter(provider))

    def preview(self, user_text: str) -> dict[str, Any]:
        return self._adapter.preview(user_text)


__all__ = ["FormalAnalysisRequestPreviewService"]
