import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.modules.audio.audio_mixer import AudioMixer
from app.modules.audio.tts_backend_registry import TtsBackendRegistry
from app.modules.audio.tts_contracts import (
    TtsBackendDiagnostic,
    TtsBackendError,
    TtsBackendErrorKind,
)
from app.modules.audio.voice_builder import VoiceBuilder
from app.modules.audio.voice_configuration import load_tts_voice_configuration
from app.modules.subtitles.io.subtitle_builder import SubtitleBuilder
from app.shared.media_probe import MediaProbe
from app.shared.operational_error import OperationalError


class MediaOperationalErrorsTest(unittest.TestCase):

    def test_ffprobe_failure_keeps_resource_and_process_cause(self):
        with tempfile.TemporaryDirectory() as directory:
            media_path = Path(directory) / "input.mp4"
            media_path.write_bytes(b"media")
            failure = subprocess.CalledProcessError(
                9, ["ffprobe", str(media_path)], stderr="bad media"
            )
            with patch("app.shared.media_probe.subprocess.run", side_effect=failure), self.assertRaises(OperationalError) as caught:
                MediaProbe.inspect(media_path)

        self.assertEqual("FFMPEG", caught.exception.context.family)
        self.assertEqual(str(media_path), caught.exception.context.resource)
        self.assertEqual(9, caught.exception.context.technical_metadata["returncode"])
        self.assertIs(caught.exception.__cause__, failure)

    def test_whisper_failure_is_contextualized_without_changing_command(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audio_path = root / "input.mp3"
            audio_path.write_bytes(b"audio")
            failure = subprocess.CalledProcessError(3, ["python", "-m", "whisper"])
            with patch("app.modules.subtitles.io.subtitle_builder.subprocess.run", side_effect=failure), self.assertRaises(OperationalError) as caught:
                SubtitleBuilder().build(audio_path=audio_path, output_path=root / "captions.srt")

        self.assertEqual("SUBTITLES", caught.exception.context.family)
        self.assertEqual(str(audio_path), caught.exception.context.resource)
        self.assertEqual("transcription", caught.exception.context.technical_metadata["phase"])
        self.assertIs(caught.exception.__cause__, failure)

    def test_tts_backend_failure_keeps_voice_and_output_context(self):
        class ConfigurationManager:
            def get_tts_voice_configuration(self):
                return load_tts_voice_configuration(
                    {
                        "kind": "tts_voice",
                        "voice_id": "test_voice",
                        "display_name": "Test voice",
                        "backend_key": "fixture_backend",
                        "backend_voice_id": "fixture-voice",
                        "language": "es-ES",
                        "prosody": {
                            "speaking_rate": 1.0,
                            "volume_gain_db": 0.0,
                        },
                        "backend_options": {},
                    }
                )

        class FailingBackend:
            backend_key = "fixture_backend"

            def __init__(self, error):
                self.error = error

            def synthesize(self, request):
                raise self.error

        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / "voice.mp3"
            failure = RuntimeError("backend unavailable")
            backend_error = TtsBackendError(
                TtsBackendDiagnostic(
                    kind=TtsBackendErrorKind.SYNTHESIS,
                    detail="TTS backend failed.",
                )
            )
            backend_error.__cause__ = failure
            builder = VoiceBuilder(
                config_manager=ConfigurationManager(),
                backend_registry=TtsBackendRegistry((FailingBackend(backend_error),)),
                workspace_parent=Path(directory) / "workspaces",
            )
            with self.assertRaises(OperationalError) as caught:
                builder.build("texto", output_path=output_path)

        self.assertEqual("AUDIO", caught.exception.context.family)
        self.assertEqual("test_voice", caught.exception.context.technical_metadata["voice_id"])
        self.assertEqual(
            "fixture_backend",
            caught.exception.context.technical_metadata["backend_key"],
        )
        self.assertEqual(str(output_path), caught.exception.context.resource)
        self.assertIs(caught.exception.__cause__, backend_error)
        self.assertIs(backend_error.__cause__, failure)

    def test_audio_mixer_failure_keeps_mix_context(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            voice_path = root / "voice.mp3"
            music_path = root / "music.mp3"
            voice_path.write_bytes(b"voice")
            music_path.write_bytes(b"music")
            failure = RuntimeError("ffmpeg failed")
            with patch.object(AudioMixer, "_run_command", side_effect=failure), patch(
                "app.modules.audio.audio_mixer.MediaProbe.get_duration", return_value=2.0
            ), self.assertRaises(OperationalError) as caught:
                AudioMixer().build(
                    voice_path=voice_path,
                    music_path=music_path,
                    output_path=root / "mixed.mp3",
                )

        self.assertEqual("AUDIO", caught.exception.context.family)
        self.assertEqual("audio_mix", caught.exception.context.technical_metadata["phase"])
        self.assertIs(caught.exception.__cause__, failure)


if __name__ == "__main__":
    unittest.main()
