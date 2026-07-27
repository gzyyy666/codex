"""Provider contract and explicit local inference error taxonomy."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .semantic_hint import SemanticHintRequest


class InferenceError(RuntimeError):
    """Base error raised by a local inference provider."""

    code = "INFERENCE_ERROR"

    def __init__(self, detail: str = "") -> None:
        message = self.code if not detail else f"{self.code}:{detail}"
        super().__init__(message)


class ProviderConfigurationError(InferenceError):
    """Configuration is invalid; a model process must not be started."""

    code = "PROVIDER_CONFIG_ERROR"


class ProviderRuntimeError(InferenceError):
    """The configured provider could not complete a model invocation."""

    code = "MODEL_RUNTIME_FAILURE"


class ProviderOutputError(InferenceError):
    """The provider completed but did not return a usable model payload."""

    code = "MODEL_INVALID_OUTPUT"


class ProcessStartError(ProviderRuntimeError):
    code = "MODEL_PROCESS_START_FAILED"


class ProcessTimeoutError(ProviderRuntimeError):
    code = "MODEL_TIMEOUT"


class ProcessExitError(ProviderRuntimeError):
    code = "MODEL_NONZERO_EXIT"


class EmptyOutputError(ProviderOutputError):
    code = "MODEL_EMPTY_OUTPUT"


class InvalidModelOutputError(ProviderOutputError):
    code = "MODEL_INVALID_OUTPUT"


# Kept as a compatibility name for code that imported the old runner error.
ModelUnavailable = ProviderRuntimeError


class InferenceProvider(ABC):
    """Small provider contract consumed by Core, CLI, and evaluation code."""

    @abstractmethod
    def infer(self, user_text: str) -> str:
        """Return one raw model response for one user request."""

    def infer_semantic_hint(self, request: "SemanticHintRequest") -> str:
        """Return a narrow hint; legacy providers must opt into this task explicitly."""
        raise ProviderConfigurationError("SEMANTIC_HINT_PROVIDER_UNSUPPORTED")

    def __call__(self, user_text: str) -> str:
        return self.infer(user_text)
