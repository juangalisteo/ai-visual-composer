from dataclasses import FrozenInstanceError, fields
import json
from pathlib import Path
import tempfile

import pytest

from app.modules.subtitles.io.external_media_subtitles import (
    ExternalMediaSubtitlePreparationService,
)
from app.modules.subtitles.io.whisper_diagnostics import (
    WhisperDiagnosticsParser,
    WhisperSegmentDiagnostics,
)
from app.modules.subtitles.io.whisper_transcription_config import (
    WhisperTranscriptionConfig,
)
from app.modules.subtitles.io.whisper_diagnostics_writer import (
    WhisperDiagnosticsWriter,
)
from app.modules.subtitles.policies.timing import (
    SpeechSegment,
    SubtitleTiming,
    WhisperTimingParser,
    WordTiming,
    whisper_timing_path,
)
from app.shared.operational_error import OperationalError


# Model, device and language have no value in the code (config/whisper.json).
TEST_TRANSCRIPTION = {
    "model": "test_model",
    "device": "test_device",
    "language": "test_language",
}

W01_SEGMENTS = [
    {
        "id": 7,
        "seek": 3000,
        "start": 30.44,
        "end": 31.9,
        "text": " La Tierra",
        "tokens": [50364, 1234],
        "temperature": 0.0,
        "avg_logprob": -0.986691,
        "compression_ratio": 0.95,
        "no_speech_prob": 0.967121,
        "words": [
            {
                "word": " La",
                "start": 30.44,
                "end": 30.9,
                "probability": 0.91,
            },
            {
                "word": " Tierra",
                "start": 30.91,
                "end": 31.9,
                "probability": 0.89,
            },
        ],
    },
    {
        "id": 8,
        "seek": 3000,
        "start": 31.9,
        "end": 33.68,
        "text": " La Tierra",
        "tokens": [50364, 1234],
        "temperature": 0.0,
        "avg_logprob": -0.986691,
        "compression_ratio": 0.95,
        "no_speech_prob": 0.967121,
        "words": [
            {
                "word": " La",
                "start": 31.9,
                "end": 32.4,
                "probability": 0.88,
            },
            {
                "word": " Tierra",
                "start": 32.5,
                "end": 33.68,
                "probability": 0.87,
            },
        ],
    },
]


def _write_native_json(path, segments=W01_SEGMENTS):
    Path(path).write_text(
        json.dumps({"segments": segments}),
        encoding="utf-8",
    )


def test_w01_native_json_preserves_segment_diagnostics_without_text_or_tokens():
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "native.json"
        _write_native_json(source)
        diagnostics = WhisperDiagnosticsParser(
            backend_version_resolver=lambda: "20250625",
        ).parse(source, config)

    assert diagnostics.backend == "openai-whisper"
    assert diagnostics.backend_version == "20250625"
    assert diagnostics.transcription_config is config
    assert diagnostics.segments == (
        WhisperSegmentDiagnostics(
            segment_id=7,
            seek=3000,
            start=30.44,
            end=31.9,
            no_speech_prob=0.967121,
            avg_logprob=-0.986691,
            compression_ratio=0.95,
            temperature=0.0,
        ),
        WhisperSegmentDiagnostics(
            segment_id=8,
            seek=3000,
            start=31.9,
            end=33.68,
            no_speech_prob=0.967121,
            avg_logprob=-0.986691,
            compression_ratio=0.95,
            temperature=0.0,
        ),
    )
    assert {field.name for field in fields(WhisperSegmentDiagnostics)} == {
        "segment_id", "seek", "start", "end", "no_speech_prob",
        "avg_logprob", "compression_ratio", "temperature",
    }
    with pytest.raises(FrozenInstanceError):
        diagnostics.segments = ()


def test_missing_native_diagnostic_fields_remain_optional():
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "native.json"
        _write_native_json(
            source,
            [{"start": 1.0, "end": 2.0}],
        )
        diagnostics = WhisperDiagnosticsParser(
            backend_version_resolver=lambda: None,
        ).parse(source, config)

    assert diagnostics.segments == (
        WhisperSegmentDiagnostics(
            segment_id=None,
            seek=None,
            start=1.0,
            end=2.0,
            no_speech_prob=None,
            avg_logprob=None,
            compression_ratio=None,
            temperature=None,
        ),
    )


def _diagnostics(config=None):
    config = config or WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "native.json"
        _write_native_json(source)
        return WhisperDiagnosticsParser(
            backend_version_resolver=lambda: "20250625",
        ).parse(source, config)


def test_diagnostics_writer_writes_deterministic_versioned_json_without_text_or_tokens():
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    diagnostics = _diagnostics(config)
    with tempfile.TemporaryDirectory() as directory:
        output_path = Path(directory) / "nested" / "diagnostics.json"
        writer = WhisperDiagnosticsWriter()
        result = writer.write(diagnostics, output_path)
        first = output_path.read_bytes()
        writer.write(diagnostics, output_path)
        second = output_path.read_bytes()

    payload = json.loads(first)
    assert result == output_path
    assert first == second
    assert payload == {
        "schema_version": 2,
        "backend": "openai-whisper",
        "backend_version": "20250625",
        "transcription_config": {
            "model": "test_model",
            "device": "test_device",
            "language": "test_language",
            "task": "transcribe",
            "word_timestamps": True,
            "condition_on_previous_text": True,
            "no_speech_threshold": 0.6,
            "logprob_threshold": -1.0,
            "compression_ratio_threshold": 2.4,
            "hallucination_silence_threshold": None,
            "temperature": 0.0,
            "temperature_increment_on_fallback": 0.2,
            "fp16": True,
            "output_format": "all",
        },
        "segments": [
            {
                "segment_id": 7,
                "seek": 3000,
                "start": 30.44,
                "end": 31.9,
                "no_speech_prob": 0.967121,
                "avg_logprob": -0.986691,
                "compression_ratio": 0.95,
                "temperature": 0.0,
            },
            {
                "segment_id": 8,
                "seek": 3000,
                "start": 31.9,
                "end": 33.68,
                "no_speech_prob": 0.967121,
                "avg_logprob": -0.986691,
                "compression_ratio": 0.95,
                "temperature": 0.0,
            },
        ],
        "discarded_segments": [],
    }
    assert b"La Tierra" not in first
    assert b"tokens" not in first


def test_diagnostics_remain_separate_from_generic_timing_and_word_confidence():
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    with tempfile.TemporaryDirectory() as directory:
        source = Path(directory) / "native.json"
        _write_native_json(source)
        timing = WhisperTimingParser().parse(source)
        diagnostics = WhisperDiagnosticsParser().parse(source, config)

    assert timing.words[0].confidence == 0.91
    assert "no_speech_prob" not in {field.name for field in fields(SubtitleTiming)}
    assert "seek" not in {field.name for field in fields(SpeechSegment)}
    assert "segment_id" not in {field.name for field in fields(WordTiming)}
    assert diagnostics.segments[0].no_speech_prob == 0.967121


class _WhisperBuilder:
    def __init__(self, config, *, valid_diagnostics=True):
        self.transcription_config = config
        self.valid_diagnostics = valid_diagnostics
        self.calls = []

    def build(self, audio_path, output_path):
        output_path = Path(output_path)
        self.calls.append((Path(audio_path), output_path))
        output_path.write_text(
            "1\n00:00:30,440 --> 00:00:31,900\nLa Tierra\n",
            encoding="utf-8",
        )
        sidecar = whisper_timing_path(output_path)
        if self.valid_diagnostics:
            _write_native_json(sidecar)
        else:
            sidecar.write_text("{invalid", encoding="utf-8")
        return output_path


class _TimingResolver:
    def resolve(self, subtitle_path, audio_path=None):
        return SubtitleTiming(
            source="whisper",
            segments=(
                SpeechSegment(
                    start=30.44,
                    end=31.9,
                    words=(
                        WordTiming(
                            text="La",
                            start=30.44,
                            end=30.9,
                            confidence=0.91,
                            source="whisper",
                        ),
                    ),
                ),
            ),
            reliability="secondary",
        )


class _Runner:
    def run(self, command):
        raise AssertionError("MP3 must not be extracted before Whisper")


@pytest.mark.parametrize("valid_diagnostics", [True, False])
def test_external_preparation_transports_optional_diagnostics_without_changing_timing(
    valid_diagnostics,
):
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    builder = _WhisperBuilder(config, valid_diagnostics=valid_diagnostics)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source.mp3"
        source.write_bytes(b"audio")
        prepared = ExternalMediaSubtitlePreparationService(
            runner=_Runner(),
            subtitle_builder=builder,
            timing_resolver=_TimingResolver(),
        ).prepare(media_path=source, working_directory=root / "work")

    assert prepared.timing.source == "whisper"
    assert prepared.timing.words[0].confidence == 0.91
    if valid_diagnostics:
        assert prepared.diagnostics is not None
        assert prepared.diagnostics.transcription_config is config
        assert prepared.diagnostics.segments[0].segment_id == 7
    else:
        assert prepared.diagnostics is None


def test_external_preparation_writes_diagnostics_only_with_explicit_opt_in():
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    builder = _WhisperBuilder(config)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source.mp3"
        source.write_bytes(b"audio")
        sidecar = root / "diagnostics" / "whisper.json"
        service = ExternalMediaSubtitlePreparationService(
            runner=_Runner(),
            subtitle_builder=builder,
            timing_resolver=_TimingResolver(),
        )

        prepared_without_opt_in = service.prepare(
            media_path=source,
            working_directory=root / "without",
        )
        assert prepared_without_opt_in.diagnostics is not None
        assert not sidecar.exists()

        prepared_with_opt_in = service.prepare(
            media_path=source,
            working_directory=root / "with",
            diagnostics_output_path=sidecar,
        )
        payload = json.loads(sidecar.read_text(encoding="utf-8"))

    assert prepared_with_opt_in.diagnostics is not None
    assert payload["transcription_config"]["model"] == "test_model"
    assert payload["segments"][0]["segment_id"] == 7


def test_external_preparation_does_not_write_when_diagnostics_are_absent():
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    builder = _WhisperBuilder(config, valid_diagnostics=False)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source.mp3"
        source.write_bytes(b"audio")
        sidecar = root / "diagnostics.json"
        prepared = ExternalMediaSubtitlePreparationService(
            runner=_Runner(),
            subtitle_builder=builder,
            timing_resolver=_TimingResolver(),
        ).prepare(
            media_path=source,
            working_directory=root / "work",
            diagnostics_output_path=sidecar,
        )

    assert prepared.diagnostics is None
    assert not sidecar.exists()


class _FailingDiagnosticsWriter:
    def write(self, diagnostics, output_path):
        raise OSError("cannot write")


def test_explicit_diagnostics_write_failure_is_an_operational_error():
    config = WhisperTranscriptionConfig(**TEST_TRANSCRIPTION)
    builder = _WhisperBuilder(config)
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source.mp3"
        output_path = root / "diagnostics.json"
        source.write_bytes(b"audio")
        with pytest.raises(OperationalError) as caught:
            ExternalMediaSubtitlePreparationService(
                runner=_Runner(),
                subtitle_builder=builder,
                timing_resolver=_TimingResolver(),
                diagnostics_writer=_FailingDiagnosticsWriter(),
            ).prepare(
                media_path=source,
                working_directory=root / "work",
                diagnostics_output_path=output_path,
            )

        subtitle_path = root / "work" / "whisper.srt"
        assert subtitle_path.exists()

    assert caught.value.context.family == "FILESYSTEM"
    assert caught.value.context.technical_metadata == {
        "phase": "whisper_diagnostics",
    }
