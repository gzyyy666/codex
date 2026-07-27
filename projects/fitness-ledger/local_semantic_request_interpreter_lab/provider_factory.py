"""Provider selection boundary for the local inference runtime."""

from __future__ import annotations

from pathlib import Path

from .inference import InferenceProvider, ProviderConfigurationError
from .llama_runner import LlamaCppCliProvider
from .runtime_config import RuntimeBundle


def create_inference_provider(bundle: RuntimeBundle, schema_path: str | Path) -> InferenceProvider:
    """Create the configured provider without exposing process details upstream."""
    if bundle.runtime_config.provider != "llama_cpp_cli":
        raise ProviderConfigurationError("CONFIG_UNSUPPORTED_PROVIDER:llama_cpp_cli")
    return LlamaCppCliProvider(bundle.model_profile, bundle.runtime_config, schema_path)
