from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import requests

from app.shared.operational_error import (
    OperationalError,
    create_operational_error,
)


class OllamaRequestError(RuntimeError):
    """A visible, actionable failure while contacting local Ollama."""


@dataclass(frozen=True)
class OllamaRequestPolicy:
    """Optional, per-call Ollama protocol settings.

    An empty policy deliberately serializes to the historical request payload.
    """

    format: str | Mapping[str, object] | None = None
    think: bool | None = None
    options: Mapping[str, object] | None = None
    timeout: float | tuple[float, float] | None = None

    def __post_init__(self):
        if isinstance(self.format, Mapping):
            object.__setattr__(
                self,
                "format",
                MappingProxyType(dict(self.format)),
            )
        if self.options is not None:
            object.__setattr__(
                self,
                "options",
                MappingProxyType(dict(self.options)),
            )


@dataclass(frozen=True)
class OllamaResponseMetadata:
    requested_model: str
    response_model: str | None
    created_at: str | None
    policy: OllamaRequestPolicy
    done: bool | None
    done_reason: str | None
    prompt_length: int
    content_length: int
    prompt_sha256: str
    content_sha256: str
    prompt_eval_count: int | None
    eval_count: int | None
    total_duration: int | None
    load_duration: int | None
    prompt_eval_duration: int | None
    eval_duration: int | None
    thinking_length: int | None
    thinking_sha256: str | None


@dataclass(frozen=True)
class OllamaProviderResult:
    content: str
    metadata: OllamaResponseMetadata


class OllamaProvider:

    def __init__(self, model):
        self.url = "http://localhost:11434/api/generate"
        self.model = model

    def generate(
        self,
        prompt,
        *,
        policy=None,
    ):
        """Return legacy text content for existing free-text consumers."""
        return self.generate_result(
            prompt,
            policy=policy,
        ).content

    def generate_result(
        self,
        prompt,
        *,
        policy=None,
    ) -> OllamaProviderResult:
        """Return generated content separated from available response metadata."""
        prompt = str(prompt)
        policy = policy or OllamaRequestPolicy()
        if not isinstance(policy, OllamaRequestPolicy):
            raise TypeError(
                "policy debe ser OllamaRequestPolicy."
            )

        try:
            return self._generate_result(
                prompt=prompt,
                policy=policy,
            )
        except OperationalError:
            raise
        except OllamaRequestError as error:
            raise create_operational_error(
                family="EXTERNAL_SERVICE",
                user_message="No se pudo completar la solicitud a Ollama.",
                recommended_action=(
                    "Comprueba que Ollama esté en ejecución y que el modelo "
                    "solicitado esté disponible."
                ),
                operation="Generar respuesta con Ollama",
                resource=self.url,
                diagnostic_reference="logs/prompt_debug.txt",
                technical_metadata={
                    "service": "ollama",
                    "model": str(self.model),
                    "provider_error": type(error).__name__,
                },
            ) from error

    def _generate_result(
        self,
        *,
        prompt,
        policy,
    ) -> OllamaProviderResult:
        Path("logs").mkdir(exist_ok=True)
        Path("logs/prompt_debug.txt").write_text(prompt, encoding="utf-8")

        try:
            request_kwargs = {
                "json": self._build_payload(
                    prompt=prompt,
                    policy=policy,
                ),
            }
            if policy.timeout is not None:
                request_kwargs["timeout"] = policy.timeout
            response = requests.post(
                self.url,
                **request_kwargs,
            )
            response.raise_for_status()
        except requests.Timeout as error:
            raise OllamaRequestError(
                "La comunicación con Ollama agotó su espera de red. "
                "Comprueba que el servicio y el modelo estén disponibles."
            ) from error
        except requests.RequestException as error:
            raise OllamaRequestError(
                f"No se pudo conectar con Ollama: {error}"
            ) from error

        try:
            response_data = response.json()
            result = response_data["response"]
        except (ValueError, KeyError, TypeError) as error:
            raise OllamaRequestError(
                "Ollama devolvió una respuesta HTTP sin el campo 'response'."
            ) from error

        if not isinstance(result, str):
            raise OllamaRequestError(
                "Ollama devolvió un campo 'response' no textual."
            )

        Path("logs/response_debug.txt").write_text(result, encoding="utf-8")

        return OllamaProviderResult(
            content=result,
            metadata=self._build_metadata(
                prompt=prompt,
                content=result,
                response_data=response_data,
                policy=policy,
            ),
        )

    def _build_payload(
        self,
        *,
        prompt,
        policy,
    ):
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
        }
        if policy.format is not None:
            payload["format"] = self._json_value(policy.format)
        if policy.think is not None:
            payload["think"] = policy.think
        if policy.options is not None:
            payload["options"] = self._json_value(policy.options)
        return payload

    def _build_metadata(
        self,
        *,
        prompt,
        content,
        response_data,
        policy,
    ):
        thinking = response_data.get("thinking")
        if not isinstance(thinking, str):
            thinking = None

        return OllamaResponseMetadata(
            requested_model=self.model,
            response_model=self._optional_text(
                response_data.get("model")
            ),
            created_at=self._optional_text(
                response_data.get("created_at")
            ),
            policy=policy,
            done=self._optional_bool(response_data.get("done")),
            done_reason=self._optional_text(
                response_data.get("done_reason")
            ),
            prompt_length=len(prompt),
            content_length=len(content),
            prompt_sha256=self._sha256(prompt),
            content_sha256=self._sha256(content),
            prompt_eval_count=self._optional_int(
                response_data.get("prompt_eval_count")
            ),
            eval_count=self._optional_int(response_data.get("eval_count")),
            total_duration=self._optional_int(
                response_data.get("total_duration")
            ),
            load_duration=self._optional_int(
                response_data.get("load_duration")
            ),
            prompt_eval_duration=self._optional_int(
                response_data.get("prompt_eval_duration")
            ),
            eval_duration=self._optional_int(
                response_data.get("eval_duration")
            ),
            thinking_length=(
                len(thinking)
                if thinking is not None
                else None
            ),
            thinking_sha256=(
                self._sha256(thinking)
                if thinking is not None
                else None
            ),
        )

    @staticmethod
    def _optional_text(value):
        return value if isinstance(value, str) else None

    @staticmethod
    def _optional_bool(value):
        return value if isinstance(value, bool) else None

    @staticmethod
    def _optional_int(value):
        return value if isinstance(value, int) and not isinstance(value, bool) else None

    @staticmethod
    def _sha256(value):
        return sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def _json_value(value):
        if isinstance(value, Mapping):
            return {
                key: OllamaProvider._json_value(item)
                for key, item in value.items()
            }
        if isinstance(value, (tuple, list)):
            return [
                OllamaProvider._json_value(item)
                for item in value
            ]
        return value
