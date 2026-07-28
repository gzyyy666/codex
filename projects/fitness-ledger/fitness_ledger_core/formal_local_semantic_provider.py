"""External llama.cpp provider for the formal narrow SemanticHint contract."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .formal_local_semantic_hint import SemanticHintRequest, build_prompt


class ProviderError(RuntimeError):
    pass


class ProviderConfigurationError(ProviderError):
    pass


class ProviderUnavailableError(ProviderError):
    pass


class ProviderTimeoutError(ProviderUnavailableError):
    pass


class ProviderOutputError(ProviderError):
    pass


class InferenceProvider(ABC):
    @abstractmethod
    def infer_semantic_hint(self, request: SemanticHintRequest) -> str:
        raise NotImplementedError


@dataclass(frozen=True)
class ModelProfile:
    name: str
    model_path: Path
    format: str = "gguf"

    def validate(self) -> None:
        if not self.name.strip():
            raise ProviderConfigurationError("MODEL_NAME_REQUIRED")
        if self.format != "gguf":
            raise ProviderConfigurationError("MODEL_FORMAT_UNSUPPORTED")
        if not self.model_path.is_file():
            raise ProviderConfigurationError(f"MODEL_NOT_FOUND:{self.model_path}")


@dataclass(frozen=True)
class RuntimeConfig:
    executable_path: Path
    grammar_tool_path: Path
    runtime_directory: Path
    backend: str = "cuda"
    gpu_layers: int = 99
    timeout_seconds: int = 60
    n_predict: int = 640
    ctx_size: int = 4096
    threads: int = 4
    threads_batch: int = 2
    temperature: float = 0.0
    top_k: int = 1

    def validate(self) -> None:
        if self.backend not in {"cpu", "cuda"}:
            raise ProviderConfigurationError("BACKEND_INVALID")
        for name in ("timeout_seconds", "n_predict", "ctx_size", "threads", "threads_batch", "top_k"):
            if isinstance(getattr(self, name), bool) or not isinstance(getattr(self, name), int) or getattr(self, name) <= 0:
                raise ProviderConfigurationError(f"RUNTIME_RANGE_INVALID:{name}")
        if not isinstance(self.gpu_layers, int) or self.gpu_layers < 0:
            raise ProviderConfigurationError("RUNTIME_RANGE_INVALID:gpu_layers")
        if self.backend == "cpu" and self.gpu_layers:
            raise ProviderConfigurationError("CPU_GPU_LAYERS_CONFLICT")
        if self.backend == "cuda" and self.gpu_layers <= 0:
            raise ProviderConfigurationError("CUDA_GPU_LAYERS_REQUIRED")
        if not isinstance(self.temperature, (int, float)) or not 0 <= self.temperature <= 2:
            raise ProviderConfigurationError("RUNTIME_RANGE_INVALID:temperature")
        if not self.executable_path.is_file():
            raise ProviderConfigurationError(f"EXECUTABLE_NOT_FOUND:{self.executable_path}")
        if not self.grammar_tool_path.is_file():
            raise ProviderConfigurationError(f"GRAMMAR_TOOL_NOT_FOUND:{self.grammar_tool_path}")


@dataclass(frozen=True)
class RuntimeBundle:
    model_profile: ModelProfile
    runtime_config: RuntimeConfig

    def validate(self) -> None:
        self.model_profile.validate()
        self.runtime_config.validate()


def load_runtime_bundle(path: str | Path) -> RuntimeBundle:
    config_path = Path(path)
    try:
        value = json.loads(config_path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ProviderConfigurationError(f"CONFIG_NOT_FOUND:{config_path}") from exc
    except json.JSONDecodeError as exc:
        raise ProviderConfigurationError(f"CONFIG_INVALID_JSON:{config_path}") from exc
    if not isinstance(value, dict) or set(value) != {"model_profile", "runtime_config"}:
        raise ProviderConfigurationError("CONFIG_ROOT_INVALID")
    model = value["model_profile"]
    runtime = value["runtime_config"]
    if not isinstance(model, dict) or not isinstance(runtime, dict):
        raise ProviderConfigurationError("CONFIG_SECTION_INVALID")
    bundle = RuntimeBundle(
        ModelProfile(str(model.get("name", "")), Path(str(model.get("model_path", ""))), str(model.get("format", "gguf"))),
        RuntimeConfig(
            executable_path=Path(str(runtime.get("executable_path", ""))),
            grammar_tool_path=Path(str(runtime.get("grammar_tool_path", ""))),
            runtime_directory=Path(str(runtime.get("runtime_directory", ""))),
            backend=str(runtime.get("backend", "cuda")),
            gpu_layers=runtime.get("gpu_layers", 99),
            timeout_seconds=runtime.get("timeout_seconds", 60),
            n_predict=runtime.get("n_predict", 640),
            ctx_size=runtime.get("ctx_size", 4096),
            threads=runtime.get("threads", 4),
            threads_batch=runtime.get("threads_batch", 2),
            temperature=runtime.get("temperature", 0.0),
            top_k=runtime.get("top_k", 1),
        ),
    )
    bundle.validate()
    return bundle


class LlamaCppCliSemanticHintProvider(InferenceProvider):
    def __init__(self, bundle: RuntimeBundle, prompt_path: str | Path | None = None) -> None:
        bundle.validate()
        self.bundle = bundle
        self.prompt_path = Path(prompt_path) if prompt_path else Path(__file__).with_name("formal_semantic_hint_prompt.txt")
        if not self.prompt_path.is_file():
            raise ProviderConfigurationError(f"PROMPT_NOT_FOUND:{self.prompt_path}")

    def build_command(self, prompt: str, grammar_path: Path) -> list[str]:
        model, config = self.bundle.model_profile, self.bundle.runtime_config
        command = [
            str(config.executable_path),
            "--model", str(model.model_path),
            "--grammar-file", str(grammar_path),
            "--prompt", prompt,
            "--n-predict", str(config.n_predict),
            "--ctx-size", str(config.ctx_size),
            "--threads", str(config.threads),
            "--threads-batch", str(config.threads_batch),
            "--temp", str(config.temperature),
            "--top-k", str(config.top_k),
            "--no-display-prompt",
            "--no-conversation",
            "--single-turn",
            "--simple-io",
        ]
        if config.backend == "cuda":
            command.extend(["--n-gpu-layers", str(config.gpu_layers)])
        return command

    @staticmethod
    def _extract_json(output: str) -> str:
        start, end = output.find("{"), output.rfind("}")
        if start < 0 or end <= start:
            if not output.strip():
                raise ProviderOutputError("EMPTY_OUTPUT")
            raise ProviderOutputError("NO_JSON_OBJECT")
        return output[start:end + 1]

    def infer_semantic_hint(self, request: SemanticHintRequest) -> str:
        config = self.bundle.runtime_config
        try:
            template = self.prompt_path.read_text(encoding="utf-8")
            prompt = build_prompt(request, template)
        except OSError as exc:
            raise ProviderConfigurationError("PROMPT_READ_FAILED") from exc
        config.runtime_directory.mkdir(parents=True, exist_ok=True)
        schema_path: Path | None = None
        grammar_path: Path | None = None
        try:
            schema_fd, schema_name = tempfile.mkstemp(
                prefix="formal-semantic-hint-", suffix=".json", dir=config.runtime_directory
            )
            os.close(schema_fd)
            schema_path = Path(schema_name)
            schema_path.write_text(
                json.dumps(request.to_json_schema(), ensure_ascii=True),
                encoding="ascii",
                newline="\n",
            )
            try:
                grammar = subprocess.check_output(
                    [sys.executable, str(config.grammar_tool_path), str(schema_path)],
                    text=True,
                    encoding="utf-8",
                    timeout=min(config.timeout_seconds, 30),
                )
            except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                raise ProviderUnavailableError("GRAMMAR_GENERATION_FAILED") from exc
            if not grammar.strip():
                raise ProviderUnavailableError("GRAMMAR_GENERATION_EMPTY")
            grammar_fd, grammar_name = tempfile.mkstemp(
                prefix="formal-semantic-hint-", suffix=".gbnf", dir=config.runtime_directory
            )
            os.close(grammar_fd)
            grammar_path = Path(grammar_name)
            grammar_path.write_text(grammar, encoding="utf-8", newline="\n")
            try:
                completed = subprocess.run(
                    self.build_command(prompt, grammar_path),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=config.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ProviderTimeoutError(f"MODEL_TIMEOUT:{config.timeout_seconds}") from exc
            except OSError as exc:
                raise ProviderUnavailableError(f"PROCESS_START_FAILED:{type(exc).__name__}") from exc
            if completed.returncode != 0:
                raise ProviderUnavailableError(f"PROCESS_EXIT:{completed.returncode}")
            return self._extract_json(completed.stdout or "")
        finally:
            if grammar_path is not None:
                grammar_path.unlink(missing_ok=True)
            if schema_path is not None:
                schema_path.unlink(missing_ok=True)
