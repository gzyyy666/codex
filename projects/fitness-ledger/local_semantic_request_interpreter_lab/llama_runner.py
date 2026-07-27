"""llama.cpp CLI InferenceProvider and the legacy runner compatibility facade."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

from .inference import (
    EmptyOutputError,
    InferenceProvider,
    InvalidModelOutputError,
    ProcessExitError,
    ProcessStartError,
    ProcessTimeoutError,
    ProviderConfigurationError,
)
from .runtime_config import ModelProfile, RuntimeBundle, RuntimeConfig
from .semantic_hint import SemanticHintRequest, build_semantic_hint_prompt


class LlamaCppCliProvider(InferenceProvider):
    """One-request llama.cpp CLI provider with validated external config."""

    def __init__(self, model_profile: ModelProfile, runtime_config: RuntimeConfig, schema_path: str | Path):
        initialized = time.perf_counter()
        self.model_profile = model_profile
        self.runtime_config = runtime_config
        self.schema_path = Path(schema_path)
        self.prompt_path = Path(__file__).with_name("prompt_v1.txt")
        self.hint_prompt_path = Path(__file__).with_name("prompt_semantic_hint_v1.txt")
        self.catalog_path = self.schema_path.parent.parent / "data" / "capability_catalog.json"
        self.hint_schema_path = self.schema_path.parent / "semantic_hint_v1.schema.json"
        if not self.schema_path.is_file():
            raise ProviderConfigurationError(f"SCHEMA_NOT_FOUND:{self.schema_path}")
        if not self.prompt_path.is_file() or not self.hint_prompt_path.is_file() or not self.catalog_path.is_file() or not self.hint_schema_path.is_file():
            raise ProviderConfigurationError("PROVIDER_PACKAGE_FILES_NOT_FOUND")
        self._last_timing: dict[str, Any] | None = None
        self.initialization_ms = round((time.perf_counter() - initialized) * 1000, 2)

    def get_last_timing(self) -> dict[str, Any] | None:
        return None if self._last_timing is None else dict(self._last_timing)

    @staticmethod
    def _parse_perf_stderr(stderr: str) -> dict[str, Any]:
        """Extract numeric llama.cpp perf summaries without retaining process output."""
        result: dict[str, Any] = {}
        number = r"([0-9]+(?:\.[0-9]+)?)"
        for line in stderr.splitlines():
            lowered = line.lower()
            match = re.search(r"prompt eval time\s*=\s*" + number + r"\s*ms", lowered)
            if match:
                result["prompt_processing_ms"] = round(float(match.group(1)), 2)
                tokens = re.search(r"/\s*([0-9]+)\s+tokens", lowered)
                if tokens:
                    result["prompt_tokens"] = int(tokens.group(1))
                continue
            match = re.search(r"(?:^|\s)eval time\s*=\s*" + number + r"\s*ms", lowered)
            if match:
                result["token_generation_ms"] = round(float(match.group(1)), 2)
                tokens = re.search(r"/\s*([0-9]+)\s+(?:runs|tokens)", lowered)
                if tokens:
                    result["output_tokens"] = int(tokens.group(1))
                continue
            if "model load" in lowered or "load time" in lowered:
                match = re.search(number + r"\s*ms", lowered)
                if match:
                    result["model_load_ms"] = round(float(match.group(1)), 2)
        return result

    def _build_grammar(self, schema_path: Path, prefix: str) -> Path:
        try:
            generated = subprocess.check_output(
                [sys.executable, str(self.runtime_config.effective_grammar_tool_path), str(schema_path)],
                text=True,
                encoding="utf-8",
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ProcessStartError("GRAMMAR_GENERATION_FAILED") from exc
        if not generated.strip():
            raise ProcessStartError("GRAMMAR_GENERATION_EMPTY")
        runtime_dir = self.runtime_config.effective_runtime_directory
        try:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            handle, name = tempfile.mkstemp(prefix=prefix, suffix=".gbnf", dir=runtime_dir)
            os.close(handle)
            grammar_path = Path(name)
            grammar_path.write_text(generated, encoding="utf-8", newline="\n")
            return grammar_path
        except OSError as exc:
            raise ProcessStartError("GRAMMAR_FILE_CREATE_FAILED") from exc

    def build_prompt(self, user_text: str, catalog: dict[str, Any], schema: dict[str, Any]) -> str:
        template = self.prompt_path.read_text(encoding="utf-8")
        schema_hint = "The llama.cpp runtime enforces the RequestDraft JSON Schema separately; emit only the JSON object."
        return template.replace("{{CAPABILITY_CATALOG}}", json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))).replace("{{REQUEST_DRAFT_SCHEMA}}", schema_hint).replace("{{USER_TEXT}}", user_text)

    def build_command(self, prompt: str, grammar_path: str | Path) -> list[str]:
        """Build argv as a list so Windows paths containing spaces stay intact."""
        config = self.runtime_config
        command = [
            str(config.executable_path),
            "--model", str(self.model_profile.model_path),
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
            "--perf",
        ]
        if config.backend == "cuda":
            command.extend(["--n-gpu-layers", str(config.gpu_layers)])
        return command

    @staticmethod
    def _extract_json(output: str) -> str:
        if not output.strip():
            raise EmptyOutputError()
        start = output.find("{")
        end = output.rfind("}")
        if start >= 0 and end > start:
            return output[start : end + 1]
        preview = " ".join(output.split())[:240]
        raise InvalidModelOutputError(f"NO_JSON:{preview}")

    def infer(self, user_text: str) -> str:
        try:
            catalog = json.loads(self.catalog_path.read_text(encoding="utf-8"))
            schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
            prompt = self.build_prompt(user_text, catalog, schema)
        except (OSError, json.JSONDecodeError) as exc:
            raise ProviderConfigurationError("PROVIDER_PACKAGE_FILES_INVALID") from exc
        grammar_path = self._build_grammar(self.schema_path, "request-draft-")
        command = self.build_command(prompt, grammar_path)
        started = time.perf_counter()
        try:
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.runtime_config.timeout_seconds,
                    check=False,
                )
            except subprocess.TimeoutExpired as exc:
                raise ProcessTimeoutError(f"{self.runtime_config.timeout_seconds}s") from exc
            except OSError as exc:
                raise ProcessStartError(type(exc).__name__) from exc
        finally:
            grammar_path.unlink(missing_ok=True)
        _ = round((time.perf_counter() - started) * 1000, 2)
        if completed.returncode != 0:
            raise ProcessExitError(str(completed.returncode))
        return self._extract_json(completed.stdout or "")

    def infer_semantic_hint(self, request: SemanticHintRequest) -> str:
        timing: dict[str, Any] = {
            "provider_initialization_ms": self.initialization_ms,
            "prompt_build_ms": None,
            "schema_prepare_ms": None,
            "grammar_prepare_ms": None,
            "process_start_ms": None,
            "cli_process_wall_ms": None,
            "model_load_ms": None,
            "prompt_processing_ms": None,
            "token_generation_ms": None,
            "prompt_tokens": None,
            "output_tokens": None,
            "output_chars": None,
        }
        prompt_started = time.perf_counter()
        try:
            template = self.hint_prompt_path.read_text(encoding="utf-8")
            prompt = build_semantic_hint_prompt(request, template)
        except OSError as exc:
            raise ProviderConfigurationError("SEMANTIC_HINT_PROMPT_INVALID") from exc
        timing["prompt_build_ms"] = round((time.perf_counter() - prompt_started) * 1000, 2)
        runtime_dir = self.runtime_config.effective_runtime_directory
        dynamic_schema_path: Path | None = None
        schema_started = time.perf_counter()
        try:
            runtime_dir.mkdir(parents=True, exist_ok=True)
            handle, name = tempfile.mkstemp(prefix="semantic-hint-schema-", suffix=".json", dir=runtime_dir)
            os.close(handle)
            dynamic_schema_path = Path(name)
            # The bundled Windows grammar helper opens schema files with the system code page.
            # ASCII JSON keeps escaped Chinese evidence portable without changing its value.
            dynamic_schema_path.write_text(json.dumps(request.to_json_schema(), ensure_ascii=True), encoding="ascii", newline="\n")
        except OSError as exc:
            raise ProcessStartError("SEMANTIC_HINT_SCHEMA_CREATE_FAILED") from exc
        timing["schema_prepare_ms"] = round((time.perf_counter() - schema_started) * 1000, 2)
        grammar_path: Path | None = None
        grammar_started = time.perf_counter()
        try:
            grammar_path = self._build_grammar(dynamic_schema_path, "semantic-hint-")
            timing["grammar_prepare_ms"] = round((time.perf_counter() - grammar_started) * 1000, 2)
            command = self.build_command(prompt, grammar_path)
            process_started = time.perf_counter()
            try:
                completed = subprocess.run(
                    command,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=self.runtime_config.timeout_seconds,
                    check=False,
                )
                timing["cli_process_wall_ms"] = round((time.perf_counter() - process_started) * 1000, 2)
            except subprocess.TimeoutExpired as exc:
                timing["cli_process_wall_ms"] = round((time.perf_counter() - process_started) * 1000, 2)
                self._last_timing = timing
                raise ProcessTimeoutError(f"{self.runtime_config.timeout_seconds}s") from exc
            except OSError as exc:
                timing["cli_process_wall_ms"] = round((time.perf_counter() - process_started) * 1000, 2)
                self._last_timing = timing
                raise ProcessStartError(type(exc).__name__) from exc
        finally:
            if grammar_path is not None:
                grammar_path.unlink(missing_ok=True)
            if dynamic_schema_path is not None:
                dynamic_schema_path.unlink(missing_ok=True)
        timing.update(self._parse_perf_stderr((completed.stderr or "") + "\n" + (completed.stdout or "")))
        timing["output_chars"] = len(completed.stdout or "")
        self._last_timing = timing
        if completed.returncode != 0:
            raise ProcessExitError(str(completed.returncode))
        return self._extract_json(completed.stdout or "")


class LlamaJsonRunner(LlamaCppCliProvider):
    """Compatibility facade for the pre-plugin ``LlamaJsonRunner`` constructor."""

    def __init__(self, executable: str | Path, model: str | Path, schema_path: str | Path, timeout_seconds: int = 180, gpu_layers: int = 0):
        bundle = RuntimeBundle.from_legacy_args(executable, model, gpu_layers=gpu_layers, timeout_seconds=timeout_seconds)
        super().__init__(bundle.model_profile, bundle.runtime_config, schema_path)


def run_once(executable: str, model: str, schema_path: str, user_text: str, timeout_seconds: int = 180) -> tuple[str, float]:
    runner = LlamaJsonRunner(executable, model, schema_path, timeout_seconds)
    started = time.perf_counter()
    output = runner.infer(user_text)
    return output, round((time.perf_counter() - started) * 1000, 2)
