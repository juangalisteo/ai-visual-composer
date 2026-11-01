from dataclasses import FrozenInstanceError, fields, is_dataclass
import inspect
import math
from pathlib import Path
import unittest

from app.modules.audio.tts_contracts import (
    ResolvedTtsVoice,
    TtsArtifactOwnership,
    TtsAudioArtifact,
    TtsBackendDiagnostic,
    TtsBackendError,
    TtsBackendErrorKind,
    TtsPause,
    TtsProsody,
    TtsSynthesisRequest,
    TtsSynthesisResult,
    TtsSynthesisWorkspace,
    TtsWordTiming,
)


def _voice(**overrides):
    values = {
        "voice_id": "fixture_voice",
        "backend_key": "fixture_backend",
        "backend_voice_id": "fixture_backend_voice",
        "language": "es-ES",
        "prosody": TtsProsody(speaking_rate=0.95, volume_gain_db=1.5),
        "backend_options": {
            "quality": "standard",
            "nested": {"threshold": 0.5},
        },
    }
    values.update(overrides)
    return ResolvedTtsVoice(**values)


def _workspace(**overrides):
    values = {
        "workspace_id": "request-001",
        "path": Path("tmp/tts/request-001"),
    }
    values.update(overrides)
    return TtsSynthesisWorkspace(**values)


def _audio(**overrides):
    values = {
        "path": Path("tmp/tts/request-001/audio.mp3"),
        "container": "mp3",
        "codec": "mp3",
        "sample_rate_hz": 24000,
        "channels": 1,
    }
    values.update(overrides)
    return TtsAudioArtifact(**values)


class TtsContractsTest(unittest.TestCase):

    def test_valid_contracts_are_pure_immutable_data(self):
        voice = _voice()
        workspace = _workspace()
        request = TtsSynthesisRequest(
            text="Texto de prueba.",
            voice=voice,
            workspace=workspace,
        )
        result = TtsSynthesisResult(
            staged_audio=_audio(),
            word_timings=(
                TtsWordTiming("Texto", 0.0, 0.4),
                TtsWordTiming("prueba", 0.4, 0.8),
            ),
            diagnostic=TtsBackendDiagnostic(
                kind=TtsBackendErrorKind.SYNTHESIS,
                detail="diagnostic detail",
            ),
        )

        for contract in (
            voice,
            workspace,
            request,
            result,
            result.staged_audio,
            result.word_timings[0],
            result.diagnostic,
        ):
            self.assertTrue(is_dataclass(contract))
            self.assertTrue(contract.__dataclass_params__.frozen)
            with self.assertRaises(FrozenInstanceError):
                setattr(contract, "immutable_probe", "value")

        self.assertEqual("Texto de prueba.", request.text)
        self.assertEqual(Path("tmp/tts/request-001"), workspace.path)
        self.assertEqual(
            TtsArtifactOwnership.VOICE_BUILDER_STAGING,
            result.staged_audio.ownership,
        )
        self.assertEqual(0.8, result.word_timings[-1].end_seconds)
        with self.assertRaises(TypeError):
            voice.backend_options["quality"] = "other"
        with self.assertRaises(TypeError):
            voice.backend_options["nested"]["threshold"] = 1.0

    def test_request_and_workspace_validate_structural_inputs(self):
        with self.assertRaisesRegex(ValueError, "text"):
            TtsSynthesisRequest("  ", _voice(), _workspace())
        with self.assertRaisesRegex(TypeError, "voice"):
            TtsSynthesisRequest("text", object(), _workspace())
        with self.assertRaisesRegex(TypeError, "workspace"):
            TtsSynthesisRequest("text", _voice(), object())
        with self.assertRaisesRegex(TypeError, "require_word_timings"):
            TtsSynthesisRequest("text", _voice(), _workspace(), "yes")
        with self.assertRaisesRegex(ValueError, "workspace_id"):
            _workspace(workspace_id=" ")
        with self.assertRaisesRegex(ValueError, "current directory"):
            _workspace(path=Path("."))
        with self.assertRaisesRegex(ValueError, "VoiceBuilder-owned"):
            _workspace(ownership=TtsArtifactOwnership.CALLER_OWNED)

    def test_voice_configuration_preserves_technical_identity_without_labels(self):
        voice = _voice()

        self.assertEqual("fixture_voice", voice.voice_id)
        self.assertEqual("fixture_backend", voice.backend_key)
        self.assertEqual("fixture_backend_voice", voice.backend_voice_id)
        self.assertEqual("es-ES", voice.language)
        self.assertNotIn("display_name", {field.name for field in fields(voice)})
        with self.assertRaisesRegex(ValueError, "backend_key"):
            _voice(backend_key=" ")
        with self.assertRaisesRegex(TypeError, "backend_options"):
            _voice(backend_options=("not", "a mapping"))

    def test_backend_voice_id_is_optional_but_preserves_structural_validation(self):
        voice = _voice(backend_voice_id=None)

        self.assertIsNone(voice.backend_voice_id)
        with self.assertRaisesRegex(ValueError, "backend_voice_id"):
            _voice(backend_voice_id=" ")
        with self.assertRaisesRegex(TypeError, "backend_voice_id"):
            _voice(backend_voice_id=42)

    def test_prosody_and_audio_validate_neutral_structural_values(self):
        self.assertEqual(0.95, _voice().prosody.speaking_rate)
        with self.assertRaisesRegex(ValueError, "speaking_rate"):
            TtsProsody(speaking_rate=0.0)
        with self.assertRaisesRegex(ValueError, "volume_gain_db"):
            TtsProsody(volume_gain_db=math.inf)
        with self.assertRaisesRegex(ValueError, "sample_rate_hz"):
            _audio(sample_rate_hz=0)
        with self.assertRaisesRegex(TypeError, "channels"):
            _audio(channels=True)
        with self.assertRaisesRegex(ValueError, "VoiceBuilder staging"):
            _audio(ownership=TtsArtifactOwnership.CALLER_OWNED)

    def test_word_timings_use_finite_non_negative_seconds(self):
        for start, end in (
            (-0.1, 0.0),
            (0.0, -0.1),
            (math.nan, 0.0),
            (0.0, math.inf),
        ):
            with self.assertRaises(ValueError):
                TtsWordTiming("word", start, end)
        with self.assertRaisesRegex(ValueError, "precede"):
            TtsWordTiming("word", 1.0, 0.9)
        self.assertEqual(
            TtsWordTiming("word", 1.0, 1.0),
            TtsWordTiming("word", 1.0, 1.0),
        )

    def test_result_requires_ordered_non_overlapping_word_timings(self):
        audio = _audio()
        valid = TtsSynthesisResult(
            staged_audio=audio,
            word_timings=(
                TtsWordTiming("one", 0.0, 0.5),
                TtsWordTiming("two", 0.5, 0.9),
            ),
        )
        self.assertEqual(2, len(valid.word_timings))
        self.assertIsNone(TtsSynthesisResult(audio, None).word_timings)
        with self.assertRaisesRegex(ValueError, "None or contain"):
            TtsSynthesisResult(audio, ())
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            TtsSynthesisResult(
                audio,
                (
                    TtsWordTiming("one", 0.0, 0.7),
                    TtsWordTiming("two", 0.6, 1.0),
                ),
            )

    def test_result_pauses_default_to_empty_and_must_be_ordered(self):
        audio = _audio()
        self.assertEqual((), TtsSynthesisResult(audio, None).pauses)
        result = TtsSynthesisResult(
            audio,
            None,
            pauses=[TtsPause(0.5, 1.0), TtsPause(1.0, 2.5)],
        )
        self.assertEqual((TtsPause(0.5, 1.0), TtsPause(1.0, 2.5)), result.pauses)
        with self.assertRaisesRegex(ValueError, "non-overlapping"):
            TtsSynthesisResult(audio, None, pauses=(TtsPause(0.5, 1.5), TtsPause(1.0, 2.0)))
        with self.assertRaisesRegex(TypeError, "TtsPause"):
            TtsSynthesisResult(audio, None, pauses=((0.5, 1.0),))

    def test_pause_requires_a_positive_finite_interval(self):
        self.assertEqual(1.5, TtsPause(0.0, 1.5).end_seconds)
        for start, end in ((-0.1, 1.0), (1.0, 1.0), (2.0, 1.0)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    TtsPause(start, end)
        for start, end in ((math.nan, 1.0), (0.0, math.inf)):
            with self.subTest(start=start, end=end):
                with self.assertRaises(ValueError):
                    TtsPause(start, end)
        with self.assertRaises(TypeError):
            TtsPause(True, 1.0)

    def test_neutral_diagnostic_and_error_preserve_typed_context(self):
        diagnostic = TtsBackendDiagnostic(
            kind="resource_unavailable",
            detail="technical resource unavailable",
            retryable=True,
        )
        error = TtsBackendError(diagnostic)

        self.assertEqual(TtsBackendErrorKind.RESOURCE_UNAVAILABLE, diagnostic.kind)
        self.assertTrue(diagnostic.retryable)
        self.assertEqual(diagnostic, error.diagnostic)
        self.assertEqual("technical resource unavailable", str(error))
        with self.assertRaisesRegex(TypeError, "retryable"):
            TtsBackendDiagnostic(TtsBackendErrorKind.SYNTHESIS, "detail", 1)

    def test_contract_module_has_no_nominal_backend_or_runtime_dependencies(self):
        from app.modules.audio import tts_contracts

        source = inspect.getsource(tts_contracts).lower()
        for forbidden in (
            "kokoro",
            "piper",
            "projectmanager",
            "display_name",
        ):
            self.assertNotIn(forbidden, source)


if __name__ == "__main__":
    unittest.main()
