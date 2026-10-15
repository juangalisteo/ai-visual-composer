import inspect
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.audio.tts_backend_registry import TtsBackendRegistry
from app.modules.audio.tts_contracts import (
    TtsAudioArtifact,
    TtsBackendDiagnostic,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsSynthesisResult,
    TtsWordTiming,
)
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.shared.operational_error import OperationalError


def _voice_configuration(stem="piper_davefx"):
    document_path = Path("config/voice_configs") / f"{stem}.json"
    return load_tts_voice_configuration(
        json.loads(document_path.read_text(encoding="utf-8"))
    )


class _ConfigurationManager:
    def __init__(self, configuration):
        self.configuration = configuration
        self.calls = 0

    def get_tts_voice_configuration(self):
        self.calls += 1
        return self.configuration


class _Backend:
    backend_key = "piper_onnx"

    def __init__(self, *, timings=None, error=None):
        self.timings = timings
        self.error = error
        self.requests = []

    def synthesize(self, request):
        self.requests.append(request)
        if self.error is not None:
            raise self.error

        staged_audio = request.workspace.path / "staged.mp3"
        request.workspace.path.mkdir(parents=True, exist_ok=True)
        staged_audio.write_bytes(b"neutral staged audio")
        return TtsSynthesisResult(
            staged_audio=TtsAudioArtifact(
                path=staged_audio,
                container="mp3",
                codec="mp3",
                sample_rate_hz=24_000,
                channels=1,
            ),
            word_timings=self.timings,
        )


def _builder(
    configuration,
    backend,
    workspace_parent,
):
    return VoiceBuilder(
        config_manager=_ConfigurationManager(configuration),
        backend_registry=TtsBackendRegistry((backend,)),
        workspace_parent=workspace_parent,
    )


class VoiceBuilderTtsBoundaryTest(unittest.TestCase):

    def test_public_signature_and_returned_path_remain_stable(self):
        signature = inspect.signature(VoiceBuilder.build)
        self.assertEqual(("self", "text", "output_path"), tuple(signature.parameters))
        self.assertIsNone(signature.parameters["output_path"].default)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = _Backend()
            output_path = root / "audio" / "voz.mp3"
            result = _builder(
                _voice_configuration(),
                backend,
                root / "workspaces",
            ).build("Texto de prueba", output_path=output_path)

            self.assertEqual(output_path, result)
            self.assertEqual(b"neutral staged audio", output_path.read_bytes())
            self.assertEqual("Texto de prueba", backend.requests[0].text)

    def test_default_registry_registers_only_piper_without_synthesizing(self):
        builder = VoiceBuilder(
            config_manager=_ConfigurationManager(_voice_configuration()),
        )

        self.assertEqual(
            ("piper_onnx",),
            builder._backend_registry.backend_keys,
        )

    def test_default_output_path_remains_the_project_audio_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = _Backend()
            expected_output = root / "audio" / "voz.mp3"

            with patch(
                "app.modules.audio.voice_builder.ProjectManager"
            ) as project_manager:
                project_manager.return_value.audio_path.return_value = expected_output
                result = _builder(
                    _voice_configuration(),
                    backend,
                    root / "workspaces",
                ).build("Texto de prueba")

            self.assertEqual(expected_output, result)
            self.assertTrue(expected_output.is_file())

    def test_accepts_neutral_timing_without_public_sidecar_and_cleans_workspace(self):
        timings = (
            TtsWordTiming("Hola", 0.0, 0.4),
            TtsWordTiming("mundo", 0.5, 0.9),
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workspace_parent = root / "workspaces"
            backend = _Backend(timings=timings)
            output_path = root / "audio" / "voz.mp3"
            builder = _builder(
                _voice_configuration(),
                backend,
                workspace_parent,
            )

            builder.build("Hola mundo", output_path=output_path)

            self.assertTrue(output_path.is_file())
            self.assertEqual((output_path,), tuple(output_path.parent.iterdir()))
            self.assertFalse(backend.requests[0].workspace.path.exists())
            self.assertEqual((), tuple(workspace_parent.iterdir()))

    def test_backend_error_is_neutral_operational_error_with_full_cause_chain(self):
        original_cause = RuntimeError("transport unavailable")
        backend_error = TtsBackendError(
            TtsBackendDiagnostic(
                kind=TtsBackendErrorKind.SYNTHESIS,
                detail="Backend synthesis failed.",
                retryable=True,
            )
        )
        backend_error.__cause__ = original_cause

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output_path = root / "voice.mp3"
            with self.assertRaises(OperationalError) as caught:
                _builder(
                    _voice_configuration(),
                    _Backend(error=backend_error),
                    root / "workspaces",
                ).build("texto", output_path=output_path)

        self.assertEqual("AUDIO", caught.exception.context.family)
        self.assertEqual("voice_generation", caught.exception.context.technical_metadata["phase"])
        self.assertEqual("piper_voice_davefx", caught.exception.context.technical_metadata["voice_id"])
        self.assertEqual("piper_onnx", caught.exception.context.technical_metadata["backend_key"])
        self.assertEqual("synthesis", caught.exception.context.technical_metadata["backend_error_kind"])
        self.assertEqual(str(output_path), caught.exception.context.resource)
        self.assertIs(caught.exception.__cause__, backend_error)
        self.assertIs(backend_error.__cause__, original_cause)

    def test_current_voice_documents_resolve_their_declared_piper_capability(self):
        expected = {
            "piper_carlfm": "piper_voice_carlfm",
            "piper_davefx": "piper_voice_davefx",
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for stem, voice_id in expected.items():
                backend = _Backend()
                _builder(
                    _voice_configuration(stem),
                    backend,
                    root / "workspaces" / stem,
                ).build("texto", output_path=root / f"{stem}.mp3")

                request = backend.requests[0]
                self.assertEqual("piper_onnx", request.voice.backend_key)
                self.assertEqual(voice_id, request.voice.voice_id)
                self.assertIsNone(request.voice.backend_voice_id)
                self.assertEqual(1.0, request.voice.prosody.speaking_rate)

    def test_facade_has_no_direct_client_or_component_backend_knowledge(self):
        from app.modules.audio import voice_builder

        source = inspect.getsource(voice_builder)
        self.assertNotIn("get_voice_config()", source)
        self.assertIn("get_tts_voice_configuration()", source)

        for component_path in (
            Path("app/core/start.py"),
            Path("app/modules/images/image_builder.py"),
            Path("app/modules/video/video_builder.py"),
        ):
            source = component_path.read_text(encoding="utf-8")
            self.assertNotIn("TtsBackendRegistry", source)


if __name__ == "__main__":
    unittest.main()
