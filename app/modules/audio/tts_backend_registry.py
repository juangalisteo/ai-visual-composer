"""Technical registry for neutral TTS backend capabilities.

This module only registers and resolves already-instantiated backend
capabilities. It does not load models, synthesize audio, read configuration,
or select a backend from any presentation value.
"""

from collections.abc import Iterable
from typing import Protocol, runtime_checkable

from app.modules.audio.tts_contracts import (
    TtsSynthesisRequest,
    TtsSynthesisResult,
)


@runtime_checkable
class TtsBackend(Protocol):
    """One technical synthesis capability identified by ``backend_key``."""

    @property
    def backend_key(self) -> str:
        """Return the exact technical key used for registry resolution."""

    def synthesize(self, request: TtsSynthesisRequest) -> TtsSynthesisResult:
        """Synthesize one validated request into its private staging result."""


@runtime_checkable
class TtsBackendProvider(Protocol):
    """Lazily construct one technical TTS capability after provisioning."""

    @property
    def backend_key(self) -> str:
        """Return the exact key owned by the provider."""

    def create(self) -> TtsBackend:
        """Validate/provision and return the capability for that key."""


class TtsBackendRegistrationError(ValueError):
    """Raised when a backend capability cannot be registered safely."""


class TtsBackendDuplicateError(TtsBackendRegistrationError):
    """Raised when two capabilities declare the same technical key."""


class UnknownTtsBackendError(LookupError):
    """Raised when no registered capability matches a technical key."""


class TtsBackendRegistry:
    """Resolve registered capabilities or lazy providers by exact technical key."""

    def __init__(self, backends: Iterable[TtsBackend | TtsBackendProvider] = ()):
        self._backends: dict[str, TtsBackend | TtsBackendProvider] = {}
        for backend in backends:
            self.register(backend)

    @property
    def backend_keys(self) -> tuple[str, ...]:
        """Return registered technical keys in registration order."""
        return tuple(self._backends)

    def register(self, backend: TtsBackend | TtsBackendProvider) -> None:
        """Register one protocol-conforming capability under its exact key."""
        self._validate_registration(backend)
        backend_key = _require_backend_key(backend.backend_key)
        if backend_key in self._backends:
            raise TtsBackendDuplicateError(
                f"TTS backend key is already registered: {backend_key}"
            )
        self._backends[backend_key] = backend

    def resolve(self, backend_key: str) -> TtsBackend:
        """Return the capability registered for one exact technical key."""
        backend_key = _require_backend_key(backend_key)
        try:
            registered = self._backends[backend_key]
        except KeyError as error:
            raise UnknownTtsBackendError(
                f"No TTS backend is registered for key: {backend_key}"
            ) from error

        if isinstance(registered, TtsBackend):
            return registered

        backend = registered.create()
        self._validate_backend(backend)
        if _require_backend_key(backend.backend_key) != backend_key:
            raise TtsBackendRegistrationError(
                "TTS backend provider returned a capability for a different key."
            )
        return backend

    @staticmethod
    def _validate_backend(backend: object) -> None:
        if not isinstance(backend, TtsBackend):
            raise TtsBackendRegistrationError(
                "TTS backend must implement backend_key and synthesize()."
            )
        if not callable(backend.synthesize):
            raise TtsBackendRegistrationError(
                "TTS backend synthesize attribute must be callable."
            )
        _require_backend_key(backend.backend_key)

    @classmethod
    def _validate_registration(cls, backend: object) -> None:
        if isinstance(backend, TtsBackend):
            cls._validate_backend(backend)
            return
        if isinstance(backend, TtsBackendProvider):
            _require_backend_key(backend.backend_key)
            if not callable(backend.create):
                raise TtsBackendRegistrationError(
                    "TTS backend provider create attribute must be callable."
                )
            return
        raise TtsBackendRegistrationError(
            "TTS registration must be a backend or backend provider."
        )


def _require_backend_key(value: object) -> str:
    if not isinstance(value, str):
        raise TtsBackendRegistrationError("backend_key must be text.")
    backend_key = value.strip()
    if not backend_key:
        raise TtsBackendRegistrationError("backend_key must not be empty.")
    return backend_key
