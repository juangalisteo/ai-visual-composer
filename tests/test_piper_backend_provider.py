"""Focused isolation tests for the lazy Piper backend provider."""

from dataclasses import dataclass
from pathlib import Path

import pytest

from app.modules.audio.piper_backend import PiperBackend
from app.modules.audio.piper_backend_provider import PiperBackendProvider
from app.modules.audio.tts_backend_registry import (
    TtsBackend,
    TtsBackendProvider,
    UnknownTtsBackendError,
)
from app.modules.audio.tts_backend_runtime import (
    DEFAULT_TTS_PROJECT_ROOT,
    build_default_tts_backend_registry,
)
from app.modules.audio.tts_contracts import TtsBackendError


@dataclass
class _BackendDouble:
    backend_key: str = "piper_onnx"

    def synthesize(self, request):
        raise AssertionError("Provider tests must not synthesize audio.")


class _RecordingFactory:
    def __init__(self, *, backend=None, error=None):
        self.backend = backend or _BackendDouble()
        self.error = error
        self.calls = []

    def __call__(self, project_root):
        self.calls.append(project_root)
        if self.error is not None:
            raise self.error
        return self.backend


def test_provider_has_only_the_exact_technical_piper_identity(tmp_path):
    provider = PiperBackendProvider(tmp_path)

    assert provider.backend_key == "piper_onnx"
    assert isinstance(provider, TtsBackendProvider)


def test_create_returns_a_fresh_piper_backend_with_explicit_project_root(tmp_path):
    provider = PiperBackendProvider(tmp_path)

    first = provider.create()
    second = provider.create()

    assert isinstance(first, PiperBackend)
    assert isinstance(second, PiperBackend)
    assert isinstance(provider, TtsBackend) is False
    assert first is not second
    assert provider.project_root == tmp_path.resolve()
    assert first._project_root == tmp_path.resolve()
    assert second._project_root == tmp_path.resolve()


def test_provider_construction_and_create_do_not_load_piper_voice_or_models(tmp_path):
    factory = _RecordingFactory()

    provider = PiperBackendProvider(tmp_path, backend_factory=factory)

    assert factory.calls == []
    backend = provider.create()

    assert backend is factory.backend
    assert factory.calls == [tmp_path.resolve()]


def test_provider_neither_reads_visible_configuration_nor_synthesizes(tmp_path):
    factory = _RecordingFactory()
    provider = PiperBackendProvider(tmp_path, backend_factory=factory)

    provider.create()

    assert factory.calls == [tmp_path.resolve()]


def test_provider_propagates_factory_cause_without_fallback(tmp_path):
    factory = _RecordingFactory(error=RuntimeError("construction failure"))
    provider = PiperBackendProvider(tmp_path, backend_factory=factory)

    with pytest.raises(TtsBackendError) as error:
        provider.create()

    assert error.value.diagnostic.kind.value == "resource_unavailable"
    assert isinstance(error.value.__cause__, RuntimeError)
    assert factory.calls == [tmp_path.resolve()]


@pytest.mark.parametrize(
    "backend",
    [object(), _BackendDouble(backend_key="different_backend")],
)
def test_provider_rejects_invalid_or_mismatched_factory_result(tmp_path, backend):
    provider = PiperBackendProvider(
        tmp_path,
        backend_factory=_RecordingFactory(backend=backend),
    )

    with pytest.raises(TtsBackendError) as error:
        provider.create()

    assert error.value.diagnostic.kind.value == "resource_unavailable"


def test_provider_requires_an_explicit_valid_project_root():
    with pytest.raises(TypeError):
        PiperBackendProvider(object())
    with pytest.raises(ValueError):
        PiperBackendProvider("   ")


def test_default_product_registry_registers_the_piper_chatterbox_and_kokoro_capabilities():
    registry = build_default_tts_backend_registry()

    assert registry.backend_keys == ("piper_onnx", "chatterbox_multilingual", "kokoro")
    with pytest.raises(UnknownTtsBackendError):
        registry.resolve("kokoro_onnx")


def test_product_registry_resolves_piper_lazily_with_the_injected_project_root(tmp_path):
    registry = build_default_tts_backend_registry(project_root=tmp_path)

    backend = registry.resolve("piper_onnx")

    assert isinstance(backend, PiperBackend)
    assert backend._project_root == tmp_path.resolve()


def test_product_registry_keeps_unknown_backend_errors_without_fallback():
    registry = build_default_tts_backend_registry()

    with pytest.raises(UnknownTtsBackendError):
        registry.resolve("unknown_backend")


def test_runtime_project_root_is_derived_from_the_composition_module_not_cwd():
    expected = Path(__file__).resolve().parents[1]

    assert DEFAULT_TTS_PROJECT_ROOT == expected


def test_provider_module_has_no_voice_or_component_dependencies():
    import app.modules.audio.piper_backend_provider as provider_module

    source = Path(provider_module.__file__).read_text(encoding="utf-8")
    forbidden = (
        "Miro",
        "Davefx",
        "Carlfm",
        "display_name",
        "MC_VOICE_CONFIG",
        "VoiceBuilder",
        "ProjectManager",
        "start.py",
        "PiperVoice",
    )

    assert all(token not in source for token in forbidden)
