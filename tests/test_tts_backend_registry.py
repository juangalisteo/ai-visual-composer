import inspect
import unittest
from dataclasses import dataclass

from app.modules.audio.tts_backend_registry import (
    TtsBackend,
    TtsBackendDuplicateError,
    TtsBackendRegistrationError,
    TtsBackendRegistry,
    TtsBackendProvider,
    UnknownTtsBackendError,
)
from app.modules.audio.tts_contracts import (
    ResolvedTtsVoice,
    TtsSynthesisRequest,
    TtsSynthesisResult,
)


@dataclass
class _FixtureBackend:
    backend_key: str

    def synthesize(self, request: TtsSynthesisRequest) -> TtsSynthesisResult:
        raise AssertionError("Registry resolution must not synthesize audio.")


class _MissingSynthesize:
    backend_key = "missing_synthesize"


@dataclass
class _FixtureProvider:
    backend_key: str
    capability: _FixtureBackend
    calls: int = 0

    def create(self):
        self.calls += 1
        return self.capability


@dataclass
class _InvalidKeyBackend:
    backend_key: object

    def synthesize(self, request: TtsSynthesisRequest) -> TtsSynthesisResult:
        raise AssertionError("Registry resolution must not synthesize audio.")


def _voice(**overrides):
    values = {
        "voice_id": "technical_voice_fixture",
        "backend_key": "test_backend",
        "backend_voice_id": "backend_voice_fixture",
        "language": "es-ES",
    }
    values.update(overrides)
    return ResolvedTtsVoice(**values)


class TtsBackendRegistryTest(unittest.TestCase):

    def test_resolves_registered_capability_by_exact_technical_backend_key(self):
        capability = _FixtureBackend("test_backend")
        registry = TtsBackendRegistry((capability,))

        self.assertIs(capability, registry.resolve("test_backend"))
        self.assertEqual(("test_backend",), registry.backend_keys)
        self.assertIsInstance(capability, TtsBackend)

    def test_resolution_uses_only_backend_key_not_voice_presentation_or_identity(self):
        backend = _FixtureBackend("test_backend")
        registry = TtsBackendRegistry((backend,))
        original = _voice()
        renamed_or_reidentified = _voice(
            voice_id="another_opaque_voice",
            backend_voice_id="another_backend_voice",
            language="ca-ES",
        )

        self.assertIs(backend, registry.resolve(original.backend_key))
        self.assertIs(backend, registry.resolve(renamed_or_reidentified.backend_key))

    def test_unknown_backend_key_is_deterministic(self):
        registry = TtsBackendRegistry((_FixtureBackend("test_backend"),))

        with self.assertRaisesRegex(
            UnknownTtsBackendError,
            "local_backend",
        ):
            registry.resolve("local_backend")

    def test_duplicate_backend_keys_are_rejected(self):
        first = _FixtureBackend("test_backend")
        duplicate = _FixtureBackend("test_backend")

        with self.assertRaisesRegex(TtsBackendDuplicateError, "test_backend"):
            TtsBackendRegistry((first, duplicate))

    def test_invalid_backend_capabilities_and_keys_are_rejected(self):
        registry = TtsBackendRegistry()

        with self.assertRaises(TtsBackendRegistrationError):
            registry.register(_MissingSynthesize())
        with self.assertRaisesRegex(TtsBackendRegistrationError, "backend_key"):
            registry.register(_InvalidKeyBackend(" "))
        with self.assertRaisesRegex(TtsBackendRegistrationError, "backend_key"):
            registry.resolve(" ")

    def test_lazy_provider_resolves_only_from_the_registered_technical_key(self):
        capability = _FixtureBackend("local_tts")
        provider = _FixtureProvider("local_tts", capability)
        registry = TtsBackendRegistry((provider,))

        self.assertIsInstance(provider, TtsBackendProvider)
        self.assertIs(capability, registry.resolve("local_tts"))
        self.assertEqual(1, provider.calls)

    def test_registry_module_has_no_component_or_runtime_dependencies(self):
        from app.modules.audio import tts_backend_registry

        source = inspect.getsource(tts_backend_registry).lower()
        for forbidden in (
            "guion",
            "imagen",
            "video",
            "projectmanager",
            "start.py",
            "display_name",
            "filename",
            "label",
            "voice_id",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
