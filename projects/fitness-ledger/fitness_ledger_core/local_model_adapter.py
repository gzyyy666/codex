"""Local model boundary for intelligent export.

Only this module knows how to speak to Ollama.  Business services depend on
the small ``LocalModelAdapter`` protocol and can therefore be tested with the
deterministic fake adapter without a running model.
"""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .intelligent_export_models import ModelCallResult


class LocalModelError(RuntimeError):
    def __init__(self, message: str, code: str = "MODEL_ERROR") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ModelConfig:
    temperature: float
    num_ctx: int
    num_predict: int
    timeout: float
    think: bool = False
    stream: bool = False
    keep_alive: str | int = 0
    ensure_ascii: bool = False


INTENT_MODEL_CONFIG = ModelConfig(0.05, 4096, 800, 30.0)
PLANNING_MODEL_CONFIG = ModelConfig(0.05, 8192, 1600, 60.0)
REPAIR_MODEL_CONFIG = ModelConfig(0.0, 4096, 1400, 30.0)


class LocalModelAdapter(Protocol):
    adapter_name: str
    model_name: str

    def health_check(self, timeout: float = 2.0) -> dict: ...

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_payload: dict,
        response_schema: dict,
        config: ModelConfig,
    ) -> ModelCallResult: ...


class FakeLocalModelAdapter:
    """A queue-backed adapter used by all automated tests."""

    adapter_name = "fake"
    model_name = "fake-model"

    def __init__(self, responses: list[Any] | None = None, errors: list[Exception] | None = None) -> None:
        self.responses = list(responses or [])
        self.errors = list(errors or [])
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    def health_check(self, timeout: float = 2.0) -> dict:
        return {"available": True, "adapter": self.adapter_name, "model": self.model_name}

    def generate_json(self, *, system_prompt: str, user_payload: dict, response_schema: dict, config: ModelConfig) -> ModelCallResult:
        with self._lock:
            self.calls.append({
                "system_prompt": system_prompt,
                "user_payload": user_payload,
                "response_schema": response_schema,
                "config": config,
            })
            if self.errors:
                error = self.errors.pop(0)
                raise error
            if not self.responses:
                raise LocalModelError("Fake adapter has no response.", "MODEL_UNAVAILABLE")
            response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        raw = response if isinstance(response, str) else json.dumps(response, ensure_ascii=False)
        return ModelCallResult(raw, self.adapter_name, self.model_name, 0, output_chars=len(raw))


class OllamaNativeAdapter:
    """Ollama's native REST adapter; it never manages the Ollama process."""

    adapter_name = "ollama-native"

    def __init__(self, base_url: str = "http://127.0.0.1:11434", model: str = "qwen3:4b", keep_alive: str | int = 0) -> None:
        self.base_url = base_url.rstrip("/")
        self.model_name = model
        self.keep_alive = keep_alive
        self._request_slots = threading.BoundedSemaphore(1)

    def health_check(self, timeout: float = 2.0) -> dict:
        request = urllib.request.Request(f"{self.base_url}/api/tags", method="GET")
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return {"available": True, "adapter": self.adapter_name, "model": self.model_name, "tags": len(payload.get("models", [])) if isinstance(payload, dict) else 0}
        except urllib.error.HTTPError as exc:
            return {"available": False, "code": "MODEL_HTTP_ERROR", "status": exc.code}
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            return {"available": False, "code": "MODEL_UNAVAILABLE", "error": str(exc)[:160]}

    def generate_json(self, *, system_prompt: str, user_payload: dict, response_schema: dict, config: ModelConfig) -> ModelCallResult:
        if not self._request_slots.acquire(timeout=max(0.1, min(config.timeout, 5.0))):
            raise LocalModelError("Ollama is busy with another Fitness Ledger request.", "MODEL_BUSY")
        try:
            payload = {
                "model": self.model_name,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": json.dumps(user_payload, ensure_ascii=config.ensure_ascii, separators=(",", ":"))},
                ],
                "stream": bool(config.stream),
                "think": bool(config.think),
                "format": response_schema,
                "options": {
                    "temperature": config.temperature,
                    "num_ctx": config.num_ctx,
                    "num_predict": config.num_predict,
                },
                "keep_alive": config.keep_alive if config.keep_alive is not None else self.keep_alive,
            }
            body = json.dumps(payload, ensure_ascii=config.ensure_ascii).encode("utf-8")
            request = urllib.request.Request(
                f"{self.base_url}/api/chat",
                data=body,
                method="POST",
                headers={"Content-Type": "application/json"},
            )
            started = time.monotonic()
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    with urllib.request.urlopen(request, timeout=config.timeout) as response:
                        status = int(getattr(response, "status", 200) or 200)
                        response_body = response.read()
                        result = json.loads(response_body.decode("utf-8"))
                    if not isinstance(result, dict):
                        raise LocalModelError("Ollama response is not an object.", "MODEL_INVALID_JSON")
                    message = result.get("message") or {}
                    content = message.get("content") if isinstance(message, dict) else None
                    if not isinstance(content, str) or not content.strip():
                        raise LocalModelError("Ollama response has no message content.", "MODEL_EMPTY_RESPONSE")
                    finish = str(result.get("done_reason", result.get("finish_reason", "")))
                    eval_count = int(result.get("eval_count", 0) or 0)
                    prompt_eval_count = int(result.get("prompt_eval_count", 0) or 0)
                    truncated = finish in {"length", "max_tokens", "stop_limit"} or (not bool(result.get("done", True)))
                    return ModelCallResult(
                        content, self.adapter_name, self.model_name,
                        int((time.monotonic() - started) * 1000),
                        sorted(str(k) for k in result.keys()),
                        sorted(str(k) for k in message.keys()) if isinstance(message, dict) else [],
                        finish, eval_count, prompt_eval_count, truncated, len(content), status, len(response_body),
                        int(result.get("load_duration", 0) or 0), int(result.get("prompt_eval_duration", 0) or 0), int(result.get("eval_duration", 0) or 0),
                    )
                except urllib.error.HTTPError as exc:
                    raise LocalModelError(f"Ollama HTTP {exc.code}.", "MODEL_CONNECTION_ERROR") from exc
                except json.JSONDecodeError as exc:
                    last_error = LocalModelError("Ollama returned invalid JSON.", "MODEL_INVALID_JSON")
                    if attempt == 0:
                        continue
                except (socket.timeout, TimeoutError) as exc:
                    last_error = LocalModelError("Ollama request timed out.", "MODEL_TIMEOUT")
                    if attempt == 0:
                        continue
                except (OSError, urllib.error.URLError, LocalModelError) as exc:
                    last_error = exc
                    if isinstance(exc, LocalModelError) and exc.code not in {"MODEL_INVALID_RESPONSE", "MODEL_EMPTY_RESPONSE"}:
                        raise exc
                    if attempt == 0:
                        continue
            if isinstance(last_error, LocalModelError):
                raise last_error
            raise LocalModelError(str(last_error or "Ollama request failed."), "MODEL_UNAVAILABLE")
        finally:
            self._request_slots.release()
