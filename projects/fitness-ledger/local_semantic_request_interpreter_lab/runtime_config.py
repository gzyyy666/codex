"""Validated model and runtime configuration with legacy CLI compatibility."""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Mapping

from .inference import ProviderConfigurationError


def _path(value: Any, label: str) -> Path:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value.strip():
        return Path(value)
    raise ProviderConfigurationError(f"CONFIG_INVALID_TYPE:{label}")


def _strict_mapping(value: Any, label: str, allowed: set[str]) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ProviderConfigurationError(f"CONFIG_INVALID_TYPE:{label}")
    unknown = set(value) - allowed
    if unknown:
        raise ProviderConfigurationError(f"CONFIG_UNKNOWN_FIELDS:{label}:{sorted(unknown)}")
    return dict(value)


@dataclass(frozen=True)
class ModelProfile:
    """Model identity and artifact location; no process/runtime flags."""

    name: str
    model_path: Path
    format: str = "gguf"

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ProviderConfigurationError("CONFIG_INVALID_TYPE:model_profile.name")
        object.__setattr__(self, "model_path", _path(self.model_path, "model_profile.model_path"))
        if self.format != "gguf":
            raise ProviderConfigurationError("CONFIG_UNSUPPORTED_MODEL_FORMAT:gguf")
        if not self.model_path.is_file():
            raise ProviderConfigurationError(f"CONFIG_MODEL_NOT_FOUND:{self.model_path}")

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ModelProfile":
        data = _strict_mapping(value, "model_profile", {"name", "model_path", "format"})
        if "name" not in data or "model_path" not in data:
            raise ProviderConfigurationError("CONFIG_MISSING_FIELDS:model_profile")
        return cls(data["name"], _path(data["model_path"], "model_profile.model_path"), data.get("format", "gguf"))


@dataclass(frozen=True)
class RuntimeConfig:
    """Provider process configuration, independent from a particular model."""

    executable_path: Path
    backend: str = "cpu"
    gpu_layers: int = 0
    timeout_seconds: int = 180
    n_predict: int = 640
    ctx_size: int = 4096
    threads: int = 2
    threads_batch: int = 2
    temperature: float = 0.0
    top_k: int = 1
    grammar_tool_path: Path | None = None
    runtime_directory: Path | None = None
    provider: str = "llama_cpp_cli"

    def __post_init__(self) -> None:
        object.__setattr__(self, "executable_path", _path(self.executable_path, "runtime_config.executable_path"))
        if self.grammar_tool_path is not None:
            object.__setattr__(self, "grammar_tool_path", _path(self.grammar_tool_path, "runtime_config.grammar_tool_path"))
        if self.runtime_directory is not None:
            object.__setattr__(self, "runtime_directory", _path(self.runtime_directory, "runtime_config.runtime_directory"))
        if not isinstance(self.provider, str) or self.provider != "llama_cpp_cli":
            raise ProviderConfigurationError("CONFIG_UNSUPPORTED_PROVIDER:llama_cpp_cli")
        if self.backend not in {"cpu", "cuda"}:
            raise ProviderConfigurationError("CONFIG_INVALID_BACKEND:cpu_or_cuda")
        for name, value, low, high in (
            ("gpu_layers", self.gpu_layers, 0, 999),
            ("timeout_seconds", self.timeout_seconds, 1, 3600),
            ("n_predict", self.n_predict, 1, 16384),
            ("ctx_size", self.ctx_size, 128, 131072),
            ("threads", self.threads, 1, 256),
            ("threads_batch", self.threads_batch, 1, 256),
            ("top_k", self.top_k, 0, 100),
        ):
            if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
                raise ProviderConfigurationError(f"CONFIG_INVALID_RANGE:{name}")
        if isinstance(self.temperature, bool) or not isinstance(self.temperature, (int, float)) or not 0 <= self.temperature <= 2:
            raise ProviderConfigurationError("CONFIG_INVALID_RANGE:temperature")
        if self.backend == "cpu" and self.gpu_layers != 0:
            raise ProviderConfigurationError("CONFIG_CPU_GPU_LAYERS_CONFLICT")
        if self.backend == "cuda" and self.gpu_layers < 1:
            raise ProviderConfigurationError("CONFIG_CUDA_REQUIRES_GPU_LAYERS")
        if not self.executable_path.is_file():
            raise ProviderConfigurationError(f"CONFIG_EXECUTABLE_NOT_FOUND:{self.executable_path}")
        if self.backend == "cuda" and not (self.executable_path.parent / "ggml-cuda.dll").is_file():
            raise ProviderConfigurationError(f"CONFIG_CUDA_RUNTIME_MISSING:{self.executable_path.parent / 'ggml-cuda.dll'}")
        grammar_tool = self.effective_grammar_tool_path
        if not grammar_tool.is_file():
            raise ProviderConfigurationError(f"CONFIG_GRAMMAR_TOOL_NOT_FOUND:{grammar_tool}")

    @property
    def effective_grammar_tool_path(self) -> Path:
        return self.grammar_tool_path or self.executable_path.parent.parent / "json_schema_to_grammar.py"

    @property
    def effective_runtime_directory(self) -> Path:
        return self.runtime_directory or self.executable_path.parent.parent / "runs"

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "RuntimeConfig":
        allowed = {
            "executable_path", "backend", "gpu_layers", "timeout_seconds", "n_predict", "ctx_size",
            "threads", "threads_batch", "temperature", "top_k", "grammar_tool_path", "runtime_directory", "provider",
        }
        data = _strict_mapping(value, "runtime_config", allowed)
        if "executable_path" not in data:
            raise ProviderConfigurationError("CONFIG_MISSING_FIELDS:runtime_config")
        return cls(**data)


@dataclass(frozen=True)
class RuntimeBundle:
    """The selected model profile paired with its provider runtime config."""

    model_profile: ModelProfile
    runtime_config: RuntimeConfig

    @classmethod
    def from_json_file(cls, path: str | Path, overrides: Mapping[str, Any] | None = None) -> "RuntimeBundle":
        config_path = _path(path, "runtime_config_file")
        if not config_path.is_file():
            raise ProviderConfigurationError(f"CONFIG_FILE_NOT_FOUND:{config_path}")
        try:
            value = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderConfigurationError(f"CONFIG_FILE_INVALID:{config_path}") from exc
        data = _strict_mapping(value, "runtime_config_file", {"model_profile", "runtime_config"})
        if "model_profile" not in data or "runtime_config" not in data:
            raise ProviderConfigurationError("CONFIG_MISSING_FIELDS:runtime_config_file")
        model_data = _strict_mapping(data["model_profile"], "model_profile", {"name", "model_path", "format"})
        runtime_data = _strict_mapping(data["runtime_config"], "runtime_config", {
            "executable_path", "backend", "gpu_layers", "timeout_seconds", "n_predict", "ctx_size",
            "threads", "threads_batch", "temperature", "top_k", "grammar_tool_path", "runtime_directory", "provider",
        })
        if overrides:
            if overrides.get("model_path") is not None:
                model_data["model_path"] = overrides["model_path"]
            if overrides.get("executable_path") is not None:
                runtime_data["executable_path"] = overrides["executable_path"]
            for key in ("backend", "gpu_layers", "timeout_seconds"):
                if overrides.get(key) is not None:
                    runtime_data[key] = overrides[key]
            if overrides.get("gpu_layers") is not None and overrides.get("backend") is None and isinstance(overrides["gpu_layers"], int) and not isinstance(overrides["gpu_layers"], bool):
                runtime_data["backend"] = "cuda" if overrides["gpu_layers"] > 0 else "cpu"
        return cls(ModelProfile.from_mapping(model_data), RuntimeConfig.from_mapping(runtime_data))

    @classmethod
    def from_legacy_args(
        cls,
        executable_path: str | Path,
        model_path: str | Path,
        *,
        backend: str | None = None,
        gpu_layers: int | None = None,
        timeout_seconds: int | None = None,
    ) -> "RuntimeBundle":
        layers = 0 if gpu_layers is None else gpu_layers
        selected_backend = backend or ("cuda" if isinstance(layers, int) and not isinstance(layers, bool) and layers > 0 else "cpu")
        profile = ModelProfile(Path(model_path).stem, _path(model_path, "model_profile.model_path"))
        runtime = RuntimeConfig(_path(executable_path, "runtime_config.executable_path"), backend=selected_backend, gpu_layers=layers, timeout_seconds=180 if timeout_seconds is None else timeout_seconds)
        return cls(profile, runtime)

    def with_overrides(self, **overrides: Any) -> "RuntimeBundle":
        model = self.model_profile
        runtime = self.runtime_config
        model_updates = {}
        runtime_updates = {}
        if overrides.get("model_path") is not None:
            model_updates["model_path"] = _path(overrides["model_path"], "model_profile.model_path")
        if overrides.get("executable_path") is not None:
            runtime_updates["executable_path"] = _path(overrides["executable_path"], "runtime_config.executable_path")
        for key in ("backend", "gpu_layers", "timeout_seconds"):
            if overrides.get(key) is not None:
                runtime_updates[key] = overrides[key]
        if overrides.get("gpu_layers") is not None and overrides.get("backend") is None:
            layers = overrides["gpu_layers"]
            if isinstance(layers, int) and not isinstance(layers, bool):
                runtime_updates["backend"] = "cuda" if layers > 0 else "cpu"
        return RuntimeBundle(replace(model, **model_updates), replace(runtime, **runtime_updates))


def load_runtime_bundle(
    config_path: str | Path | None = None,
    *,
    model_path: str | Path | None = None,
    executable_path: str | Path | None = None,
    backend: str | None = None,
    gpu_layers: int | None = None,
    timeout_seconds: int | None = None,
) -> RuntimeBundle:
    """Load defaults, then JSON config, then explicit CLI overrides."""
    if config_path is not None:
        return RuntimeBundle.from_json_file(config_path, overrides={
            "model_path": model_path,
            "executable_path": executable_path,
            "backend": backend,
            "gpu_layers": gpu_layers,
            "timeout_seconds": timeout_seconds,
        })
    if model_path is None or executable_path is None:
        raise ProviderConfigurationError("CONFIG_MISSING_LEGACY_PATHS:model_and_executable")
    return RuntimeBundle.from_legacy_args(
        executable_path,
        model_path,
        backend=backend,
        gpu_layers=gpu_layers,
        timeout_seconds=timeout_seconds,
    )
