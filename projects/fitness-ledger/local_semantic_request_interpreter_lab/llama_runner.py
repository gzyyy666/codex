"""Isolated llama.cpp runner with bounded, single-request subprocesses."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from .core import ModelUnavailable


class LlamaJsonRunner:
    def __init__(self, executable: str | Path, model: str | Path, schema_path: str | Path, timeout_seconds: int = 90):
        self.executable = Path(executable)
        self.model = Path(model)
        self.schema_path = Path(schema_path)
        self.timeout_seconds = timeout_seconds

    def _build_grammar(self) -> Path:
        script = self.executable.parent.parent / "json_schema_to_grammar.py"
        if not script.is_file():
            raise ModelUnavailable("JSON_SCHEMA_GRAMMAR_TOOL_NOT_FOUND")
        try:
            generated = subprocess.check_output([sys.executable, str(script), str(self.schema_path)], text=True, encoding="utf-8")
        except (OSError, subprocess.CalledProcessError) as exc:
            raise ModelUnavailable("JSON_SCHEMA_GRAMMAR_GENERATION_FAILED") from exc
        runtime_dir = self.executable.parent.parent / "runs"
        runtime_dir.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(prefix="request-draft-", suffix=".gbnf", dir=runtime_dir)
        os.close(handle)
        Path(name).write_text(generated, encoding="utf-8", newline="\n")
        return Path(name)

    def build_prompt(self, user_text: str, catalog: dict, schema: dict) -> str:
        template = (Path(__file__).with_name("prompt_v1.txt")).read_text(encoding="utf-8")
        # The runtime receives the full schema through --json-schema. Repeating
        # it in the prompt needlessly consumes context and slows small models.
        schema_hint = "The llama.cpp runtime enforces the RequestDraft JSON Schema separately; emit only the JSON object."
        return template.replace("{{CAPABILITY_CATALOG}}", json.dumps(catalog, ensure_ascii=False, separators=(",", ":"))).replace("{{REQUEST_DRAFT_SCHEMA}}", schema_hint).replace("{{USER_TEXT}}", user_text)

    def __call__(self, user_text: str) -> str:
        if not self.executable.is_file() or not self.model.is_file() or not self.schema_path.is_file():
            raise ModelUnavailable("MODEL_RUNTIME_NOT_FOUND")
        catalog_path = self.schema_path.parent.parent / "data" / "capability_catalog.json"
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
        schema = json.loads(self.schema_path.read_text(encoding="utf-8"))
        prompt = self.build_prompt(user_text, catalog, schema)
        grammar_path = self._build_grammar()
        command = [
            str(self.executable),
            "--model", str(self.model),
            "--grammar-file", str(grammar_path),
            "--prompt", prompt,
            "--n-predict", "640",
            "--ctx-size", "4096",
            "--threads", "2",
            "--threads-batch", "2",
            "--temp", "0",
            "--top-k", "1",
            "--no-display-prompt",
            "--no-conversation",
            "--single-turn",
            "--simple-io",
        ]
        started = time.perf_counter()
        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=self.timeout_seconds, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ModelUnavailable(f"MODEL_RUNTIME_FAILURE:{type(exc).__name__}") from exc
        finally:
            grammar_path.unlink(missing_ok=True)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
        if completed.returncode != 0:
            raise ModelUnavailable(f"MODEL_RUNTIME_EXIT:{completed.returncode}")
        output = completed.stdout.strip()
        if not output:
            raise ModelUnavailable("MODEL_EMPTY_OUTPUT")
        # llama-cli may print its startup banner to stdout even with
        # --no-display-prompt. Keep strict JSON parsing downstream by
        # extracting only the outer JSON object; malformed output still fails
        # closed in core.parse_json_strict.
        start = output.find("{")
        end = output.rfind("}")
        if start >= 0 and end > start:
            return output[start : end + 1]
        preview = " ".join(output.split())[:240]
        raise ModelUnavailable(f"MODEL_NO_JSON:{preview}")


def run_once(executable: str, model: str, schema_path: str, user_text: str, timeout_seconds: int = 90) -> tuple[str, float]:
    runner = LlamaJsonRunner(executable, model, schema_path, timeout_seconds)
    started = time.perf_counter()
    output = runner(user_text)
    return output, round((time.perf_counter() - started) * 1000, 2)
