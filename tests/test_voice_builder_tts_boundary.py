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
    TtsPause,
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

    def __init__(
        self,
        *,
        timings=None,
        error=None,
        pauses=(),
        container="mp3",
        codec="mp3",
        sample_rate_hz=44_100,
    ):
        self.timings = timings
        self.error = error
        self.pauses = pauses
        self.container = container
        self.codec = codec
        self.sample_rate_hz = sample_rate_hz
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
                container=self.container,
                codec=self.codec,
                sample_rate_hz=self.sample_rate_hz,
                channels=1,
            ),
            word_timings=self.timings,
            pauses=self.pauses,
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

    def test_staged_audio_not_at_44100_hz_is_published_as_44100_hz_mp3(self):
        cases = {
            "wav": _Backend(container="wav", codec="pcm_s16le", sample_rate_hz=22_050),
            "mpeg2_mp3": _Backend(sample_rate_hz=24_000),
        }
        for label, backend in cases.items():
            with self.subTest(label), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                output_path = root / "audio" / "voz.mp3"
                commands = []

                def encode(command, **kwargs):
                    commands.append(command)
                    Path(command[-1]).write_bytes(b"encoded audio")

                with patch(
                    "app.modules.audio.voice_builder.subprocess.run",
                    side_effect=encode,
                ):
                    _builder(
                        _voice_configuration(),
                        backend,
                        root / "workspaces",
                    ).build("Texto de prueba", output_path=output_path)

                self.assertEqual(1, len(commands))
                command = commands[0]
                self.assertEqual("44100", command[command.index("-ar") + 1])
                self.assertEqual("libmp3lame", command[command.index("-c:a") + 1])
                self.assertEqual(b"encoded audio", output_path.read_bytes())

    def test_default_registry_registers_piper_and_chatterbox_without_synthesizing(self):
        builder = VoiceBuilder(
            config_manager=_ConfigurationManager(_voice_configuration()),
        )

        self.assertEqual(
            ("piper_onnx", "chatterbox_multilingual"),
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

    def test_exposes_the_backend_pauses_of_the_last_published_voice(self):
        pauses = (TtsPause(0.4, 0.9), TtsPause(1.6, 3.1))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            builder = _builder(
                _voice_configuration(),
                _Backend(pauses=pauses),
                root / "workspaces",
            )
            self.assertEqual((), builder.last_pauses)

            builder.build("Uno. Dos.", output_path=root / "audio" / "voz.mp3")
            self.assertEqual(pauses, builder.last_pauses)

            builder._backend_registry = TtsBackendRegistry(
                (_Backend(error=RuntimeError("fallo")),)
            )
            with self.assertRaises(OperationalError):
                builder.build("Uno. Dos.", output_path=root / "audio" / "voz.mp3")
            self.assertEqual((), builder.last_pauses)

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

    def test_invalid_pause_reaches_the_user_as_spanish_configuration_error(self):
        document = json.loads(
            Path("config/voice_configs/piper_davefx.json").read_text(encoding="utf-8")
        )
        document["prosody"]["paragraph_pause_seconds"] = -1

        class _InvalidConfigurationManager:
            def get_tts_voice_configuration(self):
                return load_tts_voice_configuration(document)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            backend = _Backend()
            builder = VoiceBuilder(
                config_manager=_InvalidConfigurationManager(),
                backend_registry=TtsBackendRegistry((backend,)),
                workspace_parent=root / "workspaces",
            )
            with self.assertRaises(OperationalError) as caught:
                builder.build("texto", output_path=root / "voz.mp3")

        context = caught.exception.context
        self.assertEqual("CONFIG", context.family)
        self.assertEqual(
            "La configuración de la voz no es válida: "
            "prosody.paragraph_pause_seconds debe ser un número de segundos "
            "mayor o igual que 0 (0 = sin pausa extra); se recibió -1.",
            context.user_message,
        )
        self.assertIn("config/voice_configs/", context.recommended_action)
        self.assertEqual([], backend.requests)

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
                self.assertEqual(0.5, request.voice.prosody.sentence_pause_seconds)
                self.assertEqual(0.35, request.voice.prosody.paragraph_pause_seconds)

    def test_facade_has_no_direct_client_or_component_backend_knowledge(self):
        from app.modules.audio import voice_builder

        source = inspect.getsource(voice_builder)
        self.assertNotIn("get_voice_config()", source)
        self.assertIn("get_tts_voice_configuration()", source)

        for component_path in (
            Path("app/core/start.py"),
            Path("app/modules/standard/execution_coordinator.py"),
            Path("app/modules/images/image_builder.py"),
            Path("app/modules/video/video_builder.py"),
        ):
            source = component_path.read_text(encoding="utf-8")
            self.assertNotIn("TtsBackendRegistry", source)


if __name__ == "__main__":
    unittest.main()
