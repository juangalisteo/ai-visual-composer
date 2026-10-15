"""Lazy technical provider for the isolated Piper backend capability."""

from collections.abc import Callable
from pathlib import Path

from app.modules.audio.piper_backend import PiperBackend
from app.modules.audio.tts_backend_registry import TtsBackend
from app.modules.audio.tts_contracts import (
    TtsBackendDiagnostic,
    TtsBackendError,
    TtsBackendErrorKind,
)


PiperBackendFactory = Callable[[Path], TtsBackend]


class PiperBackendProvider:
    """Construct ``PiperBackend`` lazily from an explicitly supplied project root.

    It deliberately knows no voice documents or individual Piper resources.
    Resource resolution and ONNX loading remain inside ``PiperBackend`` when a
    request is synthesized.
    """

    backend_key = PiperBackend.backend_key

    def __init__(
        self,
        project_root: Path | str,
        *,
        backend_factory: PiperBackendFactory = PiperBackend,
    ):
        self._project_root = _project_root(project_root)
        if not callable(backend_factory):
            raise TypeError("backend_factory must be callable.")
        self._backend_factory = backend_factory

    @property
    def project_root(self) -> Path:
        """Return the explicit technical root without accessing Piper resources."""
        return self._project_root

    def create(self) -> TtsBackend:
        """Construct a fresh capability without loading a voice model."""
        try:
            backend = self._backend_factory(self._project_root)
        except TtsBackendError:
            raise
        except Exception as error:
            raise _provider_error(
                "No se pudo construir la capacidad técnica de Piper."
            ) from error

        if not isinstance(backend, TtsBackend):
            raise _provider_error(
                "La factoría de Piper no devolvió una capacidad TTS válida."
            )
        if backend.backend_key != self.backend_key:
            raise _provider_error(
                "La factoría de Piper devolvió una capacidad con identidad distinta."
            )
        return backend


def _project_root(value: Path | str) -> Path:
    if not isinstance(value, (Path, str)):
        raise TypeError("project_root must be a path.")
    if isinstance(value, str) and not value.strip():
        raise ValueError("project_root must not be empty.")
    return Path(value).resolve(strict=False)


def _provider_error(detail: str) -> TtsBackendError:
    return TtsBackendError(
        TtsBackendDiagnostic(
            kind=TtsBackendErrorKind.RESOURCE_UNAVAILABLE,
            detail=detail,
        )
    )
